import csv
import sqlite3
import statistics
import tkinter as tk
from functools import lru_cache, partial
from tkinter import ttk, filedialog, messagebox

# ── Palette ──────────────────────────────────────────────────
BG    = "#FAF7F2"
TERRA = "#C0533A"
SAGE  = "#7A9E87"
SAND  = "#E8DDD0"
DARK  = "#2B2B2B"
MUTED = "#8A8279"
LIGHT = "#F5EFE8"

FONT        = "Calibri"
NUMERIC_COL_CANDIDATES = ("BaseSalary", "Salary", "salary", "Base Pay", "TotalPay",
                           "base_salary", "SALARY", "Annual Salary", "AnnualSalary",
                           "Balance", "Score")
ID_COL_NAMES = ("id", "recordid", "empid", "employeeid", "record_id", "emp_id")

# Reusable style presets, applied with **STYLE via dict-unpacking to avoid
# repeating the same font/color kwargs on every widget.
ENTRY_STYLE = dict(font=(FONT, 10), bg="white", fg=DARK, relief="flat",
                    highlightthickness=1, highlightbackground=MUTED, highlightcolor=TERRA)
SMALL_LABEL = dict(bg=SAND, fg=MUTED, font=(FONT, 8))
BOLD_LABEL  = dict(bg=SAND, fg=DARK, font=(FONT, 10, "bold"))

# ── State ────────────────────────────────────────────────────
all_rows  = []
col_types = {}   # col -> "int" | "float" | "text"
filter_vars = {}   # col -> StringVar (text) or (min_var, max_var) tuple (numeric)


# ── Data helpers ─────────────────────────────────────────────

def detect_col_types(rows):
    types = {}
    for col in rows[0].keys():
        vals = [r[col] for r in rows if r[col].strip()]
        if all(_is_number(v, int) for v in vals):
            types[col] = "int"
        elif all(_is_number(v, float) for v in vals):
            types[col] = "float"
        else:
            types[col] = "text"
    return types


def _is_number(v, kind):
    try:
        kind(v)
        return True
    except ValueError:
        return False


@lru_cache(maxsize=None)
def _numeric(v):
    """Cached string->float conversion (columns repeat many identical values)."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def col_range(col):
    vals = [n for n in (_numeric(r[col]) for r in all_rows) if n is not None]
    return (min(vals), max(vals)) if vals else (0, 100)


def unique_vals(col):
    return sorted({r[col].strip() for r in all_rows if r[col].strip()})


def get_id_column():
    if not all_rows:
        return None
    columns = list(all_rows[0].keys())
    for col in columns:
        if col.lower() in ID_COL_NAMES:
            return col
    return columns[0]


# ── Table ────────────────────────────────────────────────────

def populate_table(rows):
    tree.delete(*tree.get_children())
    id_col = get_id_column()
    seen = set()
    for i, row in enumerate(rows):
        raw_iid = str(row[id_col]).strip() if id_col and row.get(id_col) else ""
        iid = raw_iid if raw_iid and raw_iid not in seen else str(i)
        seen.add(iid)
        tree.insert("", "end", iid=iid, values=list(row.values()),
                    tags=("even" if i % 2 else "odd",))
    status_var.set(f"  {len(rows)} of {len(all_rows)} records shown")


def apply_filters(*_args):
    if not all_rows:
        return

    kw = search_var.get().lower().strip()
    predicates = []

    if kw:
        predicates.append(lambda r: any(kw in str(v).lower() for v in r.values()))

    for col, var in filter_vars.items():
        ctype = col_types.get(col, "text")
        if ctype in ("int", "float"):
            min_var, max_var = var
            lo = _numeric(min_var.get().strip())
            hi = _numeric(max_var.get().strip())
            if lo is not None or hi is not None:
                predicates.append(partial(_in_range, col=col, lo=lo, hi=hi))
        else:
            val = var.get()
            if val and val != "All":
                predicates.append(lambda r, col=col, val=val: r[col].strip() == val)

    result = [r for r in all_rows if all(p(r) for p in predicates)] if predicates else all_rows
    populate_table(result)


def _in_range(row, col, lo, hi):
    n = _numeric(row[col])
    if n is None:
        return False
    return (lo is None or n >= lo) and (hi is None or n <= hi)


# ── Filter panel builder ────────────────────────────────────

def _labeled_frame(parent, text):
    frame = tk.Frame(parent, bg=SAND)
    frame.pack(fill="x", padx=10, pady=4)
    tk.Label(frame, text=text, anchor="w", **BOLD_LABEL).pack(fill="x")
    return frame


def _build_numeric_filter(parent, col):
    lo, hi = col_range(col)
    fmt = "{:,.0f}" if col_types[col] == "int" else "{:,.2f}"
    frame = _labeled_frame(parent, col)

    tk.Label(frame, text=f"Range: {fmt.format(lo)} — {fmt.format(hi)}",
              **SMALL_LABEL).pack(anchor="w", pady=(2, 4))

    min_var, max_var = tk.StringVar(), tk.StringVar()
    filter_vars[col] = (min_var, max_var)

    row_frame = tk.Frame(frame, bg=SAND)
    row_frame.pack(fill="x")
    for label, var, pad in (("Min", min_var, (0, 4)), ("Max", max_var, (0, 0))):
        box = tk.Frame(row_frame, bg=SAND)
        box.pack(side="left", expand=True, fill="x", padx=pad)
        tk.Label(box, text=label, **SMALL_LABEL).pack(anchor="w")
        tk.Entry(box, textvariable=var, width=9, **ENTRY_STYLE).pack(fill="x", ipady=4)
        var.trace_add("write", apply_filters)

    def reset():
        min_var.set("")
        max_var.set("")

    tk.Button(frame, text="Reset", command=reset, bg=SAND, fg=MUTED,
              font=(FONT, 8), relief="flat", cursor="hand2").pack(anchor="e", pady=(4, 0))


def _build_text_filter(parent, col):
    frame = _labeled_frame(parent, col)
    var = tk.StringVar(value="All")
    filter_vars[col] = var

    cb = ttk.Combobox(frame, textvariable=var, values=["All"] + unique_vals(col),
                       state="readonly", font=(FONT, 10))
    cb.pack(fill="x", pady=(4, 0))
    var.trace_add("write", apply_filters)


def build_filter_panel():
    for w in filter_scroll_inner.winfo_children():
        w.destroy()
    filter_vars.clear()

    if not all_rows:
        tk.Label(filter_scroll_inner, text="Load a CSV or\ndatabase to see filters",
                  bg=SAND, fg=MUTED, font=(FONT, 10, "italic"),
                  justify="center").pack(pady=40)
        return

    tk.Label(filter_scroll_inner, text="Column Filters", bg=SAND, fg=DARK,
              font=("Georgia", 11, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 4))
    tk.Frame(filter_scroll_inner, bg=MUTED, height=1).pack(fill="x", padx=10, pady=(0, 8))

    for col in all_rows[0].keys():
        builder = _build_numeric_filter if col_types.get(col) in ("int", "float") else _build_text_filter
        builder(filter_scroll_inner, col)
        tk.Frame(filter_scroll_inner, bg=LIGHT, height=1).pack(fill="x", padx=10, pady=2)

    tk.Button(filter_scroll_inner, text="Reset All Filters", command=reset_all_filters,
              bg=TERRA, fg="white", font=(FONT, 10, "bold"), relief="flat",
              cursor="hand2", padx=10, pady=6).pack(fill="x", padx=10, pady=10)


def reset_all_filters():
    for col, var in filter_vars.items():
        if col_types.get(col) in ("int", "float"):
            var[0].set("")
            var[1].set("")
        else:
            var.set("All")
    search_var.set("")
    apply_filters()


# ── Data load / stats ───────────────────────────────────────

def _finish_load(source_label):
    """Shared post-load pipeline: detect types, rebuild table + filters + status.
    Used by both CSV and database loading so they behave identically."""
    global col_types
    _numeric.cache_clear()
    col_types = detect_col_types(all_rows)

    columns = list(all_rows[0].keys())
    tree["columns"] = columns
    tree["show"] = "headings"
    for col in columns:
        tree.heading(col, text=col, anchor="w")
        tree.column(col, width=130, anchor="w", minwidth=80)

    populate_table(all_rows)
    build_filter_panel()
    status_var.set(f"  Loaded {len(all_rows)} records from {source_label}  |  {len(columns)} columns")
    stats_bar_var.set("")


def load_csv():
    global all_rows
    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if not file_path:
        return
    try:
        with open(file_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            messagebox.showwarning("Warning", "CSV file is empty.")
            return

        all_rows = rows
        _finish_load("CSV")

    except Exception as e:
        messagebox.showerror("Error", str(e))


def load_database():
    """Open a SQLite database file, let the user pick a table, and load it
    into the viewer the same way a CSV is loaded."""
    file_path = filedialog.askopenfilename(
        filetypes=[("SQLite Database", "*.db *.sqlite *.sqlite3"), ("All Files", "*.*")])
    if not file_path:
        return
    try:
        conn = sqlite3.connect(file_path)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()]
        if not tables:
            conn.close()
            messagebox.showwarning("Warning", "No tables found in this database.")
            return
        if len(tables) == 1:
            _load_table(conn, tables[0])   # closes conn when done
        else:
            _prompt_table_choice(conn, tables)   # closes conn on Load/Cancel
    except Exception as e:
        messagebox.showerror("Error", str(e))


def _load_table(conn, table_name):
    """Fetch a table's rows as string-valued dicts (matching CSV row shape)
    and hand them to the shared load pipeline."""
    global all_rows
    try:
        cur = conn.execute(f'SELECT * FROM "{table_name}"')
        cols = [d[0] for d in cur.description]
        rows = [
            {col: ("" if val is None else str(val)) for col, val in zip(cols, r)}
            for r in cur.fetchall()
        ]
        if not rows:
            messagebox.showwarning("Warning", f"Table '{table_name}' is empty.")
            return
        all_rows = rows
        _finish_load(f"table '{table_name}'")
    finally:
        conn.close()


def _prompt_table_choice(conn, tables):
    """Small modal listbox so the user can pick which table to load."""
    picker = tk.Toplevel(root)
    picker.title("Select a Table")
    picker.configure(bg=BG)
    picker.geometry("300x360")
    picker.transient(root)
    picker.grab_set()

    tk.Label(picker, text="Choose a table to load", bg=BG, fg=DARK,
              font=(FONT, 11, "bold")).pack(padx=12, pady=(14, 8))

    list_frame = tk.Frame(picker, bg=BG)
    list_frame.pack(fill="both", expand=True, padx=12)
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
    listbox = tk.Listbox(list_frame, font=(FONT, 10), relief="flat",
                          highlightthickness=1, highlightbackground=MUTED,
                          selectbackground=TERRA, selectforeground="white",
                          yscrollcommand=scrollbar.set)
    scrollbar.config(command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.pack(side="left", fill="both", expand=True)
    for t in tables:
        listbox.insert("end", t)
    listbox.selection_set(0)

    def confirm(_event=None):
        sel = listbox.curselection()
        table_name = tables[sel[0]] if sel else tables[0]
        picker.destroy()
        _load_table(conn, table_name)

    def cancel():
        conn.close()
        picker.destroy()

    listbox.bind("<Double-Button-1>", confirm)
    btn_row = tk.Frame(picker, bg=BG)
    btn_row.pack(fill="x", padx=12, pady=12)
    make_btn(btn_row, "Load", confirm, TERRA, "white").pack(side="right")
    make_btn(btn_row, "Cancel", cancel, SAND, MUTED).pack(side="right", padx=(0, 8))
    picker.protocol("WM_DELETE_WINDOW", cancel)


def show_stats():
    if not all_rows:
        messagebox.showwarning("No Data", "Please load a CSV file or database first.")
        return

    salary_column = next((c for c in NUMERIC_COL_CANDIDATES if c in all_rows[0]), None)
    if salary_column is None:
        numeric_cols = [c for c, t in col_types.items() if t in ("int", "float")]
        if not numeric_cols:
            messagebox.showerror("Error", "No numeric columns found.")
            return
        salary_column = numeric_cols[0]

    try:
        vals = [float(r[salary_column]) for r in all_rows if r[salary_column].strip() != ""]
        stats_bar_var.set(
            f"  {salary_column}  —  "
            f"Mean: {statistics.mean(vals):,.2f}   |   "
            f"Median: {statistics.median(vals):,.2f}   |   "
            f"Std Dev: {statistics.stdev(vals):,.2f}   |   "
            f"Min: {min(vals):,.2f}   |   "
            f"Max: {max(vals):,.2f}   |   "
            f"Variance: {statistics.variance(vals):,.0f}"
        )
    except Exception as e:
        messagebox.showerror("Error", str(e))


# ── Window ───────────────────────────────────────────────────

def make_btn(parent, text, cmd, bg, fg):
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                      font=(FONT, 10, "bold"), relief="flat", cursor="hand2",
                      padx=14, pady=5, activebackground=DARK, activeforeground="white")


root = tk.Tk()
root.title("Salary CSV Viewer")
root.geometry("1200x700")
root.configure(bg=BG)

# Title bar
title_bar = tk.Frame(root, bg=TERRA, height=52)
title_bar.pack(fill="x")
title_bar.pack_propagate(False)
tk.Label(title_bar, text="Salary CSV Viewer", bg=TERRA, fg="white",
         font=("Georgia", 15, "bold"), padx=16).pack(side="left", pady=10)
tk.Label(title_bar, text="Python GUI Application", bg=TERRA, fg=LIGHT,
         font=(FONT, 10, "italic"), padx=4).pack(side="left", pady=10)

# Toolbar
toolbar = tk.Frame(root, bg=SAND, pady=8)
toolbar.pack(fill="x")
make_btn(toolbar, "  Load CSV  ", load_csv, TERRA, "white").pack(side="left", padx=(12, 6), pady=2)
make_btn(toolbar, "  Load Database  ", load_database, DARK, "white").pack(side="left", padx=6, pady=2)
make_btn(toolbar, "  Show Stats  ", show_stats, SAGE, "white").pack(side="left", padx=6, pady=2)
tk.Frame(toolbar, bg=MUTED, width=1).pack(side="left", fill="y", padx=10, pady=4)
tk.Label(toolbar, text="Search:", bg=SAND, fg=DARK, font=(FONT, 10)).pack(side="left")

search_var = tk.StringVar()
search_var.trace_add("write", apply_filters)
tk.Entry(toolbar, textvariable=search_var, width=28, **ENTRY_STYLE).pack(side="left", padx=(4, 4), ipady=5)
make_btn(toolbar, "✕", lambda: search_var.set(""), SAND, MUTED).pack(side="left", padx=(0, 6), pady=2)

# ── Body: filter panel (left) + table (right) ──────────────
body = tk.Frame(root, bg=BG)
body.pack(fill="both", expand=True)

filter_panel_outer = tk.Frame(body, bg=SAND, width=220)
filter_panel_outer.pack(side="left", fill="y")
filter_panel_outer.pack_propagate(False)

filter_canvas = tk.Canvas(filter_panel_outer, bg=SAND, highlightthickness=0, width=218)
filter_canvas.pack(side="left", fill="both", expand=True)

filter_scrollbar = ttk.Scrollbar(filter_panel_outer, orient="vertical", command=filter_canvas.yview)
filter_scrollbar.pack(side="right", fill="y")
filter_canvas.configure(yscrollcommand=filter_scrollbar.set)

filter_scroll_inner = tk.Frame(filter_canvas, bg=SAND)
filter_canvas_window = filter_canvas.create_window((0, 0), window=filter_scroll_inner, anchor="nw")
filter_scroll_inner.bind("<Configure>",
                          lambda e: filter_canvas.configure(scrollregion=filter_canvas.bbox("all")))
filter_canvas.bind("<Configure>",
                    lambda e: filter_canvas.itemconfig(filter_canvas_window, width=e.width))
filter_canvas.bind_all("<MouseWheel>",
                        lambda e: filter_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

build_filter_panel()  # shows the "Load a CSV file" placeholder

# Right: table area
right_panel = tk.Frame(body, bg=BG)
right_panel.pack(side="left", fill="both", expand=True)

table_outer = tk.Frame(right_panel, bg=SAND, padx=1, pady=1)
table_outer.pack(fill="both", expand=True, padx=8, pady=(10, 0))

table_frame = tk.Frame(table_outer, bg=BG)
table_frame.pack(fill="both", expand=True)

style = ttk.Style()
style.theme_use("clam")
style.configure("Custom.Treeview", background=BG, fieldbackground=BG, foreground=DARK,
                 rowheight=30, font=(FONT, 10), borderwidth=0)
style.configure("Custom.Treeview.Heading", background=DARK, foreground="white",
                 font=(FONT, 10, "bold"), relief="flat", padding=(8, 6))
style.map("Custom.Treeview", background=[("selected", TERRA)], foreground=[("selected", "white")])
style.map("Custom.Treeview.Heading", background=[("active", TERRA)])

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
tree.tag_configure("odd", background=BG)
tree.tag_configure("even", background=LIGHT)

stats_bar_var = tk.StringVar()
tk.Label(right_panel, textvariable=stats_bar_var, bg=DARK, fg=SAND,
         font=("Consolas", 9), anchor="w", padx=8, pady=5).pack(fill="x", padx=8, pady=(4, 0))

status_bar = tk.Frame(root, bg=SAND)
status_bar.pack(fill="x")
status_var = tk.StringVar(value="  No file loaded — click Load CSV or Load Database to begin")
tk.Label(status_bar, textvariable=status_var, bg=SAND, fg=MUTED,
         font=(FONT, 9), anchor="w").pack(side="left", padx=4, pady=4)
tk.Label(status_bar, text="CSV Viewer  ·  Python  ", bg=SAND, fg=MUTED,
         font=(FONT, 9), anchor="e").pack(side="right", padx=4, pady=4)

root.mainloop()