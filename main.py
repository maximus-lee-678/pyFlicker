from typing import Any

from utils import pyflicker_logger
import os
from datetime import datetime
from pathlib import Path
import json
from enum import StrEnum


class SupportedDBTypes(StrEnum):
    MYSQL = "MYSQL"
    POSTGRES = "POSTGRES"


PATH_CFG = Path("cfg.json")
PATH_LOAD_FILES = Path("./to_load")

# force working directory to script's location
os.chdir(Path(__file__).parent)

logger = pyflicker_logger.setup_logger(logger_name="pyflicker", log_to_file=True)


def main():
    time_start = datetime.now()
    script_name = Path(__file__).name

    logger.info("pyflicker started.")

    PATH_LOAD_FILES.mkdir(parents=True, exist_ok=True)
    if not PATH_CFG.exists():
        str_error = f"Configuration file {PATH_CFG} not found. Please create it based on cfg.json.example."
        logger.error(str_error)
        raise FileNotFoundError(str_error)

    cfg = {}
    with open(PATH_CFG, "r") as cfg_file:
        cfg = json.load(cfg_file)

    if "db_type" not in cfg or cfg["db_type"] not in SupportedDBTypes.__members__:
        str_error = f"Invalid or missing db_type in configuration file. Supported types: {list(SupportedDBTypes)}"
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

        table_name = txt_file.stem
        header_read = False
        columns_list = []
        values_list = []
        with open(txt_file, "r") as f:
            # currently formatted like ("value_1","value_2",boolean_1,boolean_2,...)
            for line in f:
                if not header_read:
                    # currently formatted like (col1,col2,col3,...)
                    columns_list = [col.strip().lower() for col in line.strip("()").split(",")]
                    header_read = True
                else:
                    values_list.append(line.strip())

        result: dict[str, Any] = {}
        try:
            match cfg["db_type"]:
                case SupportedDBTypes.MYSQL:
                    from utils import pyflicker_db_mysql
                    user_supplied_db_details = pyflicker_db_mysql.PyFlickerLoadConfigMySQL(cfg).get_user_supplied_db_details()
                    db_runner = pyflicker_db_mysql.PyFlickerRunMySQL(
                        table_name=table_name,
                        columns_list=columns_list,
                        values_list=values_list,
                        maximum_threads=cfg["maximum_threads"],
                        maximum_rows_per_thread=cfg["maximum_rows_per_thread"]
                    )
                    db_runner.set_user_supplied_db_details(
                        pyflicker_db_mysql.PyFlickerDBConnectionType(cfg["auth_type"]),
                        user_supplied_db_details
                    )
                    result = db_runner.start_multithreaded_insert()

                case SupportedDBTypes.POSTGRES:
                    raise NotImplementedError("Postgres support is not yet implemented.")

                case _:
                    raise ValueError(f"""Invalid db_type: {cfg["db_type"]}. \
Supported types: {list(SupportedDBTypes)}""")

        except Exception as e:
            logger.error(f"Error processing file {txt_file}: {e}")

        transaction_successful = result.get("transaction_successful", False)
        if transaction_successful:
            successes += 1
        logger.info(f"Result for file {txt_file}: {result}")

    time_end = datetime.now()
    logger.info(f"Script {script_name} completed. Start time: {time_start}, End time: {time_end}, Duration: {time_end - time_start}")
    logger.info(f"Processed {successes}/{len(txt_files)} files successfully.")
    logger.info("Finished all tasks.")


if __name__ == "__main__":
    main()
