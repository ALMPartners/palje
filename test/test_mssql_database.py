import pyodbc
from palje.mssql_database import MSSQLDatabase
import pytest

from test.conftest import TEST_DB_NAME


def test_sql_queries_should_be_read_succesfully(mssql_db):
    queries = mssql_db.queries
    assert queries
    assert 'database_names' in queries
    assert 'table_schemas' in queries
    assert 'routine_schemas' in queries
    assert 'table_names' in queries
    assert 'routine_names' in queries
    assert 'schema_descriptions' in queries
    assert 'object_descriptions' in queries
    assert 'available_extended_properties' in queries
    assert 'select_template' in queries
    assert 'from_template' in queries
    assert 'table_columns' in queries
    assert 'view_columns' in queries
    assert 'routine_parameters' in queries
    assert 'object_indexes' in queries
    assert 'index_columns' in queries
    assert 'object_dependencies' in queries


def test_when_using_sql_auth_ask_credentials_should_return_connection_str_with_uid_and_pw(mssql_db: MSSQLDatabase, mssql_config: dict[str, str | int]):
    expected = f'DRIVER={{{mssql_config["driver"]}}};SERVER={mssql_config["server"]},{mssql_config["port"]};DATABASE={mssql_config["database"]};UID={mssql_config["username"]};PWD={mssql_config["password"]}'
    assert mssql_db.connection_string == expected


def test_when_using_win_auth_ask_credentials_should_return_connection_str_with_trusted_connection() -> None: #mssql_db: MSSQLDatabase, mssql_config: dict[str, str | int]):
    server = "localhost"
    port = 1433
    database = "PALJE_TEST"
    driver = "ODBC Driver 17 for SQL Server"
    authentication = "Windows"
    db_client = MSSQLDatabase(server=server, port=port, database=database, driver=driver, authentication=authentication)
    excpeted = f'DRIVER={{{driver}}};SERVER={server},{port};DATABASE={database};Trusted_Connection=yes;'
    actual = db_client.connection_string
    assert actual == excpeted


@pytest.mark.mssql
class TestWithSQLServer():

    def test_connect_should_fail_with_invalid_credentials(self, mssql_db, monkeypatch):
        monkeypatch.setattr('builtins.input', lambda x: '')
        with pytest.raises(pyodbc.InterfaceError):
            mssql_db.connect()

    def test_connect_should_succeed_with_valid_credentials(self, mssql_db, mssql_credentials, monkeypatch):
        monkeypatch.setattr('builtins.input', lambda x: mssql_credentials[0])
        monkeypatch.setattr('getpass.getpass', lambda x: mssql_credentials[1])
        mssql_db.connect()

    def test_close_should_succeed_with_open_connection(self, connected_db):
        connected_db.close()
        with pytest.raises(pyodbc.ProgrammingError):
            connected_db.connection.cursor()    # cannot open cursor for closed connection

    def test_close_should_fail_with_closed_connection(self, mssql_db, capsys):
        mssql_db.close()
        captured = capsys.readouterr()
        assert 'Failed to close the database connection. Most likely because the connection is already closed.' in captured.out

    def test_get_databases_should_return_list_of_database_names(self, connected_db):
        databases = connected_db.get_databases()
        assert isinstance(databases, list)
        assert TEST_DB_NAME in databases

    def test_get_databases_should_not_return_system_databases(self, connected_db):
        databases = connected_db.get_databases()
        assert 'master' not in databases
        assert 'model' not in databases
        assert 'msdb' not in databases
        assert 'tempdb' not in databases
        assert 'ReportServerTempDB' not in databases

    def test_get_schemas_should_return_list_of_schemas(self, connected_db):
        schemas = connected_db.get_schemas()
        assert isinstance(schemas, list)
        assert set(['store', 'report']) == set(schemas)

    def test_get_objects_should_return_list_of_dicts_of_objects_and_their_types(self, connected_db):
        objects = connected_db.get_objects(schema='store')
        assert objects == [
            {'type': 'BASE TABLE', 'name': 'Clients'},
            {'type': 'BASE TABLE', 'name': 'Products'},
            {'type': 'PROCEDURE', 'name': 'spSELECT'}
        ]

    def test_get_schema_description_should_return_extended_property_description(self, connected_db):
        desc = connected_db.get_schema_description(schema='store')
        assert desc == "Schema to store records."    # katso kuvaus filuista?

    def test_get_schema_description_should_return_empty_string_if_no_extended_property(self, connected_db):
        desc = connected_db.get_schema_description(schema='report')
        assert desc == ""

    def test_get_object_description_should_return_extended_property_description(self, connected_db):
        desc = connected_db.get_object_description(
            schema='store', object_name='Clients')
        assert desc == "Client information."

    def test_get_object_description_should_return_empty_string_if_no_such_object(self, connected_db):
        desc = connected_db.get_object_description(
            schema='store', object_name='no_such_object')
        assert desc == ""

    def test_get_available_extended_properties_should_return_list_of_extended_properties(self, connected_db):
        extended_properties = connected_db.get_available_extended_properties(
            'store', 'Clients')
        assert extended_properties == ['Description', 'Flag']

    def test_get_available_extended_properties_should_return_empty_list_if_no_such_object(self, connected_db):
        extended_properties = connected_db.get_available_extended_properties(
            'store', 'no_such_object')
        assert extended_properties == []

    def test_get_object_columns_should_return_list_of_dicts_of_columns(self, connected_db):
        cols = connected_db.get_object_columns('store', 'Tables', 'Clients')
        assert len(cols) == 8
        assert cols[0] == {'Column': 'id', 'Type': 'int', 'Length': '', 'Precision': '10', 'Scale': '0', 'Nullable': 'NO',
                           'Primary Key': 'x', 'Foreign Key': '', 'Description': 'Client ID or client number.', 'Flag': ''}

    def test_get_object_columns_should_return_empty_list_if_no_such_object(self, connected_db):
        cols = connected_db.get_object_columns(
            'store', 'Tables', 'no_such_object')
        assert cols == []

    def test_get_object_indexes_should_return_list_of_dicts_of_indexes(self, connected_db):
        indexes = connected_db.get_object_indexes('store', 'Clients')
        assert len(indexes) == 1
        assert indexes[0] == {'Index Name': 'Clients_NonClusteredIndex', 'Index Type': 'NONCLUSTERED',
                              'Is Unique': 'Yes', 'Index Columns': [{'column_name': 'name', 'column_sort_order': '(ascending)'},
                                                                    {'column_name': 'date_of_birth', 'column_sort_order': '(ascending)'}]}

    def test_get_object_indexes_should_return_empty_list_if_no_such_object(self, connected_db):
        indexes = connected_db.get_object_indexes('store', 'no_such_object')
        assert indexes == []

    def test_get_object_parameters_should_return_list_of_dicts_of_indexes(self, connected_db):
        params = connected_db.get_object_parameters('store', 'spSELECT')
        assert len(params) == 1
        assert params[0] == {'Parameter': '@ClientName', 'Type': 'varchar',
                             'Length': '255', 'Precision': '255', 'Scale': '', 'Parameter Order': '1'}
    
    def test_get_object_parameters_should_return_empty_list_if_no_such_object(self, connected_db):
        params = connected_db.get_object_parameters('store', 'no_such_object')
        assert params == []

    def test_get_object_dependencies_should_return_list_of_dicts_of_indexes(self, connected_db):
        deps = connected_db.get_object_dependencies('store', 'spSELECT', [TEST_DB_NAME])
        assert len(deps) == 1
        assert deps[0] == {'Database': TEST_DB_NAME, 'Schema': 'store', 'Object': 'Clients'}
    
    def test_get_object_dependencies_should_return_empty_list_if_no_such_object(self, connected_db):
        deps = connected_db.get_object_dependencies('store', 'no_such_object', [TEST_DB_NAME])
        assert deps == []

    def test_get_object_dependencies_should_return_empty_list_if_no_dependencies(self, connected_db):
        deps = connected_db.get_object_dependencies('store', 'Products', [TEST_DB_NAME])
        assert deps == []
