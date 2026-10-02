"""
CreatorMate - Manajemen konten kreator (offline, SQLite)
Framework : Flet 0.28.x (pin versi ini, API Tabs berubah di Flet 1.0+)
Jalankan  : flet run main.py
"""
import os
import sqlite3
from contextlib import closing
from functools import wraps

import flet as ft

# ----------------------------------------------------------------------------
# KONFIGURASI
# ----------------------------------------------------------------------------
try:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _BASE_DIR = os.getcwd()

# Di Android, folder app read-only; Flet menyediakan folder tulis lewat env ini.
DATA_DIR = os.getenv("FLET_APP_STORAGE_DATA", _BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "creator_data.db")

PLATFORMS = ["TikTok", "Instagram", "YouTube"]
STATUSES = ["Ide", "Scripting", "Editing", "Published"]
STATUS_COLOR = {
    "Ide": ft.Colors.AMBER,
    "Scripting": ft.Colors.LIGHT_BLUE,
    "Editing": ft.Colors.DEEP_PURPLE_ACCENT_100,
    "Published": ft.Colors.GREEN,
}
PLATFORM_ICON = {
    "TikTok": ft.Icons.MUSIC_NOTE,
    "Instagram": ft.Icons.CAMERA_ALT_OUTLINED,
    "YouTube": ft.Icons.PLAY_CIRCLE_OUTLINE,
}
TX_TYPES = ["Pemasukan", "Pengeluaran"]
TX_CATEGORIES = {
    "Pemasukan": ["Endorse", "Affiliate", "Sponsorship", "Bagi Hasil Platform", "Lainnya"],
    "Pengeluaran": ["Equipment", "Software/Tools", "Transport", "Properti/Konten", "Lainnya"],
}

BG = "#0F1115"
SURFACE = "#181B22"
ACCENT = ft.Colors.INDIGO_ACCENT_200


# ----------------------------------------------------------------------------
# DATABASE
# ----------------------------------------------------------------------------
def db_exec(sql, params=()):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid


def db_query(sql, params=()):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        return conn.execute(sql, params).fetchall()


def init_db():
    """Dibuat otomatis saat aplikasi pertama kali dibuka."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                platform TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                amount INTEGER NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS rate_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT DEFAULT '',
                handle TEXT DEFAULT '',
                followers TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS rate_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                price INTEGER NOT NULL
            );
            INSERT OR IGNORE INTO rate_profile (id, name, handle, followers)
            VALUES (1, '', '', '');
            """
        )
        conn.commit()


# ----------------------------------------------------------------------------
# HELPER
# ----------------------------------------------------------------------------
def rupiah(n):
    try:
        return "Rp " + f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "Rp 0"


def parse_int(text):
    """Ambil angka bulat dari teks ('1.500.000' -> 1500000). None jika kosong."""
    digits = "".join(ch for ch in (text or "") if ch.isdigit())
    return int(digits) if digits else None


def fmt_number(text):
    n = parse_int(text)
    return f"{n:,}".replace(",", ".") if n is not None else "-"


# ----------------------------------------------------------------------------
# APLIKASI
# ----------------------------------------------------------------------------
def main(page: ft.Page):
    page.title = "CreatorMate"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)
    page.bgcolor = BG
    page.padding = 0

    # --- inisialisasi DB (aman dari crash) ---
    try:
        init_db()
    except Exception as ex:  # noqa: BLE001
        page.add(ft.Text(f"Gagal menyiapkan database: {ex}", color=ft.Colors.RED_300))
        return

    # --- utilitas UI ---
    def notify(msg, error=False):
        page.open(
            ft.SnackBar(
                ft.Text(msg),
                bgcolor=ft.Colors.RED_700 if error else None,
            )
        )

    def guarded(fn):
        """Tangkap error apa pun di handler agar aplikasi tidak crash."""

        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as ex:  # noqa: BLE001
                notify(f"Terjadi kesalahan: {ex}", error=True)

        return wrapper

    def empty_state(text):
        return ft.Container(
            content=ft.Text(text, color=ft.Colors.GREY_500, italic=True),
            alignment=ft.alignment.center,
            padding=30,
        )

    def make_dropdown(label, options, value=None, on_change=None):
        return ft.Dropdown(
            label=label,
            options=[ft.dropdown.Option(o) for o in options],
            value=value,
            on_change=on_change,
            border_radius=10,
        )

    # =========================================================================
    # TAB 1 - KANBAN PERENCANAAN
    # =========================================================================
    kanban_list = ft.ListView(expand=True, spacing=6)
    kanban_counter = ft.Text("", size=12, color=ft.Colors.GREY_500)

    def on_filter_change(e):
        refresh_kanban()

    kanban_filter = make_dropdown("Filter status", ["Semua"] + STATUSES, "Semua", on_filter_change)

    @guarded
    def move_status(cid, new_status):
        db_exec("UPDATE contents SET status=? WHERE id=?", (new_status, cid))
        refresh_kanban()

    @guarded
    def delete_content(cid):
        db_exec("DELETE FROM contents WHERE id=?", (cid,))
        refresh_kanban()
        notify("Kartu dihapus")

    def build_content_card(row):
        cid, title, platform, status = row
        color = STATUS_COLOR.get(status, ft.Colors.GREY)

        menu_items = [
            ft.PopupMenuItem(
                text=f"Pindah ke {s}",
                on_click=lambda e, i=cid, s=s: move_status(i, s),
            )
            for s in STATUSES
            if s != status
        ]
        menu_items.append(ft.PopupMenuItem())  # pembatas
        menu_items.append(
            ft.PopupMenuItem(
                text="Hapus",
                icon=ft.Icons.DELETE_OUTLINE,
                on_click=lambda e, i=cid: delete_content(i),
            )
        )

        badge = ft.Container(
            content=ft.Text(status, size=11, color=color, weight=ft.FontWeight.W_600),
            bgcolor=ft.Colors.with_opacity(0.15, color),
            padding=ft.padding.symmetric(horizontal=10, vertical=3),
            border_radius=20,
        )

        idx = STATUSES.index(status) if status in STATUSES else 0
        actions = []
        if idx < len(STATUSES) - 1:
            nxt = STATUSES[idx + 1]
            actions.append(
                ft.IconButton(
                    icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                    tooltip=f"Lanjut ke {nxt}",
                    icon_size=20,
                    on_click=lambda e, i=cid, s=nxt: move_status(i, s),
                )
            )
        actions.append(ft.PopupMenuButton(items=menu_items, icon=ft.Icons.MORE_VERT))

        return ft.Card(
            color=SURFACE,
            elevation=1,
            content=ft.Container(
                padding=ft.padding.only(left=14, top=10, bottom=10, right=4),
                content=ft.Row(
                    [
                        ft.Icon(PLATFORM_ICON.get(platform, ft.Icons.TAG), color=ACCENT),
                        ft.Column(
                            [
                                ft.Text(title, weight=ft.FontWeight.W_600, size=15),
                                ft.Row([ft.Text(platform, size=12, color=ft.Colors.GREY_400), badge], spacing=8),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        *actions,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )

    def refresh_kanban():
        rows = db_query("SELECT id, title, platform, status FROM contents ORDER BY id DESC")
        total = len(rows)
        flt = kanban_filter.value
        if flt and flt != "Semua":
            rows = [r for r in rows if r[3] == flt]
        rows.sort(key=lambda r: STATUSES.index(r[3]) if r[3] in STATUSES else 99)
        kanban_list.controls = (
            [build_content_card(r) for r in rows]
            if rows
            else [empty_state("Belum ada konten. Tekan tombol + untuk menambah ide.")]
        )
        kanban_counter.value = f"{len(rows)} dari {total} konten"
        page.update()

    def open_add_content(e=None):
        t_title = ft.TextField(label="Judul Konten", border_radius=10, autofocus=True, max_length=100)
        d_platform = make_dropdown("Platform", PLATFORMS, PLATFORMS[0])
        d_status = make_dropdown("Status", STATUSES, STATUSES[0])

        @guarded
        def save(ev):
            title = (t_title.value or "").strip()
            if not title:
                t_title.error_text = "Judul wajib diisi"
                page.update()
                return
            db_exec(
                "INSERT INTO contents (title, platform, status) VALUES (?,?,?)",
                (title, d_platform.value or PLATFORMS[0], d_status.value or STATUSES[0]),
            )
            page.close(dlg)
            refresh_kanban()
            notify("Konten ditambahkan")

        dlg = ft.AlertDialog(
            title=ft.Text("Konten Baru"),
            content=ft.Column([t_title, d_platform, d_status], tight=True, spacing=12, width=320),
            actions=[
                ft.TextButton("Batal", on_click=lambda ev: page.close(dlg)),
                ft.FilledButton("Simpan", on_click=save),
            ],
        )
        page.open(dlg)

    tab_kanban = ft.Column(
        [
            ft.Row([kanban_filter], alignment=ft.MainAxisAlignment.START),
            kanban_counter,
            kanban_list,
        ],
        expand=True,
        spacing=8,
    )

    # =========================================================================
    # TAB 2 - KEUANGAN KREATOR
    # =========================================================================
    txt_income = ft.Text("Rp 0", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_300)
    txt_expense = ft.Text("Rp 0", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_300)
    txt_balance = ft.Text("Rp 0", size=26, weight=ft.FontWeight.BOLD)
    tx_list = ft.ListView(expand=True, spacing=0)

    def summary_card(label, value_ctrl, expand=True):
        return ft.Card(
            color=SURFACE,
            expand=expand,
            content=ft.Container(
                padding=14,
                content=ft.Column(
                    [ft.Text(label, size=12, color=ft.Colors.GREY_400), value_ctrl],
                    spacing=4,
                ),
            ),
        )

    @guarded
    def delete_tx(tid):
        db_exec("DELETE FROM transactions WHERE id=?", (tid,))
        refresh_finance()
        notify("Transaksi dihapus")

    def build_tx_tile(row):
        tid, ttype, cat, amount, note, created = row
        income = ttype == "Pemasukan"
        color = ft.Colors.GREEN_300 if income else ft.Colors.RED_300
        sub = f"{cat} • {(created or '')[:10]}"
        if note:
            sub += f"\n{note}"
        return ft.ListTile(
            leading=ft.Icon(
                ft.Icons.ARROW_DOWNWARD_ROUNDED if income else ft.Icons.ARROW_UPWARD_ROUNDED,
                color=color,
            ),
            title=ft.Text(("+ " if income else "- ") + rupiah(amount), color=color, weight=ft.FontWeight.W_600),
            subtitle=ft.Text(sub, size=12),
            is_three_line=bool(note),
            trailing=ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_size=20,
                tooltip="Hapus",
                on_click=lambda e, i=tid: delete_tx(i),
            ),
        )

    def refresh_finance():
        inc = db_query("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='Pemasukan'")[0][0]
        exp = db_query("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='Pengeluaran'")[0][0]
        txt_income.value = rupiah(inc)
        txt_expense.value = rupiah(exp)
        bal = inc - exp
        txt_balance.value = ("-" if bal < 0 else "") + rupiah(abs(bal))
        txt_balance.color = ft.Colors.RED_300 if bal < 0 else ft.Colors.WHITE
        rows = db_query(
            "SELECT id, type, category, amount, note, created_at FROM transactions ORDER BY id DESC"
        )
        tx_list.controls = (
            [build_tx_tile(r) for r in rows]
            if rows
            else [empty_state("Belum ada transaksi. Tekan tombol + untuk mencatat.")]
        )
        page.update()

    def open_add_tx(e=None):
        d_type = make_dropdown("Tipe", TX_TYPES, TX_TYPES[0])
        d_cat = make_dropdown("Kategori", TX_CATEGORIES[TX_TYPES[0]], TX_CATEGORIES[TX_TYPES[0]][0])
        t_amount = ft.TextField(
            label="Jumlah (angka bulat)",
            prefix_text="Rp ",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=10,
            max_length=15,
        )
        t_note = ft.TextField(label="Catatan (opsional)", border_radius=10, max_length=120)

        def on_type_change(ev):
            cats = TX_CATEGORIES.get(d_type.value, [])
            d_cat.options = [ft.dropdown.Option(c) for c in cats]
            d_cat.value = cats[0] if cats else None
            page.update()

        d_type.on_change = on_type_change

        @guarded
        def save(ev):
            amount = parse_int(t_amount.value)
            if not amount:
                t_amount.error_text = "Isi jumlah lebih dari 0"
                page.update()
                return
            db_exec(
                "INSERT INTO transactions (type, category, amount, note) VALUES (?,?,?,?)",
                (d_type.value, d_cat.value or "Lainnya", amount, (t_note.value or "").strip()),
            )
            page.close(dlg)
            refresh_finance()
            notify("Transaksi tersimpan")

        dlg = ft.AlertDialog(
            title=ft.Text("Transaksi Baru"),
            content=ft.Column([d_type, d_cat, t_amount, t_note], tight=True, spacing=12, width=320),
            actions=[
                ft.TextButton("Batal", on_click=lambda ev: page.close(dlg)),
                ft.FilledButton("Simpan", on_click=save),
            ],
        )
        page.open(dlg)

    tab_finance = ft.Column(
        [
            summary_card("Saldo Bersih", txt_balance),
            ft.Row(
                [
                    summary_card("Total Pemasukan", txt_income),
                    summary_card("Total Pengeluaran", txt_expense),
                ]
            ),
            ft.Text("Riwayat Transaksi", weight=ft.FontWeight.W_600),
            tx_list,
        ],
        expand=True,
        spacing=6,
    )

    # =========================================================================
    # TAB 3 - RATE CARD GENERATOR
    # =========================================================================
    prof = db_query("SELECT name, handle, followers FROM rate_profile WHERE id=1")
    prof = prof[0] if prof else ("", "", "")

    f_name = ft.TextField(label="Nama Kreator", value=prof[0], border_radius=10, max_length=60)
    f_handle = ft.TextField(label="Handle Sosmed (mis. @namakamu)", value=prof[1], border_radius=10, max_length=40)
    f_followers = ft.TextField(
        label="Jumlah Followers",
        value=prof[2],
        keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=10,
        max_length=12,
    )
    services_col = ft.Column(spacing=0)

    @guarded
    def save_profile(e=None):
        db_exec(
            "INSERT OR REPLACE INTO rate_profile (id, name, handle, followers) VALUES (1,?,?,?)",
            (f_name.value or "", f_handle.value or "", f_followers.value or ""),
        )

    for fld in (f_name, f_handle, f_followers):
        fld.on_blur = save_profile

    @guarded
    def delete_service(sid):
        db_exec("DELETE FROM rate_services WHERE id=?", (sid,))
        refresh_services()

    def refresh_services():
        rows = db_query("SELECT id, title, price FROM rate_services ORDER BY id")
        if rows:
            services_col.controls = [
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.SELL_OUTLINED, color=ACCENT),
                    title=ft.Text(title),
                    subtitle=ft.Text(rupiah(price)),
                    trailing=ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=20,
                        on_click=lambda e, i=sid: delete_service(i),
                    ),
                )
                for sid, title, price in rows
            ]
        else:
            services_col.controls = [empty_state("Belum ada layanan. Tekan + untuk menambah paket.")]
        page.update()

    def open_add_service(e=None):
        t_title = ft.TextField(label="Judul Paket (mis. 1x TikTok Video)", border_radius=10, autofocus=True, max_length=80)
        t_price = ft.TextField(
            label="Harga",
            prefix_text="Rp ",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=10,
            max_length=15,
        )

        @guarded
        def save(ev):
            title = (t_title.value or "").strip()
            price = parse_int(t_price.value)
            ok = True
            if not title:
                t_title.error_text = "Judul wajib diisi"
                ok = False
            if not price:
                t_price.error_text = "Isi harga lebih dari 0"
                ok = False
            if not ok:
                page.update()
                return
            db_exec("INSERT INTO rate_services (title, price) VALUES (?,?)", (title, price))
            page.close(dlg)
            refresh_services()

        dlg = ft.AlertDialog(
            title=ft.Text("Tambah Layanan"),
            content=ft.Column([t_title, t_price], tight=True, spacing=12, width=320),
            actions=[
                ft.TextButton("Batal", on_click=lambda ev: page.close(dlg)),
                ft.FilledButton("Simpan", on_click=save),
            ],
        )
        page.open(dlg)

    def show_premium_dialog(e=None):
        def watch_ad(ev):
            page.close(dlg)
            notify("Simulasi: iklan tidak tersedia pada uji coba offline")

        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.WORKSPACE_PREMIUM, color=ft.Colors.AMBER), ft.Text("Fitur Premium")]),
            content=ft.Text(
                "Ekspor PDF membutuhkan lisensi Premium atau menonton iklan terlebih dahulu.",
                width=300,
            ),
            actions=[
                ft.TextButton("Tutup", on_click=lambda ev: page.close(dlg)),
                ft.FilledButton("Tonton Iklan", icon=ft.Icons.PLAY_ARROW, on_click=watch_ad),
            ],
        )
        page.open(dlg)

    @guarded
    def open_preview(e=None):
        save_profile()
        name = (f_name.value or "").strip()
        handle = (f_handle.value or "").strip()
        services = db_query("SELECT title, price FROM rate_services ORDER BY id")
        if not name:
            f_name.error_text = "Nama kreator wajib diisi"
            page.update()
            return
        f_name.error_text = None
        if not services:
            notify("Tambahkan minimal 1 layanan dulu", error=True)
            return

        rows = [
            ft.Container(
                padding=ft.padding.symmetric(vertical=10),
                border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE))),
                content=ft.Row(
                    [
                        ft.Text(t, expand=True, size=14),
                        ft.Text(rupiah(p), weight=ft.FontWeight.BOLD, size=14),
                    ]
                ),
            )
            for t, p in services
        ]

        card = ft.Container(
            width=340,
            padding=20,
            border_radius=18,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=["#2B2F77", "#141633"],
            ),
            content=ft.Column(
                [
                    ft.Text("RATE CARD", size=11, color=ft.Colors.INDIGO_100, weight=ft.FontWeight.W_600),
                    ft.Text(name, size=22, weight=ft.FontWeight.BOLD),
                    ft.Text(handle or "-", color=ft.Colors.INDIGO_100),
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.PEOPLE_OUTLINE, size=16, color=ft.Colors.INDIGO_100),
                            ft.Text(f"{fmt_number(f_followers.value)} followers", size=13),
                        ],
                        spacing=6,
                    ),
                    ft.Divider(height=20, color=ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                    *rows,
                    ft.Container(height=6),
                    ft.Text(
                        "Harga belum termasuk pajak. Hubungi kreator untuk paket kustom.",
                        size=10,
                        color=ft.Colors.GREY_400,
                        italic=True,
                    ),
                ],
                spacing=4,
                tight=True,
            ),
        )

        dlg = ft.AlertDialog(
            content=ft.Column([card], scroll=ft.ScrollMode.AUTO, tight=True),
            content_padding=12,
            actions=[
                ft.OutlinedButton("Ekspor PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=show_premium_dialog),
                ft.TextButton("Tutup", on_click=lambda ev: page.close(dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dlg)

    tab_ratecard = ft.Column(
        [
            ft.Text("Profil Kreator", weight=ft.FontWeight.W_600),
            f_name,
            f_handle,
            f_followers,
            ft.Row(
                [
                    ft.Text("Daftar Layanan", weight=ft.FontWeight.W_600, expand=True),
                    ft.TextButton("Tambah", icon=ft.Icons.ADD, on_click=open_add_service),
                ]
            ),
            ft.Card(color=SURFACE, content=ft.Container(content=services_col, padding=4)),
            ft.FilledButton(
                "Pratinjau Rate Card",
                icon=ft.Icons.VISIBILITY_OUTLINED,
                on_click=open_preview,
                height=48,
            ),
            ft.Container(height=70),  # ruang agar tidak tertutup FAB
        ],
        expand=True,
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
    )

    # =========================================================================
    # TABS + FAB
    # =========================================================================
    def tab_body(ctrl):
        return ft.Container(content=ctrl, padding=ft.padding.only(left=14, right=14, top=12), expand=True)

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=250,
        expand=True,
        indicator_color=ACCENT,
        tabs=[
            ft.Tab(text="Kanban", icon=ft.Icons.DASHBOARD_OUTLINED, content=tab_body(tab_kanban)),
            ft.Tab(text="Keuangan", icon=ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, content=tab_body(tab_finance)),
            ft.Tab(text="Rate Card", icon=ft.Icons.BADGE_OUTLINED, content=tab_body(tab_ratecard)),
        ],
    )

    fab_tooltips = ["Tambah konten", "Catat transaksi", "Tambah layanan"]

    def on_tab_change(e):
        fab.tooltip = fab_tooltips[tabs.selected_index]
        page.update()

    tabs.on_change = on_tab_change

    @guarded
    def on_fab(e):
        # FAB kontekstual: aksi tergantung tab aktif
        [open_add_content, open_add_tx, open_add_service][tabs.selected_index]()

    fab = ft.FloatingActionButton(icon=ft.Icons.ADD, tooltip=fab_tooltips[0], on_click=on_fab)
    page.floating_action_button = fab

    page.add(
        ft.SafeArea(
            ft.Column(
                [
                    ft.Container(
                        padding=ft.padding.only(left=16, top=10, bottom=0),
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.AUTO_AWESOME, color=ACCENT),
                                ft.Text("CreatorMate", size=20, weight=ft.FontWeight.BOLD),
                            ]
                        ),
                    ),
                    tabs,
                ],
                expand=True,
                spacing=0,
            ),
            expand=True,
        )
    )

    # isi data awal setelah kontrol masuk ke halaman
    refresh_kanban()
    refresh_finance()
    refresh_services()


if __name__ == "__main__":
    ft.app(target=main)
