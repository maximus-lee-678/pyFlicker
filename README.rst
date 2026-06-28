pyflicker 🧨
============
| It's like pyspark, but not in the slightest!
|
| Supports multithreaded upserts to a MySQL database from textual data files.
| Writes load progress to logs located at the 'logs' directory.
| Absolutely ZERO types of transformation support.
|
| Requires pymysql library.

Data File Preparation
---------------------
Data files' contents should follow a specific format.

Header
~~~~~~
- Outer brackets are required.

.. code-block:: text

  (col_1,col_2,col_3,col_4,...)

Rows
~~~~
- Outer brackets are required.
- Values should be enclosed by single quotes.
- Booleans should NOT be enclosed by any quotes.
- *This is why this job doesn't just accept a plain CSV...*

.. code-block:: text

  ('value_1','value_2',boolean_1,boolean_2,...)

Usage Instructions
------------------
1. Name your datafiles after the convention <table_name>.txt.
2. Place them in the 'to_load' directory.
3. If you haven't already, make a copy of cfg.json.example > cfg.json.
4. Edit the copy and fill in all fields.
5. Run main.py.
6. Enjoy the fireworks.
7. Any errors during the process will be logged with levelname **ERROR**.

cfg.json
--------
- **db_hostname**

  - Type: string
  - MySQL database endpoint.

- **db_username**

  - Type: string
  - MySQL username.

- **db_password**

  - Type: string
  - MySQL password.

- **db_schema_name**

  - Type: string
  - MySQL schema.

- **db_port**

  - Type: int
  - MySQL port.
  - Default: 3306

- **db_ssl**

  - Type: string OR null
  - SSL certificate path.
  - Can be specified as null directory if not using SSL.
  - Default: null

- **db_lock_wait_timeout**

  - Type: int
  - Timeout for connecting to the database in seconds.
  - Default 10.

- **load_concurrency**

  - Type: int
  - Maximum number of active connections to MySQL database.
  - Default 15.

- **load_batch_size**

  - Type: int
  - Maximum rows upserted per connection.
  - Default 20000.

Notes
-----
- This script runs upserts. Any primary keys already present in the table will be overwritten.
- Duplicate data in datafiles is considered undefined behaviour.

  - The script may overwrite some data.
  - The database might deadlock.
