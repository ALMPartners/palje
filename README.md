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

## Development environment

Install and set up dev and test tooling with commands:

```
pip install -e .[dev, test]
pre-commit install
```

This takes `black` code formatting in use via `pre-commit`.

# Usage

Palje can be used either from the command line (CLI) or from the graphical user interface (GUI).

Notice that there are two versions of the command-line tool: legacy `palje` and newer `palje2`. See below for details.

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

## Graphical user-interface

Notice that GUI may be lacking some of the more advanced features that are available via CLI.

![Page hierarchy in Confluence](./images/palje_gui.PNG?raw=true)

Launch Palje GUI from a shell with command:

```
palje-gui
```

See the CLI documentation below for information on various parameters - it all applies to GUI, too.


## CLI and arguments (current palje2 version)

In comparison to `palje`, the new `palje2` CLI is more flexible and adds more features. For example, there
are features for deleting and alphabetically sorting existing Confluence pages.

See online help for up-to-date documentation for top-level options and sub-commands.
```
palje2 --help
```

To see specific documentation for a sub-command, use the --help switch _after_ the sub-command e.g.

```
palje2 document --help
palje2 delete --help
```

### Parameters from ENV vars

With `palje2` many parameters (e.g. Confluence authentication params) can be set into ENV variables from where they are automatically read at runtime. This makes continous use more user-friendly: less repetative typing, shorter and clearer commands, sensitive data stays out of sight, etc.

Notice that using ENV vars is optional: alternatively you can type parameters on the command line and/or leave them off and let `palje2` interactively prompt for any required parameter values.

See the online-documentation for supported ENV vars and their exact names.

Example of setting some ENV vars in PowerShell:

```
$env:SOURCE_PALJE_ATLASSIAN_USER_ID = "firstname.lastname@organization.org"
$env:SOURCE_PALJE_ATLASSIAN_API_TOKEN = "S3CR3T"
$env:PALJE_DB_SERVER = "localhost,14330"
...
```

If you want to unset an ENV var in PowerShell, you can do it by setting its value to `$null`:

```
$env:PALJE_DB_PASSWORD = $null
```

### Experimental features

There may be some features in `palje2` that are somewhat usable but known to be still incomplete or unreliable in some cases e.g. due to unresolved issues with Confluence API.

By default, these experimental features are hidden from the user and not available in regular use.

To make experimental features available, set some value to the special `PALJE_EXPERIMENTAL_FEATURES_ENABLED` enviroment variable.

```
PS > $env:PALJE_EXPERIMENTAL_FEATURES_ENABLED = "1"
PS > palje2 --help
Experimental features enabled.
Usage: palje2 [OPTIONS] COMMAND [ARGS]...
...
Commands:
  copy      Experimental: Copy pages or page hierarchies between...
...
```

## CLI and arguments (legacy version)

See online help for up-to-date documentation for available options.
```
palje -h
```

### Basic syntax

```
palje confluence-url space server database
                --parent-page PARENT_PAGE
                --schemas SCHEMAS [SCHEMAS ...]
                --dependent DEPENDENT [DEPENDENT ...]
                --db-driver DB_DRIVER
                --authentication AUTHENTICATION
```

| Argument  | Required | Description | Type | Default Value |
| --- | --- | --- | --- | --- |
| confluence-url | Yes | The organisation's atlassian root page, https://<your-org>.atlassian.net/ | str |  |
| space | Yes | Space key of the Confluence space, in which the documentation is created | str |  |
| server | Yes | Host name of the SQL Server. Include port with comma | str |  |
| database | Yes | Name of the database that is documented | str |  |
| parent-page | No | Name or title of the Confluence page, under which the documentation is created | str | If page is not given, the documentation will be created to top level (under pages) |
| schemas | No | Names of the schemas that are documented | list of str | If schemas not given, all schemas will be documented |
| dependent | No | Names of the databases, where object dependencies are sought | list of str | If databases not given, dependencies are sought only in documented database |
| db-driver | No | Name of the database driver | str | "ODBC Driver 17 for SQL Server" |
| authentication | No | Authentication method to use. Options are "SQL", "Windows", "AAD" and "AzureIdentity". | str | "SQL"


## Usage example


### Command-line interface
```
# Run via a configured script endpoint ("palje.exe")
palje "https://<your-org>.atlassian.net/" TEST "localhost,1433" MY_DB --schemas dbo store --dependent MY_OTHER_DB --authentication "SQL"

# Optionally you also run palje as a Python library module
python -m palje "https://<your-org>.atlassian.net/" TEST "localhost,1433" MY_DB --schemas dbo store --dependent MY_OTHER_DB --authentication "SQL"

```
### Output
```
User for localhost,1433.MY_DB. If you wish to use Windows Authentication, hit enter: sa
Password for user sa:
Confluence user for https://<your-org>.atlassian.net/: example.user@youremail.com
Atlassian API token for user example.user@youremail.com:
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
pip install tox # OR install as an optional depencency with palje itself: pip install .[test]

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

## MSI installers

Palje can be packaged into an MSI installer which can be used to install it into a Windows environment and easily update it later. Installers are self-contained, meaning that the package contains everything that is needed for running Palje (e.g. required parts of Python installation and all the 3rd party libraries and their dependencies are included).

### Types of MSI installers

There two types of installers, `user` and `system`. The `user` installer is suitable for single-user installations e.g. for a user who wants to run palje on their own workstation. For shared use, e.g. Azure Virtual Desktop, the `system` installer may be the better option: once installed, the tools are available for all users on that machine.

**Notice:** using the `system` installer requires administrator priviledges.

### Local MSI builds

**Notice:** using an unsigned installer can end up with Windows Defender blocking Palje as malware. There is an ALM Partners developer signing key available to overcome this problem. Ask team TA3 for help if you need to sign development MSIs for testing purposes.

To set up an environment for MSI builds, create a new venv, activate it, and install build dependencies.

```
python venv <name-of-venv>
./<name-of-venv>/Scripts/activate
pip install .[msibuild]
```

To build a `user` installer, use commands:

```
$env:PALJE_MSI_TARGET_TYPE="user"
python ./msi_build.py bdist_msi
```

To build a `system` installer, use commands:

```
$env:PALJE_MSI_TARGET_TYPE="system"
python ./msi_build.py bdist_msi
```

**Notice:** if you make changes to the code, you __must re-install the palje__ package (`pip install .` or `pip install .[msibuild]`) into the build venv for the changes to be included in the next MSI build. Editable installs don't work here, so don't use them!

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
