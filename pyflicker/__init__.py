import logging

from .pyflicker_logger import setup_logger
from .pyflicker_db_base import PyFlickerSupportedDBTypes
from .pyflicker_format_input import escape_mysql, parse_csv_mysql
from .pyflicker_format_input import escape_postgres, parse_csv_postgres

# in case user doesn't set up logging
logging.getLogger("pyflicker").addHandler(logging.NullHandler())


def _import_mysql():
    global PyFlickerDBConnectionTypeMySQL, PyFlickerLoadConfigMySQL, PyFlickerRunMySQL
    from .pyflicker_db_mysql import PyFlickerDBConnectionTypeMySQL, PyFlickerLoadConfigMySQL, PyFlickerRunMySQL


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
