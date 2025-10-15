import logging
import sys
import os
from datetime import datetime
from pathlib import Path
import json
import utils.pyflicker_logger_utils as pyflicker_logger_utils
from utils.pyflicker_run_query import run_upsert

pyflicker_logger_utils.setup_logger()
logger = logging.getLogger(__name__)

PATH_CFG = Path("cfg.json")
PATH_LOAD_FILES = Path("./to_load")


def main():
    # force working directory to script's location
    os.chdir(Path(__file__).parent)

    time_start = datetime.now()
    script_name = Path(__file__).name

    # set up the logger
    try:
        global logger
        logger = pyflicker_logger_utils.setup_logger(script_name)
    except Exception as e:
        sys.stderr.write(f"Error starting logger: {e}\n")
        raise RuntimeError(f"Error starting logger: {e}")

    logger.info("pyflicker is preparing to strike!")

    PATH_LOAD_FILES.mkdir(parents=True, exist_ok=True)
    if not PATH_CFG.exists():
        str_error = f"Configuration file {PATH_CFG} not found. Please create it based on cfg.json.example."
        logger.error(str_error)
        raise FileNotFoundError(str_error)

    cfg = {}
    with open(PATH_CFG, "r") as cfg_file:
        cfg = json.load(cfg_file)

    if cfg["db_password"] == "":
        str_error = "Please set db_password in cfg.json before running this script."
        logger.error(str_error)
        raise ValueError(str_error)

    txt_files = list(PATH_LOAD_FILES.glob("*.txt"))
    if len(txt_files) == 0:
        str_error = f"No .txt files found in {PATH_LOAD_FILES}. Please add files to load."
        logger.error(str_error)
        raise FileNotFoundError(str_error)

    successes = 0
    for txt_file in txt_files:
        logger.info(f"Processing file: {txt_file}")
        with open(txt_file, "r") as f:
            values_list = [line.strip() for line in f if line.strip()]

        table_name = txt_file.stem

        try:
            run_upsert(
                logger=logger,
                db_host_name=cfg["db_hostname"],
                db_user_name=cfg["db_username"],
                db_schema_name=cfg["db_schema_name"],
                db_password=cfg["db_password"],
                db_port=cfg["db_port"],
                db_ssl=cfg["db_ssl"],
                db_lock_wait_timeout=cfg["db_lock_wait_timeout"],
                table_name=table_name,
                data_file_lines=values_list,
                concurrency_limit=int(cfg["load_concurrency"]),
                task_value_limit=int(cfg["load_batch_size"])
            )
            logger.info(f"Finished processing file: {txt_file}")
            successes += 1
        except Exception as e:
            logger.error(f"Error processing file {txt_file}: {e}")

    time_end = datetime.now()
    logger.info(f"Script {script_name} completed. Start time: {time_start}, End time: {time_end}, Duration: {time_end - time_start}")
    logger.info(f"Processed {successes}/{len(txt_files)} files successfully.")
    logger.info("Finished all tasks.")


if __name__ == "__main__":
    main()
