import logging

from .pyflicker_logger import setup_logger
from .pyflicker_db_base import PyFlickerSupportedDBTypes

# in case user doesn't set up logging
logging.getLogger("pyflicker").addHandler(logging.NullHandler())


def _import_mysql():
    global PyFlickerDBConnectionType, PyFlickerLoadConfigMySQL, PyFlickerRunMySQL
    from .pyflicker_db_mysql import PyFlickerDBConnectionType, PyFlickerLoadConfigMySQL, PyFlickerRunMySQL


_LAZY_IMPORT = {
    "PyFlickerDBConnectionType": _import_mysql,
    "PyFlickerLoadConfigMySQL": _import_mysql,
    "PyFlickerRunMySQL": _import_mysql
}


def __getattr__(name):
    if name in _LAZY_IMPORT:
        _LAZY_IMPORT[name]()
        return globals()[name]
    raise AttributeError(f"module 'pyflicker' has no attribute {name!r}")
