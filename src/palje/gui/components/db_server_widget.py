import enum
import tkinter as tk
from tkinter import ttk
from tkinter import font

# TODO: check port requirement for Entra MFA
# TODO: handle whitepace inputs (strip on getters?)

class DBServerConnectionState(enum.Enum):
    NOT_CONNECTED = enum.auto()
    CONNECTING = enum.auto()
    CONNECTED = enum.auto()


class DbServerWidget(ttk.Frame):
    """A widget for configuring database connection settings. Emits events when the connection settings change or when the connect/disconnect button is clicked."""

    _connection_state: DBServerConnectionState
    _server: tk.StringVar
    _port: tk.IntVar
    _db_name: tk.StringVar
    _username: tk.StringVar
    _password: tk.StringVar
    _fields_and_values: dict[str, tuple[tk.Misc, tk.StringVar]]

    PADDING_PX = 3

    SUPPORTED_AUTHENTICATIONS = [
        {
            "value": "AAD",
            "available_fields": ["server", "username", "db_name"],
            # Notice: AZSQL db's can be _listed_ without a db_name but changing
            # to USE one requires reconnecting to it directly -> db_name is required
            "required_fields": ["server", "username", "db_name"],
            "display_name": "Microsoft Entra MFA",
        },
        {
            "value": "SQL",
            "available_fields": ["server", "port", "username", "password", "db_name"],
            "required_fields": ["server", "username", "password"],
            "display_name": "SQL Server Authentication",
        },
        {
            "value": "Windows",
            "available_fields": ["server", "port", "db_name"],
            "required_fields": ["server"],
            "display_name": "Windows Authentication",
        },
    ]

    def __init__(
        self, parent: tk.Misc | None = None, driver_options: list[str] | None = None
    ):
        super().__init__(master=parent)

        self._connection_state = DBServerConnectionState.NOT_CONNECTED

        self._driver = tk.StringVar(value="ODBC Driver 17 for SQL Server")
        self._server = tk.StringVar(value="")
        self._port = tk.StringVar(value="1433")
        self._db_name = tk.StringVar(value="")
        self._username = tk.StringVar(value="")
        self._password = tk.StringVar(value="")
        self._auth_method = tk.StringVar(value="SQL Server Authentication")

        self._driver.trace_add("write", self._on_db_settings_changed)
        self._server.trace_add("write", self._on_db_settings_changed)
        self._port.trace_add("write", self._on_db_settings_changed)
        self._db_name.trace_add("write", self._on_db_settings_changed)
        self._username.trace_add("write", self._on_db_settings_changed)
        self._password.trace_add("write", self._on_db_settings_changed)
        self._auth_method.trace_add("write", self._on_db_settings_changed)

        default_font = font.nametofont("TkDefaultFont")
        default_font_config = default_font.actual()

        self._label_font = font.Font(**default_font_config)
        self._label_font_bold = font.Font(**default_font_config)
        self._label_font_bold.configure(weight="bold")

        db_frame = ttk.Frame(self)
        db_frame.config(padding=self.PADDING_PX)
        db_frame.columnconfigure(0, weight=1)
        db_frame.columnconfigure(1, weight=4)
        db_frame.rowconfigure((0, 1, 2, 3, 4, 5, 6), weight=1, pad=self.PADDING_PX)

        row = 0
        driver_label = ttk.Label(db_frame, text="Driver", font=self._label_font_bold)
        driver_label.grid(row=row, column=0, sticky=tk.E, ipadx=self.PADDING_PX)
        driver_combo = ttk.Combobox(
            db_frame, textvariable=self._driver, values=driver_options, state="readonly"
        )
        driver_combo.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        server_label = ttk.Label(db_frame, text="Server")
        server_label.grid(row=row, column=0, sticky=tk.E, ipadx=self.PADDING_PX)
        server_entry = ttk.Entry(db_frame, textvariable=self._server)
        server_entry.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        port_label = ttk.Label(db_frame, text="Port")
        port_label.grid(row=row, column=0, sticky=tk.E, ipadx=self.PADDING_PX)
        port_vcmd = (self.register(self._on_validate_port_value), "%P")
        port_entry = ttk.Entry(
            db_frame, textvariable=self._port, validatecommand=port_vcmd, validate="key"
        )
        port_entry.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        db_name_label = ttk.Label(db_frame, text="Database")
        db_name_label.grid(row=row, column=0, sticky=tk.E, ipadx=self.PADDING_PX)
        db_name_entry = ttk.Entry(db_frame, textvariable=self._db_name)
        db_name_entry.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        auth_label = ttk.Label(
            db_frame, text="Authentication", font=self._label_font_bold
        )
        auth_label.grid(row=row, column=0, sticky=tk.E, ipadx=self.PADDING_PX)
        auth_options = [
            auth_item["display_name"] for auth_item in self.SUPPORTED_AUTHENTICATIONS
        ]
        auth_combo = ttk.Combobox(
            db_frame,
            textvariable=self._auth_method,
            values=auth_options,
            state="readonly",
        )
        auth_combo.grid(row=row, column=1, sticky=tk.EW)
        
        row += 1
        username_label = ttk.Label(db_frame, text="Username")
        username_label.grid(row=row, column=0, sticky=tk.E, ipadx=self.PADDING_PX)
        username_entry = ttk.Entry(db_frame, textvariable=self._username)
        username_entry.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        password_label = ttk.Label(db_frame, text="Password")
        password_label.grid(row=row, column=0, sticky=tk.E, ipadx=self.PADDING_PX)
        password_entry = ttk.Entry(db_frame, textvariable=self._password, show="*")
        password_entry.grid(row=row, column=1, sticky=tk.EW)

        row += 1
        self._connect_button = ttk.Button(
            db_frame,
            text="Connect",
            command=self._on_connect_clicked,
        )
        self._connect_button.grid(row=row, column=1, sticky=tk.E, pady=self.PADDING_PX)

        # Keep refs to inputs and related items for accessing them later
        self._fields_and_values = {
            "driver": (driver_combo, self._driver, driver_label),
            "auth_method": (auth_combo, self._auth_method, auth_label),
            "server": (server_entry, self._server, server_label),
            "port": (port_entry, self._port, port_label),
            "username": (username_entry, self._username, username_label),
            "password": (password_entry, self._password, password_label),
            "db_name": (db_name_entry, self._db_name, db_name_label),
        }

        db_frame.pack(fill=tk.X, expand=True)
        self.set_connect_button_state(enabled=False)
        self._update_inputs_for_auth_method(self._auth_method.get())

    def _on_validate_port_value(self, value_if_allowed: str) -> bool:
        """Validate port input field, only allow integers"""
        is_valid = False
        if value_if_allowed == "":
            is_valid = True
        if value_if_allowed.isdigit():
            is_valid = True
        if value_if_allowed.startswith("0"):
            is_valid = False
        if not is_valid:
            self.bell()
        return is_valid

    def _on_connect_clicked(self) -> None:
        self.event_generate("<<DbServerConnect>>")

    def _on_disconnect_clicked(self) -> None:
        self.event_generate("<<DbServerDisconnect>>")

    def _on_db_settings_changed(self, *_args) -> None:
        # TODO: validate and set the connect button state accordingly
        self._update_inputs_for_auth_method(self._auth_method.get())
        self.set_connect_button_state(self.required_fields_filled())
        self.event_generate("<<DbServerParamsChanged>>")

    def get_auth_item_by_display_name(self, display_name: str) -> dict[str, str]:
        for auth_item in self.SUPPORTED_AUTHENTICATIONS:
            if auth_item["display_name"] == display_name:
                return auth_item
        raise KeyError("Unknown auth: {display_name}")

    def required_fields_filled(self) -> bool:
        """Returns True if all required input fields are filled, False otherwise"""
        auth_item = self.get_auth_item_by_display_name(self._auth_method.get())
        for field in auth_item["required_fields"]:
            if not self._fields_and_values[field][0].get():
                return False
        return True

    def _update_inputs_for_connection_state(self) -> None:
        """Enables/disables input fields based on the current connection state"""
        match self.connection_state:
            case (
                DBServerConnectionState.NOT_CONNECTED
                | DBServerConnectionState.CONNECTING
            ):
                for widget, _, label in self._fields_and_values.values():
                    label.config(state=tk.NORMAL)
                    if isinstance(widget, ttk.Combobox):
                        widget.config(state="readonly")
                    else:
                        widget.config(state=tk.NORMAL)
                    self._update_inputs_for_auth_method(self._auth_method.get())
            case DBServerConnectionState.CONNECTED:
                for widget, _, label in self._fields_and_values.values():
                    widget.config(state=tk.DISABLED)
                    label.config(state=tk.DISABLED)

    def set_connect_button_state(self, enabled: bool) -> None:
        """Enables/disables the connect/disconnect button"""
        self._connect_button.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def set_input_state(self, enabled: bool) -> None:
        """Enable or disable all input fields."""
        self.set_connect_button_state(enabled)
        for widget, _, label in self._fields_and_values.values():
            widget.config(state=tk.NORMAL if enabled else tk.DISABLED)
            label.config(state=tk.NORMAL if enabled else tk.DISABLED)
        if enabled:
            self._update_inputs_for_connection_state()
            self._update_connect_button_for_connection_state()

    def _update_connect_button_for_connection_state(self) -> None:
        """Sets the text and command of the connect button based on the current connection state"""
        match self.connection_state:
            case DBServerConnectionState.NOT_CONNECTED:
                self._connect_button.config(
                    text="Connect", command=self._on_connect_clicked
                )
                self.set_connect_button_state(enabled=True)
            case DBServerConnectionState.CONNECTING:
                self._connect_button.config(text="Connecting...", command=None)
                self.set_connect_button_state(enabled=False)
            case DBServerConnectionState.CONNECTED:
                self._connect_button.config(
                    text="Disconnect", command=self._on_disconnect_clicked
                )
                self.set_connect_button_state(enabled=True)

    def _update_inputs_for_auth_method(self, auth_method: str) -> None:
        """Enables/disables input fields based on the selected authentication method. Clears values from fields that are not available for the selected method."""
        auth_item = self.get_auth_item_by_display_name(auth_method)
        for field_name, input_tuple in self._fields_and_values.items():
            if field_name in ["auth_method", "driver"]:
                continue
            # "Reset" fields to a known state before doing actual updates
            widget, value, label = input_tuple[0], input_tuple[1], input_tuple[2]
            widget.config(state=tk.DISABLED)
            label.config(state=tk.DISABLED, font=self._label_font)
            if field_name not in auth_item["available_fields"]:
                value.set(value="")
        for field_name in auth_item["available_fields"]:
            widget, label = (
                self._fields_and_values[field_name][0],
                self._fields_and_values[field_name][2],
            )
            label.config(state=tk.NORMAL)
            label.config(font=self._label_font)
            if isinstance(widget, ttk.Combobox):
                widget.config(state="readonly")
            else:
                widget.config(state=tk.NORMAL)
        for field_name in auth_item["required_fields"]:
            label = self._fields_and_values[field_name][2]
            label.config(font=self._label_font_bold)

    @property
    def auth_method(self) -> str:
        auth_item = self.get_auth_item_by_display_name(self._auth_method.get())
        return auth_item["value"]

    @property
    def connection_state(self) -> DBServerConnectionState:
        return self._connection_state

    @connection_state.setter
    def connection_state(self, value: DBServerConnectionState) -> None:
        self._connection_state = value
        self._update_inputs_for_connection_state()
        self._update_connect_button_for_connection_state()

    @property
    def driver(self) -> str:
        return self._driver.get()

    @driver.setter
    def driver(self, value: str) -> None:
        self._driver = value

    @property
    def server(self) -> str:
        return self._server.get()

    @server.setter
    def server(self, value: str) -> None:
        self._server.set(value)

    @property
    def port(self) -> int | None:
        if self._fields_and_values["port"][0].cget("state") == tk.DISABLED:
            return None
        return self._port.get()

    @port.setter
    def port(self, value: int) -> None:
        self._port.set(value)

    @property
    def db_name(self) -> str | None:
        if self._fields_and_values["db_name"][0].cget("state") == tk.DISABLED:
            return None
        return self._db_name.get()

    @db_name.setter
    def db_name(self, value: str) -> None:
        self._db_name.set(value)

    @property
    def username(self) -> str | None:
        if self._fields_and_values["username"][0].cget("state") == tk.DISABLED:
            return None
        return self._username.get()

    @username.setter
    def username(self, value: str) -> None:
        self._username.set(value)

    @property
    def password(self) -> str | None:
        if self._fields_and_values["password"][0].cget("state") == tk.DISABLED:
            return None
        return self._password.get()

    @password.setter
    def password(self, value: str) -> None:
        self._password.set(value)
