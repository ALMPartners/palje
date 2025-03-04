Palje
====================

# Description
Palje is a tool for creating hierarchical documentation of SQL Server databases to Confluence and managing Confluence content.

# Dependencies
See [pyproject.toml](./pyproject.toml)

# Install Guide

## PyPI
Install from the [Python Package Index](https://pypi.org/) with the following command:

```
pip install palje
```

## Clone and install
1. Clone this repository
2. Install with pip

```
cd .\palje
pip install .
```

## Development environment

Install and set up dev and test tooling with commands:

```
pip install -e .[dev, test]
pre-commit install
```

This takes `black` code formatting (and other tools) into use via `pre-commit`.

# Usage

After successful installation, there are three new commands available: `palje`, `palje-gui`, and `palje-old`.

Palje can be used either as a CLI tool (`palje`, `palje-old`) or via (limited) graphical user interface (`palje-gui`).

## Prerequisites

Before use, you should ensure that you have the following:

- Read access to a MSSQL database you wish to document
    - Documentation is generated from the database metadata that is read from the database(s), information schema and system views
    - You can use either SQL authentication, AAD, or Windows authentication

- Read/Write access to a Confluence space to work with via Atlassian API Token
    - In addition to db document creation, you may also sort and delete Confluence pages and page hierarchies
    - Palje uses your registered account email and API token to authenticate to Confluence Cloud
        - Go to https://id.atlassian.com/manage/api-tokens
        - Choose "Create API token"
        - Give it a name
        - Token password will be created automatically, save this password

## Remarks on compatibility

- Palje has been tested on multiple SQL Server versions, including [SQL Server images](https://hub.docker.com/_/microsoft-mssql-server)
- Palje has been tested on cloud database instances, such as Azure SQL Database
    - Palje supports Azure Active Directory authentication with argument --authentication "AAD"
- Palje has been tested to work with Confluence Cloud only

## Graphical user-interface

Notice that GUI may be lacking some of the features that are available via CLI.

![Page hierarchy in Confluence](./images/palje_gui.PNG?raw=true)

Launch Palje GUI from a shell with command:

```
palje-gui
```

See the CLI documentation below for information on various parameters - it all applies to GUI, too.


## CLI and arguments

See online help for up-to-date documentation for top-level options and sub-commands.

Especially notice the `--yes-to-all` option that can be given to the root command to avoid all user input - this is esssential for scripted use!

```
palje --help
```

To see specific documentation for a sub-command, use the --help switch _after_ the sub-command e.g.

```
palje document --help
palje delete --help
palje sort --help
```

### Parameters from ENV vars

Many parameters (e.g. various authentication params) can be set into ENV variables from where they are automatically read at runtime. This makes continous use more user-friendly: less repetative typing, shorter and clearer commands, sensitive data stays out of sight, etc.

Notice that using ENV vars is optional: alternatively you can type parameters on the command line and/or leave them off and let `palje` interactively prompt for any required parameter values.

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

There may be some features in `palje` that are ~somewhat usable but known to be still incomplete or unreliable e.g. due to unresolved issues with Confluence Cloud REST API.

By default, these experimental features are hidden from the user and not available in regular use.

To make experimental features available, set some value to the special `PALJE_EXPERIMENTAL_FEATURES_ENABLED` enviroment variable.

```
PS > $env:PALJE_EXPERIMENTAL_FEATURES_ENABLED = "1"
PS > palje --help
Experimental features enabled.
Usage: palje [OPTIONS] COMMAND [ARGS]...
...
Commands:
  copy      Experimental: Copy pages or page hierarchies between...
...
```

## Legacy CLI and arguments (deprecated)

The old `palje` CLI is still available as `palje-old` command.

Notice that the old CLI is **deprecated** and will be dropped completely in the near future.

See online help for up-to-date documentation for available options.
```
palje-old -h
```

### Basic syntax

```
palje-old confluence-url space server database
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

```
palje-old "https://<your-org>.atlassian.net/" TEST "localhost,1433" MY_DB --schemas dbo store --dependent MY_OTHER_DB --authentication "SQL"
```

## Testing

Install palje with testing depencies.

```
pip install .[test]
```

### Run unit tests with pytest

```
pytest
```

### Run unit tests for all supported, installed Python versions with tox

```
tox
```

## Creating MSI installers

Palje can be packaged into an MSI installer which can be used for installing palje into Windows environments and easily apply updates on it later.

MSI installers are self-contained, meaning that the package contains everything that is needed for running Palje (e.g. required parts of Python installation and all the 3rd party libraries and their dependencies are included).

### Types of MSI installers

There two types of installers, `user` and `system`. The `user` installer is suitable for single-user installations e.g. for a user who wants to run palje on their own workstation. For shared use, e.g. Azure Virtual Desktop, the `system` installer may be the better option: once installed, the tools are available for all users on that machine.

**Notice:** using the `system` installer requires administrator priviledges.

### Local MSI builds

**Notice:** make sure you are using a supported Python version (see [msi_build.py](./msi_build.py)).

To set up an environment for MSI builds, create a new venv, activate it, and install build dependencies.

```
python venv buildvenv
./buildvenv/Scripts/activate
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
