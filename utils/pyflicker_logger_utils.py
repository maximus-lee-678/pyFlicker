import logging
import logging.handlers
import re
from datetime import datetime
from pathlib import Path

LOG_DIRECTORY = Path("logs")
LOG_NAME = Path(f"""{LOG_DIRECTORY}/{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log""")
LOG_FORMAT = "[%(asctime)s] [%(filename)s/%(levelname)s]: %(message)s"


def setup_logger(write_to_file=True):
    """
    Setup a simple logger.

    :param write_to_file: whether to write logs to file.

    :return: logger object.
    """

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers to avoid duplicates
    if getattr(root_logger, "_is_configured", False):
        return root_logger

    # Normal single-process logging setup (multithreading logging is thread-safe)
    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if write_to_file:
        LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_NAME, "a", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    root_logger._is_configured = True

    return root_logger
