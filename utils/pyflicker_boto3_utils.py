import json
from typing import Union
import boto3


def get_mysql_conn_details_password(
        glue_connector_name: str, override_schema_name: str = "", ssl: Union[str, None] = None
) -> dict:
    """
    | Retrieves MySQL database login details from the specified glue connector.
    | SSL certificate file location defaults to the working directory, but can be overridden by specifying ssl.
    | Schema name is also defined in the Glue Connector itself, but can be overridden by specifying override_schema_name.
    |
    | 'ssl' key is only included in the return dictionary if ssl is specified.

    :param string glue_connector_name: Name of AWS Glue Connector containing login details.
    :param string override_schema_name: Specify a different schema name to use from the one defined in the Glue connection.
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
    default_schema = jdbc_connection_url_split[3]

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
        "schema": default_schema if not override_schema_name else override_schema_name
    }
    if ssl is not None:
        return_dict["ssl"] = {"ca": ssl}

    return return_dict


def get_mysql_conn_details_iam(hostname: str, username: str, schema: str, port: int, ssl: Union[str, None] = None) -> dict:
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
        'token': string,
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
        "token": auth_token,
        "port": int(port),
        "schema": schema
    }
    if ssl is not None:
        return_dict["ssl"] = {"ca": ssl}

    return return_dict
