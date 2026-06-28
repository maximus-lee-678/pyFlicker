from pyflicker.pyflicker_db_base import PyFlickerDBUserSuppliedDetailsBase, PyFlickerLoadConfigBase, PyFlickerRunBase, PyFlickerConnectionBase, PyFlickerMultithreaderBase
import pyflicker.pyflicker_distribute as pyflicker_distribute
import logging
from pathlib import Path
from enum import StrEnum
from typing import Any, ClassVar, Union
import json
import pymysql


logger = logging.getLogger("pyflicker.mysql")

MYSQL_DEFAULT_PORT = 3306
DB_CONNECTION_TIMEOUT = 10  # in seconds
DB_LOCK_WAIT_TIMEOUT = 60  # in seconds


class PyFlickerDBConnectionTypeMySQL(StrEnum):
    PASSWORD = "PASSWORD"
    IAM = "IAM"
    GLUE_CONN = "GLUE_CONN"


class PyFlickerUserSuppliedDBDetailsMySQLPassword(PyFlickerDBUserSuppliedDetailsBase):
    """
    MySQL connection details for password-based authentication.
    """

    hostname: str
    username: str
    password: str
    schema: str
    port: int
    ssl: Union[str, None]

    def __init__(
        self, hostname: str, username: str, password: str, schema: str, port: int = MYSQL_DEFAULT_PORT, ssl: Union[str, None] = None
    ) -> None:
        """
        :param hostname: MySQL server URI.
        :param username: connecting username.
        :param password: username's password.
        :param schema: schema to use.
        :param port: the port number to connect to. defaults to MySQL default if not specified.
        :param ssl: optional path to SSL certificate file. leave as None if not using SSL.

        :return: None
        """

        self.hostname = hostname
        self.username = username
        self.password = password
        self.schema = schema
        self.port = port
        self.ssl = ssl


class PyFlickerUserSuppliedDBDetailsMySQLIAM(PyFlickerDBUserSuppliedDetailsBase):
    """
    MySQL connection details for AWS IAM-based authentication.
    """

    hostname: str
    username: str
    schema: str
    port: int
    ssl: Union[str, None]

    def __init__(
        self, hostname: str, username: str, schema: str, port: int = MYSQL_DEFAULT_PORT, ssl: Union[str, None] = None
    ) -> None:
        """
        :param hostname: MySQL server URI.
        :param username: connecting username.
        :param schema: schema to use.
        :param port: the port number to connect to. defaults to MySQL default if not specified.
        :param ssl: optional path to SSL certificate file. leave as None if not using SSL.

        :return: None
        """

        self.hostname = hostname
        self.username = username
        self.schema = schema
        self.port = port
        self.ssl = ssl


class PyFlickerUserSuppliedDBDetailsMySQLGlueConn(PyFlickerDBUserSuppliedDetailsBase):
    """
    MySQL connection details for AWS Glue Connector-based authentication.
    """

    glue_connector_name: str
    ssl: Union[str, None]

    def __init__(self, glue_connector_name: str, ssl: Union[str, None] = None) -> None:
        """
        :param glue_connector_name: name of AWS glue connector resource to retrieve connection details from.
        :param ssl: optional path to SSL certificate file. leave as None if not using SSL.

        :return: None
        """

        self.glue_connector_name = glue_connector_name
        self.ssl = ssl


class PyFlickerLoadConfigMySQL(PyFlickerLoadConfigBase):
    """
    | Processes configuration file to get input parameters for MySQL database connection (user_supplied_db_details).
    | Call get_user_supplied_db_details() to retrieve the user_supplied_db_details object.
    """

    cfg: dict[str, Any]
    db_connection_type: PyFlickerDBConnectionTypeMySQL
    user_supplied_db_details: Union[
        PyFlickerUserSuppliedDBDetailsMySQLPassword,
        PyFlickerUserSuppliedDBDetailsMySQLIAM,
        PyFlickerUserSuppliedDBDetailsMySQLGlueConn
    ]

    def get_user_supplied_db_details(self) -> Union[
        PyFlickerUserSuppliedDBDetailsMySQLPassword,
        PyFlickerUserSuppliedDBDetailsMySQLIAM,
        PyFlickerUserSuppliedDBDetailsMySQLGlueConn
    ]:
        return super().get_user_supplied_db_details()

    def _load_type(self) -> None:
        if "auth_type" not in self.cfg:
            raise ValueError("Missing auth_type in configuration file.")

        match self.cfg["auth_type"]:
            case PyFlickerDBConnectionTypeMySQL.PASSWORD:
                self.db_connection_type = PyFlickerDBConnectionTypeMySQL.PASSWORD
            case PyFlickerDBConnectionTypeMySQL.IAM:
                self.db_connection_type = PyFlickerDBConnectionTypeMySQL.IAM
            case PyFlickerDBConnectionTypeMySQL.GLUE_CONN:
                self.db_connection_type = PyFlickerDBConnectionTypeMySQL.GLUE_CONN
            case _:
                raise ValueError(f"""Invalid auth_type: {self.cfg["auth_type"]}. \
Supported types: {list(PyFlickerDBConnectionTypeMySQL)}""")

    def _produce_user_supplied_db_details(self) -> None:
        if self.db_connection_type == PyFlickerDBConnectionTypeMySQL.PASSWORD:
            self.user_supplied_db_details = PyFlickerUserSuppliedDBDetailsMySQLPassword(
                hostname=self.cfg["auth_details"]["db_hostname"],
                username=self.cfg["auth_details"]["db_username"],
                password=self.cfg["auth_details"]["db_password"],
                schema=self.cfg["auth_details"]["db_schema"],
                port=self.cfg["auth_details"]["db_port"],
                ssl=self.cfg.get("auth_details", {}).get("db_ssl", None)
            )
        elif self.db_connection_type == PyFlickerDBConnectionTypeMySQL.IAM:
            self.user_supplied_db_details = PyFlickerUserSuppliedDBDetailsMySQLIAM(
                hostname=self.cfg["auth_details"]["db_hostname"],
                username=self.cfg["auth_details"]["db_username"],
                schema=self.cfg["auth_details"]["db_schema"],
                port=self.cfg["auth_details"]["db_port"],
                ssl=self.cfg.get("auth_details", {}).get("db_ssl", None)
            )
        elif self.db_connection_type == PyFlickerDBConnectionTypeMySQL.GLUE_CONN:
            self.user_supplied_db_details = PyFlickerUserSuppliedDBDetailsMySQLGlueConn(
                glue_connector_name=self.cfg["auth_details"]["glue_connector_name"],
                ssl=self.cfg.get("auth_details", {}).get("db_ssl", None)
            )
        else:
            raise ValueError(f"Invalid auth_type: {self.db_connection_type}. \
Supported types: {list(PyFlickerDBConnectionTypeMySQL)}")


class PyFlickerRunMySQL(PyFlickerRunBase):
    """
    | 'Tonight, a tale of true terror.'
    | 
    | Runs multithreaded upserts into a MySQL database.
    """

    base_query: ClassVar[str] = "INSERT INTO {table_name} ({final_cols_string}) VALUES {values_strings} ON DUPLICATE KEY UPDATE {update_keys};"

    def __init__(
        self, table_name: str, columns_list: list[str], values_list: list[str], maximum_threads: int, maximum_rows_per_thread: int
    ) -> None:
        super().__init__(table_name, columns_list, values_list, maximum_threads, maximum_rows_per_thread)

        self.user_supplied_db_details: Union[
            PyFlickerUserSuppliedDBDetailsMySQLPassword,
            PyFlickerUserSuppliedDBDetailsMySQLIAM,
            PyFlickerUserSuppliedDBDetailsMySQLGlueConn,
            None
        ] = None
        self.db_connection_type: Union[PyFlickerDBConnectionTypeMySQL, None] = None
        self.conn_details: dict[str, Any] = {}

    def set_user_supplied_db_details(
        self, type: PyFlickerDBConnectionTypeMySQL, user_supplied_db_details: Union[
            PyFlickerUserSuppliedDBDetailsMySQLPassword,
            PyFlickerUserSuppliedDBDetailsMySQLIAM,
            PyFlickerUserSuppliedDBDetailsMySQLGlueConn
        ]
    ) -> None:
        self.db_connection_type = type
        if type == PyFlickerDBConnectionTypeMySQL.PASSWORD and \
                isinstance(user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLPassword):
            self.user_supplied_db_details = user_supplied_db_details
        elif type == PyFlickerDBConnectionTypeMySQL.IAM and \
                isinstance(user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLIAM):
            self.user_supplied_db_details = user_supplied_db_details
        elif type == PyFlickerDBConnectionTypeMySQL.GLUE_CONN and \
                isinstance(user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLGlueConn):
            self.user_supplied_db_details = user_supplied_db_details
        else:
            raise ValueError("Invalid user supplied db details for the specified connection type.")

    def start_multithreaded_upsert(self) -> dict[str, Any]:
        """
        | 'On with the show!'
        | 
        | Start actual multithreaded upsert into the database.
        | This method should be called after set_user_supplied_db_details() has been called, or RuntimeError will be raised.
        | As this class calls the multithreader, logs will be produced for each thread. 
        | If the logger has been properly configured, these logs will be written to the console and/or a log file.
        |
        | Note that the 'rows_affected' key value may not be fully representative of data change in the database.
        | Particularly:
        - If a row is updated with the same values as already exist in the database, it will not be counted as a row affected.
        - If a row is updated with different values, it will be counted as 2 rows affected.
        - If a row is inserted, it will be counted as 1 row affected.

        :return: dict with keys "transaction_successful" (bool) and "rows_affected" (int)
        """

        logger.info(f"Starting multithreaded upsert into table {self.table_name} with {len(self.values_list)} rows.")
        logger.info(f"Maximum threads: {self.maximum_threads}, Maximum rows per thread: {self.maximum_rows_per_thread}.")

        self._instantiate_conn_details()
        conn = PyFlickerConnectionMySQL.get_conn_object(self.conn_details)
        db_column_names = self._get_column_names(conn)
        db_primary_keys = self._get_primary_keys(conn)
        conn.close()
        logger.info(f"Retrieved column names and primary keys.")

        if not self._verify_columns_match(db_column_names, self.columns_list):
            err_msg = f"Column names in the database ({db_column_names}) do not match column names in the file ({self.columns_list})."
            logger.error(err_msg)
            raise ValueError(err_msg)

        formatted_query = self.base_query.format(
            table_name=self.table_name,
            final_cols_string=",".join(self.columns_list),  # use the file column ordering
            values_strings="{values_strings}",
            update_keys=",".join(
                [f"{col}=VALUES({col})" for col in db_column_names if col not in db_primary_keys]
            )
        )
        plan_numbers = pyflicker_distribute.get_even_plan(len(self.values_list), self.maximum_threads, self.maximum_rows_per_thread)
        logger.info(f"Query plan: {plan_numbers}")
        queries = pyflicker_distribute.form_query_list_from_plan(plan_numbers, formatted_query, self.values_list)

        multi_threader = PyFlickerMultithreaderMySQL(
            maximum_threads=self.maximum_threads,
            conn_details=self.conn_details,
            db_connection_type=self.db_connection_type,
            queries=queries
        )
        return multi_threader.run()

    def _instantiate_conn_details(self) -> None:
        if self.db_connection_type == PyFlickerDBConnectionTypeMySQL.PASSWORD and \
                isinstance(self.user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLPassword):
            self.conn_details = PyFlickerConnectionMySQL.get_conn_details_password(
                hostname=self.user_supplied_db_details.hostname,
                username=self.user_supplied_db_details.username,
                password=self.user_supplied_db_details.password,
                schema=self.user_supplied_db_details.schema,
                port=self.user_supplied_db_details.port,
                ssl=self.user_supplied_db_details.ssl
            )
        elif self.db_connection_type == PyFlickerDBConnectionTypeMySQL.IAM and \
                isinstance(self.user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLIAM):
            self.conn_details = PyFlickerConnectionMySQL.get_conn_details_iam(
                hostname=self.user_supplied_db_details.hostname,
                username=self.user_supplied_db_details.username,
                schema=self.user_supplied_db_details.schema,
                port=self.user_supplied_db_details.port,
                ssl=self.user_supplied_db_details.ssl
            )
        elif self.db_connection_type == PyFlickerDBConnectionTypeMySQL.GLUE_CONN and \
                isinstance(self.user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLGlueConn):
            self.conn_details = PyFlickerConnectionMySQL.get_conn_details_glue_conn(
                glue_connector_name=self.user_supplied_db_details.glue_connector_name,
                ssl=self.user_supplied_db_details.ssl
            )
        else:
            raise RuntimeError("Invalid user supplied db details for the specified connection type.")

    def _get_column_names(self, conn: pymysql.connections.Connection) -> list[str]:
        query = f"""SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE \
TABLE_SCHEMA='{self.conn_details["schema"]}' AND TABLE_NAME='{self.table_name}'"""

        content = []
        cursor: Union[pymysql.cursors.Cursor, None] = None
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            content = cursor.fetchall()
            cursor.close()

        except pymysql.Error as e:
            if "cursor" in locals() and cursor:
                cursor.close()
            if "conn" in locals() and conn:
                conn.close()

            raise RuntimeError("Caught MySQL Error %d: %s" % (e.args[0], e.args[1]))

        except Exception as e:
            if "cursor" in locals() and cursor:
                cursor.close()
            if "conn" in locals() and conn:
                conn.close()

            raise RuntimeError(f"Caught {e.__class__.__name__} Exception: {e}")

        return [row[0] for row in content]

    def _get_primary_keys(self, conn: pymysql.connections.Connection) -> list[str]:
        query = f"""SHOW KEYS FROM {self.table_name} WHERE Key_name = 'PRIMARY'"""

        content = []
        cursor: Union[pymysql.cursors.Cursor, None] = None
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            content = cursor.fetchall()
            cursor.close()

        except pymysql.Error as e:
            if "cursor" in locals() and cursor:
                cursor.close()
            if "conn" in locals() and conn:
                conn.close()
            raise RuntimeError("Caught MySQL Error %d: %s" % (e.args[0], e.args[1]))

        except Exception as e:
            if "cursor" in locals() and cursor:
                cursor.close()
            if "conn" in locals() and conn:
                conn.close()
            raise RuntimeError(f"Caught {e.__class__.__name__} Exception: {e}")

        return [row[4] for row in content if row[2] == "PRIMARY"]


class PyFlickerConnectionMySQL(PyFlickerConnectionBase):
    @staticmethod
    def get_conn_details_password(
        hostname: str, username: str, password: str, schema: str, port: int, ssl: Union[str, None] = None
    ) -> dict:
        """
        | Generates MySQL database schema value and secure login details with ssl and password.
        | SSL certificate file location defaults to the working directory, but can be overridden by specifying ssl.
        |
        | 'ssl' key is only included in the return dictionary if ssl is specified.

        :param string hostname: URL where db is hosted.
        :param string username: Username to login with.
        :param string password: Password to login with.
        :param string schema: MySQL db schema name.
        :param int port: Port number to connect to.
        :param string ssl: Path to SSL certificate file, or None.

        :returns: dictionary - {
            'hostname': string,
            'username': string,
            'password': string,
            'ssl': dictionary - {
                'ca': string
            },
            'port': int,
            'schema': string
        }
        """

        return_dict = {
            "hostname": hostname,
            "username": username,
            "password": password,
            "port": int(port),
            "schema": schema
        }
        if ssl is not None:
            return_dict["ssl"] = {"ca": ssl}

        return return_dict

    @staticmethod
    def get_conn_details_iam(hostname: str, username: str, schema: str, port: int, ssl: Union[str, None] = None) -> dict:
        """
        | Generates MySQL database schema value and secure login details with ssl and AWS authentication token.
        | SSL certificate file location defaults to the working directory, but can be overridden by specifying ssl.
        |
        | 'ssl' key is only included in the return dictionary if ssl is specified.
        |
        | Requires boto3 to be installed. Will raise ImportError if not installed.

        :param string hostname: URL where db is hosted.
        :param string username: Username to login with.
        :param string schema: MySQL db schema name.
        :param int port: Port number to connect to.
        :param string ssl: Path to SSL certificate file, or None.

        :returns: dictionary - {
            'hostname': string,
            'username': string,
            'password': string,
            'ssl': dictionary - {
                'ca': string
            },
            'port': int,
            'schema': string
        }
        """

        import boto3

        rds_client = boto3.client("rds")
        auth_token = rds_client.generate_db_auth_token(
            DBHostname=hostname,
            Port=port,
            DBUsername=username
        )

        return_dict = {
            "hostname": hostname,
            "username": username,
            "password": auth_token,
            "port": int(port),
            "schema": schema
        }
        if ssl is not None:
            return_dict["ssl"] = {"ca": ssl}

        return return_dict

    @staticmethod
    def get_conn_details_glue_conn(glue_connector_name: str, ssl: Union[str, None] = None) -> dict:
        """
        | Retrieves MySQL database login details from the specified AWS Glue connector.
        | SSL certificate file location defaults to the working directory, but can be overridden by specifying ssl.
        | Schema name is also defined in the Glue Connector itself, but can be overridden by specifying override_schema_name.
        |
        | 'ssl' key is only included in the return dictionary if ssl is specified.
        |
        | Requires boto3 to be installed. Will raise ImportError if not installed.

        :param string glue_connector_name: Name of AWS Glue Connector containing login details.
        :param string ssl: Path to SSL certificate file, or None.

        :returns: dictionary - {
            'hostname': string,
            'username': string,
            'password': string,
            'ssl': dictionary - {
                'ca': string
            },
            'port': int,
            'schema': string
        }
        """

        import boto3

        # retrieve Glue credentials
        glue_client = boto3.client("glue")
        connection = glue_client.get_connection(Name=glue_connector_name)

        # process Glue credentials
        jdbc_connection_url = connection["Connection"]["ConnectionProperties"]["JDBC_CONNECTION_URL"]
        jdbc_connection_url_split = jdbc_connection_url.split("/")

        hostname = jdbc_connection_url_split[2].split(":")[0]
        port = jdbc_connection_url_split[2].split(":")[1]
        schema = jdbc_connection_url_split[3]

        # retrieve userpass from secret manager
        secret_client = boto3.client("secretsmanager")
        secret = secret_client.get_secret_value(SecretId=connection["Connection"]["ConnectionProperties"]["SECRET_ID"])

        creds_json = json.loads(secret["SecretString"])
        username = creds_json["username"]
        password = creds_json["password"]

        return_dict = {
            "hostname": hostname,
            "username": username,
            "password": password,
            "port": int(port),
            "schema": schema
        }
        if ssl is not None:
            return_dict["ssl"] = {"ca": ssl}

        return return_dict

    @staticmethod
    def get_conn_object(conn_details: dict[str, Any]) -> pymysql.connections.Connection:
        if "ssl" in conn_details and Path(conn_details["ssl"]["ca"]).is_file():
            conn = pymysql.connect(
                host=conn_details["hostname"],
                user=conn_details["username"],
                passwd=conn_details["password"],
                database=conn_details["schema"],
                ssl=conn_details["ssl"],
                connect_timeout=DB_CONNECTION_TIMEOUT,
                port=int(conn_details["port"])
            )
        elif "ssl" in conn_details and not Path(conn_details["ssl"]["ca"]).is_file():
            raise RuntimeError("SSL Certificate not found at specified path!")
        else:
            conn = pymysql.connect(
                host=conn_details["hostname"],
                user=conn_details["username"],
                passwd=conn_details["password"],
                database=conn_details["schema"],
                connect_timeout=DB_CONNECTION_TIMEOUT,
                port=int(conn_details["port"])
            )

        return conn


class PyFlickerMultithreaderMySQL(PyFlickerMultithreaderBase):
    def _execute_thread(self, thread_id: int, query: str) -> None:
        query_size_mb = f"{(len(query) / 2**20):.2f}"
        logger.info(
            f"[THREAD/{thread_id}] Starting with payload of size {query_size_mb} MB. Dirty reads enabled, lock wait timeout set to {DB_LOCK_WAIT_TIMEOUT} seconds.")

        thread_local_conn_details = self.conn_details
        # IAM: need to generate token for each thread, since token may be invalidated by the passage of time
        if self.db_connection_type in [PyFlickerDBConnectionTypeMySQL.IAM]:
            try:
                thread_local_conn_details = PyFlickerConnectionMySQL.get_conn_details_iam(
                    hostname=thread_local_conn_details["hostname"],
                    username=thread_local_conn_details["username"],
                    schema=thread_local_conn_details["schema"],
                    port=thread_local_conn_details["port"],
                    ssl=thread_local_conn_details["ssl"]["ca"] if "ssl" in thread_local_conn_details else None,
                )
            except Exception as e:
                self._add_exception(f"Failed to get IAM connection details: {e}")
                logger.error(f"[THREAD/{thread_id}] failed with Error {e}!")
                return

        conn = None
        cursor = None
        try:
            conn = PyFlickerConnectionMySQL.get_conn_object(thread_local_conn_details)
            cursor = conn.cursor()

            # disable row level locks
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
            # significantly increase lock wait timeout, in case of gap locks
            cursor.execute(f"""SET SESSION innodb_lock_wait_timeout = {DB_LOCK_WAIT_TIMEOUT};""")
            conn.commit()

            cursor.execute(query)
            conn.commit()

            logger.info(f"[THREAD/{thread_id}] finished.")
            self._add_rows(cursor.rowcount)

        except pymysql.Error as e:
            self._add_exception("Caught MySQL Error %d: %s" % (e.args[0], e.args[1]))
            logger.error(f"[THREAD/{thread_id}] failed with Error {e.args[0]}!")

        except Exception as e:
            self._add_exception(f"Caught {e.__class__.__name__} Exception: {e}")
            logger.error(f"[THREAD/{thread_id}] failed with Error {e}!")

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            logger.info(f"[THREAD/{thread_id}] shutting down.")
