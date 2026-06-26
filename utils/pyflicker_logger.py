import logging
from datetime import datetime
from pathlib import Path

LOG_DIRECTORY = Path("logs")
LOG_NAME = Path(f"""{LOG_DIRECTORY}/{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log""")

LOG_FORMAT = "[%(asctime)s] [%(filename)s/%(levelname)s]: %(message)s"

def setup_logger(logger_name: str, log_to_file: bool = False) -> logging.Logger:
    """
    | Set up custom logging.

    :param logger_name: The name of the logger.
    :param log_to_file: Whether to write logs to a file. Default is False.

    :return: Configured Logger instance.
    """

    logger = logging.getLogger(logger_name)
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

    if log_to_file:
        LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_NAME, "a", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
