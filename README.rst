pyflicker 🧨
============
| It's like pyspark, but not at all!
|
| Supports multithreaded **upserts** to different databases.
| Provides methods to easily parse CSV data.
1. MySQL (requires pymysql)
2. PostgreSQL* [coming soon-ish!] (requires psycopg3)

Certified 0% data transformation support!

Usage Instructions
------------------
See example.py for an example of the library in action.

1. Make a copy of cfg.json.example named cfg.json.
2. Pick a connection method to use, then edit the copy and fill in all fields.
3. In your program, call pyflicker.setup_logger() if you want better logging.
4. Pass column_names and values_list to pyflicker.PyFlickerRun<db>(). This library has native support for CSV through parse_csv_<db>().
5. Pass configuration file data prepared by pyflicker.PyFlickerLoadConfig<db>() to the set_user_supplied_db_details() method on the created object to load configuration information in.
6. Run the start_multithreaded_upsert() method on the created object to light the fuse!

End-user Functions/Classes
--------------------------
- setup_logger()

  - Set up custom logging.

- parse_csv_mysql() / parse_csv_postgres()

  - Read a CSV file and return outputs appropriate for use by the PyFlickerRun* classes.

- escape_mysql() / escape_postgres()

  - Escape a string for safe insertion into a database.
  - Outputs of this function are intended for use in SQL upsert statements in the VALUES block.
  - For when you want to handle data not from a CSV, these functions can be used to apply the same string formatting logic to any string.

- PyFlickerLoadConfigMySQL / PyFlickerLoadConfigPostgres [coming soon-ish!]

  - Processes configuration file to get input parameters for database connection.
  - Produces output suitable for use by...

- PyFlickerRunMySQL / PyFlickerRunPostgres [coming soon-ish!]

  - This class!
  - Runs multithreaded upserts into a database.

StrEnums
--------
- PyFlickerSupportedDBTypes: What databases this library supports.
- PyFlickerDBConnectionTypeMySQL: Supported connection types for MySQL.
- PyFlickerDBConnectionTypePostgres: Coming soon-ish!

Notes
-----
- This script runs upserts. Any primary keys already present in the table will be overwritten.
- Only use data you can trust. This library does not use query parameterisation for values to speed up the process.
- Duplicate data in datafiles is considered undefined behaviour.
