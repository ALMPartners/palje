"""Palje MSI build script."""

import os
import sys
from sysconfig import get_platform

from cx_Freeze import Executable, setup

from palje.version import version as palje_version

# If the value in the named env var is set to "system" (case-insensitive),
# a system ("all users") MSI installer will be created.
# Any other or missing value creates a user installer ("single user").
# The final installer name will be suffixed with "-SYSTEM" or "-USER" respectively.
MSI_TARGET_TYPE_ENV_VAR = 'PALJE_MSI_TARGET_TYPE'

# Application information
name = "Palje"
version = palje_version
author = "ALM Partners"
author_email = "servicedesk@almpartners.fi"
url = "https://almpartners.com/"
description = ""

# Specify the GUID (DO NOT CHANGE ON UPGRADE)
# This has been obtained using:
# >>> import uuid
# >>> str(uuid.uuid3(uuid.NAMESPACE_DNS, 'palje.almpartners.fi')).upper()
upgrade_code = "{E69B922F-D0A4-3D5F-942B-4C26F2309EB5}"

programfiles_dir = (
    "ProgramFiles64Folder" if get_platform() == "win-amd64" else "ProgramFilesFolder"
)

include_files = ["src/palje/queries/database_queries.ini"]

#  Python packages to include and exclude in the executable

build_exe_options = {
    "packages": ["palje"],
    "include_msvcr": True,
    "include_files": include_files,  
}

# Options affecting the installer file

installer_type = os.getenv(MSI_TARGET_TYPE_ENV_VAR, "USER").strip().upper()
installer_type_suffix = "SYSTEM" if installer_type == "SYSTEM" else "USER"
target_name = f"Palje-{version}-{get_platform()}-{installer_type_suffix}.msi"

bdist_msi_options = {
    "upgrade_code": upgrade_code,
    "add_to_path": True,
    "target_name": target_name,
    "initial_target_dir": rf"[{programfiles_dir}]\{author}\{name}",
    "all_users": installer_type == "SYSTEM",
}

options = {"build_exe": build_exe_options, "bdist_msi": bdist_msi_options}

base = "Win32GUI" if sys.platform == "win32" else None

palje_exe = Executable("src/palje/__main__.py", target_name="palje.exe", base=None)

setup(
    name=name,
    version=version,
    author=author,
    author_email=author_email,
    url=url,
    description=description,
    executables=[palje_exe],
    options=options,
)
