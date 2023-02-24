Palje
====================

# Description
Palje is a tool for creating hierarchical documentation of SQL Server databases to Confluence wiki.

# Dependencies
* [pyodbc](https://pypi.org/project/pyodbc/)
* [requests](https://pypi.org/project/requests/)

# Install Guide

## PyPI
Install from [Python Package Index](https://pypi.org/) with the following command:

```
pip install palje
```

## Clone and install
1. Clone this repository
2. Install with pip

```
cd .\palje
pip install [-e] .
```

# Usage

## Prerequisites

- Read access to the MSSQL database you wish to document
    - Data is read from documented database, information schema and system views
    - You can use either SQL authentication or Windows authentication (if available)

- Write access to Confluence space on which you wish to create the documentation pages

- Atlassian API Token for your account
    - Palje uses your registered account email and API token to authenticate to Confluence Cloud
        - Go to https://id.atlassian.com/manage/api-tokens
        - Choose "Create API token"
        - Give it a name
        - Token password will be created automatically, save this password

## Remarks on compatibility

- Palje has been tested on multiple SQL Server versions, including [SQL Server images](https://hub.docker.com/_/microsoft-mssql-server)
- Palje has been tested on cloud instances, such as Azure SQL Database
    - Palje supports Azure Active Directory authentication with argument --authentication "AAD"
- Palje has been tested to work with Confluence Cloud
    - There is a possibility that Palje works with Confluence Server since the Server REST API is similar to Cloud REST API
    - Notice that the authentication works differently in Confluence Server

## CLI and arguments
```
python -m palje confluence-url space server database
                --parent-page PARENT_PAGE
                --schemas SCHEMAS [SCHEMAS ...]
                --dependent DEPENDENT [DEPENDENT ...]
                --db-driver DB_DRIVER
                --authentication AUTHENTICATION
```
| Argument  | Required | Description | Type | Default Value |
| --- | --- | --- | --- | --- |
| confluence-url | Yes | URL to Confluence REST content. In Confluence Cloud, this is something like https://yourconfluence.atlassian.net/wiki/rest/api/content | str |  |
| space | Yes | Space key of the Confluence space, in which the documentation is created | str |  |
| server | Yes | Host name of the SQL Server. Include port with comma | str |  |
| database | Yes | Name of the database that is documented | str |  |
| parent-page | No | Name or title of the Confluence page, under which the documentation is created | str | If page is not given, the documentation will be created to top level (under pages) |
| schemas | No | Names of the schemas that are documented | list of str | If schemas not given, all schemas will be documented |
| dependent | No | Names of the databases, where object dependencies are sought | list of str | If databases not given, dependencies are sought only in documented database |
| db-driver | No | Name of the database driver | str | "ODBC Driver 17 for SQL Server" |
| authentication | No | Authentication method to use. Options are "SQL", "Windows", "AAD" | str | "SQL"
 

## Usage example
### Command
```
cd .\palje
python -m palje "https://yourconfluence.atlassian.net/wiki/rest/api/content" TEST "localhost,1433" MY_DB --schemas dbo store --dependent MY_OTHER_DB --authentication "SQL"

```
### Output
```
User for localhost,1433.MY_DB. If you wish to use Windows Authentication, hit enter: sa
Password for user sa:
Confluence user for yourconfluence.atlassian.net: example.user@youremail.com
Password for user example.user@youremail.com:
--------------------------
Object dependencies are queried from the following databases: MY_DB, MY_OTHER_DB
--------------------------
Page DATABASE: MY_DB created.
Page MY_DB.dbo created.
Page Tables MY_DB.dbo created.
Page MY_DB.dbo.schema_version created.
Page MY_DB.store created.
Page Tables MY_DB.store created.
Page MY_DB.store.Clients created.
Page MY_DB.store.Products created.
Page Procedures MY_DB.store created.
Page MY_DB.store.spSELECT created.
```
### Result
#### Page hierarchy in Confluence
![Page hierarchy in Confluence](https://github.com/ALMPartners/palje/blob/master/images/confluence_hierarchy.PNG?raw=true)

#### Page showing the database objects
![Page "DATABASE: MY_DB"](https://github.com/ALMPartners/palje/blob/master/images/confluence_database.PNG?raw=true)

#### Page showing the table information
![Page "MY_DB.store.Clients"](https://github.com/ALMPartners/palje/blob/master/images/confluence_table.PNG?raw=true)

### Re-run
Re-running the command will result updating the existing pages
```
Page DATABASE: MY_DB updated.
Page MY_DB.dbo updated.
Page Tables MY_DB.dbo updated.
Page MY_DB.dbo.schema_version updated.
Page MY_DB.store updated.
Page Tables MY_DB.store updated.
Page MY_DB.store.Clients updated.
Page MY_DB.store.Products updated.
Page Procedures MY_DB.store updated.
Page MY_DB.store.spSELECT updated.
```
If new objects have been created to database before re-run, new pages will be created for these objects. For example, if new procedure `store.spNEW_SELECT` is created to database, a new page `MY_DB.store.spNEW_SELECT` is created under page `Procedures MY_DB.store`.

Notice that if you delete objects from database, Palje won't delete the corresponding pages from Confluence. You must manually delete the pages from wiki.

## Tests

Run tests with [tox](https://pypi.org/project/tox/) 
```
pip install tox

tox -- --mssql_host MSSQL_HOST --mssql_port MSSQL_PORT --mssql_username MSSQL_USER --mssql_password MSSQL_PASSWORD --mssql_driver MSSQL_DRIVER

# without MSSQL tests
tox
```
or [pytest](https://pypi.org/project/pytest/)
```
pip install pytest ahjo sqlalchemy

pytest --mssql_host MSSQL_HOST --mssql_port MSSQL_PORT --mssql_username MSSQL_USER --mssql_password MSSQL_PASSWORD --mssql_driver MSSQL_DRIVER

# without MSSQL tests
pytest
```

Notice that tests have dependencies to packages [ahjo](https://pypi.org/project/ahjo/) and [SQL Alchemy](https://pypi.org/project/SQLAlchemy/). To succesfully run SQL Server tests, you must have permissions to create a new database in instance.

# License
Copyright 2021 ALM Partners Oy

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.