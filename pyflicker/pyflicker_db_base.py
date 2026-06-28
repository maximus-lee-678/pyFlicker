"""
Base classes for PyFlicker operations.

When adding support for new databases, please subclass the appropriate base classes in this file and implement the required methods.
A checklist is as follows:
1. import the following base classes:
    - PyFlickerDBUserSuppliedDetailsBase
    - PyFlickerLoadConfigBase
    - PyFlickerRunBase
    - PyFlickerConnectionBase
    - PyFlickerMultithreaderBase
2. Add logger at top level, following naming convention: 'pyflicker.<db_type>'
3. Add supported connection types to new class PyFlickerDBConnection<db_type>
4. Implement the following classes:
    - PyFlickerDBUserSuppliedDetails<db_type> (one subclass per supported connection type)
    - PyFlickerLoadConfig<db_type> (return an instance of PyFlickerDBUserSuppliedDetails<db_type>)
    - PyFlickerRun<db_type> (implement every abstract method, no extra methods should be needed unless you want more granularity)
    - PyFlickerConnection<db_type> (create one method per supported connection type)
    - PyFlickerMultithreader<db_type> (implement thread writer)
"""

from abc import ABC, abstractmethod
from enum import StrEnum
import logging
import threading
from typing import Any, Union, ClassVar
import time


logger = logging.getLogger("pyflicker.base")


class PyFlickerSupportedDBTypes(StrEnum):
    """
    Supported database types for PyFlicker.
    """

    MYSQL = "MYSQL"
    POSTGRES = "POSTGRES"


class PyFlickerDBUserSuppliedDetailsBase(ABC):
    """
    | Base class for user-supplied database connection details, will contain data defined by user in config file.
    | Examples of members include hostname, username, password, port, etc.
    | Subclass this for each supported database type and connection type.
    """

    @abstractmethod
    def __init__(self):
        pass


class PyFlickerLoadConfigBase(ABC):
    cfg: dict[str, Any]
    db_connection_type: Any
    user_supplied_db_details: Any

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self._load_type()
        self._produce_user_supplied_db_details()

    @abstractmethod
    def get_user_supplied_db_details(self) -> Any:
        """
        Getter for prepared user_supplied_db_details in object form.

        :return: user_supplied_db_details object
        """

        return self.user_supplied_db_details

    @abstractmethod
    def _load_type(self) -> None:
        """
        Internal method to set db_connection_type based on config file contents.

        :return: None
        """

        pass

    @abstractmethod
    def _produce_user_supplied_db_details(self) -> None:
        """
        Internal method to create user_supplied_db_details object based on config file contents.

        :return: None
        """

        pass


class PyFlickerRunBase(ABC):
    """
    | Base class for running multithreaded upserts into a database.
    |
    | 'Tonight, a tale of wonder and magic.'
    | 'Tonight, a tale of long lost worlds.'
    | 'Tonight, a tale of terrible tragedy.'
    | 'Tonight, a tale of glorious redemption!'
    """
    base_query: ClassVar[str]

    def __init__(
        self, table_name: str, columns_list: list[str], values_list: list[str], maximum_threads: int, maximum_rows_per_thread: int
    ) -> None:
        """
        :param table_name: table name in database.
        :param columns_list: list of column names in database.
        :param values_list: list of strings formatted like ["('value_1','value_2',...)"].
        :param maximum_threads: maximum number of threads to use for multithreading.
        :param maximum_rows_per_thread: maximum number of rows to upsert per thread.

        :return: None
        """

        self.table_name = table_name
        self.columns_list = columns_list
        self.values_list = values_list  # strings formatted like ["('value_1','value_2',...)"]. e.g. output of parse_csv_*
        self.maximum_threads = maximum_threads
        self.maximum_rows_per_thread = maximum_rows_per_thread

        # subclass must type annotate these in subclasses
        self.user_supplied_db_details: Any = None
        self.db_connection_type: Any = None
        self.conn_details: dict[str, Any] = {}

    @abstractmethod
    def set_user_supplied_db_details(self, type: Any, user_supplied_db_details: Any) -> None:
        """
        Provide user-supplied database connection details produced by PyFlickerLoadConfig*.

        :param type: database connection type.
        :param user_supplied_db_details: user-supplied database connection details produced by PyFlickerLoadConfig*.

        :return: None
        """

        pass

    @abstractmethod
    def start_multithreaded_upsert(self) -> dict[str, Any]:
        """
        | 'On with the show!'
        | 
        | Start actual multithreaded upsert into the database.
        | This method should be called after set_user_supplied_db_details() has been called, or RuntimeError will be raised.
        | As this class calls the multithreader, logs will be produced for each thread. 
        | If the logger has been properly configured, these logs will be written to the console and/or a log file.
        |
        | This method description should be overridden in subclasses to provide more database specific information about rows_affected.

        :return: dict with keys "transaction_successful" (bool) and "rows_affected" (int)
        """
        pass

    @abstractmethod
    def _instantiate_conn_details(self) -> None:
        """
        Internal method to instantiate conn_details based on user_supplied_db_details and db_connection_type.

        :return: None
        """

        pass

    @abstractmethod
    def _get_column_names(self, conn: Any) -> list[str]:
        """
        Internal method to get column names from the database table.

        :param conn: database connection object.

        :return: list of column names. case-sensitive as defined in the database.
        """

        pass

    @abstractmethod
    def _get_primary_keys(self, conn: Any) -> list[str]:
        """
        Internal method to get primary keys from the database table.

        :param conn: database connection object.

        :return: list of primary key names. case-sensitive as defined in the database.
        """

        pass

    def _verify_columns_match(self, db_columns: list[str], user_provided_columns: list[str]) -> bool:
        """
        Internal method to verify that the columns in the database table match the columns from the user's source.

        :param db_columns: list of column names from the database table.
        :param user_provided_columns: list of column names from the user's source.

        :return: bool of whether the columns match.
        """

        return len(db_columns) == len(user_provided_columns) and set(db_columns) == set(user_provided_columns)


class PyFlickerConnectionBase(ABC):
    """
    Base class for building database connection objects.
    Subclasses should implement 1 method per supported connection type, in addition to implmenting get_conn_object().
    """

    @staticmethod
    @abstractmethod
    def get_conn_object(conn_details: dict[str, Any]) -> Any:
        """
        Parse conn_details dictionary produced by one of this classes' connection type methods and return a database connection object.

        :param conn_details: dictionary of connection details.

        :return: database connection object.
        """

        pass


class PyFlickerMultithreaderBase(ABC):
    """
    Base class for multithreading database upserts.
    Subclasses should implement _execute_thread() to define how each thread will execute its query.
    """

    def __init__(
        self, maximum_threads: int, conn_details: dict, db_connection_type: Any, queries: list[str]
    ) -> None:
        """
        :param maximum_threads: maximum number of threads to use for multithreading.
        :param conn_details: dictionary of connection details produced by PyFlickerRun*.
        :param db_connection_type: database connection type. needed as some connection types alter connection behaviour.
        :param queries: list of queries to execute in threads. output of pyflicker_distribute.form_query_list_from_plan().
        """

        self.maximum_threads = maximum_threads
        self.conn_details = conn_details
        self.db_connection_type = db_connection_type
        # tasks should be never needed for our upserts, we bake the values in directly by necessity. if you want to use tasks, you can subclass this and add a task list and modify _execute_thread() to use it.
        self.queries = queries

        self._row_count = 0
        self._exceptions: list[str] = []
        self._lock = threading.Lock()

    # ---- thread-safe shared-state mutators ----

    def _add_rows(self, count: int) -> None:
        with self._lock:
            self._row_count += count

    def _add_exception(self, exception_str: str) -> None:
        with self._lock:
            self._exceptions.append(exception_str)

    @property
    def row_count(self) -> int:
        with self._lock:
            return self._row_count

    @property
    def exceptions(self) -> list[str]:
        with self._lock:
            return list(self._exceptions)

    # --------------------------------------------------

    @abstractmethod
    def _execute_thread(self, thread_id: int, query: str) -> None:
        """
        | Internal method to execute a single query.
        | Things this method should do:
        1. Open connection to database using PyFlickerConnection*.get_conn_object().
        2. Perform any session setup needed.
        3. Execute the query and commit the transaction.

        | Throughout, it should log the thread id and any relevant information to the logger.
        | Exceptions should be caught and logged, and the exception string should be added to self._exceptions using self._add_exception().
        |
        | Remember that specific connection types may have different connection behaviour, e.g. IAM times out after a while.

        :param thread_id: thread id, used for logging.
        :param query: query to execute.

        :return: None
        """

        pass

    def run(self) -> dict[str, Any]:
        """
        | 'Perhaps one is weak. To be ignored. Perhaps two are not much better. But what of five? Ten? Twenty? ...'
        |
        | Starts the multithreading process, creating threads to execute queries in self.queries.
        | This method will block until all threads have completed.

        :return: dict with keys "transaction_successful" (bool) and "rows_affected" (int)
        """
        threads_created = 0
        displayed_active_thread_count = 0  # used to not spam stdout with currently active threads every second
        has_started = False
        num_threads_to_run = len(self.queries)
        threads: list[threading.Thread] = []

        logger.info("Multithreading function starting.")
        logger.info(f"[MAIN] Starting up to {self.maximum_threads} threads.")

        while len(threads) != 0 or not has_started:
            for thread in threads[:]:  # iterate over a copy of the list to avoid shooting yourself
                if not thread.is_alive():
                    threads.remove(thread)

            if threads_created < num_threads_to_run and len(threads) < self.maximum_threads:
                logger.debug(f"[MAIN] Threads Active before addition: {len(threads)}")

                # minimum of how many threads left to create or how much the "buffer" can fit
                # in this loop, i can be treated as thread id to create and is zero-based
                for i in range(threads_created, min(num_threads_to_run, threads_created + (self.maximum_threads - len(threads)))):
                    thread = threading.Thread(target=self._execute_thread, args=(i, self.queries[i]))
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

        return self._build_result()

    def _build_result(self) -> dict[str, Any]:
        """
        Internal method to build the result dictionary after all threads have completed.

        :return: dict with keys "transaction_successful" (bool) and "rows_affected" (int)
        """

        if self.exceptions:
            logger.error(f"[MAIN] [ERROR] Exceptions were raised by {len(self.exceptions)} threads! All Exceptions:")
            for i, exception in enumerate(self.exceptions):
                logger.error(f"[MAIN] Exception {i}: {exception}")
            logger.info("Multithreading function finished.")
            return {"transaction_successful": False, "exception": self.exceptions}

        logger.info("Multithreading function finished.")
        return {"transaction_successful": True, "rows_affected": self.row_count}
