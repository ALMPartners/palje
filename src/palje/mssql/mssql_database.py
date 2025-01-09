# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0

"""Module for querying data from MSSQL database."""
from enum import Enum
import struct
import pyodbc
import importlib
from os import path
from configparser import ConfigParser


QUERY_FILE = "database_queries.ini"
DATABASE_OBJECT_TYPES = {
    "BASE TABLE": "Tables",
    "VIEW": "Views",
    "PROCEDURE": "Procedures",
    "FUNCTION": "Functions",
}
SQL_COPT_SS_ACCESS_TOKEN = (
    1256  # This connection option is defined by microsoft in msodbcsql.h
)


class DatabaseConnectionError(Exception):
    """Exception for failures related to database connection."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class MSSQLDatabaseAuthType(Enum):
    SQL = "SQL"
    WINDOWS = "Windows"
    AAD = "AAD"
    AZURE_IDENTITY = "AzureIdentity"


# TODO: exception handling (wrap into custom exceptions)
# TODO: use logging instead of print

DEFAULT_DB_PORT = 1433


class MSSQLDatabase:
    """Class for connecting and querying data from an MSSQL database."""

    _connection: pyodbc.Connection | None
    _queries: dict[str, str]

    _driver: str
    _server_addr: str
    _server_port: int
    _authentication: MSSQLDatabaseAuthType

    _database: str
    _username: str | None
    _password: str | None

    def __init__(
        self,
        server: str,
        database: str,
        driver: str,
        authentication: MSSQLDatabaseAuthType,
        port: int = DEFAULT_DB_PORT,
        username: str | None = None,
        password: str | None = None,
    ):
        """Initialize the MSSQLDatabase object."""

        self._connection = None
        self._queries = self._read_queries_from_ini()

        if server and "," in server:
            server_part, port_part = server.split(",")
            self._server_addr = server_part.strip()
            if port_part and DEFAULT_DB_PORT == port:
                port_int = int(port_part.strip())
                if port_int:
                    self._server_port = port_int
                else:
                    self._server_port = port
            elif port_part and port != DEFAULT_DB_PORT:
                raise ValueError(
                    f"Port is defined both in the server address ({port_part}) "
                    + f"and as a separate parameter ({port}). "
                    + "Only one port value is allowed."
                )
        else:
            self._server_addr = server
            self._server_port = port

        # FIXME: A check against .available_db_drivers() could be made here, but it'd
        #        complicate unit testing in pipeline environments
        self._driver = driver

        if authentication not in MSSQLDatabaseAuthType:
            raise ValueError(
                f"Authentication type {authentication} is not supported. "
                + "Supported authentication types are: "
                + f"{[t.value for t in list(MSSQLDatabaseAuthType)]}"
            )
        else:
            self._authentication = authentication

        self._database = database
        self._username = username
        self._password = password

    @staticmethod
    def available_db_drivers() -> list[str]:
        """Return a list of available SQL Server drivers available to pyodbc."""
        all_drivers = pyodbc.drivers()
        applicable_drivers = list(
            filter(lambda driver_name: "SQL Server" in driver_name, all_drivers)
        )
        applicable_drivers.sort()
        return applicable_drivers

    @staticmethod
    def _read_queries_from_ini() -> dict[str, str]:
        """Read queries from the INI file."""
        # TODO: check path resolving with cx_freeze, tox etc.
        current_dir = path.dirname(path.abspath(__file__))
        config_file = path.join(current_dir, QUERY_FILE)
        config = ConfigParser()
        config.read(config_file)
        return config["Queries"]

    def close(self) -> None:
        """Close the database connection."""
        try:
            self._connection.close()
        except Exception as ex:
            raise DatabaseConnectionError(
                f"Failed to close the database connection. {ex}"
            ) from ex

    def connect(self) -> None:
        """Connect to the database."""
        try:
            if self._authentication == MSSQLDatabaseAuthType.AZURE_IDENTITY:
                self._connection = pyodbc.connect(
                    self.connection_string,
                    attrs_before={SQL_COPT_SS_ACCESS_TOKEN: self.get_az_token()},
                )
            else:
                self._connection = pyodbc.connect(self.connection_string)
        except Exception as ex:
            raise DatabaseConnectionError(
                f"Failed to connect to {self._server_addr}.{self._database}. {ex}"
            ) from ex

    def change_current_db(self, db_name: str) -> None:
        """Change the current database.

        Arguments
        ---------

        db_name : str
            Name of the database to switch to.

        Raises
        ------

        DatabaseConnectionError
            If the database switch fails

        """

        if self._authentication == MSSQLDatabaseAuthType.AAD:
            # AZSQL does not support "USE", needs reconnection instead
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            self._database = db_name
            self.connect()
        else:
            if self._connection is None:
                self.connect()
            cursor = self._connection.cursor()
            try:
                # TODO: sanitize db_name?
                # Apparently default sanitization (?, db_name) is not supported for
                # this kind of query.
                cursor.execute(f"USE {db_name}")
                self._database = db_name
            except pyodbc.Error as ex:
                raise DatabaseConnectionError(f"{ex}") from ex

    @property
    def database(self) -> str:
        """Current database name."""
        return self._database

    @property
    def connection_string(self) -> str:
        """Connection string from current values"""

        driver_lower = self._driver.lower()

        conn_params = {
            "DRIVER": f"{{{self._driver}}}",
            "SERVER": (
                self._server_addr
                if not self._server_port
                else f"{self._server_addr},{self._server_port}"
            ),
        }

        if self._database:
            conn_params["DATABASE"] = self._database

        match self._authentication:
            case MSSQLDatabaseAuthType.SQL:
                conn_params["UID"] = self._username
                conn_params["PWD"] = self._password
            case MSSQLDatabaseAuthType.WINDOWS:
                conn_params["Trusted_Connection"] = "yes"
            case MSSQLDatabaseAuthType.AAD:
                conn_params["Authentication"] = "ActiveDirectoryInteractive"
            case _:
                raise ValueError(
                    "Unsupported authentication type: {self._authentication}"
                )

        if driver_lower == "odbc driver 18 for sql server":
            if self._server_addr.lower() in ["localhost"]:
                conn_params["Encrypt"] = "no"
                conn_params["TrustServerCertificate"] = "yes"

        conn_str = ";".join([f"{key}={value}" for key, value in conn_params.items()])
        return conn_str

    def get_az_token(self) -> bytes:
        """Return Azure AD access token for the connection."""
        # TODO: check if this import works with a cx_freezed app
        identity = importlib.import_module(".identity", "azure")
        credential = identity.DefaultAzureCredential(
            exclude_interactive_browser_credential=False
        )
        token_bytes = credential.get_token(
            "https://database.windows.net/.default"
        ).token.encode("UTF-16-LE")
        token_struct = struct.pack(
            f"<I{len(token_bytes)}s", len(token_bytes), token_bytes
        )
        return token_struct

    def get_databases(self) -> list[str]:
        """Return list of database names."""
        cursor = self._connection.cursor()
        try:
            cursor.execute(self._queries["database_names"])
            return [base.database_name for base in cursor.fetchall()]
        finally:
            cursor.close()

    def get_schemas(self) -> list[str]:
        """Return list of object and routine schemas."""
        cursor = self._connection.cursor()
        try:
            # database table and view schemas
            cursor.execute(self._queries["table_schemas"])
            table_schemas = [schema.schema_table for schema in cursor.fetchall()]
            # database procedure and function schemas
            cursor.execute(self._queries["routine_schemas"])
            routine_schemas = [schema.schema_routine for schema in cursor.fetchall()]
            return sorted(table_schemas + routine_schemas)
        finally:
            cursor.close()

    def get_objects(self, schema) -> list[dict[str, str]]:
        """Return list of dicts of database objects and their types.

        Arguments:
        ----------

        schema : str
            Schema name to query objects from.
        """
        cursor = self._connection.cursor()
        try:
            # table and view names
            cursor.execute(self._queries["table_names"], (schema,))
            tables = [
                {"type": table.TABLE_TYPE, "name": table.TABLE_NAME}
                for table in cursor.fetchall()
                if table.TABLE_TYPE in DATABASE_OBJECT_TYPES
            ]
            # procedure and function names
            cursor.execute(self._queries["routine_names"], (schema,))
            routines = [
                {"type": routine.ROUTINE_TYPE, "name": routine.ROUTINE_NAME}
                for routine in cursor.fetchall()
                if routine.ROUTINE_TYPE in DATABASE_OBJECT_TYPES
            ]
            all_items = routines + tables
            all_items.sort(
                key=lambda x: "TABLE" if x["type"] == "BASE TABLE" else x["type"]
            )
            return all_items
        finally:
            cursor.close()

    def get_schema_description(self, schema) -> str:
        """Get extended property name 'Description' for given schema.

        Arguments:
        ----------

        schema : str
            Schema name to query description from.


        Returns:
        --------
        str   Description of the schema.
        """
        cursor = self._connection.cursor()
        try:
            cursor.execute(self._queries["schema_descriptions"], (schema,))
            row = cursor.fetchone()
            description = row.description if row is not None else ""
            return description
        finally:
            cursor.close()

    def get_object_description(self, schema, object_name) -> str:
        """Get extended property name 'Description' for given object.

        Arguments:
        ----------

        schema : str
            Schema name of the object.

        object_name : str
            Name of the object.


        Returns:
        --------

        str   Description of the object.

        """
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                self._queries["object_descriptions"], (f"{schema}.{object_name}",)
            )
            row = cursor.fetchone()
            description = row.description if row is not None else ""
            return description
        finally:
            cursor.close()

    def get_available_extended_properties(self, schema, object_name) -> list[str]:
        """Get the names of extended properties available for object.

        Arguments:
        ----------

        schema : str
            Schema name of the object.

        object_name : str
            Name of the object.

        Returns:
        --------

        list[str]   List of extended property names.

        """
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                self._queries["available_extended_properties"],
                (f"{self._database}.{schema}.{object_name}",),
            )
            extended_property_names = [row[0] for row in cursor.fetchall()]
            return extended_property_names
        finally:
            cursor.close()

    def _get_view_columns(
        self, schema_name: str, view_name: str
    ) -> list[dict[str, str]]:
        """Return list of dicts of view columns and their properties.

        Arguments:
        ----------

        schema_name : str
            Schema name of the view.

        view_name : str
            Name of the view.

        Returns:

        list[dict[str, str]]   List of dicts of columns and their properties.
        """

        extended_properties = self.get_available_extended_properties(
            schema_name, view_name
        )

        select_addition = ""
        from_addition = ""

        for index, extended_property in enumerate(extended_properties):
            select_addition = (
                select_addition
                + " "
                + self._queries["view_col_ext_prop_value_select_template"].format(
                    index, extended_property
                )
            )
            from_addition = (
                from_addition
                + " "
                + self._queries["view_col_ext_prop_joiner_template"].format(
                    index, extended_property
                )
            )
        query = self._queries["view_col_select_body"].format(
            select_addition, from_addition
        )

        cursor = self._connection.cursor()
        try:
            cursor.execute(query, (schema_name, view_name))
            result = []
            for row in cursor.fetchall():
                keys = [col[0] for col in row.cursor_description]
                values = [str(cell) for cell in row]
                result.append(dict(zip(keys, values)))
            return result
        finally:
            cursor.close()

    def _get_table_columns(
        self, schema_name: str, table_name: str
    ) -> list[dict[str, str]]:
        """Return list of dicts of table columns and their properties.

        Arguments:
        ----------

        schema_name : str
            Schema name of the table.

        table_name : str
            Name of the table.

        Returns:
        --------
        list[dict[str, str]]   List of dicts of columns and their properties.

        """
        extended_properties = self.get_available_extended_properties(
            schema_name, table_name
        )

        select_addition = ""
        from_addition = ""

        for index, extended_property in enumerate(extended_properties):
            select_addition = (
                select_addition
                + " "
                + self._queries["table_col_ext_prop_value_select_template"].format(
                    index, extended_property
                )
            )
            from_addition = (
                from_addition
                + " "
                + self._queries["table_col_ext_prop_joiner_template"].format(
                    index, extended_property
                )
            )
        query = self._queries["table_col_select_body"].format(
            select_addition, from_addition
        )

        cursor = self._connection.cursor()
        try:
            cursor.execute(query, (schema_name, table_name))
            result = []
            for row in cursor.fetchall():
                keys = [col[0] for col in row.cursor_description]
                values = [str(cell) for cell in row]
                result.append(dict(zip(keys, values)))
            return result
        finally:
            cursor.close()

    def get_object_column_info(
        self, schema, object_type, object_name
    ) -> list[dict[str, str]]:
        """Return list of dicts of object's columns and their properties.

        Arguments:
        ----------

        schema : str
            Schema name of the object.

        object_type : str
            Type of the object (Tables, Views).

        object_name : str
            Name of the object.

        Returns:
        --------
        list[dict[str, str]]   List of dicts of columns and their properties.
        """

        # start = time.perf_counter()

        if object_type == "Views":
            columns = self._get_view_columns(schema, object_name)

        else:
            columns = self._get_table_columns(schema, object_name)

        # end = time.perf_counter()
        # elapsed_time = (end - start)
        # print(f"    -- get_object_column_info {elapsed_time:.03f} secs.")

        return columns

    def get_object_indexes(self, schema, object_name) -> list[dict[str, str]]:
        """Return list of dicts of object indexes."""

        cursor = self._connection.cursor()
        try:
            cursor.execute(self._queries["object_indexes"], (schema, object_name))
            indexes = []
            for row in cursor.fetchall():
                keys = [col[0] for col in row.cursor_description]
                values = [str(cell) for cell in row]
                indexes.append(dict(zip(keys, values)))
            for index in indexes:
                index["Index Columns"] = []
                cursor.execute(
                    self._queries["index_columns"],
                    (schema, object_name, index["Index Name"]),
                )
                for row in cursor.fetchall():
                    keys = [col[0] for col in row.cursor_description]
                    values = [str(cell) for cell in row]
                    index["Index Columns"].append(dict(zip(keys, values)))
            return indexes
        finally:
            cursor.close()

    def get_object_parameters(self, schema, object_name) -> list[dict[str, str]]:
        """Return list of dicts of object parameters."""
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                self._queries["routine_parameters"], (f"{schema}.{object_name}",)
            )
            result = []
            for row in cursor.fetchall():
                keys = [col[0] for col in row.cursor_description]
                values = [str(cell) for cell in row]
                result.append(dict(zip(keys, values)))
            return result
        finally:
            cursor.close()

    def get_object_dependencies(
        self, dep_databases: list[str]
    ) -> list[dict[str, dict[str, str]]]:
        """Return list of dicts of all dependencies between objects in given databases."""
        cursor = self._connection.cursor()
        try:
            headers = ["Database", "Schema", "Object"]
            result = []
            if not isinstance(dep_databases, list):  # make sure its list
                dep_databases = [dep_databases]
            for database in dep_databases:
                cursor.execute(self._queries["object_dependencies"].format(database))
                for row in cursor.fetchall():
                    result.append(
                        {
                            "target": dict(zip(headers, row.target.split("."))),
                            "source": dict(zip(headers, row.source.split("."))),
                        }
                    )
            return result
        finally:
            cursor.close()
