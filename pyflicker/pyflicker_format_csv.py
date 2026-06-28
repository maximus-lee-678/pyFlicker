import csv
from pathlib import Path


def escape_mysql(v: str) -> str:
    if isinstance(v, bool):  # convert boolean to 1 or 0 for mysql (does not have a native boolean type)
        return "1" if v else "0"
    if isinstance(v, (int, float)):  # handle numeric types
        return str(v)
    v = str(v).replace("\\", "\\\\").replace("'", "\\'")  # escape backslashes and single quotes

    return f"'{v}'"


def escape_postgres(v: str) -> str:
    if isinstance(v, bool):  # handle boolean types
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):  # handle numeric types
        return str(v)
    v = str(v).replace("'", "''")  # handle single quotes following postgres conventions

    return f"'{v}'"


def _parse_csv(path: Path, escape_fn) -> tuple[list[str], list[str]]:
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
    return _parse_csv(path, escape_mysql)


def parse_csv_postgres(path: Path) -> tuple[list[str], list[str]]:
    return _parse_csv(path, escape_postgres)
