import argparse
import asyncio
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from pathlib import Path
import sys

from palje.cli_commands.document_cmd import _document_db_to_confluence_async
from palje.confluence.confluence_ops import is_page_creation_allowed_async
from palje.confluence.confluence_rest import (
    ConfluenceRestClientAsync,
    ConfluenceRESTError,
)
from palje.gui.components.confluence_connection_widget import ConfluenceConnectionWidget
from palje.gui.components.db_browser_widget import DbBrowserWidget
from palje.gui.components.db_server_widget import (
    DBServerConnectionState,
    DbServerWidget,
)
from palje.mssql.mssql_database import (
    MSSQLDatabaseAuthType,
    MSSQLDatabase as MSSQLDatabase,
)
from palje.progress_tracker import ProgressTracker
from palje.version import __version__ as PALJE_VERSION

# TODO: dependent databases selection

WINDOW_TITLE = f"Palje v{PALJE_VERSION}"
DEFAULT_WINDOW_SIZE = (430, 720)
WINDOW_PADDING = 5
FRAME_PADDING = 7
ICON = Path(__file__).parent / "palje.png"
if not ICON.exists():
    # When running the built version installed from the .msi
    ICON = Path(sys.executable).parent / "palje.png"
CONFLUENCE_REQUEST_LIMIT = 30


class App(tk.Tk):
    def __init__(
        self,
        args: argparse.Namespace,
        start_size: tuple[int, int] = DEFAULT_WINDOW_SIZE,
    ):
        super().__init__()
        window_title = WINDOW_TITLE
        if args.request_limit != CONFLUENCE_REQUEST_LIMIT:
            if args.request_limit < 1:
                window_title += f" (request limit: unlimited)"
            else:
                window_title += f" (request limit: {args.request_limit})"
        self.title(window_title)
        self.iconphoto(True, tk.PhotoImage(file=ICON))
        self.geometry(f"{start_size[0]}x{start_size[1]}")
        self.configure(padx=WINDOW_PADDING, pady=WINDOW_PADDING)
        Main(parent=self, request_limit=args.request_limit).pack(
            fill=tk.BOTH, expand=True
        )

        self.mainloop()


class Main(ttk.Frame):
    _mssql_database: MSSQLDatabase | None
    _db_server_widget: DbServerWidget
    _db_browser_widget: DbBrowserWidget

    _progress_tracker: ProgressTracker
    _progressbar: ttk.Progressbar
    _progressbar_var: tk.DoubleVar

    _request_limit: int

    def __init__(
        self,
        parent: tk.Misc | None = None,
        request_limit: int = CONFLUENCE_REQUEST_LIMIT,
    ):
        super().__init__(master=parent)

        self._request_limit = request_limit

        self._progress_tracker = ProgressTracker()
        self._mssql_database = None

        actions_notebook = ttk.Notebook(self)

        # TODO: split this into more manageable pieces when wikitool actions are added

        #
        # Source database params
        #

        db_to_cnflc_action_frame = ttk.Frame(actions_notebook, padding=FRAME_PADDING)

        db_server_frame = tk.LabelFrame(
            db_to_cnflc_action_frame, text="Database connection"
        )
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

        db_browser_frame = tk.LabelFrame(
            db_to_cnflc_action_frame, text="Objects to document"
        )

        self._db_browser_widget = DbBrowserWidget(parent=db_browser_frame)
        self._db_browser_widget.set_input_state(enabled=False)
        self._db_browser_widget.bind(
            "<<DatabaseSelectionChanged>>", lambda _: self._on_db_selected()
        )
        self._db_browser_widget.pack(fill=tk.X, expand=True)

        db_browser_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        #
        # Target Confluence params
        #

        target_confluence_frame = tk.LabelFrame(
            db_to_cnflc_action_frame, text="Target Confluence"
        )
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
        # Execution
        #

        exec_frame = ttk.Frame(db_to_cnflc_action_frame)
        exec_frame.rowconfigure((0, 1), weight=1)
        exec_frame.columnconfigure((0, 1), weight=1)

        self._progressbar_var = tk.DoubleVar()
        self._progressbar = ttk.Progressbar(
            exec_frame,
            orient="horizontal",
            length=200,
            mode="determinate",
            variable=self._progressbar_var,
        )
        self._progressbar.grid(row=0, column=0, sticky=tk.W)

        self._progress_label = ttk.Label(exec_frame)
        self._progress_label.grid(row=1, column=0, sticky=tk.W, columnspan=2)

        self._execute_button = ttk.Button(
            exec_frame, text="Execute", command=self._on_execute_clicked
        )
        self._execute_button.grid(
            row=0,
            column=1,
            sticky=tk.E,
        )
        exec_frame.pack(fill=tk.X, expand=True, side=tk.TOP, pady=5)

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
        self._confluence_widget.set_test_connection_button_state(
            self._confluence_widget.required_fields_filled()
        )

    def _on_input_params_changed(self) -> None:
        self._refresh_button_states()

    def _connect_db_server(self) -> None:
        try:
            self._mssql_database = MSSQLDatabase(
                server=self._db_server_widget.server,
                database=self._db_server_widget.db_name,
                driver=self._db_server_widget.driver,
                authentication=MSSQLDatabaseAuthType[
                    self._db_server_widget.auth_method
                ],
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
        try:
            self._mssql_database.change_current_db(
                self._db_browser_widget.selected_database
            )
            available_schemas = list(set(self._mssql_database.get_schemas()))
            available_schemas.sort()
            self._db_browser_widget.available_schemas = available_schemas
        except Exception as e:
            # E.g. a sleeping AZSQL db may cause this
            self._db_browser_widget.available_schemas = []
            err_msg = f"Failed to change the database. {str(e)}"
            messagebox.showerror("Database error", err_msg)
        finally:
            self._refresh_button_states()

    async def _test_confluence_connection(self) -> None:
        try:

            async with ConfluenceRestClientAsync(
                self._confluence_widget.confluence_root_url,
                self._confluence_widget.confluence_user_id,
                self._confluence_widget.confluence_api_token,
            ) as confluence_client:
                space_writable = await is_page_creation_allowed_async(
                    confluence_client,
                    space_key=self._confluence_widget.confluence_space_key,
                )
        except ConfluenceRESTError as e:
            messagebox.showerror(
                "Connection error",
                f"Connection error: {e}",
            )
            return
        except Exception as e:
            # TODO: in client, wrap specific errors into ConfluenceRESTErrors
            #       with meaningful, displayable error messages e.g. "invalid URL"
            messagebox.showerror(
                "Connection error",
                f"Please check the parameters and try again.",
            )
            return
        if not space_writable:
            messagebox.showerror(
                "Connection error",
                "The space doesn't allow page creation with current credentials.",
            )
        else:
            messagebox.showinfo(
                "Connection OK",
                "Connection to the Confluence with given parameters seems to work OK.",
            )

    def _on_test_confluence_connection_clicked(self) -> None:
        self._set_input_state(enabled=False)
        self._confluence_widget.update_test_connection_button_title(testing=True)
        self.update()
        asyncio.run(self._test_confluence_connection())
        self._confluence_widget.update_test_connection_button_title(testing=False)
        self._set_input_state(enabled=True)

    def _set_input_state(self, enabled: bool) -> None:
        """Enable/disable all inputs in the GUI.
        On enable, tries to keep a reasonable state by checking other components.
        """
        self._execute_button.config(state=tk.DISABLED if not enabled else tk.NORMAL)
        self._db_server_widget.set_input_state(enabled=enabled)
        self._db_browser_widget.set_input_state(enabled=enabled)
        self._confluence_widget.set_input_state(enabled=enabled)
        if enabled:
            self._db_browser_widget.set_input_state(
                enabled=self._db_server_widget.connection_state
                == DBServerConnectionState.CONNECTED
            )
            self._refresh_button_states()

    def _update_progressbar(self, _: ProgressTracker | None = None) -> None:
        self._progressbar_var.set(
            self._progress_tracker.percents / 100 * self._progressbar.cget("maximum")
        )
        progress_text = ""
        if self._progress_tracker.target_total > 0:
            progress_text = (
                f"{self._progress_tracker.completed}"
                + f"/{self._progress_tracker.target_total} "
                + f"({self._progress_tracker.elapsed_time:.1f}s)"
            )
        if self._progress_tracker.message:
            progress_text += f" - {self._progress_tracker.message}"
        self._progress_label.config(text=progress_text)
        self.update()

    def _start_db_documenter_worker(self) -> None:
        """Start the database documenter worker thread."""
        exc_thread = threading.Thread(target=self._execute_db_documenter)
        exc_thread.start()

    def _execute_db_documenter(self) -> None:
        """Database documenter GUI flow."""
        self._set_input_state(enabled=False)
        self._execute_button.config(text="Executing...")
        self.update()
        asyncio.run(self._document_db_to_confluence_async())
        self._set_input_state(enabled=True)
        self._execute_button.config(text="Execute")

    async def _document_db_to_confluence_async(self) -> None:
        """Collect documentation from the database and upload it to Confluence."""
        # TODO: dependent databases selection
        self._progress_tracker = ProgressTracker(
            on_step_callback=self._update_progressbar
        )
        try:

            await _document_db_to_confluence_async(
                tgt_confluence_root_url=self._confluence_widget.confluence_root_url,
                tgt_atlassian_user_id=self._confluence_widget.confluence_user_id,
                tgt_atlassian_api_token=self._confluence_widget.confluence_api_token,
                database_client=self._mssql_database,
                tgt_confluence_space_key=self._confluence_widget.confluence_space_key,
                parent_page_title=self._confluence_widget.confluence_parent_page,
                schema=self._db_browser_widget.selected_schemas,
                confl_update_pt=self._progress_tracker,
                doc_files_pt=self._progress_tracker,
                confl_sort_pt=self._progress_tracker,
                dependency_db=[],
                request_limit=self._request_limit,
            )

            messagebox.showinfo(
                "Execution complete",
                "The documentation was successfully uploaded to Confluence.",
            )
            self._progress_tracker.reset()
            self._update_progressbar()
            self._progressbar_var.set(0)
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
        self._start_db_documenter_worker()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Palje GUI v{PALJE_VERSION} "
        + "- A Swiss army knife for managing documentation in Confluence ."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Palje GUI v{PALJE_VERSION}",
    )
    parser.add_argument(
        "--request-limit",
        type=int,
        default=CONFLUENCE_REQUEST_LIMIT,
        help="Maximum number of concurrent requests to Confluence. "
        + "Increase for faster processing, decrease to avoid Confluence errors. "
        + f"Default: {CONFLUENCE_REQUEST_LIMIT}",
        required=False,
    )
    return parser.parse_args()


def main():
    args = parse_args()
    _ = App(args)


if __name__ == "__main__":
    main()
