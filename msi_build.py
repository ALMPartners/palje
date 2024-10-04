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
MSI_TARGET_TYPE_ENV_VAR = "PALJE_MSI_TARGET_TYPE"

# Application information
name = "Palje"
version = palje_version
author = "ALM Partners"
author_email = "servicedesk@almpartners.fi"
url = "https://almpartners.com/"
description = ""
icon = "palje.ico"

# Specify the GUID (DO NOT CHANGE ON UPGRADE)
# This has been obtained using:
# >>> import uuid
# >>> str(uuid.uuid3(uuid.NAMESPACE_DNS, 'palje.almpartners.fi')).upper()
upgrade_code = "{E69B922F-D0A4-3D5F-942B-4C26F2309EB5}"

programfiles_dir = (
    "ProgramFiles64Folder" if get_platform() == "win-amd64" else "ProgramFilesFolder"
)

include_files = [
    "src/palje/mssql/database_queries.ini",
    "src/palje/gui/palje.png",
]

#  Python packages to include and exclude in the executable

build_exe_options = {
    "packages": ["palje"],
    "include_msvcr": True,
    "include_files": include_files,
}

# Icon table, see: https://learn.microsoft.com/en-us/windows/win32/msi/icon-table
icon_table = [("PaljeIcon", icon)]

# Shortcut table, see: https://learn.microsoft.com/en-us/windows/win32/msi/shortcut-table
shortcut_table = [
    (
        "PaljeGUIStartMenu",  # Unique shortcut key
        "StartMenuFolder",  # Directory
        "Palje",  # Name
        "TARGETDIR",  # Component_
        "[TARGETDIR]palje-gui.exe",  # Target
        None,  # Arguments
        None,  # Description
        None,  # Hotkey
        "PaljeIcon",  # Icon
        None,  # IconIndex
        None,  # ShowCmd
        "TARGETDIR",  # WkDir
    )
]

# Property table, see: https://learn.microsoft.com/en-us/windows/win32/msi/property-table
property_table = [
    (
        # This property is used to set the icon for the Add/Remove Programs entry
        "ARPPRODUCTICON",
        "PaljeIcon",
    )
]

# MSI data containing installer database tables
msi_data = {"Icon": icon_table, "Shortcut": shortcut_table, "Property": property_table}

# Options affecting the installer file

installer_type = os.getenv(MSI_TARGET_TYPE_ENV_VAR, "USER").strip().upper()
installer_type_suffix = "SYSTEM" if installer_type == "SYSTEM" else "USER"
target_name = f"Palje-{version}-{get_platform()}-{installer_type_suffix}.msi"

bdist_msi_options = {
    "upgrade_code": upgrade_code,
    "add_to_path": True,
    "target_name": name,
    "initial_target_dir": rf"[{programfiles_dir}]\{author}\{name}",
    "all_users": installer_type == "SYSTEM",
    "data": msi_data,
}

options = {"build_exe": build_exe_options, "bdist_msi": bdist_msi_options}

base = "Win32GUI" if sys.platform == "win32" else None

palje_exe = Executable("src/palje/cli.py", target_name="palje.exe", base=None)
palje2_exe = Executable("src/palje/cli2.py", target_name="palje2.exe", base=None)
palje_gui_exe = Executable(
    "src/palje/gui/gui.py", target_name="palje-gui.exe", base=base, icon=icon
)

setup(
    name=name,
    version=version,
    author=author,
    author_email=author_email,
    url=url,
    description=description,
    executables=[palje_exe, palje2_exe, palje_gui_exe],
    options=options,
)
