import os
import bz2

import lxml.etree as etree
from lxml.etree import iterparse, Element, ParseError

from typing import Any, Union, Iterable, Tuple, Optional

from tqdm import tqdm


def open_and_parse(filename: str, events: Union[str, Iterable[str]],
                   progress: Optional[tqdm],
                   schema_filename: Optional[str] = None) -> Iterable[Tuple[str, Element]]:
    if isinstance(events, str):
        events = (events,)

    assert os.path.exists(filename), 'The specified file does not exist.'
    if progress is not None:
        progress.unit = 'B'
        progress.unit_divisor = 1024
        progress.unit_scale = True
        progress.total = os.path.getsize(filename)

    xsd_path = schema_filename if schema_filename is not None else os.path.join('osm-extracts', 'osm.xsd')
    xsd_doc = etree.parse(xsd_path)
    schema = etree.XMLSchema(etree=xsd_doc)

    def probe_gzip() -> bool:
        try:
            with _open_file(filename, open_gzip=True) as pf:
                # An error is only thrown at the first attempt to read, so
                # we simply
                next(iterparse(pf, events=('start',), schema=schema))
                return True  # it's a gzipped file
        except OSError:
            pass

        try:
            with _open_file(filename, open_gzip=False) as pf:
                next(iterparse(pf, events=('start',)))
                return False  # it's not a gzipped file
        except ParseError:
            raise FileTypeException('The specified file does not appear to be an XML file.')

    open_gzip = probe_gzip()
    with _open_file(filename, open_gzip=open_gzip) as f:
        root = None
        for event, elem in iterparse(f, events=events):
            if progress is not None:
                current = f.tell() if not open_gzip else f._fp.tell()
                progress.update(current - progress.n)
            yield event, elem
            # To save memory, we need to clear the element.
            # See e.g.
            # - https://www.ibm.com/developerworks/xml/library/x-hiperfparse/
            # - https://stackoverflow.com/questions/7697710/python-running-out-of-memory-parsing-xml-using-celementtree-iterparse
            root = elem if root is None else root
            root.clear()


def _open_file(filename: str, open_gzip: bool) -> Any:
    assert isinstance(filename, str) and filename is not None, "The specified file name was not a valid string."
    return bz2.open(filename, mode='rb') if open_gzip else open(filename, mode='rb')


class FileTypeException(Exception):
    def __init__(self, message):
        super().__init__(message)
