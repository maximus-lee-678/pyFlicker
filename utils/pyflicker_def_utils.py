from enum import Enum


class CONN_TYPE(Enum):
    AWS_IAM = 0
    PASSWORD = 1


CONN_DETAILS_ARGS = ["hostname", "username", "schema", "ssl", "port", "db_lock_wait_timeout"]
CONN_DETAILS_PASSWORD_ARGS = CONN_DETAILS_ARGS + ["password"]
CONN_DETAILS_IAM_ARGS = CONN_DETAILS_ARGS + ["token"]
