"""
Example usage of pyFlicker to load CSV files into a database using multithreading.
"""

import pyflicker
import logging
from typing import Any
import os
from datetime import datetime
from pathlib import Path
import json


PATH_CFG = Path("cfg.json")
PATH_LOAD_FILES = Path("./to_load")
PATH_LOGS = Path("./logs")

# force working directory to script's location
os.chdir(Path(__file__).parent)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def main():
    pyflicker.setup_logger(PATH_LOGS)

    time_start = datetime.now()
    script_name = Path(__file__).name

    logger.info(f"{script_name} started.")

    PATH_LOAD_FILES.mkdir(parents=True, exist_ok=True)
    if not PATH_CFG.exists():
        str_error = f"Configuration file {PATH_CFG} not found. Please create it based on cfg.json.example."
        logger.error(str_error)
        raise FileNotFoundError(str_error)

    cfg: dict[str, Any] = {}
    with open(PATH_CFG, "r") as cfg_file:
        cfg = json.load(cfg_file)

    if "db_type" not in cfg or cfg["db_type"] not in pyflicker.PyFlickerSupportedDBTypes.__members__:
        str_error = f"Invalid or missing db_type in configuration file. Supported types: {list(pyflicker.PyFlickerSupportedDBTypes)}"
        logger.error(str_error)
        raise ValueError(str_error)

    csv_files = list(PATH_LOAD_FILES.glob("*.csv"))
    if len(csv_files) == 0:
        str_error = f"No .csv files found in {PATH_LOAD_FILES}. Please add files to load."
        logger.error(str_error)
        raise FileNotFoundError(str_error)

    successes = 0
    for csv_file in csv_files:
        logger.info(f"Processing file: {csv_file}")

        table_name = csv_file.stem
        columns_list: list[str]
        values_list: list[str]
        result: dict[str, Any] = {}
        try:
            match cfg["db_type"]:
                case pyflicker.PyFlickerSupportedDBTypes.MYSQL:
                    columns_list, values_list = pyflicker.parse_csv_mysql(csv_file)

                    db_runner = pyflicker.PyFlickerRunMySQL(
                        table_name=table_name,
                        columns_list=columns_list,
                        values_list=values_list,
                        maximum_threads=cfg["maximum_threads"],
                        maximum_rows_per_thread=cfg["maximum_rows_per_thread"]
                    )
                    db_runner.set_user_supplied_db_details(
                        cfg["auth_type"], pyflicker.PyFlickerLoadConfigMySQL(cfg).get_user_supplied_db_details()
                    )
                    result = db_runner.start_multithreaded_upsert()

                case pyflicker.PyFlickerSupportedDBTypes.POSTGRES:
                    columns_list, values_list = pyflicker.parse_csv_postgres(csv_file)

                    raise NotImplementedError("Postgres support is not yet implemented.")

                case _:
                    raise ValueError(f"""Invalid db_type: {cfg["db_type"]}. \
Supported types: {list(pyflicker.PyFlickerSupportedDBTypes)}""")

        except Exception as e:
            logger.error(f"Error processing file {csv_file}: {e}")

        transaction_successful = result.get("transaction_successful", False)
        if transaction_successful:
            successes += 1
        logger.info(f"Result for file {csv_file}: {result}")

    time_end = datetime.now()
    logger.info(f"Script {script_name} completed. Start time: {time_start}, End time: {time_end}, Duration: {time_end - time_start}")
    logger.info(f"Processed {successes}/{len(csv_files)} files successfully.")
    logger.info("Finished all tasks.")


if __name__ == "__main__":
    main()
