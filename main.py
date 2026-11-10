"""SmartCalc: a calculator desktop app built with Python and Tkinter.

Run it with:  python3 main.py
"""

import threading
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk

from calculator_engine import (
    UNITS,
    CalculationError,
    apply_function,
    calculate_age,
    calculate_bmi,
    convert_currency,
    convert_units,
    currency_codes,
    download_rates,
    evaluate,
    format_number,
    graph_points,
    load_history,
    load_saved_rates,
    save_history,
)


# One calm colour theme: dark navy with a single teal accent, for good contrast.
BACKGROUND = "#0f1b26"
PANEL = "#182734"
BUTTON = "#22384a"
OPERATOR = "#2c4a60"
ACCENT = "#3fbfa8"
TEXT = "#f4f7f9"
MUTED = "#a9b8c4"
ERROR = "#ff9e8f"
BLUE = "#2f6db5"  # the "." and "C" keys
SMALL_FONT = 12  # tabs, DEG/RAD buttons and the hint use one size
FONT = "Helvetica"
TOOL_FONT = (FONT, 14)  # every word and value on the History, Convert, Graph, BMI and Age tabs

# Each button: (label on the button, what it does).
KEYPAD = [
    [("sin", "fn:sin"), ("cos", "fn:cos"), ("tan", "fn:tan"), ("√", "fn:sqrt"), ("⌫", "back")],
    [("sin⁻¹", "fn:asin"), ("cos⁻¹", "fn:acos"), ("tan⁻¹", "fn:atan"), ("x²", "square"), ("÷", "÷")],
    [("log", "fn:log"), ("ln", "fn:ln"), ("(", "("), (")", ")"), ("×", "×")],
    [("7", "7"), ("8", "8"), ("9", "9"), ("xʸ", "^"), ("−", "−")],
    [("4", "4"), ("5", "5"), ("6", "6"), ("π", "π"), ("+", "+")],
    [("1", "1"), ("2", "2"), ("3", "3"), ("x!", "fn:fact"), ("%", "percent")],
    [("±", "negate"), ("0", "0"), (".", "."), ("C", "clear"), ("=", "equals")],
]
OPERATORS = {"÷", "×", "−", "+", "^"}
# Keys that start a new calculation when pressed straight after an answer.
STARTS_NEW_NUMBER = set("0123456789.(") | {"π"}


class SmartCalc:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SmartCalc")
        self.root.geometry("500x720")
        self.root.minsize(480, 660)
        self.root.configure(bg=BACKGROUND)

        self.expression = tk.StringVar()
        self.previous = tk.StringVar()
        self.status = tk.StringVar(value="Ready")
        self.degrees = True
        self.just_calculated = False

        self._build_styles()
        notebook = ttk.Notebook(self.root, style="Calc.TNotebook")
        notebook.pack(fill="both", expand=True, padx=14, pady=14)
        notebook.add(self._build_calculator_tab(notebook), text="Calculator")
        notebook.add(self._build_history_tab(notebook), text="History")
        notebook.add(self._build_converter_tab(notebook), text="Convert")
        notebook.add(self._build_graph_tab(notebook), text="Graph")
        notebook.add(self._build_bmi_tab(notebook), text="BMI")
        notebook.add(self._build_age_tab(notebook), text="Age")

    # ---------- Look and feel ----------

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Calc.TNotebook",
            background=BACKGROUND,
            borderwidth=0,
            bordercolor=BACKGROUND,
            lightcolor=BACKGROUND,
            darkcolor=BACKGROUND,
        )
        style.configure(
            "Calc.TNotebook.Tab",
            background=PANEL,
            foreground=MUTED,
            padding=(10, 6),
            font=(FONT, SMALL_FONT),
            borderwidth=0,
            bordercolor=BACKGROUND,
            lightcolor=PANEL,
        )
        style.map(
            "Calc.TNotebook.Tab",
            background=[("selected", ACCENT)],
            foreground=[("selected", BACKGROUND)],
        )
        style.configure(
            "Calc.TCombobox",
            fieldbackground=PANEL,
            background=OPERATOR,
            foreground=TEXT,
            arrowcolor=TEXT,
            arrowsize=16,
            bordercolor=OPERATOR,
            lightcolor=PANEL,
            darkcolor=PANEL,
            padding=6,
        )
        # Keep the arrow box dark in every state (hovered, clicked, focused), so the
        # white arrow never sits on the light default colour.
        style.map(
            "Calc.TCombobox",
            background=[("pressed", ACCENT), ("active", "#35596f"), ("focus", OPERATOR), ("readonly", OPERATOR)],
            arrowcolor=[("disabled", MUTED), ("pressed", BACKGROUND), ("!disabled", TEXT)],
            fieldbackground=[("readonly", PANEL)],
            foreground=[("readonly", TEXT)],
            selectbackground=[("readonly", PANEL)],
            selectforeground=[("readonly", TEXT)],
        )
        # The drop-down list of a combobox is a plain Tk listbox.
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", BACKGROUND)
        self.root.option_add("*TCombobox*Listbox.font", TOOL_FONT)
        hover = {ACCENT: ("#33a08c", "#5cd0bb"), BLUE: ("#285f9e", "#3d80cc")}
        # Keypad buttons use a large font. DEG and RAD use the same size and
        # padding as the tab names, so the top row looks like one neat set.
        for name, colour, text, weight, size, padding in (
            ("Key", BUTTON, TEXT, "normal", 15, (2, 8)),
            ("Operator", OPERATOR, TEXT, "normal", 15, (2, 8)),
            ("Blue", BLUE, TEXT, "bold", 15, (2, 8)),
            ("Equals", ACCENT, BACKGROUND, "bold", 15, (2, 8)),
            ("Mode", PANEL, MUTED, "normal", SMALL_FONT, (10, 6)),
            ("ModeOn", ACCENT, BACKGROUND, "normal", SMALL_FONT, (10, 6)),
            ("Action", ACCENT, BACKGROUND, "normal", TOOL_FONT[1], (2, 6)),
            ("Tool", OPERATOR, TEXT, "normal", TOOL_FONT[1], (2, 6)),
        ):
            style.configure(
                f"{name}.TButton",
                background=colour,
                foreground=text,
                borderwidth=0,
                relief="flat",
                font=(FONT, size, weight),
                padding=padding,
            )
            pressed, active = hover.get(colour, ("#35596f", "#35596f"))
            style.map(
                f"{name}.TButton",
                background=[("pressed", pressed), ("active", active)],
                foreground=[("active", text)],
            )

    def _tab_frame(self, parent: ttk.Notebook) -> tk.Frame:
        return tk.Frame(parent, bg=BACKGROUND, padx=12, pady=14)

    def _label(self, parent: tk.Widget, text: str = "", **options) -> tk.Label:
        options.setdefault("font", TOOL_FONT)
        options.setdefault("fg", TEXT)
        return tk.Label(parent, text=text, bg=BACKGROUND, anchor="w", **options)

    def _entry(self, parent: tk.Widget, **options) -> tk.Entry:
        return tk.Entry(
            parent,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=OPERATOR,
            highlightcolor=ACCENT,
            **options,
        )

    # ---------- Calculator tab ----------

    def _build_calculator_tab(self, notebook: ttk.Notebook) -> tk.Frame:
        tab = self._tab_frame(notebook)

        modes = tk.Frame(tab, bg=BACKGROUND)
        modes.pack(fill="x", pady=(0, 10))
        self.deg_button = ttk.Button(modes, text="DEG", width=4, command=lambda: self._set_mode(True))
        self.rad_button = ttk.Button(modes, text="RAD", width=4, command=lambda: self._set_mode(False))
        self.deg_button.pack(side="left")
        self.rad_button.pack(side="left", padx=(2, 0))
        self._label(modes, "Keyboard: Enter =   Esc clear", fg=MUTED, font=(FONT, SMALL_FONT)).pack(side="right")

        display = tk.Frame(tab, bg=PANEL, padx=12, pady=10)
        display.pack(fill="x", pady=(0, 10))
        tk.Label(
            display, textvariable=self.previous, bg=PANEL, fg=MUTED, anchor="e", font=(FONT, 13)
        ).pack(fill="x")
        self.entry = tk.Entry(
            display,
            textvariable=self.expression,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=0,
            justify="right",
            font=(FONT, 28),
        )
        self.entry.pack(fill="x", ipady=4)
        self.status_label = tk.Label(
            display, textvariable=self.status, bg=PANEL, fg=MUTED, anchor="e", font=(FONT, 12)
        )
        self.status_label.pack(fill="x")
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda _event: self._equals())
        self.entry.bind("<KP_Enter>", lambda _event: self._equals())
        self.entry.bind("<equal>", lambda _event: self._equals() or "break")
        self.entry.bind("<Escape>", lambda _event: self._clear())
        self.entry.bind("<Key>", self._on_key, add="+")

        keypad = tk.Frame(tab, bg=BACKGROUND)
        keypad.pack(fill="both", expand=True)
        # Every column and row gets the same weight, so all buttons are the same size.
        for column in range(5):
            keypad.columnconfigure(column, weight=1, uniform="key")
        for row in range(len(KEYPAD)):
            keypad.rowconfigure(row, weight=1, uniform="key")

        for row_index, row in enumerate(KEYPAD):
            for column_index, (label, action) in enumerate(row):
                if action == "equals":
                    style = "Equals.TButton"
                elif action in (".", "clear"):
                    style = "Blue.TButton"
                elif label.isdigit():
                    style = "Key.TButton"
                else:
                    style = "Operator.TButton"
                ttk.Button(
                    keypad,
                    text=label,
                    style=style,
                    command=lambda value=action: self._press(value),
                ).grid(row=row_index, column=column_index, sticky="nsew", padx=3, pady=3)
        self._set_mode(True)
        return tab

    def _set_mode(self, degrees: bool) -> None:
        self.degrees = degrees
        self.deg_button.configure(style="ModeOn.TButton" if degrees else "Mode.TButton")
        self.rad_button.configure(style="Mode.TButton" if degrees else "ModeOn.TButton")
        self._show_status("Angles in degrees" if degrees else "Angles in radians")

    def _on_key(self, event: tk.Event) -> None:
        # Typing a new number straight after an answer starts a new calculation.
        if self.just_calculated and event.char in STARTS_NEW_NUMBER:
            self.expression.set("")
        if event.char:
            self.just_calculated = False
            self._show_status("Ready")

    def _press(self, action: str) -> None:
        if action == "clear":
            self._clear()
        elif action == "back":
            self.expression.set(self.expression.get()[:-1])
            self.just_calculated = False
        elif action == "equals":
            self._equals()
        elif action.startswith("fn:"):
            self._apply(action[3:])
        elif action == "square":
            self._calculate_into_display(f"({self.expression.get()})^2", label="sqr")
        elif action == "negate":
            self._calculate_into_display(f"−({self.expression.get()})", label="negate")
        elif action == "percent":
            self._calculate_into_display(f"({self.expression.get()})÷100", label="percent")
        else:
            if self.just_calculated and action in STARTS_NEW_NUMBER:
                self.expression.set("")
            self.expression.set(self.expression.get() + action)
            self.just_calculated = False
            self._show_status("Ready")
        self.entry.focus_set()
        self.entry.icursor(tk.END)

    def _apply(self, name: str) -> None:
        """A function button works on the number already on screen: 81 then √ gives 9."""
        current = self.expression.get().strip()
        if not current:
            # Nothing on screen yet, so start a typed function such as sin(30).
            self.expression.set(f"{name}(")
            self.just_calculated = False
            return
        try:
            value = evaluate(current, degrees=self.degrees)
            result = apply_function(name, value, degrees=self.degrees)
        except CalculationError as error:
            self._show_error(error)
            return
        shown_name = "√" if name == "sqrt" else name
        self._show_result(f"{shown_name}({current})", result)

    def _calculate_into_display(self, expression: str, label: str) -> None:
        if not self.expression.get().strip():
            self._show_error(CalculationError("Enter a number first"))
            return
        try:
            result = evaluate(expression, degrees=self.degrees)
        except CalculationError as error:
            self._show_error(error)
            return
        self._show_result(f"{label}({self.expression.get()})", result)

    def _equals(self) -> None:
        current = self.expression.get()
        try:
            result = evaluate(current, degrees=self.degrees)
        except CalculationError as error:
            self._show_error(error)
            return
        self._show_result(current, result)

    def _show_result(self, worked: str, result: float) -> None:
        answer = format_number(result)
        # The sum moves to the small line and only the answer stays on the big line.
        self.previous.set(f"{worked} =")
        self.expression.set(answer)
        self.history.insert(0, f"{worked} = {answer}")
        save_history(list(self.history.get(0, tk.END)))
        self.just_calculated = True
        self._show_status("Ready")

    def _show_error(self, error: CalculationError) -> None:
        self.previous.set("")
        self.status.set(f"Error: {error}")
        self.status_label.configure(fg=ERROR)

    def _show_status(self, text: str) -> None:
        self.status.set(text)
        self.status_label.configure(fg=MUTED)

    def _clear(self) -> None:
        self.expression.set("")
        self.previous.set("")
        self.just_calculated = False
        self._show_status("Ready")

    # ---------- History tab ----------

    def _build_history_tab(self, notebook: ttk.Notebook) -> tk.Frame:
        tab = self._tab_frame(notebook)
        self._label(tab, "Newest first, saved even after you close the app", fg=MUTED).pack(
            fill="x", pady=(0, 8)
        )
        self.history = tk.Listbox(
            tab,
            bg=PANEL,
            fg=TEXT,
            selectbackground=ACCENT,
            selectforeground=BACKGROUND,
            relief="flat",
            highlightthickness=0,
            font=TOOL_FONT,
            activestyle="none",
        )
        self.history.pack(fill="both", expand=True)
        for item in load_history():
            self.history.insert(tk.END, item)
        self.history.bind("<Double-Button-1>", lambda _event: self._reuse_answer())

        buttons = tk.Frame(tab, bg=BACKGROUND)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Use answer", style="Action.TButton", command=self._reuse_answer).pack(
            side="left", expand=True, fill="x", padx=(0, 4)
        )
        ttk.Button(
            buttons,
            text="Clear history",
            style="Tool.TButton",
            command=self._clear_history,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))
        return tab

    def _reuse_answer(self) -> None:
        selected = self.history.curselection()
        if selected:
            answer = self.history.get(selected[0]).rsplit("=", 1)[1].strip()
            self.expression.set(answer)
            self.just_calculated = True
            self._show_status("Answer copied from history")

    def _clear_history(self) -> None:
        self.history.delete(0, tk.END)
        save_history([])

    # ---------- Converter tab ----------

    def _build_converter_tab(self, notebook: ttk.Notebook) -> tk.Frame:
        tab = self._tab_frame(notebook)
        self._label(tab, "Unit converter", font=TOOL_FONT).pack(fill="x")
        self._label(tab, "Currency, length, weight, temperature and more", fg=MUTED).pack(
            fill="x", pady=(2, 16)
        )

        self.category = tk.StringVar(value="Length")
        self.from_unit = tk.StringVar()
        self.to_unit = tk.StringVar()
        self.convert_value = tk.StringVar(value="1")
        self.rates = None  # Exchange rates, filled in when Currency is first chosen.
        self.rates_status = ""
        self.rates_download: dict = {}

        self._label(tab, "Type of unit").pack(fill="x")
        category_box = ttk.Combobox(
            tab, textvariable=self.category, values=[*UNITS, "Currency"], state="readonly",
            style="Calc.TCombobox", font=TOOL_FONT,
        )
        category_box.pack(fill="x", pady=(4, 12))
        category_box.bind("<<ComboboxSelected>>", lambda _event: self._fill_units())

        self._label(tab, "Value").pack(fill="x")
        value_entry = self._entry(tab, textvariable=self.convert_value, font=TOOL_FONT)
        value_entry.pack(fill="x", ipady=6, pady=(4, 12))

        units = tk.Frame(tab, bg=BACKGROUND)
        units.pack(fill="x", pady=(0, 16))
        units.columnconfigure(0, weight=1)
        units.columnconfigure(2, weight=1)
        self._label(units, "From").grid(row=0, column=0, sticky="w")
        self._label(units, "To").grid(row=0, column=2, sticky="w")
        self.from_box = ttk.Combobox(
            units, textvariable=self.from_unit, state="readonly", style="Calc.TCombobox", font=TOOL_FONT
        )
        self.to_box = ttk.Combobox(
            units, textvariable=self.to_unit, state="readonly", style="Calc.TCombobox", font=TOOL_FONT
        )
        self.from_box.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(units, text="⇄", width=3, style="Tool.TButton", command=self._swap_units).grid(
            row=1, column=1, padx=6, pady=(4, 0)
        )
        self.to_box.grid(row=1, column=2, sticky="ew", pady=(4, 0))

        self.convert_result = self._label(tab, "", font=TOOL_FONT, wraplength=400, justify="left")
        self.convert_result.pack(fill="x", pady=(8, 4))
        self.convert_note = self._label(tab, "", fg=MUTED)
        self.convert_note.pack(fill="x")
        self.rates_label = self._label(tab, "", fg=MUTED, font=TOOL_FONT, wraplength=440, justify="left")
        self.rates_label.pack(fill="x", pady=(10, 0))

        # The answer updates by itself whenever the value or a unit changes.
        for variable in (self.convert_value, self.from_unit, self.to_unit):
            variable.trace_add("write", lambda *_args: self._convert())
        self._fill_units()
        return tab

    def _unit_names(self) -> list[str]:
        if self.category.get() == "Currency":
            return currency_codes(self.rates) if self.rates else []
        return list(UNITS[self.category.get()])

    def _fill_units(self) -> None:
        if self.category.get() == "Currency":
            self._start_rates_download()
        names = self._unit_names()
        state = "readonly" if names else "disabled"
        self.from_box.configure(values=names, state=state)
        self.to_box.configure(values=names, state=state)
        if not names:
            self.from_unit.set("")
            self.to_unit.set("")
            self._convert()
            return
        self.from_unit.set(names[0])
        self.to_unit.set(names[1] if self.category.get() in ("Temperature", "Currency") else names[-1])

    def _start_rates_download(self) -> None:
        """Get today's exchange rates once per session, without freezing the window."""
        # Download once per session, but try again if the last try failed.
        if self.rates_download and "error" not in self.rates_download:
            return
        self.rates = self.rates or load_saved_rates()
        self.rates_status = "Downloading today's exchange rates..."
        self.rates_download = {"running": True}
        download_state = self.rates_download

        def download() -> None:
            # This runs in the background, so it must not touch the window directly.
            try:
                download_state["result"] = download_rates()
            except CalculationError as error:
                download_state["error"] = str(error)

        threading.Thread(target=download, daemon=True).start()
        self.root.after(200, self._check_rates_download)

    def _check_rates_download(self) -> None:
        if "result" not in self.rates_download and "error" not in self.rates_download:
            self.root.after(200, self._check_rates_download)
            return
        had_rates = self.rates is not None
        if "result" in self.rates_download:
            self.rates = self.rates_download["result"]
            self.rates_status = f"Rates: {self.rates['source']}, {self.rates['date']}"
        elif self.rates:
            self.rates_status = f"Offline: using saved rates from {self.rates['date']}"
        else:
            self.rates_status = (
                f"Error: {self.rates_download['error']}. "
                "Choose another type and then Currency again to retry."
            )
        if self.category.get() == "Currency":
            if had_rates or self.rates is None:
                # Keep the chosen currencies; only the rates (or the message) changed.
                self.from_box.configure(values=self._unit_names())
                self.to_box.configure(values=self._unit_names())
                self._convert()
            else:
                self._fill_units()

    def _swap_units(self) -> None:
        from_unit, to_unit = self.from_unit.get(), self.to_unit.get()
        self.from_unit.set(to_unit)
        self.to_unit.set(from_unit)

    def _convert(self) -> None:
        category, from_unit, to_unit = self.category.get(), self.from_unit.get(), self.to_unit.get()
        self.rates_label.configure(text=self.rates_status if category == "Currency" else "")
        names = self._unit_names()
        if category == "Currency" and not names:
            self.convert_result.configure(text="")
            self.convert_note.configure(text="Exchange rates are not available yet")
            return
        if from_unit not in names or to_unit not in names:
            return  # The unit lists are still being filled in.
        text = self.convert_value.get().strip()
        if not text:
            self.convert_result.configure(text="")
            self.convert_note.configure(text="Type a value to convert")
            return
        try:
            if category == "Currency":
                result = convert_currency(float(text), from_unit, to_unit, self.rates)
            else:
                result = convert_units(float(text), category, from_unit, to_unit)
        except ValueError as error:
            message = str(error) if isinstance(error, CalculationError) else "Enter numbers only"
            self.convert_result.configure(text="Error", fg=ERROR)
            self.convert_note.configure(text=message)
            return
        if category == "Currency":
            answer = f"{result:,.2f}"  # Money is shown with two decimals.
        else:
            # 8 significant figures is plenty for everyday conversions.
            answer = format_number(float(f"{result:.8g}"))
        self.convert_result.configure(text=f"{answer} {to_unit}", fg=ACCENT)
        self.convert_note.configure(text=f"{text} {from_unit} = {answer} {to_unit}")

    # ---------- Graph tab ----------

    def _build_graph_tab(self, notebook: ttk.Notebook) -> tk.Frame:
        tab = self._tab_frame(notebook)
        self._label(tab, "Graph plotter", font=TOOL_FONT).pack(fill="x")
        self._label(tab, "Type a formula using x, for example x^2 or 2sin(x)", fg=MUTED).pack(
            fill="x", pady=(2, 12)
        )

        inputs = tk.Frame(tab, bg=BACKGROUND)
        inputs.pack(fill="x")
        inputs.columnconfigure(1, weight=1)
        self._label(inputs, "y =").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.formula = self._entry(inputs, font=TOOL_FONT)
        self.formula.insert(0, "sin(x)")
        self.formula.grid(row=0, column=1, columnspan=4, sticky="ew", ipady=5)

        self._label(inputs, "From x").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.x_from = self._entry(inputs, font=TOOL_FONT, width=7)
        self.x_from.insert(0, "-360")
        self.x_from.grid(row=1, column=1, sticky="w", pady=(10, 0), ipady=4)
        self._label(inputs, "To x").grid(row=1, column=2, sticky="e", padx=(10, 8), pady=(10, 0))
        self.x_to = self._entry(inputs, font=TOOL_FONT, width=7)
        self.x_to.insert(0, "360")
        self.x_to.grid(row=1, column=3, sticky="w", pady=(10, 0), ipady=4)
        ttk.Button(inputs, text="Plot", style="Action.TButton", command=self._plot).grid(
            row=1, column=4, sticky="e", padx=(10, 0), pady=(10, 0)
        )
        for entry in (self.formula, self.x_from, self.x_to):
            entry.bind("<Return>", lambda _event: self._plot())

        self.canvas = tk.Canvas(tab, bg=PANEL, highlightthickness=0, height=330)
        self.canvas.pack(fill="both", expand=True, pady=(12, 6))
        self.canvas.bind("<Configure>", lambda _event: self._plot())
        self.canvas.bind("<Motion>", self._show_point)
        self.graph_note = self._label(tab, "", fg=MUTED, font=TOOL_FONT, wraplength=440, justify="left")
        self.graph_note.pack(fill="x")
        self.graph_area = None
        return tab

    def _plot(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        self.graph_area = None
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 50 or height < 50:
            return  # The window is still opening.
        try:
            x_from, x_to = float(self.x_from.get()), float(self.x_to.get())
            points = graph_points(self.formula.get(), x_from, x_to, degrees=self.degrees)
        except ValueError as error:
            message = str(error) if isinstance(error, CalculationError) else "From x and To x must be numbers"
            if message == "Invalid input":
                message = "Invalid formula: use x, numbers and the calculator functions"
            self.graph_note.configure(text=f"Error: {message}", fg=ERROR)
            return
        ys = sorted(y for _x, y in points if y is not None)
        if not ys:
            self.graph_note.configure(text="Error: no answers in this range of x", fg=ERROR)
            return

        # Ignore the extreme 2% at each end, so tan(x) does not squash the graph flat.
        cut = len(ys) // 50
        y_low, y_high = ys[cut], ys[-1 - cut]
        if y_high - y_low < 1e-9:
            y_low, y_high = y_low - 1, y_high + 1
        padding = (y_high - y_low) * 0.1
        y_low, y_high = y_low - padding, y_high + padding

        left, right, top, bottom = 62, width - 18, 14, height - 34
        self.graph_area = (left, right, top, bottom, x_from, x_to, y_low, y_high)

        def to_pixel(x: float, y: float) -> tuple[float, float]:
            px = left + (x - x_from) / (x_to - x_from) * (right - left)
            py = bottom - (y - y_low) / (y_high - y_low) * (bottom - top)
            return px, py

        # Light grid lines, then the x and y axes if they are in view.
        for step in range(5):
            gx = left + (right - left) * step / 4
            gy = top + (bottom - top) * step / 4
            canvas.create_line(gx, top, gx, bottom, fill=BUTTON)
            canvas.create_line(left, gy, right, gy, fill=BUTTON)
        if y_low <= 0 <= y_high:
            canvas.create_line(left, to_pixel(x_from, 0)[1], right, to_pixel(x_from, 0)[1], fill=MUTED)
        if x_from <= 0 <= x_to:
            canvas.create_line(to_pixel(0, 0)[0], top, to_pixel(0, 0)[0], bottom, fill=MUTED)

        # Draw the curve piece by piece, lifting the pen at gaps and sudden jumps.
        span = y_high - y_low
        line: list[float] = []
        previous = None
        for x, y in points:
            jump = previous is not None and y is not None and abs(y - previous) > span
            if y is None or y < y_low - span or y > y_high + span or jump:
                if len(line) >= 4:
                    canvas.create_line(*line, fill=ACCENT, width=2)
                line = []
            if y is not None and y_low - span <= y <= y_high + span:
                line.extend(to_pixel(x, y))
            previous = y
        if len(line) >= 4:
            canvas.create_line(*line, fill=ACCENT, width=2)
        # Cover anything drawn outside the grid, then write the values along the edges.
        canvas.create_rectangle(0, 0, width, top, fill=PANEL, outline="")
        canvas.create_rectangle(0, bottom, width, height, fill=PANEL, outline="")
        for step in range(5):
            gx = left + (right - left) * step / 4
            gy = top + (bottom - top) * step / 4
            x_value = x_from + (x_to - x_from) * step / 4
            y_value = y_high - (y_high - y_low) * step / 4
            canvas.create_text(gx, bottom + 18, text=f"{x_value:.3g}", fill=MUTED, font=TOOL_FONT)
            canvas.create_text(left - 4, gy, text=f"{y_value:.3g}", fill=MUTED, font=TOOL_FONT, anchor="e")

        unit = "degrees" if self.degrees else "radians"
        self.graph_note.configure(
            text=f"Angles in {unit}. Point at the graph to read values.",
            fg=MUTED,
        )

    def _show_point(self, event: tk.Event) -> None:
        if not self.graph_area:
            return
        left, right, top, bottom, x_from, x_to, _y_low, _y_high = self.graph_area
        if not (left <= event.x <= right and top <= event.y <= bottom):
            return
        x = x_from + (event.x - left) / (right - left) * (x_to - x_from)
        try:
            y_value = graph_points(self.formula.get(), x, x + 1, degrees=self.degrees, steps=1)[0][1]
        except CalculationError:
            y_value = None
        y = "no answer" if y_value is None else format_number(float(f"{y_value:.6g}"))
        self.graph_note.configure(text=f"x = {x:.4g}   y = {y}", fg=TEXT)

    # ---------- BMI tab ----------

    def _build_bmi_tab(self, notebook: ttk.Notebook) -> tk.Frame:
        tab = self._tab_frame(notebook)
        self._label(tab, "Body mass index", font=TOOL_FONT).pack(fill="x")
        self._label(tab, "A quick health check from weight and height", fg=MUTED).pack(fill="x", pady=(2, 16))

        self._label(tab, "Weight (kg)").pack(fill="x")
        self.weight = self._entry(tab, font=TOOL_FONT)
        self.weight.pack(fill="x", ipady=6, pady=(4, 12))
        self._label(tab, "Height (cm)").pack(fill="x")
        self.height = self._entry(tab, font=TOOL_FONT)
        self.height.pack(fill="x", ipady=6, pady=(4, 16))
        self.height.bind("<Return>", lambda _event: self._bmi())

        ttk.Button(tab, text="Calculate BMI", style="Action.TButton", command=self._bmi).pack(fill="x")
        self.bmi_result = self._label(tab, "", font=TOOL_FONT)
        self.bmi_result.pack(fill="x", pady=(20, 4))
        self.bmi_note = self._label(tab, "", fg=MUTED, wraplength=380, justify="left")
        self.bmi_note.pack(fill="x")
        return tab

    def _bmi(self) -> None:
        try:
            weight = float(self.weight.get())
            height = float(self.height.get())
            bmi, category = calculate_bmi(weight, height)
        except ValueError as error:
            message = str(error) if isinstance(error, CalculationError) else "Enter numbers only"
            self.bmi_result.configure(text="Error", fg=ERROR)
            self.bmi_note.configure(text=message)
            return
        self.bmi_result.configure(text=f"BMI {bmi}: {category}", fg=ACCENT)
        self.bmi_note.configure(text="The healthy range for adults is 18.5 to 24.9 (WHO).")

    # ---------- Age tab ----------

    def _build_age_tab(self, notebook: ttk.Notebook) -> tk.Frame:
        tab = self._tab_frame(notebook)
        self._label(tab, "Age calculator", font=TOOL_FONT).pack(fill="x")
        self._label(tab, "Exact age and days to the next birthday", fg=MUTED).pack(fill="x", pady=(2, 16))

        self._label(tab, "Date of birth (DD-MM-YYYY)").pack(fill="x")
        self.birth = self._entry(tab, font=TOOL_FONT)
        self.birth.pack(fill="x", ipady=6, pady=(4, 16))
        self.birth.bind("<Return>", lambda _event: self._age())

        ttk.Button(tab, text="Calculate age", style="Action.TButton", command=self._age).pack(fill="x")
        self.age_result = self._label(tab, "", font=TOOL_FONT, wraplength=380, justify="left")
        self.age_result.pack(fill="x", pady=(20, 4))
        self.age_note = self._label(tab, "", fg=MUTED)
        self.age_note.pack(fill="x")
        return tab

    def _age(self) -> None:
        try:
            birth = datetime.strptime(self.birth.get().strip(), "%d-%m-%Y").date()
            years, months, days, to_birthday = calculate_age(birth, date.today())
        except ValueError as error:
            message = str(error) if isinstance(error, CalculationError) else "Use the format DD-MM-YYYY"
            self.age_result.configure(text="Error", fg=ERROR)
            self.age_note.configure(text=message)
            return
        self.age_result.configure(text=f"{years} years, {months} months, {days} days", fg=ACCENT)
        if to_birthday == 0:
            self.age_note.configure(text="Happy birthday!")
        else:
            self.age_note.configure(text=f"Next birthday in {to_birthday} days")


def main() -> None:
    root = tk.Tk()
    SmartCalc(root)
    root.mainloop()


if __name__ == "__main__":
    main()
