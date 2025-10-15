import logging
from pathlib import Path
from enum import Enum
from typing import Union
import threading
import time
import pymysql

import utils.pyflicker_def_utils as pyflicker_def_utils
import utils.pyflicker_boto3_utils as pyflicker_boto3_utils

logger = logging.getLogger(__name__)


def get_conn_object(conn_details: dict) -> pymysql.connections.Connection:
    """
    | Returns a pymysql connection object based on the conn_details dictionary. IAM token and password compatible.
    | Requires SSL. If it is not found at the specified path, raises RuntimeError.

    :param dict conn_details: dictionary produced by boto3_utils.get_mysql_conn_details_iam() or boto3_utils.get_mysql_conn_details_password().

    :returns: pymysql connection object
    """

    password_or_token = conn_details["password"] if "password" in conn_details else conn_details["token"]

    if "ssl" in conn_details and Path(conn_details["ssl"]["ca"]).is_file():
        conn = pymysql.connect(
            host=conn_details["hostname"],
            user=conn_details["username"],
            passwd=password_or_token,
            database=conn_details["schema"],
            ssl=conn_details["ssl"],
            connect_timeout=conn_details["db_lock_wait_timeout"],
            port=int(conn_details["port"])
        )
    elif "ssl" in conn_details and not Path(conn_details["ssl"]["ca"]).is_file():
        raise RuntimeError("SSL Certificate not found at specified path!")
    else:
        conn = pymysql.connect(
            host=conn_details["hostname"],
            user=conn_details["username"],
            passwd=password_or_token,
            database=conn_details["schema"],
            connect_timeout=conn_details["db_lock_wait_timeout"],
            port=int(conn_details["port"])
        )

    return conn


def safe_select(conn_details: dict, query: str, task: Union[tuple, None], get_type: str) -> dict:
    """
    | SELECT MYSQL Wrapper.

    :param dict conn_details: dictionary produced by boto3_utils.get_mysql_conn_details_iam() or boto3_utils.get_mysql_conn_details_password().
    :param string query: query string
    :param tuple/None task: tuple containing values for substitution into prepared statement, or None
    :param string get_type: 'one' or 'all'

    :returns: dictionary - {
        'select_successful': boolean,
        'num_rows' - iff 'select_successful' == True: int - number of rows returned.
        'content' - iff 'select_successful' == True: list - select output. may be empty.
        'exception' - iff 'select_successful' == False: string - sql exception in string format.
    }
    """

    try:
        conn = get_conn_object(conn_details)
        cursor = conn.cursor()

        if task:
            cursor.execute(query, task)
        else:
            cursor.execute(query)

        field_names = [i[0] for i in cursor.description]

        if get_type == "one":
            content = cursor.fetchone()
            return_dict = {
                "select_successful": True,
                "num_rows": 0 if content is None else 1,
                "headers": field_names,
                "content": content
            }

        elif get_type == "all":
            content = cursor.fetchall()
            return_dict = {
                "select_successful": True,
                "num_rows": len(content),
                "headers": field_names,
                "content": content
            }

        else:
            return_dict = {"select_successful": False, "exception": "Wrongly specified get_type."}

    except pymysql.Error as e:
        exception_str = "Caught MySQL Error %d: %s" % (e.args[0], e.args[1])

        return_dict = {"select_successful": False, "exception": exception_str}

    except Exception as e:
        exception_str = f"Caught {e.__class__.__name__} Exception: {e}"

        return_dict = {"select_successful": False, "exception": exception_str}

    finally:
        if "cursor" in locals() and cursor:
            cursor.close()
        if "conn" in locals() and conn:
            conn.close()

        if not return_dict:
            return_dict = {"transaction_successful": False, "exception": "FATAL: EXCEPTION COULD NOT BE CAUGHT. CHECK STACK TRACE."}
        return return_dict


def safe_transaction_multithread(
        maximum_threads: int, dirty_reads_enabled: bool, conn_details: dict,
        conn_type: Enum, queries: list[str], task: Union[tuple, None]
) -> dict:
    """
    | CREATE, UPDATE, DELETE MySQL Wrapper that executes each query in the queries list in parallel.
    | Logs threads starting and stopping. If the maximum number of threads are created
    | and there are more queries to execute, they are queued for subesequent executions. Any exceptions caught will be returned in list format,
    | and all threads must complete before this function returns.
    |
    | Due to the long-running nature of this job, credentials using authentication tokens have a chance of expiring.
    | Because of this, this function accepts a dict to submit to boto3_utils.get_mysql_conn_details_iam() or boto3_utils.get_mysql_conn_details_password().
    | or boto3_utils.get_mysql_conn_details_password() instead of a conn_details dictionary directly.
    | When CONN_TYPE.IAM is specified, a token will be generated for each thread.
    | When CONN_TYPE.PASSWORD is specified, the same password will be used for all threads.
    | 
    | WARNING: This function very easily runs into table locks, which causes all but one thread to fail. Even if it doesn't fail,
    | the other threads must wait for the one thread to release the lock, after which another single thread takes over, which 
    | results in basically only one thread executing at a time. You may set dirty_reads_enabled, which runs the statement
    | 'SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;' which cause all reads to happen in a non-locking fashion. 
    | This allows for reading of tables without locking them, but may result in reads of uncommited data. 
    | This shouldn't be an issue in our scope, no one else will be hitting the table so all the data should not change.

    :param int maximum_threads: maximum number of connections to open at once
    :param bool dirty_reads_enabled: whether table locks should be disabled for all threads
    :param dict conn_details: dictionary for use by boto3_utils.get_mysql_conn_details_iam() or boto3_utils.get_mysql_conn_details_password(), 
    should contain all keys named as required by the functions.
    :param CONN_TYPE conn_type: CONN_TYPE.IAM or CONN_TYPE.PASSWORD.
    :param list[str] queries: query list generated by QUERY_FRAGMENTER.get_even_plan() or QUERY_FRAGMENTER.get_front_heavy_plan() (latter not recommended)
    :param tuple/None task: tuple containing values for substitution into prepared statement, or None

    :returns: dictionary - {
        'transaction_successful': boolean,
        'rows_affected' - iff 'transaction_successful' == True: int - number of rows affected.
        'exception' - iff 'transaction_successful' == False: list - sql exception(s) in string format. may contain multiple exceptions.
    }
    """

    row_count = 0
    threads_created = 0
    displayed_active_thread_count = 0   # used to not spam stdout with currently active threads every second
    has_started = False
    num_threads_to_run = len(queries)

    conn_details_password = None

    threads = []
    exceptions_list = []

    def transaction_thread(thread_id: int, query: str, task: Union[tuple, None]):
        nonlocal row_count

        query_len = len(query)
        query_size_mb = f"{(query_len / 2**20):.2f}"
        logger.info(f"""[THREAD/{thread_id}] starting with payload of size {query_size_mb} MB! \
{"[DIRTY READ MODE ENABLED, TREAD LIGHTLY!]" if dirty_reads_enabled else ""}""")

        try:
            # IAM: need to generate token for each thread, since token may be invalidated by time passing
            if conn_type == pyflicker_def_utils.CONN_TYPE.AWS_IAM:
                conn_details = pyflicker_boto3_utils.get_mysql_conn_details_iam(
                    hostname=conn_details["hostname"],
                    username=conn_details["username"],
                    schema=conn_details["schema"],
                    port=conn_details["port"],
                    ssl=conn_details["ssl"] if "ssl" in conn_details else None
                )
            else:
                conn_details = conn_details_password

            conn = get_conn_object(conn_details)
            cursor = conn.cursor()

            if dirty_reads_enabled:
                # disable row level locks
                cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
                # significantly increase lock wait timeout, in case of gap locks
                cursor.execute(
                    f"""SET SESSION innodb_lock_wait_timeout = {conn_details["db_lock_wait_timeout"]};""")
                conn.commit()

            if task:
                cursor.execute(query, task)
            else:
                cursor.execute(query)

            conn.commit()

            logger.info(f"[THREAD/{thread_id}] finished.")

            row_count += cursor.rowcount

        except pymysql.Error as e:
            exception_str = "Caught MySQL Error %d: %s" % (e.args[0], e.args[1])

            exceptions_list.append(exception_str)
            logger.error(f"[THREAD/{thread_id}] failed with Error {e.args[0]}!")

        except Exception as e:
            exception_str = f"Caught {e.__class__.__name__} Exception: {e}"

            exceptions_list.append(exception_str)
            logger.error(f"[THREAD/{thread_id}] failed with Error {e}!")

        finally:
            if "cursor" in locals() and cursor:
                cursor.close()
            if "conn" in locals() and conn:
                conn.close()
            logger.info(f"[THREAD/{thread_id}] shutting down.")

    if conn_type == pyflicker_def_utils.CONN_TYPE.AWS_IAM and not \
            set(pyflicker_def_utils.CONN_DETAILS_IAM_ARGS).issubset(conn_details.keys()):
        raise ValueError(f"conn_details_creation_dict must contain keys {pyflicker_def_utils.CONN_DETAILS_IAM_ARGS}.")
    elif conn_type == pyflicker_def_utils.CONN_TYPE.PASSWORD and not \
            set(pyflicker_def_utils.CONN_DETAILS_PASSWORD_ARGS).issubset(conn_details.keys()):
        raise ValueError(f"conn_details_creation_dict must contain keys {pyflicker_def_utils.CONN_DETAILS_PASSWORD_ARGS}.")

    logger.info("Multithreading function starting.")
    logger.info(f"[MAIN] Starting up to {maximum_threads} threads.")

    # password: can reuse the same password for all threads
    if conn_type == pyflicker_def_utils.CONN_TYPE.PASSWORD:
        conn_details_password = conn_details
    while len(threads) != 0 or not has_started:
        for thread in threads:
            if not thread.is_alive():
                threads.remove(thread)

        if threads_created < num_threads_to_run and len(threads) < maximum_threads:
            logger.debug(f"[MAIN] Threads Active before addition: {len(threads)}")

            # minimum of how many threads left to create or how much the "buffer" can fit
            # in this loop, i can be treated as thread id to create and is zero-based
            for i in range(threads_created, min(num_threads_to_run, threads_created + (maximum_threads - len(threads)))):
                thread = threading.Thread(target=transaction_thread, args=(i, queries[i], task))
                threads.append(thread)
                thread.start()
                logger.info(f"[MAIN] Thread ID {threads_created} created.")

                threads_created += 1

            logger.debug(f"[MAIN] Threads Active after addition: {len(threads)}")
            displayed_active_thread_count = len(threads)

        elif displayed_active_thread_count != len(threads):
            # only show updates if there's changes
            logger.debug(f"[MAIN] Threads Currently Active: {len(threads)}")
            displayed_active_thread_count = len(threads)

        if not has_started:
            has_started = True

        time.sleep(1)

    if exceptions_list:
        logger.error(f"[MAIN] [ERROR] Exceptions were raised by {len(exceptions_list)} threads! All Exceptions:")
        for i, exception in enumerate(exceptions_list):
            logger.error(f"[MAIN] Exception {i}: {exception}")

        return_dict = {
            "transaction_successful": False,
            "exception": exceptions_list
        }
    else:
        return_dict = {
            "transaction_successful": True,
            "rows_affected": row_count
        }

    logger.info("Multithreading function finished.")
    return return_dict
