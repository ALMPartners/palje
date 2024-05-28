import tkinter as tk
from tkinter import ttk
from tkinter import font

# TODO: validate params e.g. root url is a valid url

class ConfluenceConnectionWidget(tk.Frame):

    PADDING = 3

    _confluence_root_url: tk.StringVar
    _confluence_user_id: tk.StringVar
    _confluence_space_key: tk.StringVar
    _confluence_parent_page: tk.StringVar
    _confluence_api_token: tk.StringVar

    def __init__(self, parent: tk.Misc | None = None):
        super().__init__(master=parent)

        self._confluence_root_url = tk.StringVar(
            value=""
        )
        self._confluence_user_id = tk.StringVar(value="")
        self._confluence_space_key = tk.StringVar(value="")
        self._confluence_parent_page = tk.StringVar(value="")
        self._confluence_api_token = tk.StringVar(value="")

        self._confluence_root_url.trace_add("write", self._on_input_changed)
        self._confluence_user_id.trace_add("write", self._on_input_changed)
        self._confluence_space_key.trace_add("write", self._on_input_changed)
        self._confluence_parent_page.trace_add("write", self._on_input_changed)
        self._confluence_api_token.trace_add("write", self._on_input_changed)

        default_font = font.nametofont("TkDefaultFont")
        default_font_config = default_font.actual()

        self._label_font_bold = font.Font(**default_font_config)
        self._label_font_bold.configure(weight="bold")

        self.configure(padx=3, pady=3)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=4)
        self.rowconfigure((0, 1, 2, 3, 4), weight=1, pad=self.PADDING)

        row = 0
        self._root_url_label = ttk.Label(self, text="Root URL", font=self._label_font_bold)
        self._root_url_label.grid(
            row=row, column=0, sticky=tk.E, ipadx=self.PADDING
        )
        self._root_url_entry = ttk.Entry(self, textvariable=self._confluence_root_url)
        self._root_url_entry.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        self._space_key_label = ttk.Label(self, text="Space key", font=self._label_font_bold)
        self._space_key_label.grid(
            row=row, column=0, sticky=tk.E, ipadx=self.PADDING
        )
        self._space_key_entry = ttk.Entry(self, textvariable=self._confluence_space_key)
        self._space_key_entry.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        self._parent_page_label = ttk.Label(self, text="Parent page")
        self._parent_page_label.grid(
            row=row, column=0, sticky=tk.E, ipadx=self.PADDING
        )
        self._parent_page_entry = ttk.Entry(
            self, textvariable=self._confluence_parent_page
        )
        self._parent_page_entry.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        self._user_id_label = ttk.Label(
            self, text="User id (email address)", font=self._label_font_bold
        )
        self._user_id_label.grid(row=row, column=0, sticky=tk.E, ipadx=self.PADDING)
        self._user_id_entry = ttk.Entry(self, textvariable=self._confluence_user_id)
        self._user_id_entry.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        self._api_token_label = ttk.Label(self, text="Atlassian API token", font=self._label_font_bold)
        self._api_token_label.grid(
            row=row, column=0, sticky=tk.E, ipadx=self.PADDING
        )
        self._api_token_entry = ttk.Entry(
            self, textvariable=self._confluence_api_token, show="*"
        )
        self._api_token_entry.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        self._connect_button = ttk.Button(
            self,
            text="Test",
            command=self._on_test_connection_clicked,
        )
        self._connect_button.grid(
            row=row, column=1, sticky=tk.E, pady=self.PADDING
        )

        self.set_test_connection_button_state(self.required_fields_filled())

    def _on_input_changed(self, *_args) -> None:
        self.event_generate("<<ConfluenceParamsChanged>>")
        self.set_test_connection_button_state(self.required_fields_filled())

    def _on_test_connection_clicked(self) -> None:
        self.event_generate("<<ConfluenceConnect>>")

    def set_test_connection_button_state(self, enabled: bool) -> None:
        self._connect_button.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def update_test_connection_button_title(self, testing: bool) -> None:
        self._connect_button.config(
            text="Testing..." if testing else "Test"
        )

    def required_fields_filled(self) -> bool:
        return all(
            (
                self._confluence_root_url.get(),
                self._confluence_user_id.get(),
                self._confluence_space_key.get(),
                self._confluence_api_token.get(),
            )
        )

    def set_input_state(self, enabled: bool) -> None:
        self.set_test_connection_button_state(enabled=enabled)
        for widget in (
            self._root_url_label,
            self._root_url_entry,
            self._space_key_label,
            self._space_key_entry,
            self._parent_page_label,
            self._parent_page_entry,
            self._user_id_label,
            self._user_id_entry,
            self._api_token_label,
            self._api_token_entry,
        ):
            widget.config(state=tk.NORMAL if enabled else tk.DISABLED)

    @property
    def confluence_root_url(self) -> str:
        return self._confluence_root_url.get().strip()

    @property
    def confluence_user_id(self) -> str:
        return self._confluence_user_id.get().strip()

    @property
    def confluence_space_key(self) -> str:
        return self._confluence_space_key.get().strip()

    @property
    def confluence_parent_page(self) -> str:
        return self._confluence_parent_page.get().strip()

    @property
    def confluence_api_token(self) -> str:
        return self._confluence_api_token.get().strip()
