
from typing import NewType

html = NewType('html', str)
OK = NewType('"OK"/error', str)
file = NewType('file', bytes)
status = NewType('status: msg', str)
path = NewType('path', str)
