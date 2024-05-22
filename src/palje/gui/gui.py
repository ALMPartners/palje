import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from pathlib import Path
import sys
import os

from palje.__main__ import (
    collect_databases_to_query_dependencies,
    collect_schemas_to_document,
    create_or_update_root_page,
    create_or_update_subpages,
)
from palje.confluence_rest import ConfluenceREST, ConfluenceRESTError
from palje.gui.components.confluence_connection_widget import ConfluenceConnectionWidget
from palje.gui.components.db_browser_widget import DbBrowserWidget
from palje.gui.components.db_server_widget import (
    DBServerConnectionState,
    DbServerWidget,
)
from palje.mssql_database import MSSQLDatabase as MSSQLDatabase
from palje.version import __version__ as PALJE_VERSION

# TODO: progress indicator
# TODO: dependent databases selection

WINDOW_TITLE = f"Palje v{PALJE_VERSION}"
DEFAULT_WINDOW_SIZE = (430, 710)
WINDOW_PADDING = 5
FRAME_PADDING = 7
ICON = Path(__file__).parent / "palje.png"
if not ICON.exists():
    # When running the built version installed from the .msi
    ICON = Path(sys.executable).parent / "palje.png"


class App(tk.Tk):
    def __init__(self, start_size: tuple[int, int] = DEFAULT_WINDOW_SIZE):
        super().__init__()
        self.title(WINDOW_TITLE)
        self.iconphoto(True, tk.PhotoImage(file=ICON))
        self.geometry(f"{start_size[0]}x{start_size[1]}")
        self.configure(padx=WINDOW_PADDING, pady=WINDOW_PADDING)
        Main(self).pack(fill=tk.BOTH, expand=True)

        self.mainloop()


class Main(ttk.Frame):

    _mssql_database: MSSQLDatabase | None
    _db_server_widget: DbServerWidget
    _db_browser_widget: DbBrowserWidget

    def __init__(self, parent: tk.Misc | None = None):
        super().__init__(master=parent)

        self._mssql_database = None

        actions_notebook = ttk.Notebook(self)

        # TODO: split this into more manageable pieces when wikitool actions are added

        #
        # Source database params
        #

        db_to_cnflc_action_frame = ttk.Frame(actions_notebook, padding=FRAME_PADDING)

        db_server_frame = tk.LabelFrame(db_to_cnflc_action_frame, text="Database connection")
        self._db_server_widget = DbServerWidget(
            db_server_frame, driver_options=MSSQLDatabase.available_db_drivers()
        )
        self._db_server_widget.pack(fill=tk.X, expand=True)

        self._db_server_widget.bind(
            "<<DbServerParamsChanged>>", lambda _: self._on_input_params_changed()
        )
        self._db_server_widget.bind(
            "<<DbServerConnect>>", lambda _: self._on_connect_db_server_clicked()
        )
        self._db_server_widget.bind(
            "<<DbServerDisconnect>>", lambda _: self._on_disconnect_db_server_clicked()
        )

        db_server_frame.pack(fill=tk.BOTH, expand=True)

        db_browser_frame = tk.LabelFrame(db_to_cnflc_action_frame, text="Objects to document")

        self._db_browser_widget = DbBrowserWidget(parent=db_browser_frame)
        self._db_browser_widget.set_input_state(enabled=False)
        self._db_browser_widget.bind("<<DatabaseSelectionChanged>>", lambda _: self._on_db_selected())
        self._db_browser_widget.pack(fill=tk.X, expand=True)

        db_browser_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        #
        # Target Confluence params
        #

        target_confluence_frame = tk.LabelFrame(db_to_cnflc_action_frame, text="Target Confluence")
        self._confluence_widget = ConfluenceConnectionWidget(
            parent=target_confluence_frame
        )
        self._confluence_widget.bind(
            "<<ConfluenceConnect>>",
            lambda _: self._on_test_confluence_connection_clicked(),
        )
        self._confluence_widget.bind(
            "<<ConfluenceParamsChanged>>", lambda _: self._on_input_params_changed()
        )
        self._confluence_widget.pack(fill=tk.X, expand=True)
        target_confluence_frame.pack(fill=tk.BOTH, expand=True)

        actions_notebook.add(db_to_cnflc_action_frame, text="Database documenter")
        actions_notebook.pack(fill=tk.BOTH, expand=True)

        #
        # Execute button
        #

        self._execute_button = ttk.Button(
            db_to_cnflc_action_frame, text="Execute", command=self._on_execute_clicked
        )
        self._execute_button.pack(expand=True, anchor=tk.E, side=tk.TOP, pady=5)

        self._refresh_button_states()

    def _required_fields_filled(self) -> bool:
        return (
            self._confluence_widget.required_fields_filled()
            and self._db_server_widget.required_fields_filled()
            and self._db_browser_widget.required_fields_filled()
        )

    def _set_execute_button_state(self, enabled: bool) -> None:
        self._execute_button.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def _refresh_button_states(self):
        self._set_execute_button_state(self._required_fields_filled())
        self._confluence_widget.set_test_connection_button_state(self._confluence_widget.required_fields_filled())

    def _on_input_params_changed(self) -> None:
        self._refresh_button_states()

    def _connect_db_server(self) -> None:
        try:
            self._mssql_database = MSSQLDatabase(
                server=self._db_server_widget.server,
                database=self._db_server_widget.db_name,
                driver=self._db_server_widget.driver,
                authentication=self._db_server_widget.auth_method,
                port=self._db_server_widget.port,
                username=self._db_server_widget.username,
                password=self._db_server_widget.password,
            )
            self._mssql_database.connect()
            self._db_browser_widget.set_input_state(enabled=True)
            # TODO: if db_name is not None, pre-select it?
            available_databases = self._mssql_database.get_databases()
            self._db_browser_widget.available_databases = available_databases
            self._db_server_widget.connection_state = DBServerConnectionState.CONNECTED
        except Exception as e:
            messagebox.showerror(
                "Connection error",
                f"Failed to connect to database: {e}",
            )
            self._db_server_widget.connection_state = (
                DBServerConnectionState.NOT_CONNECTED
            )

    def _on_connect_db_server_clicked(self) -> None:
        self._db_server_widget.connection_state = DBServerConnectionState.CONNECTING
        self._set_input_state(enabled=False)
        self.update()
        self._connect_db_server()
        self._set_input_state(enabled=True)

    def _on_disconnect_db_server_clicked(self) -> None:
        self._mssql_database.close()
        self._db_server_widget.connection_state = DBServerConnectionState.NOT_CONNECTED
        self._db_browser_widget.available_databases = []
        self._db_browser_widget.available_schemas = []
        self._db_browser_widget.set_input_state(enabled=False)
        self._refresh_button_states()

    def _on_db_selected(self) -> None:
        self._mssql_database.change_current_db(
            self._db_browser_widget.selected_database
        )
        available_schemas = list(set(self._mssql_database.get_schemas()))
        available_schemas.sort()
        self._db_browser_widget.available_schemas = available_schemas
        self._refresh_button_states()

    def _test_confluence_connection(self) -> None:
        try:
            confluence = ConfluenceREST(
                atlassian_url=self._confluence_widget.confluence_root_url
            )
            confluence.test_confluence_access(
                self._confluence_widget.confluence_user_id,
                self._confluence_widget.confluence_api_token,
                space_key=self._confluence_widget.confluence_space_key,
            )
            messagebox.showinfo(
                "Connection OK",
                f"Connection to the Confluence space with given parameters seems to work OK.",
            )
        except ConfluenceRESTError as e:
            messagebox.showerror(
                "Connection error",
                f"There were problems while trying to access the space in Confluence.\n\n{e}",
            )

    def _on_test_confluence_connection_clicked(self) -> None:
        self._set_input_state(enabled=False)
        self._confluence_widget.update_test_connection_button_title(testing=True)
        self.update()
        self._test_confluence_connection()
        self._confluence_widget.update_test_connection_button_title(testing=False)
        self._set_input_state(enabled=True)

    def _set_input_state(self, enabled: bool) -> None:
        """Enable/disable all inputs in the GUI. On enable, tries to keep a reasonable state by checking other components."""
        self._execute_button.config(state=tk.DISABLED if not enabled else tk.NORMAL)
        self._db_server_widget.set_input_state(enabled=enabled)
        self._db_browser_widget.set_input_state(enabled=enabled)
        self._confluence_widget.set_input_state(enabled=enabled)
        if enabled:
            self._db_browser_widget.set_input_state(enabled=self._db_server_widget.connection_state == DBServerConnectionState.CONNECTED)
            self._refresh_button_states()

    def _execute(self) -> None:
        """Collect documentation from the database and upload it to Confluence."""
        # TODO: progress indicator; this is a long operation and blocks the GUI -> should be done async / threaded
        # FIXME: just following the flow of the original code to see if it works -> make it better
        try:
            confluence = ConfluenceREST(
                atlassian_url=self._confluence_widget.confluence_root_url
            )
            confluence.auth = (
                self._confluence_widget.confluence_user_id,
                self._confluence_widget.confluence_api_token,
            )
            confluence_space_id = confluence.get_space_id(
                self._confluence_widget.confluence_space_key
            )
            # FIXME: unncessary to collect schemas again, we already have them selected?
            schemas = collect_schemas_to_document(
                self._mssql_database, self._db_browser_widget.selected_schemas
            )
            # TODO: implement dependant database filtering
            database_filter = None
            dep_databases = collect_databases_to_query_dependencies(
                self._mssql_database, database_filter, self._mssql_database.get_databases()
            )
            confulence_parent_page = self._confluence_widget.confluence_parent_page
            parent_page_id = create_or_update_root_page(
                self._mssql_database,
                confluence,
                confluence_space_id,
                confulence_parent_page,
            )
            create_or_update_subpages(
                self._mssql_database,
                confluence,
                confluence_space_id,
                schemas,
                dep_databases,
                parent_page_id,
            )
            messagebox.showinfo(
                "Execution complete",
                "The documentation was successfully uploaded to Confluence.",
            )
        except ConfluenceRESTError as e:
            messagebox.showerror(
                "Execution error",
                f"Processing failed due to an error with Confluence:\n\n{e}",
            )
        except Exception as e:
            messagebox.showerror(
                "Execution error",
                f"Processing failed due to an unexpected error:\n\n{e}",
            )

    def _set_execute_button_title(self, title: str) -> None:
        self._execute_button.config(text=title)

    def _on_execute_clicked(self) -> None:
        self._set_input_state(enabled=False)
        self._execute_button.config(text="Executing...")
        self.update()
        self._execute()
        self._set_input_state(enabled=True)
        self._execute_button.config(text="Execute")


def main():
    _ = App()


if __name__ == "__main__":
    main()
