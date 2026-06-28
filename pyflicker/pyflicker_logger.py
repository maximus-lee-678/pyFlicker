import logging
from datetime import datetime
from pathlib import Path
from typing import Union

LOG_FORMAT = "[%(asctime)s] [%(filename)s/%(levelname)s]: %(message)s"

def setup_logger(log_to_folder: Union[Path, None] = None) -> logging.Logger:
    """
    Set up custom logging.

    :param log_to_folder: The folder to write logs to. Default is None.

    :return: Configured Logger instance.
    """

    logger = logging.getLogger("pyflicker")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # clear existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_to_folder:
        LOG_NAME = Path(f"""{log_to_folder}/{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log""")
        log_to_folder.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_NAME, "a", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
