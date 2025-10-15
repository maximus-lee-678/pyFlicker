import logging
from pathlib import Path
from utils.pyflicker_pymysql_utils import safe_select, safe_transaction_multithread
import utils.pyflicker_def_utils as pyflicker_def_utils

logger = logging.getLogger(__name__)


def get_even_plan(values_count, concurrency_target, maximum_tasks_per_query) -> list[int]:
    """
    | Distributes data evenly (e.g. [101, 101, 100, 100, 100] for 502 parameters).
    | Usually paired with safe_transaction_multithread().
    | Ensures no value exceeds maximum_tasks_per_query, and that the number of parts is at most concurrency_target.

    :param int values_count: total number of parameters to distribute
    :param int concurrency_target: target number of concurrent threads to use
    :param int maximum_tasks_per_query: maximum number of parameters to put into each query

    :return: list[int]
    """

    global logger

    if values_count <= 0:
        logger.warning("No values to process.")
        return []

    # Ensure we have enough parts so no value exceeds y
    concurrency_target = max(concurrency_target, -(-values_count // maximum_tasks_per_query))  # ceiling division

    base = values_count // concurrency_target
    remainder = values_count % concurrency_target

    # Distribute the remainder across the first few elements
    result = [base + 1] * remainder + [base] * (concurrency_target - remainder)

    while 0 in result:
        result.remove(0)

    logger.info(f"Final Partition Plan: {values_count} -> {result}")

    return result


def form_query_list_from_plan(query_plan: list[int], formattable_query: str, params: list[str]) -> list[str]:
    """
    | Substitutes a list of parameters into a new list containing formatted queries based on a query plan.

    :param list[int] query_plan: list of integers representing the number of parameters to put into each query
    :param string formattable_query: query to substitute parameters into (must have {0} where parameters are to be placed)
    :param list[str] params: list of queries to substitute into {0} in formattable_query

    :return: list[str]
    """

    fragmented_queries = []
    query_index = 0

    for query_count in query_plan:
        if query_count == 0:
            continue

        fragmented_queries.append(formattable_query.format(",".join(param for param in params[query_index:query_index + query_count])))
        query_index += query_count

    return fragmented_queries


def get_mysql_columns(conn_details, table_name):
    query = f"""SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='{conn_details["schema"]}' AND TABLE_NAME='{table_name}'"""

    mysql_response = safe_select(conn_details, query, task=None, get_type="all")
    if not mysql_response["select_successful"]:
        error_msg = f"""Failed to get column names: {mysql_response["exception"]}"""
        raise RuntimeError(error_msg)

    return [row[0] for row in mysql_response["content"]]


def get_mysql_primary_keys(conn_details, table_name):
    query = f"""SHOW KEYS FROM {table_name} WHERE Key_name = 'PRIMARY'"""

    mysql_response = safe_select(conn_details, query, task=None, get_type="all")
    if not mysql_response["select_successful"]:
        error_msg = f"""Failed to get primary keys: {mysql_response["exception"]}"""
        raise RuntimeError(error_msg)

    return [row[4] for row in mysql_response["content"] if row[2] == "PRIMARY"]


def run_upsert(
        logger, db_host_name, db_user_name, db_schema_name, db_password, db_port, db_ssl, db_lock_wait_timeout,
        table_name, data_file_lines, concurrency_limit, task_value_limit
):
    """
    | data_file_lines is a list of strings, where each string represents a row
    | first string is header, subsequent strings are values
    | 
    | each line contains opening and closing parentheses, to prevent confusion between 'true' and true
    | header also contains parentheses, e.g. (col1, col2, col3)
    """

    conn_details = {
        "hostname": db_host_name,
        "username": db_user_name,
        "password": db_password,
        "port": int(db_port),
        "schema": db_schema_name,
        "db_lock_wait_timeout": db_lock_wait_timeout
    }
    if db_ssl and Path(db_ssl).is_file():
        conn_details["ssl"] = {"ca": db_ssl}
    elif db_ssl and not Path(db_ssl).is_file():
        raise RuntimeError("SSL Certificate not found at specified path!")

    # get the column names from the table
    db_col_names = get_mysql_columns(conn_details, table_name)
    db_col_names = [col_name.lower() for col_name in db_col_names]
    logger.info(f"Database column names: {db_col_names}")

    primary_keys = get_mysql_primary_keys(conn_details, table_name)
    logger.info(f"Primary keys: {primary_keys}")

    file_col_names = [col.strip().lower() for col in data_file_lines[0].strip("()").split(",")]
    logger.info(f"File column names: {file_col_names}")

    if set(file_col_names) != set(db_col_names):
        str_error = "Column names in file do not match column names in database table."
        logger.error(str_error)
        raise ValueError(str_error)

    update_keys = ",".join(
        [f"{col}=alias.{col}" for col in db_col_names if col not in primary_keys]
    )  # includes all columns accept primary keys
    final_cols_string = ",".join(file_col_names)  # use file column ordering

    query = f"""INSERT INTO {table_name} ({final_cols_string}) VALUES {{0}} AS alias ON DUPLICATE KEY UPDATE {update_keys};"""

    values_list = data_file_lines[1:]

    query_fragmentation_plan = get_even_plan(len(values_list), concurrency_limit, task_value_limit)

    fragmented_queries = form_query_list_from_plan(query_fragmentation_plan, query, values_list)
    logger.info(f"""Query assembled: {len(query_fragmentation_plan)} updates to be carried out, \
{query_fragmentation_plan[0]} +-1 rows per operation.""")

    mysql_response = safe_transaction_multithread(
        maximum_threads=concurrency_limit,
        dirty_reads_enabled=True,
        conn_details=conn_details,
        conn_type=pyflicker_def_utils.CONN_TYPE.PASSWORD,
        queries=fragmented_queries,
        task=None
    )
    if not mysql_response["transaction_successful"]:
        raise RuntimeError(mysql_response["exception"])

    logger.info(f"Updates to rows completed.")
