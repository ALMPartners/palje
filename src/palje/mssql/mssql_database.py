# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0

"""Module for querying data from MSSQL database."""
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

# TODO: exception handling (wrap into custom exceptions)
# TODO: use logging instead of print


class MSSQLDatabase:
    """Class for connecting and querying data from an MSSQL database."""

    def __init__(
        self,
        server,
        database,
        driver,
        authentication,
        port: int = 1433,
        username: str | None = None,
        password: str | None = None,
    ):
        self.server = server
        self.database = database
        self.driver = driver
        self.authentication = authentication
        self.connection = None
        self.queries = self._read_queries_from_ini()
        self.username = username
        self.password = password
        self.port = port

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
        # TODO: likely needs to be fixed for cx_freeze
        current_dir = path.dirname(path.abspath(__file__))
        config_file = path.join(current_dir, QUERY_FILE)
        config = ConfigParser()
        config.read(config_file)
        return config["Queries"]

    def close(self) -> None:
        """Close the database connection."""
        try:
            self.connection.close()
        except:
            print(
                "Failed to close the database connection. Most likely because the connection is already closed."
            )

    def connect(self) -> None:
        """Connect to the database."""
        try:
            if self.authentication.lower() == "azureidentity":
                self.connection = pyodbc.connect(
                    self.connection_string,
                    attrs_before={SQL_COPT_SS_ACCESS_TOKEN: self.get_az_token()},
                )
            else:
                self.connection = pyodbc.connect(self.connection_string)
        except:
            print(
                f"Failed to connect to {self.server}.{self.database}. Check your server details, username and password."
            )
            raise

    def change_current_db(self, db_name: str) -> None:
        """Change the current database."""

        # FIXME: This does NOT work with AzureSQL databases
        #        (a direct connection is needed to change the database)
        if self.connection is None:
            self.connect()
        cursor = self.connection.cursor()
        try:
            # TODO: sanitize db_name?
            # Apparently default sanitization (?, db_name) is not supported for
            # this kind of query.
            cursor.execute(f"USE {db_name}")
            self.database = db_name
        except pyodbc.Error as ex:
            print(f"Failed to change database to {db_name}")
            raise ex

    @property
    def connection_string(self) -> str:
        """Construct and returne the connection string for current auth method."""
        # FIXME: mind the driver, e.g. "ODBC Driver 18 for SQL Server" requires
        #        diffrent settings for secure local connections
        conn_str = f"DRIVER={{{self.driver}}};SERVER={self.server}"
        if self.port:
            conn_str = f"{conn_str},{self.port}"
        if self.database:
            conn_str = f"{conn_str};DATABASE={self.database}"
        if self.authentication == "SQL":
            conn_str = f"{conn_str};UID={self.username};PWD={self.password}"
        elif self.authentication == "Windows":
            conn_str = f"{conn_str};Trusted_Connection=yes;"
        elif self.authentication == "AAD":
            conn_str = f"{conn_str};Authentication=ActiveDirectoryInteractive;"

        return conn_str

    def get_az_token(self) -> bytes:
        """Return Azure AD access token for the connection."""
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
        cursor = self.connection.cursor()
        try:
            cursor.execute(self.queries["database_names"])
            return [base.database_name for base in cursor.fetchall()]
        finally:
            cursor.close()

    def get_schemas(self) -> list[str]:
        """Return list of object and routine schemas."""
        cursor = self.connection.cursor()
        try:
            # database table and view schemas
            cursor.execute(self.queries["table_schemas"])
            table_schemas = [schema.schema_table for schema in cursor.fetchall()]
            # database procedure and function schemas
            cursor.execute(self.queries["routine_schemas"])
            routine_schemas = [schema.schema_routine for schema in cursor.fetchall()]
            return table_schemas + routine_schemas
        finally:
            cursor.close()

    def get_objects(self, schema) -> list[dict[str, str]]:
        """Return list of dicts of database objects and their types.

        Arguments:
        ----------

        schema : str
            Schema name to query objects from.
        """
        cursor = self.connection.cursor()
        try:
            # table and view names
            cursor.execute(self.queries["table_names"], (schema,))
            tables = [
                {"type": table.TABLE_TYPE, "name": table.TABLE_NAME}
                for table in cursor.fetchall()
                if table.TABLE_TYPE in DATABASE_OBJECT_TYPES
            ]
            # procedure and function names
            cursor.execute(self.queries["routine_names"], (schema,))
            routines = [
                {"type": routine.ROUTINE_TYPE, "name": routine.ROUTINE_NAME}
                for routine in cursor.fetchall()
                if routine.ROUTINE_TYPE in DATABASE_OBJECT_TYPES
            ]
            return tables + routines
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
        cursor = self.connection.cursor()
        try:
            cursor.execute(self.queries["schema_descriptions"], (schema,))
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
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                self.queries["object_descriptions"], (f"{schema}.{object_name}",)
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
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                self.queries["available_extended_properties"],
                (f"{self.database}.{schema}.{object_name}",),
            )
            extended_property_names = [row[0] for row in cursor.fetchall()]
            return extended_property_names
        finally:
            cursor.close()

    def get_object_columns(
        self, schema, object_type, object_name
    ) -> list[dict[str, str]]:
        """Return list of dicts of database columns and their properties.

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
        # Complete the query to fetch all available extended properties
        # with object metadata
        # Additions are made to SELECT and FROM clauses
        extended_properties = self.get_available_extended_properties(
            schema, object_name
        )
        select_addition = ""
        from_addition = ""
        for extended_property in extended_properties:
            select_addition = (
                select_addition
                + " "
                + self.queries["select_template"].format(extended_property)
            )
            from_addition = (
                from_addition
                + " "
                + self.queries["from_template"].format(extended_property)
            )
        if object_type == "Tables":
            query = self.queries["table_columns"].format(select_addition, from_addition)
        elif object_type == "Views":
            query = self.queries["view_columns"].format(select_addition, from_addition)
        # Finally execute the query to retrieve metadata and extended properties
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (self.database, schema, object_name))
            result = []
            for row in cursor.fetchall():
                keys = [col[0] for col in row.cursor_description]
                values = [str(cell) for cell in row]
                result.append(dict(zip(keys, values)))
            return result
        finally:
            cursor.close()

    def get_object_indexes(self, schema, object_name) -> list[dict[str, str]]:
        """Return list of dicts of object indexes."""
        cursor = self.connection.cursor()
        try:
            cursor.execute(self.queries["object_indexes"], (schema, object_name))
            indexes = []
            for row in cursor.fetchall():
                keys = [col[0] for col in row.cursor_description]
                values = [str(cell) for cell in row]
                indexes.append(dict(zip(keys, values)))
            for index in indexes:
                index["Index Columns"] = []
                cursor.execute(
                    self.queries["index_columns"],
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
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                self.queries["routine_parameters"], (f"{schema}.{object_name}",)
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
        cursor = self.connection.cursor()
        try:
            headers = ["Database", "Schema", "Object"]
            result = []
            if not isinstance(dep_databases, list):  # make sure its list
                dep_databases = [dep_databases]
            for database in dep_databases:
                cursor.execute(self.queries["object_dependencies"].format(database))
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
