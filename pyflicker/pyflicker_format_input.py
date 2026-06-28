import csv
from pathlib import Path


def escape_mysql(v: str) -> str:
    """
    | Escape a string for safe insertion into a MySQL database.
    | Outputs of this function are intended for use in SQL upsert statements in the VALUES block.
    | e.g. INSERT INTO table (col1, col2) VALUES ((escape_mysql(row['col1']), (escape_mysql(row['col2'])), (escape_mysql(row['col1']), (escape_mysql(row['col2'])), ...).
    | 
    | Note that this function only escapes strings, you must format the outer SQL statement and brackets yourself.

    :param v: The string to escape.

    :return: string
    """
    if isinstance(v, bool):  # convert boolean to 1 or 0 for mysql (does not have a native boolean type)
        return "1" if v else "0"
    if isinstance(v, (int, float)):  # handle numeric types
        return str(v)
    v = str(v).replace("\\", "\\\\").replace("'", "\\'")  # escape backslashes and single quotes

    return f"'{v}'"


def escape_postgres(v: str) -> str:
    """
    | Escape a string for safe insertion into a Postgres database.
    | Outputs of this function are intended for use in SQL upsert statements in the VALUES block.
    | e.g. INSERT INTO table (col1, col2) VALUES ((escape_postgres(row['col1']), (escape_postgres(row['col2'])), (escape_postgres(row['col1']), (escape_postgres(row['col2'])), ...).
    | 
    | Note that this function only escapes strings, you must format the outer SQL statement and brackets yourself.

    :param v: The string to escape.

    :return: string
    """

    if isinstance(v, bool):  # handle boolean types
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):  # handle numeric types
        return str(v)
    v = str(v).replace("'", "''")  # handle single quotes following postgres conventions

    return f"'{v}'"


def _parse_csv(path: Path, escape_fn) -> tuple[list[str], list[str]]:
    """
    Read a CSV file and return outputs appropriate for use by the PyFlickerRun* classes.

    :param path: Path to the CSV file.
    :param escape_fn: Function to escape values for the target database.

    :return: tuple of (columns_list, values_list)
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Could not read header from CSV file: {path}")

        columns_list = list(reader.fieldnames)
        values_list = [
            "(" + ",".join(escape_fn(row[col]) for col in columns_list) + ")"
            for row in reader
        ]
    return columns_list, values_list


def parse_csv_mysql(path: Path) -> tuple[list[str], list[str]]:
    """
    Read a CSV file and return outputs appropriate for use by the PyFlickerRunMySQL class.

    :param path: Path to the CSV file.

    :return: tuple of (columns_list, values_list)
    """

    return _parse_csv(path, escape_mysql)


def parse_csv_postgres(path: Path) -> tuple[list[str], list[str]]:
    """

    Read a CSV file and return outputs appropriate for use by the PyFlickerRunPostgres class.

    :param path: Path to the CSV file.

    :return: tuple of (columns_list, values_list)
    """

    return _parse_csv(path, escape_postgres)
