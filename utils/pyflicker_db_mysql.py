from utils.pyflicker_db_base import PyFlickerConnectionBase, PyFlickerMultithreaderBase, PyFlickerRunBase, PyFlickerDBUserSuppliedDetailsBase
import utils.pyflicker_distribute as pyflicker_distribute
import boto3
import logging
from pathlib import Path
from enum import StrEnum
from typing import Any, Union
import json
import pymysql


logger = logging.getLogger("pyflicker.mysql")


class PyFlickerDBConnectionType(StrEnum):
    PASSWORD = "PASSWORD"
    IAM = "IAM"
    GLUE_CONN = "GLUE_CONN"


class PyFlickerUserSuppliedDBDetailsMySQLPassword(PyFlickerDBUserSuppliedDetailsBase):
    hostname: str
    username: str
    password: str
    schema: str
    port: int
    ssl: Union[str, None]

    def __init__(self, hostname: str, username: str, password: str, schema: str, port: int, ssl: Union[str, None] = None):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.schema = schema
        self.port = port
        self.ssl = ssl


class PyFlickerUserSuppliedDBDetailsMySQLIAM(PyFlickerDBUserSuppliedDetailsBase):
    hostname: str
    username: str
    schema: str
    port: int
    ssl: Union[str, None]

    def __init__(self, hostname: str, username: str, schema: str, port: int, ssl: Union[str, None] = None):
        self.hostname = hostname
        self.username = username
        self.schema = schema
        self.port = port
        self.ssl = ssl


class PyFlickerUserSuppliedDBDetailsMySQLGlueConn(PyFlickerDBUserSuppliedDetailsBase):
    glue_connector_name: str
    ssl: Union[str, None]

    def __init__(self, glue_connector_name: str, ssl: Union[str, None] = None):
        self.glue_connector_name = glue_connector_name
        self.ssl = ssl


class PyFlickerLoadConfigMySQL:
    cfg: dict[str, Any]
    db_connection_type: PyFlickerDBConnectionType
    user_supplied_db_details: Union[
        PyFlickerUserSuppliedDBDetailsMySQLPassword,
        PyFlickerUserSuppliedDBDetailsMySQLIAM,
        PyFlickerUserSuppliedDBDetailsMySQLGlueConn
    ]

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self._load_type()
        self._produce_user_supplied_db_details()

    def get_user_supplied_db_details(self) -> Union[
        PyFlickerUserSuppliedDBDetailsMySQLPassword,
        PyFlickerUserSuppliedDBDetailsMySQLIAM,
        PyFlickerUserSuppliedDBDetailsMySQLGlueConn
    ]:
        return self.user_supplied_db_details

    def _load_type(self) -> None:
        if "auth_type" not in self.cfg:
            raise ValueError("Missing auth_type in configuration file.")

        match self.cfg["auth_type"]:
            case PyFlickerDBConnectionType.PASSWORD:
                self.db_connection_type = PyFlickerDBConnectionType.PASSWORD
            case PyFlickerDBConnectionType.IAM:
                self.db_connection_type = PyFlickerDBConnectionType.IAM
            case PyFlickerDBConnectionType.GLUE_CONN:
                self.db_connection_type = PyFlickerDBConnectionType.GLUE_CONN
            case _:
                raise ValueError(f"""Invalid auth_type: {self.cfg["auth_type"]}. \
Supported types: {list(PyFlickerDBConnectionType)}""")

    def _produce_user_supplied_db_details(self) -> None:
        if self.db_connection_type == PyFlickerDBConnectionType.PASSWORD:
            self.user_supplied_db_details = PyFlickerUserSuppliedDBDetailsMySQLPassword(
                hostname=self.cfg["auth_details"]["db_hostname"],
                username=self.cfg["auth_details"]["db_username"],
                password=self.cfg["auth_details"]["db_password"],
                schema=self.cfg["auth_details"]["db_schema"],
                port=self.cfg["auth_details"]["db_port"],
                ssl=self.cfg.get("auth_details", {}).get("db_ssl", None)
            )
        elif self.db_connection_type == PyFlickerDBConnectionType.IAM:
            self.user_supplied_db_details = PyFlickerUserSuppliedDBDetailsMySQLIAM(
                hostname=self.cfg["auth_details"]["db_hostname"],
                username=self.cfg["auth_details"]["db_username"],
                schema=self.cfg["auth_details"]["db_schema"],
                port=self.cfg["auth_details"]["db_port"],
                ssl=self.cfg.get("auth_details", {}).get("db_ssl", None)
            )
        elif self.db_connection_type == PyFlickerDBConnectionType.GLUE_CONN:
            self.user_supplied_db_details = PyFlickerUserSuppliedDBDetailsMySQLGlueConn(
                glue_connector_name=self.cfg["auth_details"]["glue_connector_name"],
                ssl=self.cfg.get("auth_details", {}).get("db_ssl", None)
            )
        else:
            raise ValueError(f"Invalid auth_type: {self.db_connection_type}. \
Supported types: {list(PyFlickerDBConnectionType)}")


class PyFlickerRunMySQL(PyFlickerRunBase):
    BASE_QUERY = "INSERT INTO {table_name} ({final_cols_string}) VALUES {values_strings} AS alias ON DUPLICATE KEY UPDATE {update_keys};"

    user_supplied_db_details: Union[
        PyFlickerUserSuppliedDBDetailsMySQLPassword,
        PyFlickerUserSuppliedDBDetailsMySQLIAM,
        PyFlickerUserSuppliedDBDetailsMySQLGlueConn,
        None
    ]
    db_connection_type: Union[PyFlickerDBConnectionType, None]
    conn_details: dict[str, Any]

    def __init__(
        self, table_name: str, columns_list: list[str], values_list: list[str], maximum_threads: int, maximum_rows_per_thread: int
    ):
        super().__init__(table_name, columns_list, values_list, maximum_threads, maximum_rows_per_thread)

        self.user_supplied_db_details = None
        self.db_connection_type = None

    def set_user_supplied_db_details(
        self, type: PyFlickerDBConnectionType, user_supplied_db_details: Union[
            PyFlickerUserSuppliedDBDetailsMySQLPassword,
            PyFlickerUserSuppliedDBDetailsMySQLIAM,
            PyFlickerUserSuppliedDBDetailsMySQLGlueConn
        ]
    ) -> None:
        self.db_connection_type = type
        if type == PyFlickerDBConnectionType.PASSWORD and \
                isinstance(user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLPassword):
            self.user_supplied_db_details = user_supplied_db_details
        elif type == PyFlickerDBConnectionType.IAM and \
                isinstance(user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLIAM):
            self.user_supplied_db_details = user_supplied_db_details
        elif type == PyFlickerDBConnectionType.GLUE_CONN and \
                isinstance(user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLGlueConn):
            self.user_supplied_db_details = user_supplied_db_details
        else:
            raise ValueError("Invalid user supplied db details for the specified connection type.")

    def start_multithreaded_insert(self) -> dict[str, Any]:
        self._instantiate_conn_details()
        conn = PyFlickerConnectionMySQL.get_conn_object(self.conn_details)
        db_column_names = self._get_column_names(conn)
        db_primary_keys = self._get_primary_keys(conn)
        conn.close()

        if not self._verify_columns_match(db_column_names, self.columns_list):
            raise ValueError(
                f"Column names in the database ({db_column_names}) do not match column names in the file ({self.columns_list})."
            )

        formatted_query = self.BASE_QUERY.format(
            table_name=self.table_name,
            final_cols_string=",".join(self.columns_list),  # use the file column ordering
            values_strings="{values_strings}",
            update_keys=",".join(
                [f"{col}=alias.{col}" for col in db_column_names if col not in db_primary_keys]
            )
        )
        plan_numbers = pyflicker_distribute.get_even_plan(len(self.values_list), self.maximum_threads, self.maximum_rows_per_thread)
        queries = pyflicker_distribute.form_query_list_from_plan(plan_numbers, formatted_query, self.values_list)

        multi_threader = PyFlickerMultithreaderMySQL(
            logger=logger,
            maximum_threads=self.maximum_threads,
            conn_details=self.conn_details,
            conn_type=self.db_connection_type,
            queries=queries,
            task=None
        )
        return multi_threader.run()


    def _instantiate_conn_details(self) -> None:
        if self.db_connection_type == PyFlickerDBConnectionType.PASSWORD and \
                isinstance(self.user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLPassword):
            self.conn_details = PyFlickerConnectionMySQL.get_conn_details_password(
                hostname=self.user_supplied_db_details.hostname,
                username=self.user_supplied_db_details.username,
                password=self.user_supplied_db_details.password,
                schema=self.user_supplied_db_details.schema,
                port=self.user_supplied_db_details.port,
                ssl=self.user_supplied_db_details.ssl
            )
        elif self.db_connection_type == PyFlickerDBConnectionType.IAM and \
                isinstance(self.user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLIAM):
            self.conn_details = PyFlickerConnectionMySQL.get_conn_details_iam(
                hostname=self.user_supplied_db_details.hostname,
                username=self.user_supplied_db_details.username,
                schema=self.user_supplied_db_details.schema,
                port=self.user_supplied_db_details.port,
                ssl=self.user_supplied_db_details.ssl
            )
        elif self.db_connection_type == PyFlickerDBConnectionType.GLUE_CONN and \
                isinstance(self.user_supplied_db_details, PyFlickerUserSuppliedDBDetailsMySQLGlueConn):
            self.conn_details = PyFlickerConnectionMySQL.get_conn_details_glue_conn(
                glue_connector_name=self.user_supplied_db_details.glue_connector_name,
                ssl=self.user_supplied_db_details.ssl
            )
        else:
            raise ValueError("Invalid user supplied db details for the specified connection type.")

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
    DB_LOCK_WAIT_TIMEOUT = 900  # in seconds

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
        | Generates MySQL database schema value and secure login details with ssl and authentication token.
        | SSL certificate file location defaults to the working directory, but can be overridden by specifying ssl.
        |
        | 'ssl' key is only included in the return dictionary if ssl is specified.

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
        | Retrieves MySQL database login details from the specified glue connector.
        | SSL certificate file location defaults to the working directory, but can be overridden by specifying ssl.
        | Schema name is also defined in the Glue Connector itself, but can be overridden by specifying override_schema_name.
        |
        | 'ssl' key is only included in the return dictionary if ssl is specified.

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
                connect_timeout=PyFlickerConnectionMySQL.DB_LOCK_WAIT_TIMEOUT,
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
                connect_timeout=PyFlickerConnectionMySQL.DB_LOCK_WAIT_TIMEOUT,
                port=int(conn_details["port"])
            )

        return conn


class PyFlickerMultithreaderMySQL(PyFlickerMultithreaderBase):
    def _execute_thread(self, thread_id: int, query: str) -> None:
        query_size_mb = f"{(len(query) / 2**20):.2f}"
        self.logger.info(
            f"[THREAD/{thread_id}] starting with payload of size {query_size_mb} MB. Dirty reads enabled for upsert."
        )

        conn_details = self.conn_details
        # IAM: need to generate token for each thread, since token may be invalidated by the passage of time
        if self.conn_type in [PyFlickerDBConnectionType.IAM]:
            try:
                conn_details = PyFlickerConnectionMySQL.get_conn_details_iam(
                    hostname=conn_details["hostname"],
                    username=conn_details["username"],
                    schema=conn_details["schema"],
                    port=conn_details["port"],
                    ssl=conn_details["ssl"]["ca"] if "ssl" in conn_details else None,
                )
            except Exception as e:
                self._add_exception(f"Failed to get IAM connection details: {e}")
                self.logger.error(f"[THREAD/{thread_id}] failed with Error {e}!")
                return

        conn = None
        cursor = None
        try:
            conn = PyFlickerConnectionMySQL.get_conn_object(conn_details)
            cursor = conn.cursor()

            # disable row level locks
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
            # significantly increase lock wait timeout, in case of gap locks
            cursor.execute(f"""SET SESSION innodb_lock_wait_timeout = {PyFlickerConnectionMySQL.DB_LOCK_WAIT_TIMEOUT};""")
            conn.commit()

            if self.task:
                cursor.execute(query, self.task)
            else:
                cursor.execute(query)
            conn.commit()

            self.logger.info(f"[THREAD/{thread_id}] finished.")
            self._add_rows(cursor.rowcount)

        except pymysql.Error as e:
            self._add_exception("Caught MySQL Error %d: %s" % (e.args[0], e.args[1]))
            self.logger.error(f"[THREAD/{thread_id}] failed with Error {e.args[0]}!")

        except Exception as e:
            self._add_exception(f"Caught {e.__class__.__name__} Exception: {e}")
            self.logger.error(f"[THREAD/{thread_id}] failed with Error {e}!")

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            self.logger.info(f"[THREAD/{thread_id}] shutting down.")
