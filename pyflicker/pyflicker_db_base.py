from abc import ABC, abstractmethod
from enum import StrEnum
import logging
import threading
from typing import Any, Union
import time


logger = logging.getLogger("pyflicker.base")


class PyFlickerSupportedDBTypes(StrEnum):
    MYSQL = "MYSQL"
    POSTGRES = "POSTGRES"


class PyFlickerLoadConfigBase(ABC):
    cfg: dict[str, Any]
    db_connection_type: Any
    user_supplied_db_details: Any

    @abstractmethod
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self._load_type()
        self._produce_user_supplied_db_details()

    @abstractmethod
    def get_user_supplied_db_details(self) -> Any:
        return self.user_supplied_db_details

    @abstractmethod
    def _load_type(self) -> None:
        raise NotImplementedError("Subclasses must implement this!")

    @abstractmethod
    def _produce_user_supplied_db_details(self) -> None:
        raise NotImplementedError("Subclasses must implement this!")


class PyFlickerDBUserSuppliedDetailsBase(ABC):
    @abstractmethod
    def __init__(self):
        raise NotImplementedError("Subclasses must implement this!")


class PyFlickerRunBase(ABC):
    table_name: str
    # strings formatted like ["('value_1','value_2',boolean_1,boolean_2,...)" ...] perhaps this could be changed in the future...
    values_list: list[str]
    maximum_threads: int

    def __init__(
        self, table_name: str, columns_list: list[str], values_list: list[str], maximum_threads: int, maximum_rows_per_thread: int
    ):
        self.table_name = table_name
        self.columns_list = columns_list
        self.values_list = values_list
        self.maximum_threads = maximum_threads
        self.maximum_rows_per_thread = maximum_rows_per_thread

    @abstractmethod
    def set_user_supplied_db_details(self, type: Any, user_supplied_db_details: Any):
        raise NotImplementedError("Subclasses must implement this!")

    @abstractmethod
    def start_multithreaded_insert(self) -> dict[str, Any]:
        raise NotImplementedError("Subclasses must implement this!")

    @abstractmethod
    def _instantiate_conn_details(self) -> Any:
        raise NotImplementedError("Subclasses must implement this!")

    @abstractmethod
    def _get_column_names(self, conn: Any) -> list[str]:
        raise NotImplementedError("Subclasses must implement this!")

    @abstractmethod
    def _get_primary_keys(self, conn: Any) -> list[str]:
        raise NotImplementedError("Subclasses must implement this!")

    def _verify_columns_match(self, db_columns: list[str], file_columns: list[str]) -> bool:
        return len(db_columns) == len(file_columns) and set(db_columns) == set(file_columns)


class PyFlickerConnectionBase(ABC):
    @staticmethod
    @abstractmethod
    def get_conn_object(conn_details: dict[str, Any]) -> Any:
        raise NotImplementedError("Subclasses must implement this!")


class PyFlickerMultithreaderBase(ABC):
    """
    | Base runner that executes each query in parallel, one connection per thread.
    | Subclass and override _execute_thread() for db-specific connection/execution logic.
    | Shared row_count and exceptions are thread-safe via internal lock.
    """

    def __init__(
        self, maximum_threads: int, conn_details: dict, conn_type: Any, queries: list[str], task: Union[tuple, None]
    ) -> None:
        self.maximum_threads = maximum_threads
        self.conn_details = conn_details
        self.conn_type = conn_type
        self.queries = queries
        self.task = task

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
        raise NotImplementedError("Subclasses must implement this!")

    def run(self) -> dict[str, Any]:
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
        exceptions = self.exceptions
        if exceptions:
            logger.error(f"[MAIN] [ERROR] Exceptions were raised by {len(exceptions)} threads! All Exceptions:")
            for i, exception in enumerate(exceptions):
                logger.error(f"[MAIN] Exception {i}: {exception}")
            logger.info("Multithreading function finished.")
            return {"transaction_successful": False, "exception": exceptions}

        logger.info("Multithreading function finished.")
        return {"transaction_successful": True, "rows_affected": self.row_count}
