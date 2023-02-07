from contextlib import contextmanager
from http.server import HTTPServer
from os import chdir, getcwd, path
from threading import Thread
from warnings import catch_warnings, simplefilter

import pytest
from ahjo.operations.tsql import db_object_properties as ahjo
from palje.mssql_database import MSSQLDatabase
from sqlalchemy.exc import SAWarning
from sqlalchemy.schema import CreateSchema
from sqlalchemy import text

from .conftest import TEST_DB_NAME, engine_from
from .database.models import Base
from .http_server import RequestHandler


@pytest.fixture(scope='session')
def mssql_config(request):
    mssql_host = request.config.getoption('mssql_host')
    if mssql_host:
        server = mssql_host + ',' + request.config.getoption('mssql_port')
    else:
        server = ''
    authentication = 'SQL'
    return (server, TEST_DB_NAME, request.config.getoption('mssql_driver'), authentication)


@pytest.fixture(scope='function')
def mssql_db(mssql_config):
    return MSSQLDatabase(*mssql_config)


@pytest.fixture(scope='session')
def mssql_credentials(request):
    return (request.config.getoption('mssql_username'), request.config.getoption('mssql_password'))


@pytest.fixture(scope='function')
def connected_db(mssql_db, mssql_credentials, monkeypatch):
    monkeypatch.setattr('builtins.input', lambda x: mssql_credentials[0])
    monkeypatch.setattr('getpass.getpass', lambda x: mssql_credentials[1])
    mssql_db.connect()
    return mssql_db


@contextmanager
def database_cwd():
    test_dir = path.dirname(path.abspath(__file__))
    database_dir = path.join(test_dir, 'database')
    oldpwd = getcwd()
    chdir(database_dir)
    try:
        yield
    finally:
        chdir(oldpwd)


def sql_file(file_name):
    with open(file_name, 'r', encoding='utf-8') as f:
        content = f.read()
    return content


@pytest.fixture(scope='session')
def mssql_setup_and_teardown(request):
    # create database
    with catch_warnings():
        simplefilter("ignore", category=SAWarning)
        master_engine = engine_from(request.config)
        with master_engine.connect() as connection:
            connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(f'CREATE DATABASE {TEST_DB_NAME}')
    # create schema and tables
    engine = engine_from(request.config, database=TEST_DB_NAME)
    with engine.connect() as connection:
        connection.execute(CreateSchema('store'))
        connection.execute(CreateSchema('report'))
        Base.metadata.create_all(engine)
        with database_cwd():
            # create index and procedure
            create_index = open('index.sql', 'r', encoding='utf-8').read()
            connection.execute(text(create_index))
            create_procedure = open('procedure.sql', 'r', encoding='utf-8').read()
            connection.execute(text(create_procedure))
            # add extended properties with ahjo
            ahjo.update_db_object_properties(engine, ['store', 'report'])
    engine.dispose()
    yield
    # drop database
    with master_engine.connect() as connection:
        connection.execution_options(isolation_level="AUTOCOMMIT")
        result = connection.execute(
            'SELECT session_id FROM sys.dm_exec_sessions WHERE database_id = DB_ID(?)', (TEST_DB_NAME,))
        for row in result.fetchall():
            connection.execute(f'KILL {row.session_id}')
        connection.execute(f'DROP DATABASE {TEST_DB_NAME}')


@pytest.fixture(autouse=True, scope='session')
def http_server_setup_and_teardown():
    server = HTTPServer(('', 10300), RequestHandler)
    thread = Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield
    server.shutdown()
