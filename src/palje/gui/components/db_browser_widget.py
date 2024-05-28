import tkinter as tk
from tkinter import ttk
from tkinter import font


class DbBrowserWidget(ttk.Frame):

    _selected_database: tk.StringVar
    _available_databases: list[str]
    _available_schemas: list[str]

    _db_listbox: tk.Listbox
    _database_label: ttk.Label
    _schemas_listbox: tk.Listbox
    _schemas_label: ttk.Label

    PADDING_PX = 3

    def __init__(
        self, parent: tk.Misc | None = None, databases: list[str] | None = None
    ):
        super().__init__(master=parent)

        self._available_databases = databases if databases is not None else []
        self._available_schemas = []
        self._available_db_objects = []

        self._selected_database = tk.StringVar()

        default_font = font.nametofont("TkDefaultFont")
        default_font_config = default_font.actual()
        self._label_font_bold = font.Font(**default_font_config)
        self._label_font_bold.configure(weight="bold")

        self.config(padding=self.PADDING_PX)
        self.columnconfigure((0, 1), weight=1)
        self.rowconfigure((0, 1), weight=1)

        self._database_label = ttk.Label(self, text="Database", font=self._label_font_bold)
        self._database_label.grid(row=0, column=0, sticky=tk.EW, ipadx=self.PADDING_PX)
        self._db_listbox = tk.Listbox(self, exportselection=False, activestyle="none")
        for db in self._available_databases:
            self._db_listbox.insert(tk.END, db)
        self._db_listbox.bind("<<ListboxSelect>>", lambda _: self._on_db_selected())
        self._db_listbox.grid(row=1, column=0, sticky=tk.EW, ipadx=self.PADDING_PX)

        self._schemas_label = ttk.Label(self, text="Schema filter", )
        self._schemas_label.grid(
            row=0,
            column=1,
            sticky=tk.EW,
            ipadx=self.PADDING_PX,
        )
        self._schemas_listbox = tk.Listbox(
            self, selectmode="multiple", exportselection=False, activestyle="none"
        )
        self._schemas_listbox.bind("<<ListboxSelect>>", lambda _: self._on_schemas_selected())
        self._schemas_listbox.grid(row=1, column=1, sticky=tk.EW, ipadx=self.PADDING_PX)

    def _on_db_selected(self) -> None:
        self._selected_database.set(
            self._db_listbox.get(self._db_listbox.curselection()[0])
        )
        self.event_generate("<<DatabaseSelectionChanged>>")

    def _on_schemas_selected(self) -> None:
        self.event_generate("<<DatabaseSchemaSelectionChanged>>")

    def set_input_state(self, enabled: bool) -> None:
        """Enable or disable all input fields."""
        self._database_label.config(state=tk.NORMAL if enabled else tk.DISABLED)
        self._schemas_label.config(state=tk.NORMAL if enabled else tk.DISABLED)
        self._db_listbox.config(state=tk.NORMAL if enabled else tk.DISABLED)
        self._schemas_listbox.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def required_fields_filled(self) -> bool:
        """Check if all required fields are filled."""
        return len(self._db_listbox.curselection()) == 1

    @property
    def available_databases(self) -> list[str]:
        return self._available_databases

    @available_databases.setter
    def available_databases(self, value: list[str]) -> None:
        self._available_databases = value
        while self._db_listbox.size() > 0:
            self._db_listbox.delete(0, tk.END)
        for db in self._available_databases:
            self._db_listbox.insert(tk.END, db)

    @property
    def selected_database(self) -> str | None:
        return (
            self._selected_database.get()
            if self._selected_database is not None
            else None
        )

    @property
    def available_schemas(self) -> list[str]:
        return self._available_schemas

    @available_schemas.setter
    def available_schemas(self, value: list[str]) -> None:
        self._available_schemas = value
        while self._schemas_listbox.size() > 0:
            self._schemas_listbox.delete(0, tk.END)
        for schema in self._available_schemas:
            self._schemas_listbox.insert(tk.END, schema)

    @property
    def selected_schemas(self) -> list[str]:
        return [
            self._schemas_listbox.get(i) for i in self._schemas_listbox.curselection()
        ]
