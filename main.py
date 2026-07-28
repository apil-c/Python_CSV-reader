import csv
import sqlite3
import statistics
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ── Colors and fonts used throughout the app ───────────────────
BACKGROUND_COLOR = "#FAF7F2"
TERRACOTTA_COLOR = "#C0533A"
SAGE_COLOR = "#7A9E87"
SAND_COLOR = "#E8DDD0"
DARK_TEXT_COLOR = "#2B2B2B"
MUTED_TEXT_COLOR = "#8A8279"
LIGHT_ROW_COLOR = "#F5EFE8"

FONT_NAME = "Calibri"

SALARY_COLUMN_GUESSES = (
    "BaseSalary", "Salary", "salary", "Base Pay", "TotalPay",
    "base_salary", "SALARY", "Annual Salary", "AnnualSalary",
    "Balance", "Score",
)

# Column names that likely represent a unique row ID.
ID_COLUMN_GUESSES = ("id", "recordid", "empid", "employeeid", "record_id", "emp_id")

# ── App state (filled in once data is loaded) ───────────────────
all_rows = []          # every row loaded from the CSV/database
column_types = {}      # column name -> "int" / "float" / "text"
filter_widgets = {}    # column name -> StringVar (text) or (min_var, max_var) for numbers


# =================================================================
# Data helper functions
# =================================================================

def to_number(text):
    """Try to convert a string to a float. Return None if it isn't a number."""
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def looks_like_int(text):
    try:
        int(text)
        return True
    except ValueError:
        return False


def looks_like_float(text):
    try:
        float(text)
        return True
    except ValueError:
        return False


def detect_column_types(rows):
    """Look at every value in each column and guess whether the column
    holds whole numbers, decimal numbers, or plain text."""
    types = {}
    first_row = rows[0]

    for column_name in first_row.keys():
        # collect all non-empty values in this column
        values = []
        for row in rows:
            value = row[column_name].strip()
            if value:
                values.append(value)

        if all(looks_like_int(v) for v in values):
            types[column_name] = "int"
        elif all(looks_like_float(v) for v in values):
            types[column_name] = "float"
        else:
            types[column_name] = "text"

    return types


def get_column_min_max(column_name):
    """Return the smallest and largest numeric value found in a column."""
    numbers = []
    for row in all_rows:
        number = to_number(row[column_name])
        if number is not None:
            numbers.append(number)

    if numbers:
        return min(numbers), max(numbers)
    return 0, 100


def get_unique_text_values(column_name):
    """Return a sorted list of the distinct values found in a text column."""
    values = set()
    for row in all_rows:
        value = row[column_name].strip()
        if value:
            values.add(value)
    return sorted(values)


def get_id_column():
    """Pick the column to use as each table row's unique ID."""
    if not all_rows:
        return None

    columns = list(all_rows[0].keys())
    for column_name in columns:
        if column_name.lower() in ID_COLUMN_GUESSES:
            return column_name

    # no obvious ID column found, just use the first column
    return columns[0]


# =================================================================
# Table display
# =================================================================

def show_rows_in_table(rows):
    """Clear the table and re-fill it with the given rows."""
    tree.delete(*tree.get_children())

    id_column = get_id_column()
    used_ids = set()

    for index, row in enumerate(rows):
        row_id = ""
        if id_column and row.get(id_column):
            row_id = str(row[id_column]).strip()

        # if two rows share the same ID (or it's blank), fall back to the
        # row's position so Treeview doesn't reject it as a duplicate
        if not row_id or row_id in used_ids:
            row_id = str(index)
        used_ids.add(row_id)

        # alternate row colors for readability
        stripe = "even" if index % 2 == 0 else "odd"
        tree.insert("", "end", iid=row_id, values=list(row.values()), tags=(stripe,))

    status_text.set(f"  {len(rows)} of {len(all_rows)} records shown")


def apply_filters(*_ignored_args):
    """Re-filter the full data set based on the search box and every
    column filter, then refresh the table."""
    if not all_rows:
        return

    search_text = search_text_var.get().lower().strip()
    filtered_rows = []

    for row in all_rows:
        if not row_matches_search(row, search_text):
            continue
        if not row_matches_all_filters(row):
            continue
        filtered_rows.append(row)

    show_rows_in_table(filtered_rows)


def row_matches_search(row, search_text):
    """True if the search box is empty, or the search text appears
    somewhere in the row."""
    if not search_text:
        return True
    for value in row.values():
        if search_text in str(value).lower():
            return True
    return False


def row_matches_all_filters(row):
    """True if the row satisfies every column filter currently set."""
    for column_name, widget in filter_widgets.items():
        column_type = column_types.get(column_name, "text")

        if column_type in ("int", "float"):
            min_var, max_var = widget
            low = to_number(min_var.get().strip())
            high = to_number(max_var.get().strip())
            value = to_number(row[column_name])

            if low is not None and (value is None or value < low):
                return False
            if high is not None and (value is None or value > high):
                return False

        else:  # text column
            chosen_value = widget.get()
            if chosen_value and chosen_value != "All":
                if row[column_name].strip() != chosen_value:
                    return False

    return True


# =================================================================
# Filter panel (left sidebar)
# =================================================================

def add_section_label(parent, text):
    """Create a small titled frame used as the container for one
    column's filter controls."""
    section = tk.Frame(parent, bg=SAND_COLOR)
    section.pack(fill="x", padx=10, pady=4)
    tk.Label(section, text=text, anchor="w", bg=SAND_COLOR,
             fg=DARK_TEXT_COLOR, font=(FONT_NAME, 10, "bold")).pack(fill="x")
    return section


def make_styled_entry(parent, variable, width=9):
    return tk.Entry(parent, textvariable=variable, width=width, font=(FONT_NAME, 10),
                     bg="white", fg=DARK_TEXT_COLOR, relief="flat",
                     highlightthickness=1, highlightbackground=MUTED_TEXT_COLOR,
                     highlightcolor=TERRACOTTA_COLOR)


def build_numeric_filter(parent, column_name):
    """Build a Min/Max range filter for a numeric column."""
    low, high = get_column_min_max(column_name)
    number_format = "{:,.0f}" if column_types[column_name] == "int" else "{:,.2f}"

    section = add_section_label(parent, column_name)
    range_text = f"Range: {number_format.format(low)} — {number_format.format(high)}"
    tk.Label(section, text=range_text, bg=SAND_COLOR, fg=MUTED_TEXT_COLOR,
             font=(FONT_NAME, 8)).pack(anchor="w", pady=(2, 4))

    min_var = tk.StringVar()
    max_var = tk.StringVar()
    filter_widgets[column_name] = (min_var, max_var)

    row = tk.Frame(section, bg=SAND_COLOR)
    row.pack(fill="x")

    min_box = tk.Frame(row, bg=SAND_COLOR)
    min_box.pack(side="left", expand=True, fill="x", padx=(0, 4))
    tk.Label(min_box, text="Min", bg=SAND_COLOR, fg=MUTED_TEXT_COLOR,
             font=(FONT_NAME, 8)).pack(anchor="w")
    make_styled_entry(min_box, min_var).pack(fill="x", ipady=4)
    min_var.trace_add("write", apply_filters)

    max_box = tk.Frame(row, bg=SAND_COLOR)
    max_box.pack(side="left", expand=True, fill="x")
    tk.Label(max_box, text="Max", bg=SAND_COLOR, fg=MUTED_TEXT_COLOR,
             font=(FONT_NAME, 8)).pack(anchor="w")
    make_styled_entry(max_box, max_var).pack(fill="x", ipady=4)
    max_var.trace_add("write", apply_filters)

    def reset_this_filter():
        min_var.set("")
        max_var.set("")

    tk.Button(section, text="Reset", command=reset_this_filter, bg=SAND_COLOR,
              fg=MUTED_TEXT_COLOR, font=(FONT_NAME, 8), relief="flat",
              cursor="hand2").pack(anchor="e", pady=(4, 0))


def build_text_filter(parent, column_name):
    """Build a dropdown filter for a text column."""
    section = add_section_label(parent, column_name)

    chosen_value = tk.StringVar(value="All")
    filter_widgets[column_name] = chosen_value

    options = ["All"] + get_unique_text_values(column_name)
    dropdown = ttk.Combobox(section, textvariable=chosen_value, values=options,
                             state="readonly", font=(FONT_NAME, 10))
    dropdown.pack(fill="x", pady=(4, 0))
    chosen_value.trace_add("write", apply_filters)


def build_filter_panel():
    """Rebuild the entire left-hand filter panel from scratch, one
    section per column."""
    for widget in filter_panel_content.winfo_children():
        widget.destroy()
    filter_widgets.clear()

    if not all_rows:
        tk.Label(filter_panel_content, text="Load a CSV or\ndatabase to see filters",
                  bg=SAND_COLOR, fg=MUTED_TEXT_COLOR, font=(FONT_NAME, 10, "italic"),
                  justify="center").pack(pady=40)
        return

    tk.Label(filter_panel_content, text="Column Filters", bg=SAND_COLOR,
              fg=DARK_TEXT_COLOR, font=("Georgia", 11, "bold"),
              anchor="w").pack(fill="x", padx=10, pady=(10, 4))
    tk.Frame(filter_panel_content, bg=MUTED_TEXT_COLOR, height=1).pack(fill="x", padx=10, pady=(0, 8))

    for column_name in all_rows[0].keys():
        if column_types.get(column_name) in ("int", "float"):
            build_numeric_filter(filter_panel_content, column_name)
        else:
            build_text_filter(filter_panel_content, column_name)
        tk.Frame(filter_panel_content, bg=LIGHT_ROW_COLOR, height=1).pack(fill="x", padx=10, pady=2)

    tk.Button(filter_panel_content, text="Reset All Filters", command=reset_all_filters,
              bg=TERRACOTTA_COLOR, fg="white", font=(FONT_NAME, 10, "bold"), relief="flat",
              cursor="hand2", padx=10, pady=6).pack(fill="x", padx=10, pady=10)


def reset_all_filters():
    for column_name, widget in filter_widgets.items():
        if column_types.get(column_name) in ("int", "float"):
            min_var, max_var = widget
            min_var.set("")
            max_var.set("")
        else:
            widget.set("All")
    search_text_var.set("")
    apply_filters()


# =================================================================
# Loading data (CSV and SQLite) + statistics
# =================================================================

def finish_loading(source_description):
    """Steps that need to happen every time new data is loaded,
    whether it came from a CSV file or a database table."""
    global column_types
    column_types = detect_column_types(all_rows)

    columns = list(all_rows[0].keys())
    tree["columns"] = columns
    tree["show"] = "headings"
    for column_name in columns:
        tree.heading(column_name, text=column_name, anchor="w")
        tree.column(column_name, width=130, anchor="w", minwidth=80)

    show_rows_in_table(all_rows)
    build_filter_panel()
    status_text.set(f"  Loaded {len(all_rows)} records from {source_description}  |  {len(columns)} columns")
    stats_text.set("")


def load_csv():
    global all_rows

    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if not file_path:
        return

    try:
        with open(file_path, newline="", encoding="utf-8") as csv_file:
            rows = list(csv.DictReader(csv_file))

        if not rows:
            messagebox.showwarning("Warning", "CSV file is empty.")
            return

        all_rows = rows
        finish_loading("CSV")

    except Exception as error:
        messagebox.showerror("Error", str(error))


def load_database():
    """Open a SQLite database file. If it has more than one table,
    ask the user which one to load."""
    file_path = filedialog.askopenfilename(
        filetypes=[("SQLite Database", "*.db *.sqlite *.sqlite3"), ("All Files", "*.*")]
    )
    if not file_path:
        return

    try:
        connection = sqlite3.connect(file_path)
        table_rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        table_names = [row[0] for row in table_rows]

        if not table_names:
            connection.close()
            messagebox.showwarning("Warning", "No tables found in this database.")
            return

        if len(table_names) == 1:
            load_table_from_database(connection, table_names[0])
        else:
            ask_user_to_pick_table(connection, table_names)

    except Exception as error:
        messagebox.showerror("Error", str(error))


def load_table_from_database(connection, table_name):
    """Read every row of one table and hand it to the same loading
    pipeline used for CSV files. Always closes the connection."""
    global all_rows
    try:
        cursor = connection.execute(f'SELECT * FROM "{table_name}"')
        columns = [description[0] for description in cursor.description]

        rows = []
        for db_row in cursor.fetchall():
            row_dict = {}
            for column_name, value in zip(columns, db_row):
                row_dict[column_name] = "" if value is None else str(value)
            rows.append(row_dict)

        if not rows:
            messagebox.showwarning("Warning", f"Table '{table_name}' is empty.")
            return

        all_rows = rows
        finish_loading(f"table '{table_name}'")

    finally:
        connection.close()


def ask_user_to_pick_table(connection, table_names):
    """Show a small popup window listing every table so the user can
    choose which one to load."""
    picker = tk.Toplevel(root)
    picker.title("Select a Table")
    picker.configure(bg=BACKGROUND_COLOR)
    picker.geometry("300x360")
    picker.transient(root)
    picker.grab_set()

    tk.Label(picker, text="Choose a table to load", bg=BACKGROUND_COLOR,
              fg=DARK_TEXT_COLOR, font=(FONT_NAME, 11, "bold")).pack(padx=12, pady=(14, 8))

    list_frame = tk.Frame(picker, bg=BACKGROUND_COLOR)
    list_frame.pack(fill="both", expand=True, padx=12)

    scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
    scrollbar.pack(side="right", fill="y")

    table_listbox = tk.Listbox(list_frame, font=(FONT_NAME, 10), relief="flat",
                                highlightthickness=1, highlightbackground=MUTED_TEXT_COLOR,
                                selectbackground=TERRACOTTA_COLOR, selectforeground="white",
                                yscrollcommand=scrollbar.set)
    scrollbar.config(command=table_listbox.yview)
    table_listbox.pack(side="left", fill="both", expand=True)

    for table_name in table_names:
        table_listbox.insert("end", table_name)
    table_listbox.selection_set(0)

    def confirm_choice(_event=None):
        selection = table_listbox.curselection()
        chosen_table = table_names[selection[0]] if selection else table_names[0]
        picker.destroy()
        load_table_from_database(connection, chosen_table)

    def cancel_choice():
        connection.close()
        picker.destroy()

    table_listbox.bind("<Double-Button-1>", confirm_choice)

    button_row = tk.Frame(picker, bg=BACKGROUND_COLOR)
    button_row.pack(fill="x", padx=12, pady=12)
    make_button(button_row, "Load", confirm_choice, TERRACOTTA_COLOR, "white").pack(side="right")
    make_button(button_row, "Cancel", cancel_choice, SAND_COLOR, MUTED_TEXT_COLOR).pack(side="right", padx=(0, 8))

    picker.protocol("WM_DELETE_WINDOW", cancel_choice)


def show_stats():
    """Calculate and display mean/median/std-dev/etc. for a salary-like
    numeric column."""
    if not all_rows:
        messagebox.showwarning("No Data", "Please load a CSV file or database first.")
        return

    salary_column = None
    for guess in SALARY_COLUMN_GUESSES:
        if guess in all_rows[0]:
            salary_column = guess
            break

    if salary_column is None:
        numeric_columns = [name for name, kind in column_types.items() if kind in ("int", "float")]
        if not numeric_columns:
            messagebox.showerror("Error", "No numeric columns found.")
            return
        salary_column = numeric_columns[0]

    try:
        values = []
        for row in all_rows:
            text = row[salary_column].strip()
            if text != "":
                values.append(float(text))

        stats_text.set(
            f"  {salary_column}  —  "
            f"Mean: {statistics.mean(values):,.2f}   |   "
            f"Median: {statistics.median(values):,.2f}   |   "
            f"Std Dev: {statistics.stdev(values):,.2f}   |   "
            f"Min: {min(values):,.2f}   |   "
            f"Max: {max(values):,.2f}   |   "
            f"Variance: {statistics.variance(values):,.0f}"
        )
    except Exception as error:
        messagebox.showerror("Error", str(error))


# =================================================================
# Window setup
# =================================================================

def make_button(parent, text, command, bg_color, fg_color):
    return tk.Button(parent, text=text, command=command, bg=bg_color, fg=fg_color,
                      font=(FONT_NAME, 10, "bold"), relief="flat", cursor="hand2",
                      padx=14, pady=5, activebackground=DARK_TEXT_COLOR, activeforeground="white")


root = tk.Tk()
root.title("Salary CSV Viewer")
root.geometry("1200x700")
root.configure(bg=BACKGROUND_COLOR)

# --- Title bar ---
title_bar = tk.Frame(root, bg=TERRACOTTA_COLOR, height=52)
title_bar.pack(fill="x")
title_bar.pack_propagate(False)
tk.Label(title_bar, text="Salary CSV Viewer", bg=TERRACOTTA_COLOR, fg="white",
         font=("Georgia", 15, "bold"), padx=16).pack(side="left", pady=10)
tk.Label(title_bar, text="Python GUI Application", bg=TERRACOTTA_COLOR, fg=LIGHT_ROW_COLOR,
         font=(FONT_NAME, 10, "italic"), padx=4).pack(side="left", pady=10)

# --- Toolbar ---
toolbar = tk.Frame(root, bg=SAND_COLOR, pady=8)
toolbar.pack(fill="x")
make_button(toolbar, "  Load CSV  ", load_csv, TERRACOTTA_COLOR, "white").pack(side="left", padx=(12, 6), pady=2)
make_button(toolbar, "  Load Database  ", load_database, DARK_TEXT_COLOR, "white").pack(side="left", padx=6, pady=2)
make_button(toolbar, "  Show Stats  ", show_stats, SAGE_COLOR, "white").pack(side="left", padx=6, pady=2)
tk.Frame(toolbar, bg=MUTED_TEXT_COLOR, width=1).pack(side="left", fill="y", padx=10, pady=4)
tk.Label(toolbar, text="Search:", bg=SAND_COLOR, fg=DARK_TEXT_COLOR, font=(FONT_NAME, 10)).pack(side="left")

search_text_var = tk.StringVar()
search_text_var.trace_add("write", apply_filters)
make_styled_entry(toolbar, search_text_var, width=28).pack(side="left", padx=(4, 4), ipady=5)
make_button(toolbar, "✕", lambda: search_text_var.set(""), SAND_COLOR, MUTED_TEXT_COLOR).pack(side="left", padx=(0, 6), pady=2)

# --- Body: filter panel on the left, table on the right ---
body = tk.Frame(root, bg=BACKGROUND_COLOR)
body.pack(fill="both", expand=True)

filter_panel_outer = tk.Frame(body, bg=SAND_COLOR, width=220)
filter_panel_outer.pack(side="left", fill="y")
filter_panel_outer.pack_propagate(False)

filter_canvas = tk.Canvas(filter_panel_outer, bg=SAND_COLOR, highlightthickness=0, width=218)
filter_canvas.pack(side="left", fill="both", expand=True)

filter_scrollbar = ttk.Scrollbar(filter_panel_outer, orient="vertical", command=filter_canvas.yview)
filter_scrollbar.pack(side="right", fill="y")
filter_canvas.configure(yscrollcommand=filter_scrollbar.set)

# this inner frame holds all the filter widgets and scrolls inside the canvas
filter_panel_content = tk.Frame(filter_canvas, bg=SAND_COLOR)
filter_canvas_window = filter_canvas.create_window((0, 0), window=filter_panel_content, anchor="nw")

filter_panel_content.bind(
    "<Configure>",
    lambda event: filter_canvas.configure(scrollregion=filter_canvas.bbox("all"))
)
filter_canvas.bind(
    "<Configure>",
    lambda event: filter_canvas.itemconfig(filter_canvas_window, width=event.width)
)
filter_canvas.bind_all(
    "<MouseWheel>",
    lambda event: filter_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
)

build_filter_panel()  # shows the "Load a CSV file" placeholder at startup

# --- Right side: the data table ---
right_panel = tk.Frame(body, bg=BACKGROUND_COLOR)
right_panel.pack(side="left", fill="both", expand=True)

table_outer = tk.Frame(right_panel, bg=SAND_COLOR, padx=1, pady=1)
table_outer.pack(fill="both", expand=True, padx=8, pady=(10, 0))

table_frame = tk.Frame(table_outer, bg=BACKGROUND_COLOR)
table_frame.pack(fill="both", expand=True)

style = ttk.Style()
style.theme_use("clam")
style.configure("Custom.Treeview", background=BACKGROUND_COLOR, fieldbackground=BACKGROUND_COLOR,
                 foreground=DARK_TEXT_COLOR, rowheight=30, font=(FONT_NAME, 10), borderwidth=0)
style.configure("Custom.Treeview.Heading", background=DARK_TEXT_COLOR, foreground="white",
                 font=(FONT_NAME, 10, "bold"), relief="flat", padding=(8, 6))
style.map("Custom.Treeview", background=[("selected", TERRACOTTA_COLOR)], foreground=[("selected", "white")])
style.map("Custom.Treeview.Heading", background=[("active", TERRACOTTA_COLOR)])

scroll_y = ttk.Scrollbar(table_frame, orient="vertical")
scroll_y.pack(side="right", fill="y")
scroll_x = ttk.Scrollbar(table_frame, orient="horizontal")
scroll_x.pack(side="bottom", fill="x")

tree = ttk.Treeview(table_frame, style="Custom.Treeview",
                     yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set,
                     selectmode="browse")
tree.pack(fill="both", expand=True)
scroll_y.config(command=tree.yview)
scroll_x.config(command=tree.xview)
tree.tag_configure("odd", background=BACKGROUND_COLOR)
tree.tag_configure("even", background=LIGHT_ROW_COLOR)

stats_text = tk.StringVar()
tk.Label(right_panel, textvariable=stats_text, bg=DARK_TEXT_COLOR, fg=SAND_COLOR,
         font=("Consolas", 9), anchor="w", padx=8, pady=5).pack(fill="x", padx=8, pady=(4, 0))

# --- Status bar at the very bottom ---
status_bar = tk.Frame(root, bg=SAND_COLOR)
status_bar.pack(fill="x")
status_text = tk.StringVar(value="  No file loaded — click Load CSV or Load Database to begin")
tk.Label(status_bar, textvariable=status_text, bg=SAND_COLOR, fg=MUTED_TEXT_COLOR,
         font=(FONT_NAME, 9), anchor="w").pack(side="left", padx=4, pady=4)
tk.Label(status_bar, text="CSV Viewer  ·  Python  ", bg=SAND_COLOR, fg=MUTED_TEXT_COLOR,
         font=(FONT_NAME, 9), anchor="e").pack(side="right", padx=4, pady=4)

root.mainloop()