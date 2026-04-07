import streamlit as st
import pandas as pd
import json
from io import BytesIO
import hashlib
import reportlab

# Patch untuk kompatibilitas Python 3.9+ dengan reportlab lama
try:
    import _md5
except ImportError:
    pass

try:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

# ══════════════════════════════════════════
# LOAD DATA — support upload file & fallback CSV
# ══════════════════════════════════════════
def load_dataframe(source):
    """Baca CSV atau Excel dari path string atau file upload."""
    try:
        if isinstance(source, str):
            ext = source.split(".")[-1].lower()
        else:
            ext = source.name.split(".")[-1].lower()

        if ext == "csv":
            raw = pd.read_csv(source)
        elif ext in ("xlsx", "xls"):
            raw = pd.read_excel(source)
        else:
            return None, f"Format .{ext} tidak didukung. Gunakan .csv atau .xlsx"

        raw.columns = raw.columns.str.strip()

        # Kolom wajib
        required = {"Employee ID", "Employee Name", "Manager ID", "Job Position", "Division", "Business Unit"}
        missing = required - set(raw.columns)
        if missing:
            return None, f"Kolom tidak ditemukan: {', '.join(missing)}"

        raw["Employee ID"] = raw["Employee ID"].astype(str).str.strip()
        raw["Manager ID"]  = raw["Manager ID"].fillna("").astype(str).str.strip()
        raw["SBU/Tribe"]   = raw.get("SBU/Tribe", pd.Series([""] * len(raw))).fillna("").astype(str).str.strip()

        return raw, None

    except Exception as e:
        return None, f"Gagal membaca file: {str(e)}"

# ══════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════
def get_all_managers(emp_ids, all_data):
    result = set(emp_ids)
    to_check = set(emp_ids)
    while to_check:
        mgr_ids = set(all_data[all_data["Employee ID"].isin(to_check)]["Manager ID"].tolist()) - {"", "nan"}
        new_mgrs = mgr_ids - result
        if not new_mgrs:
            break
        result.update(new_mgrs)
        to_check = new_mgrs
    return result

def build_tree_json(full_data, selected_div, root_ids, mode="division"):
    children_map = {}
    for _, row in full_data.iterrows():
        mgr = str(row["Manager ID"])
        emp = str(row["Employee ID"])
        if mgr and mgr != "nan" and mgr != "":
            children_map.setdefault(mgr, []).append(emp)

    info_map = {}
    for _, row in full_data.iterrows():
        info_map[str(row["Employee ID"])] = {
            "name": str(row["Employee Name"]),
            "position": str(row["Job Position"]),
            "division": str(row["Division"]),
            "sbu": str(row.get("SBU/Tribe", "")),
            "bu": str(row["Business Unit"]),
            "in_div": bool(row["Division"] == selected_div) if mode == "division" else True
        }

    def build_node(emp_id, visited=None):
        if visited is None:
            visited = set()
        if emp_id in visited or emp_id not in info_map:
            return None
        visited.add(emp_id)
        info = info_map[emp_id]
        node = {
            "id": emp_id,
            "name": info["name"],
            "position": info["position"],
            "division": info["division"],
            "sbu": info["sbu"],
            "bu": info["bu"],
            "in_div": info["in_div"],
            "children": []
        }
        for child_id in children_map.get(emp_id, []):
            child_node = build_node(child_id, visited)
            if child_node:
                node["children"].append(child_node)
        return node

    roots = []
    for rid in root_ids:
        n = build_node(rid)
        if n:
            roots.append(n)
    return roots

def to_excel(dataframe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Data Karyawan")
    return output.getvalue()

# ══════════════════════════════════════════
# PDF GENERATOR (ReportLab)
# ══════════════════════════════════════════
def generate_pdf(tree_nodes, title_text):
    """Buat PDF org chart menggunakan ReportLab dengan layout box hierarki."""
    if not REPORTLAB_OK:
        raise ImportError("ReportLab tidak tersedia")

    # Konstanta layout
    NODE_W = 150
    NODE_H = 60
    H_GAP = 30
    V_GAP = 50

    # Hitung posisi setiap node (layout tree)
    positions = {}
    draw_order = []

    def calc_subtree_width(node):
        if not node["children"]:
            return NODE_W
        total = sum(calc_subtree_width(c) for c in node["children"])
        total += H_GAP * (len(node["children"]) - 1)
        return max(total, NODE_W)

    def assign_positions(node, x_center, y):
        positions[node["id"]] = (x_center, y)
        draw_order.append(node)
        if not node["children"]:
            return
        total_w = sum(calc_subtree_width(c) for c in node["children"])
        total_w += H_GAP * (len(node["children"]) - 1)
        x_start = x_center - total_w / 2
        for child in node["children"]:
            cw = calc_subtree_width(child)
            assign_positions(child, x_start + cw / 2, y - (NODE_H + V_GAP))
            x_start += cw + H_GAP

    # Hitung total lebar & tinggi
    total_w = sum(calc_subtree_width(r) for r in tree_nodes) + H_GAP * (len(tree_nodes) - 1)
    max_depth = [0]

    def get_depth(node, d=0):
        max_depth[0] = max(max_depth[0], d)
        for c in node["children"]:
            get_depth(c, d + 1)

    for r in tree_nodes:
        get_depth(r)

    total_h = (max_depth[0] + 1) * (NODE_H + V_GAP) + 120

    # Page size dinamis (minimum A3 landscape)
    page_w = max(total_w + 100, landscape(A3)[0])
    page_h = max(total_h + 100, landscape(A3)[1])

    # Assign posisi mulai dari tengah atas
    x_offset = page_w / 2
    y_top = page_h - 80
    x_start = x_offset - total_w / 2
    for root in tree_nodes:
        rw = calc_subtree_width(root)
        assign_positions(root, x_start + rw / 2, y_top)
        x_start += rw + H_GAP

    # Buat PDF
    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=(page_w, page_h))

    # Background
    c.setFillColor(colors.HexColor("#0f1117"))
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Judul
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(page_w / 2, page_h - 45, title_text)
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#6b7280"))
    c.drawCentredString(page_w / 2, page_h - 62, f"Total: {len(draw_order)} karyawan ditampilkan")

    # Gambar garis koneksi dulu (di belakang node)
    c.setStrokeColor(colors.HexColor("#3d4160"))
    c.setLineWidth(1.5)
    for node in draw_order:
        if node["id"] not in positions:
            continue
        nx, ny = positions[node["id"]]
        for child in node["children"]:
            if child["id"] not in positions:
                continue
            cx, cy = positions[child["id"]]
            # Garis dari bawah parent ke atas child
            parent_bottom_x = nx
            parent_bottom_y = ny - NODE_H / 2
            child_top_x = cx
            child_top_y = cy + NODE_H / 2
            mid_y = (parent_bottom_y + child_top_y) / 2
            c.line(parent_bottom_x, parent_bottom_y, parent_bottom_x, mid_y)
            c.line(parent_bottom_x, mid_y, child_top_x, mid_y)
            c.line(child_top_x, mid_y, child_top_x, child_top_y)

    # Gambar node
    for node in draw_order:
        if node["id"] not in positions:
            continue
        nx, ny = positions[node["id"]]
        x_left = nx - NODE_W / 2
        y_bottom = ny - NODE_H / 2

        # Warna node
        if node.get("in_div", True):
            fill_color = colors.HexColor("#CCCCFF")   # periwinkle
            text_color = colors.HexColor("#1a1a2e")
            border_color = colors.HexColor("#9999ee")
        else:
            fill_color = colors.HexColor("#2a2d3e")
            text_color = colors.HexColor("#a0a8c0")
            border_color = colors.HexColor("#3d4160")

        # Kotak dengan rounded corner (simulasi)
        c.setFillColor(fill_color)
        c.setStrokeColor(border_color)
        c.setLineWidth(1.5)
        c.roundRect(x_left, y_bottom, NODE_W, NODE_H, 8, fill=1, stroke=1)

        # Nama
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 8)
        name = node["name"]
        if len(name) > 22:
            name = name[:21] + "…"
        c.drawCentredString(nx, y_bottom + NODE_H - 16, name)

        # Jabatan
        c.setFont("Helvetica", 7)
        pos_text = node["position"]
        if len(pos_text) > 26:
            pos_text = pos_text[:25] + "…"
        c.drawCentredString(nx, y_bottom + NODE_H - 28, pos_text)

        # Divisi
        c.setFont("Helvetica", 6.5)
        c.setFillColor(text_color if node.get("in_div") else colors.HexColor("#6b7280"))
        div_text = node["division"]
        if len(div_text) > 28:
            div_text = div_text[:27] + "…"
        c.drawCentredString(nx, y_bottom + NODE_H - 40, div_text)

        # SBU
        sbu = node.get("sbu", "")
        if sbu and sbu != "nan" and sbu != "":
            c.setFont("Helvetica", 6)
            c.setFillColor(colors.HexColor("#888888"))
            if len(sbu) > 28:
                sbu = sbu[:27] + "…"
            c.drawCentredString(nx, y_bottom + NODE_H - 51, sbu)

    # Legend
    legend_y = 30
    legend_x = 40

    c.setFillColor(colors.HexColor("#CCCCFF"))
    c.setStrokeColor(colors.HexColor("#9999ee"))
    c.roundRect(legend_x, legend_y, 14, 14, 3, fill=1, stroke=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 8)
    c.drawString(legend_x + 18, legend_y + 3, "Karyawan divisi ini")

    c.setFillColor(colors.HexColor("#2a2d3e"))
    c.setStrokeColor(colors.HexColor("#3d4160"))
    c.roundRect(legend_x + 140, legend_y, 14, 14, 3, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#a0a8c0"))
    c.drawString(legend_x + 158, legend_y + 3, "Atasan dari divisi lain")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ══════════════════════════════════════════
# PDF GENERATOR — LEVEL SUMMARY (Level 0-1 Detail, Level 2 Division Only)
# ══════════════════════════════════════════
def generate_pdf_summary(tree_nodes, title_text):
    """
    PDF khusus dengan aturan:
    - Level 0 & 1 : tampil Nama, Job Position, Division, Business Unit (kotak penuh)
    - Level 2      : tampil Nama Division saja (kotak ringkas)
    - Level 3+     : tidak ditampilkan
    """
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib import colors
    from io import BytesIO

    NODE_W_FULL = 170   # lebar node level 0-1
    NODE_H_FULL = 68    # tinggi node level 0-1
    NODE_W_DIV  = 130   # lebar node level 2
    NODE_H_DIV  = 32    # tinggi node level 2
    H_GAP = 28
    V_GAP = 45

    # ── Potong tree hingga level 2 saja ──
    def trim_tree(node, depth=0):
        if depth > 2:
            return None
        trimmed = dict(node)
        if depth == 2:
            trimmed["children"] = []   # level 2 tidak punya anak
        else:
            trimmed["children"] = [
                c for c in [trim_tree(ch, depth+1) for ch in node.get("children", [])]
                if c is not None
            ]
        trimmed["_depth"] = depth
        return trimmed

    trimmed_roots = [t for t in [trim_tree(r) for r in tree_nodes] if t]

    # ── Hitung lebar subtree ──
    def node_w(node):
        return NODE_W_FULL if node["_depth"] < 2 else NODE_W_DIV

    def node_h(node):
        return NODE_H_FULL if node["_depth"] < 2 else NODE_H_DIV

    def subtree_width(node):
        if not node["children"]:
            return node_w(node)
        total = sum(subtree_width(c) for c in node["children"])
        total += H_GAP * (len(node["children"]) - 1)
        return max(total, node_w(node))

    # ── Assign posisi (x_center, y_center) ──
    positions = {}
    draw_list  = []

    def assign_pos(node, x_center, y):
        positions[node["id"]] = (x_center, y, node["_depth"])
        draw_list.append(node)
        if not node["children"]:
            return
        total_w = sum(subtree_width(c) for c in node["children"])
        total_w += H_GAP * (len(node["children"]) - 1)
        x_start = x_center - total_w / 2
        child_y  = y - (node_h(node)/2) - V_GAP - (NODE_H_DIV/2 if node["_depth"] == 1 else NODE_H_FULL/2)
        for child in node["children"]:
            cw = subtree_width(child)
            assign_pos(child, x_start + cw/2, child_y)
            x_start += cw + H_GAP

    # Hitung kedalaman maksimum
    def max_depth_tree(node):
        if not node["children"]:
            return node["_depth"]
        return max(max_depth_tree(c) for c in node["children"])

    actual_max_depth = max((max_depth_tree(r) for r in trimmed_roots), default=0)

    total_w = sum(subtree_width(r) for r in trimmed_roots) + H_GAP*(len(trimmed_roots)-1)
    # estimasi tinggi: level0 + gap + level1 + gap + level2
    h_levels = [NODE_H_FULL, NODE_H_FULL, NODE_H_DIV]
    total_h = sum(h_levels[:actual_max_depth+1]) + V_GAP * actual_max_depth + 130

    page_w = max(total_w + 120, landscape(A3)[0])
    page_h = max(total_h + 80,  landscape(A3)[1])

    x_start = page_w/2 - total_w/2
    y_top = page_h - 90
    for root in trimmed_roots:
        rw = subtree_width(root)
        assign_pos(root, x_start + rw/2, y_top)
        x_start += rw + H_GAP

    # ── Gambar PDF ──
    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=(page_w, page_h))

    # Background
    c.setFillColor(colors.HexColor("#0f1117"))
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Judul
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(page_w/2, page_h - 40, title_text)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#6b7280"))
    c.drawCentredString(page_w/2, page_h - 56,
        f"Ditampilkan hingga Level 2  ·  {len(draw_list)} node")

    # Label level di sisi kiri
    level_labels = {0: "Top Level", 1: "Level 1", 2: "Level 2"}
    y_seen = {}
    for node in draw_list:
        nx, ny, depth = positions[node["id"]]
        if depth not in y_seen:
            y_seen[depth] = ny
    for depth, label in level_labels.items():
        if depth in y_seen:
            c.setFillColor(colors.HexColor("#4b5563"))
            c.setFont("Helvetica-Bold", 8)
            c.drawString(12, y_seen[depth] - 4, label)
            # garis pemisah horizontal tipis
            c.setStrokeColor(colors.HexColor("#1f2937"))
            c.setLineWidth(0.5)
            c.line(70, y_seen[depth] - node_h({"_depth": depth})/2 - V_GAP/2,
                   page_w - 20, y_seen[depth] - node_h({"_depth": depth})/2 - V_GAP/2)

    # Garis konektor
    c.setStrokeColor(colors.HexColor("#3d4160"))
    c.setLineWidth(1.2)
    for node in draw_list:
        nx, ny, depth = positions[node["id"]]
        nh = node_h(node)
        for child in node["children"]:
            if child["id"] not in positions:
                continue
            cx, cy, cd = positions[child["id"]]
            ch = node_h(child)
            p_bottom_y = ny - nh/2
            c_top_y    = cy + ch/2
            mid_y = (p_bottom_y + c_top_y) / 2
            c.line(nx, p_bottom_y, nx, mid_y)
            c.line(nx, mid_y, cx, mid_y)
            c.line(cx, mid_y, cx, c_top_y)

    # Node boxes
    for node in draw_list:
        nx, ny, depth = positions[node["id"]]
        nw = node_w(node)
        nh = node_h(node)
        x_left   = nx - nw/2
        y_bottom = ny - nh/2

        if depth < 2:
            # Level 0 & 1 — full detail
            if node.get("in_div", True):
                fill   = colors.HexColor("#CCCCFF")
                txt    = colors.HexColor("#1a1a2e")
                border = colors.HexColor("#9999ee")
            else:
                fill   = colors.HexColor("#2a2d3e")
                txt    = colors.HexColor("#c0c8e0")
                border = colors.HexColor("#3d4160")

            c.setFillColor(fill)
            c.setStrokeColor(border)
            c.setLineWidth(1.5)
            c.roundRect(x_left, y_bottom, nw, nh, 7, fill=1, stroke=1)

            # Nama
            c.setFillColor(txt)
            c.setFont("Helvetica-Bold", 8)
            name = node["name"][:24] + "…" if len(node["name"]) > 24 else node["name"]
            c.drawCentredString(nx, y_bottom + nh - 15, name)

            # Job Position
            c.setFont("Helvetica", 7)
            pos = node["position"][:28] + "…" if len(node["position"]) > 28 else node["position"]
            c.drawCentredString(nx, y_bottom + nh - 27, pos)

            # Division
            c.setFont("Helvetica", 6.5)
            div = node["division"][:30] + "…" if len(node["division"]) > 30 else node["division"]
            c.drawCentredString(nx, y_bottom + nh - 39, div)

            # Business Unit
            c.setFont("Helvetica-Oblique", 6)
            c.setFillColor(colors.HexColor("#888888") if not node.get("in_div") else colors.HexColor("#3d3d6b"))
            bu = node["bu"][:30] + "…" if len(node["bu"]) > 30 else node["bu"]
            c.drawCentredString(nx, y_bottom + nh - 51, bu)

        else:
            # Level 2 — hanya Division
            c.setFillColor(colors.HexColor("#1e2433"))
            c.setStrokeColor(colors.HexColor("#3d4160"))
            c.setLineWidth(1)
            c.roundRect(x_left, y_bottom, nw, nh, 5, fill=1, stroke=1)

            c.setFillColor(colors.HexColor("#94a3b8"))
            c.setFont("Helvetica", 7)
            div = node["division"][:22] + "…" if len(node["division"]) > 22 else node["division"]
            c.drawCentredString(nx, y_bottom + nh/2 - 4, div)

    # Legend
    ly = 28
    lx = 40
    c.setFillColor(colors.HexColor("#CCCCFF"))
    c.setStrokeColor(colors.HexColor("#9999ee"))
    c.roundRect(lx, ly, 12, 12, 3, fill=1, stroke=1)
    c.setFillColor(colors.white); c.setFont("Helvetica", 7.5)
    c.drawString(lx+16, ly+2, "Top/Level 1 (divisi ini)")

    c.setFillColor(colors.HexColor("#2a2d3e"))
    c.setStrokeColor(colors.HexColor("#3d4160"))
    c.roundRect(lx+150, ly, 12, 12, 3, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#a0a8c0"))
    c.drawString(lx+166, ly+2, "Top/Level 1 (atasan luar)")

    c.setFillColor(colors.HexColor("#1e2433"))
    c.setStrokeColor(colors.HexColor("#3d4160"))
    c.roundRect(lx+310, ly, 12, 12, 3, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#94a3b8"))
    c.drawString(lx+326, ly+2, "Level 2 (nama divisi saja)")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# ══════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════
st.set_page_config(page_title="OrgChart HR", layout="wide", page_icon="🏢", initial_sidebar_state="expanded")

# ── Dark/Light mode state ──
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# ── Active tab navigation from sidebar cards ──
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0   # 0=OrgChart, 1=DataKaryawan, 2=Manager ID Hilang, 3=Manager List
if "nav_filter" not in st.session_state:
    st.session_state.nav_filter = {}  # konteks filter dari card click

# ══════════════════════════════════════════
# LOAD DATA — Google Sheets via Service Account, CSV fallback
# ══════════════════════════════════════════
import gspread
from google.oauth2.service_account import Credentials
import os

SHEET_ID   = "1LaZpDfmFZJvIARf0RYoX-DtcbkjgOMlwT74nbamnvqM"
CREDS_FILE = "credentials.json"
SCOPES     = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def clean_df(df):
    df.columns = df.columns.str.strip()
    df["Employee ID"] = df["Employee ID"].astype(str).str.strip()
    df["Manager ID"]  = df["Manager ID"].fillna("").astype(str).str.strip()
    df["SBU/Tribe"]   = df["SBU/Tribe"].fillna("").astype(str).str.strip()
    return df

@st.cache_data(ttl=300)
def load_data():
    # ── Coba via Streamlit Secrets (untuk deployment online) ──
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]),
                scopes=SCOPES
            )
            client = gspread.authorize(creds)
            sheet  = client.open_by_key(SHEET_ID).sheet1
            data   = sheet.get_all_records()
            df     = pd.DataFrame(data)
            return clean_df(df), "google_sheets"
    except Exception as e:
        st.warning(f"⚠️ Gagal membaca via Secrets: {str(e)[:80]}")

    # ── Coba via credentials.json lokal (untuk run di laptop) ──
    if os.path.exists(CREDS_FILE):
        try:
            creds  = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
            client = gspread.authorize(creds)
            sheet  = client.open_by_key(SHEET_ID).sheet1
            data   = sheet.get_all_records()
            df     = pd.DataFrame(data)
            return clean_df(df), "google_sheets"
        except Exception as e:
            st.warning(f"⚠️ Gagal membaca Google Sheets: {str(e)[:80]}. Menggunakan data lokal.")

    # ── Fallback ke CSV lokal ──
    try:
        df = pd.read_csv("employee_data.csv")
        return clean_df(df), "local_csv"
    except:
        return None, "error"

df, data_source = load_data()

# ══════════════════════════════════════════
# GSPREAD CLIENT — untuk write ke Sheets
# ══════════════════════════════════════════
def get_gspread_client():
    """Buat gspread client dengan credentials yang tersedia."""
    try:
        if "gcp_service_account" in st.secrets:
            creds  = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
        elif os.path.exists(CREDS_FILE):
            creds  = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
        else:
            return None
        return gspread.authorize(creds)
    except Exception:
        return None

def get_cr_sheet():
    """Ambil worksheet change_requests dari Google Sheets."""
    client = get_gspread_client()
    if not client:
        return None
    try:
        wb = client.open_by_key(SHEET_ID)
        return wb.worksheet("change_requests")
    except Exception:
        return None

def load_change_requests():
    """Load semua change requests dari Google Sheets."""
    ws = get_cr_sheet()
    if not ws:
        return pd.DataFrame()
    try:
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame(columns=[
                "request_id","submitted_date","requester_name","requester_email",
                "change_type","employee_id","employee_name","data_lama","data_baru",
                "alasan","status","reviewed_by","reviewed_date","catatan"
            ])
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

def save_change_request(row_data: dict):
    """Tambah satu baris request baru ke sheet."""
    ws = get_cr_sheet()
    if not ws:
        return False
    try:
        cols = ["request_id","submitted_date","requester_name","requester_email",
                "change_type","employee_id","employee_name","data_lama","data_baru",
                "alasan","status","reviewed_by","reviewed_date","catatan"]
        row = [str(row_data.get(c, "")) for c in cols]
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        st.error(f"Gagal menyimpan: {e}")
        return False

def update_cr_status(request_id: str, status: str, reviewed_by: str, catatan: str):
    """Update status request di Google Sheets berdasarkan request_id."""
    ws = get_cr_sheet()
    if not ws:
        return False
    try:
        cell = ws.find(request_id)
        if not cell:
            return False
        row = cell.row
        # Kolom: status=11, reviewed_by=12, reviewed_date=13, catatan=14
        from datetime import datetime
        ws.update_cell(row, 11, status)
        ws.update_cell(row, 12, reviewed_by)
        ws.update_cell(row, 13, datetime.now().strftime("%Y-%m-%d %H:%M"))
        ws.update_cell(row, 14, catatan)
        return True
    except Exception as e:
        st.error(f"Gagal update: {e}")
        return False

def generate_request_id():
    """Generate ID unik untuk request baru."""
    import time
    return f"REQ-{int(time.time())}"

if df is None:
    st.error("❌ Tidak ada data yang bisa dimuat. Pastikan credentials.json dan employee_data.csv tersedia.")
    st.stop()

# ══════════════════════════════════════════
# THEME — Dark / Light
# ══════════════════════════════════════════
dm = st.session_state.dark_mode

T = {
    "bg":           "#0f1117" if dm else "#f5f5f7",
    "bg2":          "#1a1d2e" if dm else "#ffffff",
    "bg3":          "#252840" if dm else "#f0eeff",
    "sidebar_bg":   "#1a1040" if dm else "#CCCCFF",
    "sidebar_text": "#e8e6ff" if dm else "#1a1040",
    "sidebar_text2":"#a89eef" if dm else "#4a3fa0",
    "sidebar_active":"#ffffff" if dm else "#ffffff",
    "sidebar_active_bg": "#3d2fa0" if dm else "#5b4fcf",
    "sidebar_hover": "#2d2060" if dm else "#b8b0ff",
    "border":       "#2d3160" if dm else "#e2e0f5",
    "border2":      "#3d4180" if dm else "#c4b5fd",
    "text":         "#e8e6ff" if dm else "#1a1040",
    "text2":        "#9e9ec8" if dm else "#4a4a7a",
    "text3":        "#6b6b9e" if dm else "#7a7aaa",
    "accent":       "#9b8fef" if dm else "#5b4fcf",
    "accent2":      "#b8b0ff" if dm else "#7c6fcd",
    "accent_bg":    "#1e1a3a" if dm else "#ede9fe",
    "node_in_bg":   "linear-gradient(135deg,#2a2060,#3d2f8a)" if dm else "linear-gradient(135deg,#ede9fe,#ddd6fe)",
    "node_in_txt":  "#e0d8ff" if dm else "#2e1a6e",
    "node_in_bdr":  "#5b4fcf" if dm else "#c4b5fd",
    "node_out_bg":  "#1a1d2e" if dm else "#ffffff",
    "node_out_txt": "#9e9ec8" if dm else "#4b5563",
    "node_out_bdr": "#2d3160" if dm else "#e5e7eb",
    "connector":    "#2d3160" if dm else "#ddd6fe",
    "badge_bg":     "#7c6fcd" if dm else "#5b4fcf",
    "chart_bg":     "#0f1117" if dm else "#f5f5f7",
    "tb_bg":        "#1a1d2e" if dm else "#ffffff",
    "tb_color":     "#9b8fef" if dm else "#7c6fcd",
    "tb_border":    "#2d3160" if dm else "#ede9fe",
    "metric_shadow":"rgba(124,111,205,0.18)" if dm else "rgba(91,79,207,0.08)",
    "dl_btn_bg":    "#1a1d2e" if dm else "#ffffff",
    "dl_btn_color": "#9b8fef" if dm else "#5b4fcf",
    "input_bg":     "#1a1d2e" if dm else "#ffffff",
    "success_bg":   "#0f2a1a" if dm else "#f0fff4",
    "success_bdr":  "#166534" if dm else "#86efac",
    "success_txt":  "#86efac" if dm else "#166534",
    "warn_bg":      "#2a1f00" if dm else "#fffbeb",
    "warn_bdr":     "#92400e" if dm else "#fde68a",
    "warn_txt":     "#fde68a" if dm else "#92400e",
    "tab_active":   "#9b8fef" if dm else "#5b4fcf",
    "tab_inactive": "#4a4a7a" if dm else "#9e9ec0",
    "divider":      "#2d3160" if dm else "#e2e0f5",
    "radio_txt":    "#c4b5fd" if dm else "#4b4b6b",
    "label_txt":    "#6b6b9e" if dm else "#9e9ec0",
    "section_bg":   "#13152a" if dm else "#ffffff",
    "section_bdr":  "#2d3160" if dm else "#e2e0f5",
}

# ══════════════════════════════════════════
# GLOBAL CSS — Split Layout
# ══════════════════════════════════════════
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=DM+Sans:wght@300;400;500;600;700&display=swap');

/* ── Reset & Base ── */
*, *::before, *::after {{ box-sizing: border-box; }}
html, body, [class*="css"] {{
    font-family: 'DM Sans', sans-serif !important;
    color: {T["text"]} !important;
}}

/* ── Full app background ── */
.stApp {{
    background: {T["bg"]} !important;
}}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header {{ visibility: hidden !important; }}
[data-testid="stToolbar"] {{ display: none !important; }}

/* ── Force full viewport ── */
.stApp > div:first-child {{
    min-height: 100vh;
}}

/* ── Main block container — right panel ── */
.block-container {{
    padding: 0 !important;
    max-width: 100% !important;
    background: {T["bg"]} !important;
}}

/* ── SIDEBAR — Fixed left panel ── */
[data-testid="stSidebar"] {{
    background: {T["sidebar_bg"]} !important;
    min-width: 260px !important;
    max-width: 260px !important;
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    height: 100vh !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    border-right: none !important;
    box-shadow: 4px 0 24px rgba(0,0,0,0.12) !important;
    z-index: 999 !important;
    transition: background 0.3s ease !important;
}}
[data-testid="stSidebar"] > div {{
    padding: 0 !important;
    height: 100% !important;
}}
[data-testid="stSidebar"] .block-container {{
    padding: 0 !important;
    background: transparent !important;
}}
[data-testid="stSidebar"] * {{
    color: {T["sidebar_text"]} !important;
}}

/* Sidebar scrollbar */
[data-testid="stSidebar"]::-webkit-scrollbar {{ width: 4px; }}
[data-testid="stSidebar"]::-webkit-scrollbar-track {{ background: transparent; }}
[data-testid="stSidebar"]::-webkit-scrollbar-thumb {{ background: {T["sidebar_hover"]}; border-radius: 2px; }}

/* ── MAIN CONTENT — offset for sidebar ── */
section.main > div {{
    margin-left: 260px !important;
    padding: 0 !important;
    min-height: 100vh !important;
}}

/* ── Tabs — hide native Streamlit tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    display: none !important;
}}
[data-testid="stTabs"] [data-baseweb="tab-panel"] {{
    padding: 0 !important;
}}

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div {{
    background: {T["input_bg"]} !important;
    border: 1.5px solid {T["border"]} !important;
    border-radius: 10px !important;
    font-size: 14px !important;
    color: {T["text"]} !important;
}}
[data-testid="stSelectbox"] > div > div:focus-within {{
    border-color: {T["accent"]} !important;
    box-shadow: 0 0 0 3px {T["accent_bg"]} !important;
}}
[data-testid="stSelectbox"] svg {{ fill: {T["text2"]} !important; }}
div[data-baseweb="popover"] ul,
div[data-baseweb="menu"] {{
    background: {T["bg2"]} !important;
    border: 1px solid {T["border"]} !important;
    border-radius: 10px !important;
}}
div[data-baseweb="popover"] li,
[role="option"] {{
    background: {T["bg2"]} !important;
    color: {T["text"]} !important;
}}
div[data-baseweb="popover"] li:hover,
[role="option"]:hover {{
    background: {T["accent_bg"]} !important;
    color: {T["accent"]} !important;
}}

/* ── Radio ── */
[data-testid="stRadio"] label {{
    font-size: 13px !important;
    font-weight: 500 !important;
    color: {T["radio_txt"]} !important;
}}

/* ── Metric cards ── */
div[data-testid="stMetric"] {{
    background: {T["bg2"]} !important;
    border-radius: 16px !important;
    padding: 20px 24px !important;
    border: 1px solid {T["border"]} !important;
    box-shadow: 0 2px 16px {T["metric_shadow"]} !important;
    transition: all 0.25s ease !important;
}}
div[data-testid="stMetric"]:hover {{
    box-shadow: 0 8px 32px {T["metric_shadow"]} !important;
    transform: translateY(-2px) !important;
}}
div[data-testid="stMetric"] label {{
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    color: {T["text3"]} !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    font-size: 30px !important;
    font-weight: 700 !important;
    color: {T["text"]} !important;
    font-family: 'Sora', sans-serif !important;
}}

/* ── Buttons ── */
[data-testid="stButton"] button {{
    background: {T["accent"]} !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    transition: all 0.2s !important;
}}
[data-testid="stButton"] button:hover {{
    background: {T["accent2"]} !important;
    box-shadow: 0 4px 16px rgba(124,111,205,0.4) !important;
    transform: translateY(-1px) !important;
}}

/* ── Download buttons ── */
[data-testid="stDownloadButton"] button {{
    background: {T["dl_btn_bg"]} !important;
    color: {T["dl_btn_color"]} !important;
    border: 1.5px solid {T["border"]} !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    transition: all 0.2s !important;
}}
[data-testid="stDownloadButton"] button:hover {{
    background: {T["accent_bg"]} !important;
    border-color: {T["accent"]} !important;
}}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {{
    border-radius: 12px !important;
    overflow: hidden !important;
    border: 1px solid {T["border"]} !important;
}}

/* ── Text input ── */
[data-testid="stTextInput"] input {{
    background: {T["input_bg"]} !important;
    border: 1.5px solid {T["border"]} !important;
    border-radius: 10px !important;
    font-size: 14px !important;
    color: {T["text"]} !important;
}}
[data-testid="stTextInput"] input:focus {{
    border-color: {T["accent"]} !important;
    box-shadow: 0 0 0 3px {T["accent_bg"]} !important;
}}
[data-testid="stTextInput"] input::placeholder {{ color: {T["text3"]} !important; }}

/* ── Textarea ── */
[data-testid="stTextArea"] textarea {{
    background: {T["input_bg"]} !important;
    border: 1.5px solid {T["border"]} !important;
    border-radius: 10px !important;
    color: {T["text"]} !important;
    font-size: 14px !important;
    font-family: 'DM Sans', sans-serif !important;
}}
[data-testid="stTextArea"] textarea:focus {{
    border-color: {T["accent"]} !important;
    box-shadow: 0 0 0 3px {T["accent_bg"]} !important;
}}
[data-testid="stTextArea"] textarea::placeholder {{ color: {T["text3"]} !important; }}

/* ── Number input ── */
[data-testid="stNumberInput"] input {{
    background: {T["input_bg"]} !important;
    border: 1.5px solid {T["border"]} !important;
    border-radius: 10px !important;
    color: {T["text"]} !important;
    font-size: 14px !important;
}}
[data-testid="stNumberInput"] button {{
    background: {T["bg3"]} !important;
    border: 1px solid {T["border"]} !important;
    color: {T["text"]} !important;
}}

/* ── Date input ── */
[data-testid="stDateInput"] > div > div {{
    background: {T["input_bg"]} !important;
    border: 1.5px solid {T["border"]} !important;
    border-radius: 10px !important;
}}
[data-testid="stDateInput"] input {{
    color: {T["text"]} !important;
    background: transparent !important;
}}

/* ── Calendar popup ── */
div[data-baseweb="calendar"] {{
    background: {T["bg2"]} !important;
    border: 1px solid {T["border"]} !important;
    border-radius: 14px !important;
}}
div[data-baseweb="calendar"] * {{ color: {T["text"]} !important; font-family: 'DM Sans', sans-serif !important; }}
div[data-baseweb="calendar"] button {{ background: transparent !important; border-radius: 8px !important; border: none !important; }}
div[data-baseweb="calendar"] button:hover {{ background: {T["accent_bg"]} !important; color: {T["accent"]} !important; }}
div[data-baseweb="calendar"] [aria-selected="true"] button {{ background: {T["accent"]} !important; color: white !important; border-radius: 50% !important; }}
div[data-baseweb="calendar"] [data-baseweb="button"] {{ background: {T["bg3"]} !important; }}
div[data-baseweb="calendar"] [data-baseweb="button"]:hover {{ background: {T["accent_bg"]} !important; }}

/* ── Form container ── */
[data-testid="stForm"] {{
    background: {T["bg2"]} !important;
    border: 1px solid {T["border"]} !important;
    border-radius: 16px !important;
    padding: 24px !important;
}}

/* ── Expander ── */
[data-testid="stExpander"] {{
    background: {T["bg2"]} !important;
    border: 1px solid {T["border"]} !important;
    border-radius: 12px !important;
    margin-bottom: 8px !important;
}}
[data-testid="stExpander"] summary {{
    color: {T["text"]} !important;
    font-weight: 500 !important;
}}

/* ── Alerts ── */
[data-testid="stAlert"] {{
    border-radius: 12px !important;
    font-size: 13px !important;
    background: {T["bg2"]} !important;
    color: {T["text"]} !important;
}}

/* ── Caption ── */
[data-testid="stCaptionContainer"] p {{ color: {T["text3"]} !important; }}
small {{ color: {T["text3"]} !important; }}

/* ── Divider ── */
hr {{ border-color: {T["divider"]} !important; }}

/* ── Form submit button ── */
[data-testid="stFormSubmitButton"] button {{
    background: {T["accent"]} !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 12px !important;
    transition: all 0.2s !important;
    width: 100% !important;
}}
[data-testid="stFormSubmitButton"] button:hover {{
    background: {T["accent2"]} !important;
    box-shadow: 0 4px 16px rgba(124,111,205,0.4) !important;
    transform: translateY(-1px) !important;
}}

/* ── Nested tabs (sub-tabs) ── */
[data-testid="stTabs"] [data-testid="stTabs"] [data-baseweb="tab-list"] {{
    display: flex !important;
    border-bottom: 1px solid {T["border"]} !important;
    background: transparent !important;
    padding: 0 !important;
    margin-bottom: 16px !important;
}}
[data-testid="stTabs"] [data-testid="stTabs"] button {{
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    color: {T["tab_inactive"]} !important;
    padding: 8px 16px !important;
    border-radius: 0 !important;
    background: transparent !important;
}}
[data-testid="stTabs"] [data-testid="stTabs"] button[aria-selected="true"] {{
    color: {T["tab_active"]} !important;
    border-bottom: 2px solid {T["tab_active"]} !important;
}}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════
# SIDEBAR — New Fixed Navigation
# ══════════════════════════════════════════
with st.sidebar:
    total_karyawan = len(df)
    total_bu       = df["Business Unit"].nunique()
    total_div      = df["Division"].nunique()
    total_mgr      = df[df["Employee ID"].isin(df["Manager ID"].unique())]["Employee ID"].nunique()
    toggle_icon    = "☀️" if dm else "🌙"
    toggle_label   = "Light Mode" if dm else "Dark Mode"
    status_dot     = "🟢" if data_source == "google_sheets" else "🟡"
    status_txt     = "Live · Google Sheets" if data_source == "google_sheets" else "Lokal · CSV"

    st.markdown(f"""
    <style>
    /* ── Override all sidebar buttons to nav style ── */
    [data-testid="stSidebar"] [data-testid="stButton"] button {{
        background: transparent !important;
        color: {T['sidebar_text']} !important;
        border: none !important;
        border-radius: 12px !important;
        text-align: left !important;
        font-size: 13.5px !important;
        font-weight: 500 !important;
        padding: 11px 16px !important;
        box-shadow: none !important;
        margin-bottom: 2px !important;
        width: 100% !important;
        transition: all 0.18s ease !important;
        font-family: 'DM Sans', sans-serif !important;
    }}
    [data-testid="stSidebar"] [data-testid="stButton"] button:hover {{
        background: {T['sidebar_hover']} !important;
        color: {T['sidebar_active']} !important;
        transform: translateX(4px) !important;
    }}
    </style>

    <!-- Brand -->
    <div style="padding: 28px 20px 20px 20px; border-bottom: 1px solid rgba(255,255,255,0.15);">
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:16px;">
            <div style="
                width:42px; height:42px; border-radius:12px;
                background: rgba(255,255,255,0.2);
                display:flex; align-items:center; justify-content:center;
                font-size:22px; flex-shrink:0; backdrop-filter: blur(10px);
            ">🏢</div>
            <div>
                <div style="font-size:16px; font-weight:700; color:{T['sidebar_active']}; line-height:1.2; font-family:'Sora',sans-serif;">Mekari</div>
                <div style="font-size:11px; color:{T['sidebar_text2']}; font-weight:500;">Organizational Chart Dashboard</div>
            </div>
        </div>
        <!-- Data status -->
        <div style="
            background: rgba(255,255,255,0.12); border-radius:8px;
            padding: 7px 12px; display:flex; align-items:center; gap:7px;
        ">
            <span style="font-size:9px;">{status_dot}</span>
            <span style="font-size:11px; color:{T['sidebar_text2']}; font-weight:500;">{status_txt}</span>
        </div>
    </div>

    <!-- Stats strip -->
    <div style="padding: 16px 20px; border-bottom: 1px solid rgba(255,255,255,0.1);">
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
            <div style="background:rgba(255,255,255,0.1); border-radius:10px; padding:10px 12px; text-align:center;">
                <div style="font-size:18px; font-weight:700; color:{T['sidebar_active']}; font-family:'Sora',sans-serif;">{total_karyawan:,}</div>
                <div style="font-size:10px; color:{T['sidebar_text2']}; font-weight:500; margin-top:2px;">Karyawan</div>
            </div>
            <div style="background:rgba(255,255,255,0.1); border-radius:10px; padding:10px 12px; text-align:center;">
                <div style="font-size:18px; font-weight:700; color:{T['sidebar_active']}; font-family:'Sora',sans-serif;">{total_mgr}</div>
                <div style="font-size:10px; color:{T['sidebar_text2']}; font-weight:500; margin-top:2px;">Manager</div>
            </div>
            <div style="background:rgba(255,255,255,0.1); border-radius:10px; padding:10px 12px; text-align:center;">
                <div style="font-size:18px; font-weight:700; color:{T['sidebar_active']}; font-family:'Sora',sans-serif;">{total_bu}</div>
                <div style="font-size:10px; color:{T['sidebar_text2']}; font-weight:500; margin-top:2px;">Business Unit</div>
            </div>
            <div style="background:rgba(255,255,255,0.1); border-radius:10px; padding:10px 12px; text-align:center;">
                <div style="font-size:18px; font-weight:700; color:{T['sidebar_active']}; font-family:'Sora',sans-serif;">{total_div}</div>
                <div style="font-size:10px; color:{T['sidebar_text2']}; font-weight:500; margin-top:2px;">Divisi</div>
            </div>
        </div>
    </div>

    <!-- Nav menu label -->
    <div style="padding: 16px 20px 8px 20px;">
        <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; color:{T['sidebar_text2']};">Menu</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Nav menu buttons ──
    nav_items = [
        ("📊", "Data Summary",       "sec-summary"),
        ("🌳", "Org Chart",          "sec-orgchart"),
        ("👥", "Data Karyawan",      "sec-karyawan"),
        ("⚠️", "Manager ID Hilang",  "sec-managerid"),
        ("👔", "Daftar Manager",     "sec-manager"),
        ("📝", "Change Request",     "sec-changereq"),
    ]
    for icon_nav, label_nav, sec_id in nav_items:
        if st.button(f"{icon_nav}  {label_nav}", key=f"nav_{sec_id}", use_container_width=True):
            st.session_state[f"scroll_to"] = sec_id
            st.rerun()

    st.markdown(f"""
    <div style="padding: 0 20px; margin-top: 4px;">
        <div style="height:1px; background:rgba(255,255,255,0.12); margin:12px 0;"></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Refresh & Toggle ──
    col_sb1, col_sb2 = st.columns(2)
    with col_sb1:
        if st.button("🔄 Refresh", use_container_width=True, key="refresh_btn"):
            st.cache_data.clear()
            st.rerun()
    with col_sb2:
        if st.button(f"{toggle_icon} Mode", use_container_width=True, key="toggle_btn"):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

    st.markdown(f"""
    <div style="padding: 16px 20px; position:absolute; bottom:0; left:0; right:0;">
        <div style="font-size:10px; color:{T['sidebar_text2']}; text-align:center;">
            Auto-refresh setiap 5 menit
        </div>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════
# MAIN CONTENT — Scrollable Sections
# ══════════════════════════════════════════

# JS scroll-to-section handler
scroll_target = st.session_state.get("scroll_to", "")
if scroll_target:
    st.markdown(f"""
    <script>
    (function() {{
        function scrollToSection() {{
            const el = document.getElementById("{scroll_target}");
            if (el) {{
                el.scrollIntoView({{ behavior: "smooth", block: "start" }});
                return true;
            }}
            return false;
        }}
        let attempts = 0;
        const iv = setInterval(function() {{
            if (scrollToSection() || attempts > 20) clearInterval(iv);
            attempts++;
        }}, 100);
    }})();
    </script>
    """, unsafe_allow_html=True)
    st.session_state["scroll_to"] = ""

# Section wrapper helper
def section_header(sec_id, icon, title, subtitle=""):
    return f"""
    <div id="{sec_id}" style="
        padding: 32px 40px 0 40px;
        scroll-margin-top: 20px;
    ">
        <div style="display:flex; align-items:center; gap:14px; margin-bottom:6px;">
            <div style="
                width:44px; height:44px; border-radius:12px;
                background: linear-gradient(135deg, #5b4fcf, #9b8fef);
                display:flex; align-items:center; justify-content:center;
                font-size:20px; flex-shrink:0;
                box-shadow: 0 4px 16px rgba(91,79,207,0.3);
            ">{icon}</div>
            <div>
                <div style="font-size:22px; font-weight:700; color:{T['text']}; font-family:'Sora',sans-serif; line-height:1.2;">{title}</div>
                {"" if not subtitle else f'<div style="font-size:13px; color:{T["text3"]}; margin-top:3px;">{subtitle}</div>'}
            </div>
        </div>
        <div style="height:1px; background:{T['border']}; margin: 16px 0 24px 0;"></div>
    </div>
    """

def section_body_start():
    return f'<div style="padding: 0 40px 40px 40px;">'

def section_body_end():
    return '</div>'

def section_divider():
    return f'<div style="height:8px; background:{T["bg"]}; margin:0;"></div>'

# Keep tabs for content organization (hidden via CSS)
TAB_LABELS = ["🌳  Org Chart", "📋  Data Karyawan", "⚠️  Manager ID Hilang", "👔  Daftar Manager", "📝  Change Request"]
active = st.session_state.active_tab
tab1, tab2, tab3, tab4, tab5 = st.tabs(TAB_LABELS)

# ══════════════════════════════════════════
# ORG CHART HTML
# ══════════════════════════════════════════
def render_org_chart(tree_json_str, chart_height=700, initial_level="all", theme=None):
    level_map = {"all": "999", "top": "0", "level1": "1"}
    init_depth = level_map.get(initial_level, "999")

    # ── Resolve theme tokens ──
    th          = theme or {}
    bg          = th.get("chart_bg",    "#f8f7ff")
    node_in_bg  = th.get("node_in_bg",  "linear-gradient(135deg,#ede9fe,#ddd6fe)")
    node_in_txt = th.get("node_in_txt", "#2e1a6e")
    node_in_bdr = th.get("node_in_bdr", "#c4b5fd")
    node_out_bg = th.get("node_out_bg", "#ffffff")
    node_out_txt= th.get("node_out_txt","#4b5563")
    node_out_bdr= th.get("node_out_bdr","#e5e7eb")
    connector   = th.get("connector",   "#ddd6fe")
    badge_bg    = th.get("badge_bg",    "#5b4fcf")
    tb_bg       = th.get("tb_bg",       "#ffffff")
    tb_color    = th.get("tb_color",    "#7c6fcd")
    tb_border   = th.get("tb_border",   "#ede9fe")
    hint_color  = th.get("text3",       "#9e9ec0")

    html_code = f"""
<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: {bg}; font-family: 'DM Sans', sans-serif; overflow: hidden; width: 100%; height: {chart_height}px; }}
  .toolbar {{ position: fixed; top: 12px; right: 16px; display: flex; flex-direction: column; gap: 6px; z-index: 100; }}
  .tb-btn {{ width: 34px; height: 34px; background: {tb_bg}; border: 1.5px solid {tb_border}; border-radius: 10px; color: {tb_color}; font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s; user-select: none; box-shadow: 0 2px 8px rgba(91,79,207,0.08); }}
  .tb-btn:hover {{ background: {node_in_bg}; color: {tb_color}; border-color: {node_in_bdr}; box-shadow: 0 4px 16px rgba(91,79,207,0.16); transform: translateY(-1px); }}
  .zoom-label {{ background: {tb_bg}; border: 1.5px solid {tb_border}; border-radius: 8px; color: {hint_color}; font-size: 10px; font-weight: 700; text-align: center; padding: 4px 0; letter-spacing: 0.04em; }}
  #canvas {{ width: 100%; height: 100%; overflow: hidden; cursor: grab; position: relative; }}
  #canvas:active {{ cursor: grabbing; }}
  #tree-root {{ position: absolute; top: 40px; left: 50%; transform-origin: top center; display: flex; flex-direction: row; gap: 24px; align-items: flex-start; }}
  .node-wrapper {{ display: flex; flex-direction: column; align-items: center; }}
  .node-box {{
    padding: 12px 16px; border-radius: 14px; text-align: center;
    min-width: 160px; max-width: 210px; cursor: pointer;
    border: 1.5px solid transparent;
    transition: all 0.2s cubic-bezier(0.34,1.56,0.64,1);
    position: relative; user-select: none;
    box-shadow: 0 2px 12px rgba(91,79,207,0.08);
  }}
  .node-box:hover {{
    transform: translateY(-3px) scale(1.02);
    box-shadow: 0 12px 32px rgba(91,79,207,0.18);
  }}
  .node-box.in-div {{
    background: {node_in_bg};
    border-color: {node_in_bdr};
    color: {node_in_txt};
  }}
  .node-box.out-div {{
    background: {node_out_bg};
    border-color: {node_out_bdr};
    color: {node_out_txt};
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }}
  .node-box.company-mode {{
    background: linear-gradient(135deg, #5b4fcf, #7c6fcd);
    border-color: #4a3fb8;
    color: white;
    box-shadow: 0 4px 20px rgba(91,79,207,0.3);
  }}
  .badge {{
    position: absolute; top: -8px; right: -8px;
    background: {badge_bg}; color: white;
    border-radius: 999px; font-size: 9px; font-weight: 700;
    padding: 2px 7px; min-width: 20px;
    border: 2px solid #f8f7ff;
    box-shadow: 0 2px 8px rgba(91,79,207,0.3);
  }}
  .node-name {{ font-weight: 700; font-size: 12px; line-height: 1.3; margin-bottom: 3px; }}
  .node-pos {{ font-size: 10px; opacity: 0.8; line-height: 1.3; margin-bottom: 3px; }}
  .node-div {{ font-size: 9px; opacity: 0.6; margin-bottom: 1px; }}
  .node-sbu {{ font-size: 9px; opacity: 0.45; font-style: italic; }}
  .connector-v {{ width: 2px; background: {connector}; flex-shrink: 0; }}
  .children-row {{ display: flex; flex-direction: row; align-items: flex-start; position: relative; }}
  .children-row::before {{ content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%); height: 2px; background: {connector}; width: calc(100% - 100px); pointer-events: none; }}
  .single-child::before {{ display: none !important; }}
  .child-col {{ display: flex; flex-direction: column; align-items: center; padding: 0 10px; }}
  .collapsed-hint {{ font-size: 10px; color: {hint_color}; margin-top: 4px; text-align: center; font-weight: 500; }}
  .legend {{ position: fixed; bottom: 16px; left: 16px; display: flex; gap: 16px; font-size: 11px; color: #a0a8c0; background: rgba(15,17,23,0.9); padding: 8px 14px; border-radius: 10px; border: 1px solid #2d3448; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}
</style></head><body>
<div class="toolbar">
  <button class="tb-btn" onclick="zoomIn()">＋</button>
  <div class="zoom-label" id="zoom-label">100%</div>
  <button class="tb-btn" onclick="zoomOut()">－</button>
  <button class="tb-btn" onclick="resetView()" style="font-size:13px">⟳</button>
  <button class="tb-btn" onclick="fitView()" style="font-size:12px">⤢</button>
</div>
<div id="canvas"><div id="tree-root"></div></div>
<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#CCCCFF;border:1px solid #9999ee"></div><span>Divisi ini</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:#2a2d3e;border:1px solid #3d4160"></div><span>Atasan luar divisi</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:#f59e0b;border-radius:999px"></div><span>Jml subordinate</span></div>
  <div class="legend-item" style="color:#5a6080">💡 Klik node • Scroll zoom • Drag geser</div>
</div>
<script>
const treeData = {tree_json_str};
const collapsed = {{}};
let initDepth = {init_depth};

let scale = 1, translateX = 0, translateY = 0;
let isDragging = false, dragStartX = 0, dragStartY = 0, dragStartTX = 0, dragStartTY = 0;
const canvas = document.getElementById('canvas');
const treeRoot = document.getElementById('tree-root');

function applyTransform() {{
  treeRoot.style.transform = `translateX(calc(-50% + ${{translateX}}px)) translateY(${{translateY}}px) scale(${{scale}})`;
  document.getElementById('zoom-label').textContent = Math.round(scale * 100) + '%';
}}
function zoomIn() {{ scale = Math.min(scale + 0.15, 3); applyTransform(); }}
function zoomOut() {{ scale = Math.max(scale - 0.15, 0.2); applyTransform(); }}
function resetView() {{ scale = 1; translateX = 0; translateY = 0; applyTransform(); }}
function fitView() {{
  const treeW = treeRoot.scrollWidth, treeH = treeRoot.scrollHeight;
  scale = Math.min(canvas.clientWidth / (treeW + 60), canvas.clientHeight / (treeH + 60), 1);
  translateX = 0; translateY = 20; applyTransform();
}}
canvas.addEventListener('wheel', (e) => {{
  e.preventDefault();
  scale = Math.max(0.2, Math.min(3, scale + (e.deltaY > 0 ? -0.1 : 0.1)));
  applyTransform();
}}, {{ passive: false }});
canvas.addEventListener('mousedown', (e) => {{
  if (e.target.closest('.node-box')) return;
  isDragging = true; dragStartX = e.clientX; dragStartY = e.clientY;
  dragStartTX = translateX; dragStartTY = translateY;
}});
window.addEventListener('mousemove', (e) => {{
  if (!isDragging) return;
  translateX = dragStartTX + (e.clientX - dragStartX);
  translateY = dragStartTY + (e.clientY - dragStartY);
  applyTransform();
}});
window.addEventListener('mouseup', () => {{ isDragging = false; }});

function countDescendants(node) {{
  let count = 0;
  for (const c of node.children || []) count += 1 + countDescendants(c);
  return count;
}}

function getNodeDepth(nodeId, nodes, depth) {{
  for (const n of nodes) {{
    if (n.id === nodeId) return depth;
    const found = getNodeDepth(nodeId, n.children || [], depth + 1);
    if (found !== -1) return found;
  }}
  return -1;
}}

// Pre-collapse berdasarkan level
function applyInitialCollapse(node, depth) {{
  if (initDepth < 999 && depth >= initDepth && node.children && node.children.length > 0) {{
    collapsed[node.id] = true;
  }}
  for (const child of node.children || []) {{
    applyInitialCollapse(child, depth + 1);
  }}
}}

function renderNode(node) {{
  const isCollapsed = collapsed[node.id] || false;
  const hasChildren = node.children && node.children.length > 0;
  const descCount = countDescendants(node);
  const wrapper = document.createElement('div');
  wrapper.className = 'node-wrapper';
  const box = document.createElement('div');
  const modeClass = node.company_mode ? 'company-mode' : (node.in_div ? 'in-div' : 'out-div');
  box.className = `node-box ${{modeClass}}`;

  if (hasChildren && descCount > 0) {{
    const badge = document.createElement('div');
    badge.className = 'badge';
    badge.textContent = isCollapsed ? descCount : node.children.length;
    box.appendChild(badge);
  }}

  const nameEl = document.createElement('div'); nameEl.className = 'node-name'; nameEl.textContent = node.name;
  const posEl = document.createElement('div'); posEl.className = 'node-pos'; posEl.textContent = node.position;
  const divEl = document.createElement('div'); divEl.className = 'node-div'; divEl.textContent = node.division;
  box.appendChild(nameEl); box.appendChild(posEl); box.appendChild(divEl);

  if (node.sbu && node.sbu !== '' && node.sbu !== 'nan') {{
    const sbuEl = document.createElement('div'); sbuEl.className = 'node-sbu'; sbuEl.textContent = node.sbu;
    box.appendChild(sbuEl);
  }}

  if (hasChildren) {{
    box.addEventListener('click', () => {{ collapsed[node.id] = !collapsed[node.id]; rerenderTree(); }});
    box.title = isCollapsed ? 'Klik untuk expand' : 'Klik untuk collapse';
  }}
  wrapper.appendChild(box);

  if (hasChildren && !isCollapsed) {{
    const connV = document.createElement('div'); connV.className = 'connector-v'; connV.style.height = '20px';
    wrapper.appendChild(connV);
    const childRow = document.createElement('div');
    childRow.className = 'children-row' + (node.children.length <= 1 ? ' single-child' : '');
    node.children.forEach(child => {{
      const col = document.createElement('div'); col.className = 'child-col';
      const connTop = document.createElement('div'); connTop.className = 'connector-v'; connTop.style.height = '20px';
      col.appendChild(connTop); col.appendChild(renderNode(child)); childRow.appendChild(col);
    }});
    wrapper.appendChild(childRow);
  }} else if (hasChildren && isCollapsed) {{
    const hint = document.createElement('div'); hint.className = 'collapsed-hint';
    hint.textContent = `▼ ${{descCount}} tersembunyi`; wrapper.appendChild(hint);
  }}
  return wrapper;
}}

function rerenderTree() {{
  const root = document.getElementById('tree-root');
  root.innerHTML = '';
  treeData.forEach(rootNode => root.appendChild(renderNode(rootNode)));
}}

// Apply initial collapse state
treeData.forEach(rootNode => applyInitialCollapse(rootNode, 0));
rerenderTree();
setTimeout(fitView, 300);
</script></body></html>"""
    return html_code

# ══════════════════════════════════════════
# TAB 1 — ORG CHART
# ══════════════════════════════════════════
# ══════════════════════════════════════════
# SECTION 0 — DATA SUMMARY
# ══════════════════════════════════════════
st.markdown(section_header("sec-summary", "📊", "Data Summary", "Ringkasan kondisi organisasi saat ini"), unsafe_allow_html=True)
st.markdown(section_body_start(), unsafe_allow_html=True)

_summary_missing = len(df[(df["Manager ID"] == "") | (df["Manager ID"].isna()) | (df["Manager ID"] == "nan")])
_summary_mgr_ids = df[df["Manager ID"] != ""]["Manager ID"].unique()
_summary_total_mgr = len(df[df["Employee ID"].isin(_summary_mgr_ids)])
_summary_level0 = len(df[df["Career Stage"].astype(str).str.strip().str.lower() == "level 0"])

_s1, _s2, _s3, _s4, _s5 = st.columns(5)
_s1.metric("👥 Total Karyawan",   f"{len(df):,}")
_s2.metric("🏢 Business Unit",    df["Business Unit"].nunique())
_s3.metric("📁 Divisi",           df["Division"].nunique())
_s4.metric("👔 Total Manager",    _summary_total_mgr)
_s5.metric("⚠️ Manager ID Hilang", _summary_missing)

st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)

_col_dist1, _col_dist2 = st.columns(2)
with _col_dist1:
    _bu_count = df.groupby("Business Unit").size().reset_index(name="Jumlah").sort_values("Jumlah", ascending=False)
    st.markdown(f"<div style='font-size:13px; font-weight:700; color:{T["text"]}; margin-bottom:10px;'>Distribusi per Business Unit</div>", unsafe_allow_html=True)
    st.dataframe(_bu_count, use_container_width=True, height=240, hide_index=True)
with _col_dist2:
    _cs_count = df[df["Career Stage"].astype(str).str.strip() != ""].groupby("Career Stage").size().reset_index(name="Jumlah").sort_values("Jumlah", ascending=False)
    st.markdown(f"<div style='font-size:13px; font-weight:700; color:{T["text"]}; margin-bottom:10px;'>Distribusi Career Stage</div>", unsafe_allow_html=True)
    st.dataframe(_cs_count, use_container_width=True, height=240, hide_index=True)

st.markdown(section_body_end(), unsafe_allow_html=True)
st.markdown(f'<div style="height:4px; background:linear-gradient(90deg,{T["accent"]},transparent); margin:0 40px;"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════
# SECTION 1 — ORG CHART
# ══════════════════════════════════════════
st.markdown(section_header("sec-orgchart", "🌳", "Org Chart", "Visualisasi hierarki struktur organisasi real-time"), unsafe_allow_html=True)
st.markdown(section_body_start(), unsafe_allow_html=True)

with tab1:

    st.markdown(f"""
    <div style="margin-bottom:16px;">
        <div style="font-size:13px; font-weight:600; color:{T['text3']}; text-transform:uppercase;
            letter-spacing:0.06em; margin-bottom:10px;">Mode Tampilan</div>
    </div>
    """, unsafe_allow_html=True)
    view_mode = st.radio("", ["Per Divisi", "Seluruh Perusahaan"], horizontal=True, label_visibility="collapsed")

    if view_mode == "Per Divisi":

        st.markdown(f"""
        <div style="font-size:12px; font-weight:600; color:{T['text3']}; text-transform:uppercase;
            letter-spacing:0.06em; margin: 16px 0 10px 0;">Filter</div>
        """, unsafe_allow_html=True)
        col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 2])
        with col_a:
            bu_list = sorted(df["Business Unit"].dropna().unique().tolist())
            selected_bu = st.selectbox("🏢 Business Unit", bu_list, key="sel_bu")
        with col_b:
            div_list = sorted(df[df["Business Unit"] == selected_bu]["Division"].dropna().unique().tolist())
            selected_div = st.selectbox("📁 Divisi", div_list, key="sel_div")
        with col_c:
            sbu_opts_raw = df[
                (df["Business Unit"] == selected_bu) & (df["Division"] == selected_div)
            ]["SBU/Tribe"].dropna().unique().tolist()
            sbu_opts_raw = [s for s in sbu_opts_raw if s.strip() != ""]
            sbu_opts = ["Semua SBU"] + sorted(sbu_opts_raw)
            selected_sbu = st.selectbox("🏷️ SBU/Tribe", sbu_opts, key="sel_sbu")

        filtered = df[(df["Business Unit"] == selected_bu) & (df["Division"] == selected_div)].copy()
        if selected_sbu != "Semua SBU":
            filtered = filtered[filtered["SBU/Tribe"] == selected_sbu].copy()

        all_leaders = filtered[filtered["Employee ID"].isin(df["Manager ID"].unique())]["Employee Name"].tolist()

        with col_d:
            leader_opts = ["Semua (divisi penuh)"] + sorted(all_leaders)
            selected_leader = st.selectbox("👤 Filter by Leader", leader_opts, key="sel_leader")

        if selected_leader != "Semua (divisi penuh)":
            leader_id = filtered[filtered["Employee Name"] == selected_leader]["Employee ID"].values
            if len(leader_id) > 0:
                leader_id = leader_id[0]
                sub_ids = set()
                to_visit = [leader_id]
                while to_visit:
                    curr = to_visit.pop()
                    sub_ids.add(curr)
                    to_visit.extend(df[df["Manager ID"] == curr]["Employee ID"].tolist())
                filtered = df[df["Employee ID"].isin(sub_ids)].copy()

        # ── Level filter ──
        col_lv, col_info = st.columns([2, 4])
        with col_lv:
            level_opt = st.selectbox(
                "📶 Expand Level",
                ["All Level", "Top Level", "Level 1"],
                help="Atur berapa level yang ditampilkan secara default"
            )
        with col_info:
            st.caption(f"📊 Menampilkan **{len(filtered)}** karyawan di divisi ini")

        level_map = {"All Level": "all", "Top Level": "top", "Level 1": "level1"}
        selected_level = level_map[level_opt]

        all_ids_needed = get_all_managers(filtered["Employee ID"].tolist(), df)
        full_data = df[df["Employee ID"].isin(all_ids_needed)].copy()
        all_ids_set = set(full_data["Employee ID"].tolist())
        root_ids = [
            str(row["Employee ID"]) for _, row in full_data.iterrows()
            if str(row["Manager ID"]) not in all_ids_set or str(row["Manager ID"]) in {"", "nan"}
        ]

        tree_data = build_tree_json(full_data, selected_div, root_ids, mode="division")
        chart_html = render_org_chart(json.dumps(tree_data), chart_height=680, initial_level=selected_level, theme=T)
        st.components.v1.html(chart_html, height=680, scrolling=False)

        # ── Download buttons ──
        st.markdown("**⬇️ Download Data**")
        col_dl1, col_dl2, col_dl3, col_dl4 = st.columns([1, 1, 1, 1])
        with col_dl1:
            csv = filtered.to_csv(index=False).encode("utf-8")
            st.download_button("📄 CSV", csv, f"{selected_div}.csv", "text/csv", use_container_width=True)
        with col_dl2:
            excel_data = to_excel(filtered)
            st.download_button("📊 Excel", excel_data, f"{selected_div}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_dl3:
            try:
                pdf_title = f"Org Chart — {selected_div} ({selected_bu})"
                pdf_data = generate_pdf(tree_data, pdf_title)
                st.download_button("📑 PDF (Full)", pdf_data, f"{selected_div}_full.pdf", "application/pdf", use_container_width=True)
            except Exception:
                st.button("📑 PDF (N/A)", disabled=True, use_container_width=True)
        with col_dl4:
            try:
                pdf_title_sum = f"Org Chart Summary — {selected_div} ({selected_bu})"
                pdf_data_sum = generate_pdf_summary(tree_data, pdf_title_sum)
                st.download_button("📑 PDF (Summary)", pdf_data_sum, f"{selected_div}_summary.pdf", "application/pdf", use_container_width=True)
            except Exception:
                st.button("📑 Summary (N/A)", disabled=True, use_container_width=True)

    else:
        # ── SELURUH PERUSAHAAN ──
        st.info("⚠️ Mode seluruh perusahaan menampilkan semua karyawan. Gunakan zoom out dan collapse untuk navigasi.")

        col_lv2, col_inf2 = st.columns([2, 4])
        with col_lv2:
            level_opt2 = st.selectbox("📶 Expand Level", ["All Level", "Top Level", "Level 1"], key="lv2")
        with col_inf2:
            st.caption(f"📊 Menampilkan **{len(df)}** karyawan")

        level_map2 = {"All Level": "all", "Top Level": "top", "Level 1": "level1"}
        selected_level2 = level_map2[level_opt2]

        root_ids = df[(df["Manager ID"] == "") | (df["Manager ID"].isna())]["Employee ID"].tolist()
        tree_data2 = build_tree_json(df, "", root_ids, mode="company")
        chart_html2 = render_org_chart(json.dumps(tree_data2), chart_height=750, initial_level=selected_level2, theme=T)
        st.components.v1.html(chart_html2, height=750, scrolling=False)

        st.markdown("**⬇️ Download Data**")
        col_dl4, col_dl5, col_dl6, col_dl7 = st.columns([1, 1, 1, 1])
        with col_dl4:
            csv2 = df.to_csv(index=False).encode("utf-8")
            st.download_button("📄 CSV", csv2, "all_employees.csv", "text/csv", use_container_width=True)
        with col_dl5:
            excel2 = to_excel(df)
            st.download_button("📊 Excel", excel2, "all_employees.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_dl6:
            try:
                pdf_data2 = generate_pdf(tree_data2, "Org Chart — Seluruh Perusahaan")
                st.download_button("📑 PDF (Full)", pdf_data2, "orgchart_perusahaan_full.pdf", "application/pdf", use_container_width=True)
            except Exception:
                st.button("📑 PDF (N/A)", disabled=True, use_container_width=True)
        with col_dl7:
            try:
                pdf_sum2 = generate_pdf_summary(tree_data2, "Org Chart Summary — Seluruh Perusahaan")
                st.download_button("📑 PDF (Summary)", pdf_sum2, "orgchart_perusahaan_summary.pdf", "application/pdf", use_container_width=True)
            except Exception:
                st.button("📑 Summary (N/A)", disabled=True, use_container_width=True)

# ══════════════════════════════════════════
# TAB 2 — DATA KARYAWAN
# ══════════════════════════════════════════
st.markdown(section_body_end(), unsafe_allow_html=True)
st.markdown(f'<div style="height:4px; background:linear-gradient(90deg,{T["accent"]},transparent); margin:0 40px;"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════
# SECTION 2 — DATA KARYAWAN
# ══════════════════════════════════════════
st.markdown(section_header("sec-karyawan", "👥", "Data Karyawan", "Seluruh data karyawan dengan filter dan pencarian"), unsafe_allow_html=True)
st.markdown(section_body_start(), unsafe_allow_html=True)

with tab2:
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:20px; font-weight:700; color:{T['text']};">Data Karyawan</div>
        <div style="font-size:13px; color:{T['text3']}; margin-top:4px;">Seluruh data karyawan dengan filter dan pencarian</div>
    </div>
    """, unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        search = st.text_input("🔍 Cari nama karyawan")
    with c2:
        bu_f = st.selectbox("Filter BU", ["Semua"] + sorted(df["Business Unit"].unique().tolist()), key="t2bu")
    with c3:
        div_opts = ["Semua"] + sorted(
            df[df["Business Unit"] == bu_f]["Division"].unique().tolist() if bu_f != "Semua"
            else df["Division"].unique().tolist()
        )
        div_f = st.selectbox("Filter Divisi", div_opts, key="t2div")
    with c4:
        sbu_source = df.copy()
        if bu_f != "Semua":
            sbu_source = sbu_source[sbu_source["Business Unit"] == bu_f]
        if div_f != "Semua":
            sbu_source = sbu_source[sbu_source["Division"] == div_f]
        sbu_opts_t2 = ["Semua"] + sorted([
            s for s in sbu_source["SBU/Tribe"].dropna().unique().tolist()
            if s.strip() != ""
        ])
        sbu_f = st.selectbox("Filter SBU/Tribe", sbu_opts_t2, key="t2sbu")

    data_view = df.copy()
    if search:
        data_view = data_view[data_view["Employee Name"].str.contains(search, case=False, na=False)]
    if bu_f != "Semua":
        data_view = data_view[data_view["Business Unit"] == bu_f]
    if div_f != "Semua":
        data_view = data_view[data_view["Division"] == div_f]
    if sbu_f != "Semua":
        data_view = data_view[data_view["SBU/Tribe"] == sbu_f]

    st.caption(f"Menampilkan **{len(data_view)}** karyawan")
    st.dataframe(data_view, use_container_width=True, height=480)

    col_dl7, col_dl8, _ = st.columns([1, 1, 3])
    with col_dl7:
        st.download_button("📄 CSV", data_view.to_csv(index=False).encode("utf-8"),
            "filtered.csv", "text/csv", use_container_width=True)
    with col_dl8:
        st.download_button("📊 Excel", to_excel(data_view), "filtered.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

# ══════════════════════════════════════════
# TAB 3 — KARYAWAN DENGAN MANAGER ID HILANG
# ══════════════════════════════════════════
st.markdown(section_body_end(), unsafe_allow_html=True)
st.markdown(f'<div style="height:4px; background:linear-gradient(90deg,{T["accent"]},transparent); margin:0 40px;"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════
# SECTION 3 — MANAGER ID HILANG
# ══════════════════════════════════════════
st.markdown(section_header("sec-managerid", "⚠️", "Manager ID Hilang", "Karyawan dengan Manager ID kosong — perlu diperbaiki di backend"), unsafe_allow_html=True)
st.markdown(section_body_start(), unsafe_allow_html=True)

with tab3:
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:20px; font-weight:700; color:{T['text']};">Manager ID Hilang</div>
        <div style="font-size:13px; color:{T['text3']}; margin-top:4px;">
            Karyawan yang Manager ID-nya kosong atau tidak terdaftar — perlu diperbaiki di backend
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Karyawan yang Manager ID-nya kosong / null
    missing_mgr_df = df[
        (df["Manager ID"] == "") | (df["Manager ID"].isna()) | (df["Manager ID"] == "nan")
    ].copy()

    # Metrik
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("⚠️ Total Data Bermasalah", len(missing_mgr_df))
    m2.metric("🏢 Tersebar di BU", missing_mgr_df["Business Unit"].nunique())
    m3.metric("📁 Tersebar di Divisi", missing_mgr_df["Division"].nunique())
    m4.metric("📊 % dari Total", f"{len(missing_mgr_df)/len(df)*100:.1f}%")

    st.divider()

    # Filter
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        bu_nr = st.selectbox(
            "Filter Business Unit",
            ["Semua"] + sorted(missing_mgr_df["Business Unit"].dropna().unique().tolist()),
            key="bu_nr"
        )
    with col_f2:
        div_opts_nr = (
            sorted(missing_mgr_df[missing_mgr_df["Business Unit"] == bu_nr]["Division"].dropna().unique().tolist())
            if bu_nr != "Semua"
            else sorted(missing_mgr_df["Division"].dropna().unique().tolist())
        )
        div_nr = st.selectbox("Filter Divisi", ["Semua"] + div_opts_nr, key="div_nr")

    view_nr = missing_mgr_df.copy()
    if bu_nr != "Semua":
        view_nr = view_nr[view_nr["Business Unit"] == bu_nr]
    if div_nr != "Semua":
        view_nr = view_nr[view_nr["Division"] == div_nr]

    st.caption(f"Menampilkan **{len(view_nr)}** karyawan dengan Manager ID kosong")

    # Kolom yang ditampilkan
    display_cols = ["Employee ID", "Employee Name", "Job Position", "Division", "Business Unit", "SBU/Tribe", "Manager ID"]
    st.dataframe(view_nr[display_cols], use_container_width=True, height=450)

    # Breakdown per divisi
    st.divider()
    st.markdown(f"""
    <div style="font-size:15px; font-weight:700; color:{T['text']}; margin-bottom:12px;">Breakdown per Divisi</div>
    """, unsafe_allow_html=True)
    breakdown = (
        view_nr.groupby(["Business Unit", "Division"])
        .size()
        .reset_index(name="Jumlah")
        .sort_values("Jumlah", ascending=False)
    )
    st.dataframe(breakdown, use_container_width=True, height=250)

    # Download
    st.divider()
    st.markdown("**⬇️ Download Data**")
    col_d1, col_d2, _ = st.columns([1, 1, 3])
    with col_d1:
        st.download_button(
            "📄 CSV", view_nr.to_csv(index=False).encode("utf-8"),
            "missing_manager_id.csv", "text/csv", use_container_width=True
        )
    with col_d2:
        st.download_button(
            "📊 Excel", to_excel(view_nr),
            "missing_manager_id.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# ══════════════════════════════════════════
st.markdown(section_body_end(), unsafe_allow_html=True)
st.markdown(f'<div style="height:4px; background:linear-gradient(90deg,{T["accent"]},transparent); margin:0 40px;"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════
# SECTION 4 — DAFTAR MANAGER
# ══════════════════════════════════════════
st.markdown(section_header("sec-manager", "👔", "Daftar Manager", "Seluruh karyawan yang memiliki bawahan langsung"), unsafe_allow_html=True)
st.markdown(section_body_start(), unsafe_allow_html=True)

# TAB 4 — DAFTAR MANAGER
# ══════════════════════════════════════════
with tab4:
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:20px; font-weight:700; color:{T['text']};">Daftar Manager</div>
        <div style="font-size:13px; color:{T['text3']}; margin-top:4px;">
            Seluruh karyawan yang memiliki bawahan langsung
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Bangun level hierarki dari SLKR001 (Suwandi) ──
    CHIEF_ROOT = "SLKR001"

    def get_level_from_root(root_id, all_df, max_depth=2):
        """
        Kembalikan dict {employee_id: level} di mana:
        level 0 = Chief (bawahan langsung root)
        level 1 = C-1 (bawahan Chief)
        level 2 = C-2 (bawahan C-1)
        """
        levels = {}
        current_level_ids = [root_id]
        for depth in range(max_depth + 1):
            next_level_ids = []
            for mgr_id in current_level_ids:
                children = all_df[all_df["Manager ID"] == mgr_id]["Employee ID"].tolist()
                for child in children:
                    if child not in levels:
                        levels[child] = depth  # depth 0 = Chief, 1 = C-1, 2 = C-2
                        next_level_ids.append(child)
            current_level_ids = next_level_ids
            if not current_level_ids:
                break
        return levels

    hierarchy_levels = get_level_from_root(CHIEF_ROOT, df, max_depth=2)

    # ── Karyawan dengan Career Stage Level 0 ──
    level0_ids = set(
        df[df["Career Stage"].astype(str).str.strip().str.lower() == "level 0"]["Employee ID"].tolist()
    )

    # ── Build manager list ──
    mgr_ids = df[df["Manager ID"] != ""]["Manager ID"].unique().tolist()
    mgr_df  = df[df["Employee ID"].isin(mgr_ids)].copy()

    # Tambah kolom Jumlah Bawahan
    sub_count = df[df["Manager ID"] != ""].groupby("Manager ID").size().reset_index(name="Jumlah Bawahan")
    sub_count.rename(columns={"Manager ID": "Employee ID"}, inplace=True)
    mgr_df = mgr_df.merge(sub_count, on="Employee ID", how="left")
    mgr_df["Jumlah Bawahan"] = mgr_df["Jumlah Bawahan"].fillna(0).astype(int)

    # Tambah kolom Level Hierarki
    mgr_df["Level Hierarki"] = mgr_df["Employee ID"].apply(
        lambda eid: {0: "Chief", 1: "C-1", 2: "C-2"}.get(hierarchy_levels.get(eid), "-")
    )

    # Tambah kolom: apakah punya bawahan Level 0
    def has_level0_subordinate(mgr_id, all_df, level0_set):
        """Cek apakah manager ini punya bawahan langsung dengan Career Stage Level 0."""
        direct_subs = all_df[all_df["Manager ID"] == mgr_id]["Employee ID"].tolist()
        return any(sid in level0_set for sid in direct_subs)

    mgr_df["Ada Bawahan Level 0"] = mgr_df["Employee ID"].apply(
        lambda eid: has_level0_subordinate(eid, df, level0_ids)
    )

    mgr_df = mgr_df.sort_values("Jumlah Bawahan", ascending=False)

    # ── Metrics ──
    m1, m2, m3 = st.columns(3)
    m1.metric("👔 Total Manager", len(mgr_df))
    m2.metric("📊 Rata-rata Bawahan", f"{mgr_df['Jumlah Bawahan'].mean():.1f}")
    m3.metric("🏆 Max Bawahan", int(mgr_df['Jumlah Bawahan'].max()))

    st.divider()

    # ── Filters ──
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        search_mgr = st.text_input("🔍 Cari nama manager", key="search_mgr")
    with col_m2:
        bu_mgr = st.selectbox(
            "Filter BU",
            ["Semua"] + sorted(mgr_df["Business Unit"].dropna().unique().tolist()),
            key="bu_mgr"
        )
    with col_m3:
        div_mgr_opts = (
            ["Semua"] + sorted(mgr_df[mgr_df["Business Unit"] == bu_mgr]["Division"].dropna().unique().tolist())
            if bu_mgr != "Semua"
            else ["Semua"] + sorted(mgr_df["Division"].dropna().unique().tolist())
        )
        div_mgr = st.selectbox("Filter Divisi", div_mgr_opts, key="div_mgr")
    with col_m4:
        level_filter = st.selectbox(
            "🎯 Filter Level Hierarki",
            ["Semua", "Chief", "C-1", "C-2"],
            key="level_mgr",
            help="Chief = bawahan langsung Suwandi (SLKR001) | C-1 = 1 tingkat di bawah Chief | C-2 = 2 tingkat di bawah Chief"
        )

    # ── Toggle: sembunyikan manager yang punya bawahan Level 0 ──
    hide_level0 = st.checkbox(
        "🚫 Sembunyikan manager yang memiliki bawahan Career Stage Level 0",
        value=True,
        help="Aktif = hanya tampilkan leader tanpa bawahan Level 0"
    )

    # ── Apply filters ──
    view_mgr = mgr_df.copy()
    if search_mgr:
        view_mgr = view_mgr[view_mgr["Employee Name"].str.contains(search_mgr, case=False, na=False)]
    if bu_mgr != "Semua":
        view_mgr = view_mgr[view_mgr["Business Unit"] == bu_mgr]
    if div_mgr != "Semua":
        view_mgr = view_mgr[view_mgr["Division"] == div_mgr]
    if level_filter != "Semua":
        view_mgr = view_mgr[view_mgr["Level Hierarki"] == level_filter]
    if hide_level0:
        view_mgr = view_mgr[~view_mgr["Ada Bawahan Level 0"]]

    # ── Info badge filter aktif ──
    active_filters = []
    if level_filter != "Semua":
        active_filters.append(f"Level: **{level_filter}**")
    if hide_level0:
        active_filters.append("Tanpa bawahan Level 0")

    if active_filters:
        st.markdown(f"""
        <div style="background:{T['accent_bg']}; border:1px solid {T['border2']};
            border-radius:8px; padding:8px 14px; margin-bottom:12px;
            font-size:12px; color:{T['accent']};">
            🔎 Filter aktif: {' · '.join(active_filters)}
        </div>
        """, unsafe_allow_html=True)

    st.caption(f"Menampilkan **{len(view_mgr)}** manager")

    # ── Tampilkan kolom Level Hierarki dengan warna ──
    display_cols_mgr = ["Employee ID", "Employee Name", "Job Position", "Division",
                        "Business Unit", "SBU/Tribe", "Level Hierarki", "Jumlah Bawahan"]
    available_display = [c for c in display_cols_mgr if c in view_mgr.columns]

    # Style Level Hierarki
    def style_level(val):
        if val == "Chief":  return "background-color:#ddd6fe; color:#4c1d95; font-weight:700;"
        if val == "C-1":    return "background-color:#ede9fe; color:#5b4fcf; font-weight:600;"
        if val == "C-2":    return "background-color:#f3f0ff; color:#7c6fcd; font-weight:500;"
        return ""

    styled_view = view_mgr[available_display].reset_index(drop=True)
    st.dataframe(styled_view, use_container_width=True, height=480)

    st.divider()
    st.markdown("**⬇️ Download Data**")
    col_dm1, col_dm2, _ = st.columns([1, 1, 3])
    with col_dm1:
        st.download_button(
            "📄 CSV", view_mgr.to_csv(index=False).encode("utf-8"),
            "daftar_manager.csv", "text/csv", use_container_width=True
        )
    with col_dm2:
        st.download_button(
            "📊 Excel", to_excel(view_mgr),
            "daftar_manager.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# ══════════════════════════════════════════
st.markdown(section_body_end(), unsafe_allow_html=True)
st.markdown(f'<div style="height:4px; background:linear-gradient(90deg,{T["accent"]},transparent); margin:0 40px;"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════
# SECTION 5 — CHANGE REQUEST
# ══════════════════════════════════════════
st.markdown(section_header("sec-changereq", "📝", "Change Request", "Kelola permintaan perubahan struktur organisasi"), unsafe_allow_html=True)
st.markdown(section_body_start(), unsafe_allow_html=True)

# TAB 5 — CHANGE REQUEST
# ══════════════════════════════════════════
with tab5:
    from datetime import datetime

    st.markdown(f"""
    <div style="margin-bottom:24px;">
        <div style="font-size:20px; font-weight:700; color:{T['text']};">Structure Change Request</div>
        <div style="font-size:13px; color:{T['text3']}; margin-top:4px;">
            Kelola permintaan perubahan struktur organisasi — Reporting Line & Divisi
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Sub-tabs ──
    cr_tab1, cr_tab2, cr_tab3 = st.tabs(["➕  Buat Request", "📥  Inbox & Review", "📜  History"])

    # ══════════════════════════════════
    # SUB-TAB 1 — FORM INPUT
    # ══════════════════════════════════
    with cr_tab1:
        st.markdown(f"""
        <div style="font-size:15px; font-weight:600; color:{T['text']}; margin-bottom:16px;">
            Form Permintaan Perubahan Struktur
        </div>
        """, unsafe_allow_html=True)

        # ── Helper: generate template download ──
        def make_template(change_type_tmpl):
            if change_type_tmpl == "Reporting Line":
                cols = ["Employee ID", "Employee Name", "Previous Manager", "New Manager"]
            else:
                cols = ["Employee ID", "Employee Name", "Nama Divisi Lama", "Nama Divisi Baru"]
            return pd.DataFrame(columns=cols)

        # ── Helper: validate & save rows ──
        def process_and_save(rows_data, req_name, req_email, change_type, alasan, eff_date):
            valid_rows = [(str(eid).strip(), str(en).strip(), str(ov).strip(), str(nv).strip())
                          for eid, en, ov, nv in rows_data
                          if str(eid).strip() or str(en).strip()]
            if not valid_rows:
                return [], [], 0

            warnings = []
            for emp_id, emp_name, old_val, new_val in valid_rows:
                if emp_id and emp_id not in df["Employee ID"].values:
                    warnings.append(f"Employee ID **{emp_id}** tidak ditemukan di data.")
                if change_type == "Reporting Line" and new_val:
                    if len(df[df["Employee Name"].str.lower() == new_val.lower()]) == 0:
                        warnings.append(f"Manager baru **{new_val}** tidak ditemukan di data.")

            success_count = 0
            for emp_id, emp_name, old_val, new_val in valid_rows:
                req_id = generate_request_id()
                row = {
                    "request_id":      req_id,
                    "submitted_date":  datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "requester_name":  req_name.strip(),
                    "requester_email": req_email.strip(),
                    "change_type":     change_type,
                    "employee_id":     emp_id,
                    "employee_name":   emp_name,
                    "data_lama":       old_val,
                    "data_baru":       new_val,
                    "alasan":          f"{alasan.strip()} | Effective: {eff_date}",
                    "status":          "Pending",
                    "reviewed_by":     "",
                    "reviewed_date":   "",
                    "catatan":         "",
                }
                if save_change_request(row):
                    success_count += 1
            return valid_rows, warnings, success_count

        # ── CSS form buttons ──
        st.markdown(f"""
        <style>
        [data-testid="stFormSubmitButton"] button {{
            background: {T['accent']} !important;
            color: white !important; border: none !important;
            border-radius: 10px !important; font-weight: 600 !important;
            font-size: 14px !important; padding: 12px !important;
            transition: all 0.2s !important; width: 100% !important;
        }}
        [data-testid="stFormSubmitButton"] button:hover {{
            background: {T['accent2']} !important;
            box-shadow: 0 4px 16px rgba(124,111,205,0.4) !important;
            transform: translateY(-1px) !important;
        }}
        </style>
        """, unsafe_allow_html=True)

        # ── Informasi Requester & Jenis Perubahan (di luar form, shared) ──
        st.markdown(f"<div style='font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:{T['text3']}; margin-bottom:8px;'>Informasi Requester</div>", unsafe_allow_html=True)
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            req_name_shared  = st.text_input("Nama Requester *", placeholder="Nama lengkap pengirim request", key="req_name_shared")
        with col_r2:
            req_email_shared = st.text_input("Email Requester *", placeholder="email@mekari.com", key="req_email_shared")

        st.markdown(f"<div style='height:1px; background:{T['border']}; margin:16px 0;'></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:{T['text3']}; margin-bottom:8px;'>Detail Perubahan</div>", unsafe_allow_html=True)
        col_ct, col_ed = st.columns(2)
        with col_ct:
            change_type_shared = st.selectbox("Jenis Perubahan *", ["Reporting Line", "Nama Divisi"], key="ct_shared")
        with col_ed:
            eff_date_shared = st.date_input("Effective Date", value=datetime.today(), key="ed_shared")

        st.markdown(f"<div style='height:1px; background:{T['border']}; margin:16px 0;'></div>", unsafe_allow_html=True)
        alasan_shared = st.text_area("Alasan / Keterangan *", placeholder="Jelaskan alasan perubahan struktur ini...", height=90, key="alasan_shared")

        st.markdown(f"<div style='height:1px; background:{T['border']}; margin:16px 0;'></div>", unsafe_allow_html=True)

        # ── Mode Input: Manual atau Upload ──
        st.markdown(f"<div style='font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:{T['text3']}; margin-bottom:12px;'>Metode Input Data Karyawan</div>", unsafe_allow_html=True)

        input_mode = st.radio(
            "",
            ["✏️  Input Manual (1–5 karyawan)", "📤  Upload Spreadsheet (>5 karyawan)"],
            horizontal=True,
            label_visibility="collapsed",
            key="input_mode"
        )

        # ════════════════════════════════
        # MODE 1 — INPUT MANUAL
        # ════════════════════════════════
        if input_mode == "✏️  Input Manual (1–5 karyawan)":
            with st.form("cr_form_manual", clear_on_submit=True):
                st.markdown(f"<div style='font-size:12px; color:{T['text3']}; margin-bottom:12px;'>Isi data karyawan yang akan diubah. Maksimal 5 karyawan per request.</div>", unsafe_allow_html=True)

                num_rows = st.number_input("Jumlah karyawan", min_value=1, max_value=5, value=1, step=1, key="num_rows_manual")

                # Header kolom
                h1c, h2c, h3c, h4c = st.columns([1.5, 2, 2.5, 2.5])
                h1c.markdown(f"<div style='font-size:11px; font-weight:700; color:{T['text3']};'>Employee ID</div>", unsafe_allow_html=True)
                h2c.markdown(f"<div style='font-size:11px; font-weight:700; color:{T['text3']};'>Nama Karyawan</div>", unsafe_allow_html=True)
                if change_type_shared == "Reporting Line":
                    h3c.markdown(f"<div style='font-size:11px; font-weight:700; color:{T['text3']};'>Previous Manager</div>", unsafe_allow_html=True)
                    h4c.markdown(f"<div style='font-size:11px; font-weight:700; color:{T['text3']};'>New Manager</div>", unsafe_allow_html=True)
                else:
                    h3c.markdown(f"<div style='font-size:11px; font-weight:700; color:{T['text3']};'>Divisi Lama</div>", unsafe_allow_html=True)
                    h4c.markdown(f"<div style='font-size:11px; font-weight:700; color:{T['text3']};'>Divisi Baru</div>", unsafe_allow_html=True)

                rows_data_manual = []
                for i in range(int(num_rows)):
                    c1, c2, c3, c4 = st.columns([1.5, 2, 2.5, 2.5])
                    with c1:
                        emp_id = st.text_input("", key=f"eid_{i}", placeholder="EMP001", label_visibility="collapsed")
                    with c2:
                        emp_match = df[df["Employee ID"] == emp_id]["Employee Name"].values
                        emp_name_default = emp_match[0] if len(emp_match) > 0 else ""
                        emp_name = st.text_input("", key=f"ename_{i}", value=emp_name_default,
                                                  placeholder="Nama lengkap", label_visibility="collapsed")
                    with c3:
                        old_val = st.text_input("", key=f"old_{i}",
                                                 placeholder="Manager lama" if change_type_shared=="Reporting Line" else "Divisi saat ini",
                                                 label_visibility="collapsed")
                    with c4:
                        new_val = st.text_input("", key=f"new_{i}",
                                                 placeholder="Manager baru" if change_type_shared=="Reporting Line" else "Divisi tujuan",
                                                 label_visibility="collapsed")
                    rows_data_manual.append((emp_id, emp_name, old_val, new_val))

                submitted_manual = st.form_submit_button("📨  Kirim Request", use_container_width=True)

            if submitted_manual:
                errors = []
                if not req_name_shared.strip():   errors.append("Nama Requester harus diisi")
                if not req_email_shared.strip() or "@" not in req_email_shared: errors.append("Email Requester tidak valid")
                if not alasan_shared.strip():     errors.append("Alasan perubahan harus diisi")
                if errors:
                    for e in errors: st.error(f"❌ {e}")
                else:
                    valid_rows, warnings, success_count = process_and_save(
                        rows_data_manual, req_name_shared, req_email_shared,
                        change_type_shared, alasan_shared, eff_date_shared
                    )
                    for w in warnings: st.warning(f"⚠️ {w}")
                    if success_count > 0:
                        st.success(f"✅ **{success_count} request** berhasil dikirim! Tim OD akan segera mereview.")
                        st.balloons()
                    elif not errors:
                        st.error("❌ Tidak ada data yang valid untuk dikirim.")

        # ════════════════════════════════
        # MODE 2 — UPLOAD SPREADSHEET
        # ════════════════════════════════
        else:
            # Download template
            template_df = make_template(change_type_shared)
            col_tmpl, _ = st.columns([2, 4])
            with col_tmpl:
                st.download_button(
                    "⬇️  Download Template",
                    data=to_excel(template_df),
                    file_name=f"template_cr_{change_type_shared.lower().replace(' ','_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            st.markdown(f"""
            <div style="background:{T['bg3']}; border:1px solid {T['border']}; border-radius:12px;
                padding:14px 18px; margin:12px 0; font-size:13px; color:{T['text2']};">
                <b style="color:{T['text']};">📋 Petunjuk Upload:</b><br>
                1. Download template di atas sesuai jenis perubahan<br>
                2. Isi data karyawan di template (jangan ubah nama kolom)<br>
                3. Upload file yang sudah diisi di bawah ini<br>
                4. Sistem akan memvalidasi data sebelum dikirim
            </div>
            """, unsafe_allow_html=True)

            uploaded_file = st.file_uploader(
                "Upload file Excel (.xlsx) atau CSV (.csv)",
                type=["xlsx", "csv"],
                key="cr_upload"
            )

            if uploaded_file:
                try:
                    if uploaded_file.name.endswith(".csv"):
                        upload_df = pd.read_csv(uploaded_file)
                    else:
                        upload_df = pd.read_excel(uploaded_file)

                    upload_df.columns = upload_df.columns.str.strip()
                    upload_df = upload_df.dropna(how="all")

                    # Validasi kolom
                    if change_type_shared == "Reporting Line":
                        required_cols = ["Employee ID", "Employee Name", "Previous Manager", "New Manager"]
                        old_col, new_col = "Previous Manager", "New Manager"
                    else:
                        required_cols = ["Employee ID", "Employee Name", "Nama Divisi Lama", "Nama Divisi Baru"]
                        old_col, new_col = "Nama Divisi Lama", "Nama Divisi Baru"

                    missing_cols = [c for c in required_cols if c not in upload_df.columns]
                    if missing_cols:
                        st.error(f"❌ Kolom tidak sesuai template. Kolom yang kurang: {', '.join(missing_cols)}")
                    else:
                        # Preview data
                        st.markdown(f"<div style='font-size:13px; font-weight:600; color:{T['text']}; margin:12px 0 8px 0;'>Preview Data ({len(upload_df)} karyawan)</div>", unsafe_allow_html=True)
                        st.dataframe(upload_df[required_cols], use_container_width=True, height=200)

                        # Validasi per baris
                        upload_warnings = []
                        for _, urow in upload_df.iterrows():
                            eid = str(urow.get("Employee ID","")).strip()
                            nv  = str(urow.get(new_col,"")).strip()
                            if eid and eid not in df["Employee ID"].values:
                                upload_warnings.append(f"Employee ID **{eid}** tidak ditemukan di data")
                            if change_type_shared == "Reporting Line" and nv:
                                if len(df[df["Employee Name"].str.lower() == nv.lower()]) == 0:
                                    upload_warnings.append(f"Manager baru **{nv}** tidak ditemukan di data")

                        if upload_warnings:
                            with st.expander(f"⚠️ {len(upload_warnings)} peringatan validasi — klik untuk lihat detail"):
                                for w in upload_warnings:
                                    st.warning(w)

                        # Tombol submit upload
                        errors_upload = []
                        if not req_name_shared.strip():   errors_upload.append("Nama Requester harus diisi")
                        if not req_email_shared.strip() or "@" not in req_email_shared: errors_upload.append("Email Requester tidak valid")
                        if not alasan_shared.strip():     errors_upload.append("Alasan perubahan harus diisi")

                        if errors_upload:
                            for e in errors_upload: st.error(f"❌ {e}")
                        else:
                            if st.button("📨  Kirim Semua Request dari File", use_container_width=True, key="submit_upload"):
                                rows_from_file = [
                                    (
                                        str(r.get("Employee ID","")).strip(),
                                        str(r.get("Employee Name","")).strip(),
                                        str(r.get(old_col,"")).strip(),
                                        str(r.get(new_col,"")).strip(),
                                    )
                                    for _, r in upload_df.iterrows()
                                ]
                                _, _, success_count = process_and_save(
                                    rows_from_file, req_name_shared, req_email_shared,
                                    change_type_shared, alasan_shared, eff_date_shared
                                )
                                if success_count > 0:
                                    st.success(f"✅ **{success_count} request** dari file berhasil dikirim!")
                                    st.balloons()
                                else:
                                    st.error("❌ Tidak ada data yang berhasil disimpan. Periksa koneksi Google Sheets.")

                except Exception as e:
                    st.error(f"❌ Gagal membaca file: {str(e)}")

    # ══════════════════════════════════
    # SUB-TAB 2 — INBOX & REVIEW
    # ══════════════════════════════════
    with cr_tab2:
        col_reload, _ = st.columns([1, 5])
        with col_reload:
            if st.button("🔄 Refresh", key="refresh_cr"):
                st.rerun()

        cr_df = load_change_requests()

        if cr_df.empty:
            st.info("📭 Belum ada request yang masuk.")
        else:
            # Ensure status column exists
            if "status" not in cr_df.columns:
                cr_df["status"] = "Pending"

            pending_df  = cr_df[cr_df["status"] == "Pending"].copy()
            inreview_df = cr_df[cr_df["status"] == "In Review"].copy()

            # Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📥 Total Masuk",   len(cr_df))
            m2.metric("🟡 Pending",       len(pending_df))
            m3.metric("✅ Approved",      len(cr_df[cr_df["status"] == "Approved"]))
            m4.metric("❌ Rejected",      len(cr_df[cr_df["status"] == "Rejected"]))

            st.markdown(f"<div style='height:1px; background:{T['border']}; margin:16px 0;'></div>", unsafe_allow_html=True)

            # Pending requests
            if len(pending_df) == 0:
                st.success("✅ Semua request sudah diproses!")
            else:
                st.markdown(f"""
                <div style="font-size:14px; font-weight:700; color:{T['text']}; margin-bottom:12px;">
                    🟡 Pending — Perlu Direview ({len(pending_df)} request)
                </div>
                """, unsafe_allow_html=True)

                for _, row in pending_df.iterrows():
                    # Hitung usia request
                    try:
                        submitted = datetime.strptime(str(row.get("submitted_date",""))[:16], "%Y-%m-%d %H:%M")
                        age_days  = (datetime.now() - submitted).days
                        age_label = f"{age_days} hari yang lalu" if age_days > 0 else "Hari ini"
                        age_color = "#ef4444" if age_days >= 3 else "#f59e0b" if age_days >= 1 else "#22c55e"
                    except Exception:
                        age_label = "-"
                        age_color = T["text3"]

                    with st.expander(
                        f"📋 {row.get('request_id','-')}  ·  {row.get('change_type','-')}  ·  "
                        f"{row.get('employee_name','-')}  ·  dari {row.get('requester_name','-')}",
                        expanded=False
                    ):
                        # Detail card
                        col_info, col_action = st.columns([3, 2])
                        with col_info:
                            st.markdown(f"""
                            <div style="background:{T['bg3']}; border-radius:12px; padding:16px;
                                border:1px solid {T['border']};">
                                <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                                    <div>
                                        <div style="font-size:10px; color:{T['text3']}; text-transform:uppercase; letter-spacing:0.06em;">Request ID</div>
                                        <div style="font-size:13px; font-weight:600; color:{T['text']};">{row.get('request_id','-')}</div>
                                    </div>
                                    <div>
                                        <div style="font-size:10px; color:{T['text3']}; text-transform:uppercase; letter-spacing:0.06em;">Masuk</div>
                                        <div style="font-size:13px; color:{age_color}; font-weight:600;">{age_label}</div>
                                    </div>
                                    <div>
                                        <div style="font-size:10px; color:{T['text3']}; text-transform:uppercase; letter-spacing:0.06em;">Karyawan</div>
                                        <div style="font-size:13px; font-weight:600; color:{T['text']};">{row.get('employee_name','-')} ({row.get('employee_id','-')})</div>
                                    </div>
                                    <div>
                                        <div style="font-size:10px; color:{T['text3']}; text-transform:uppercase; letter-spacing:0.06em;">Jenis</div>
                                        <div style="font-size:13px; font-weight:600; color:{T['accent']};">{row.get('change_type','-')}</div>
                                    </div>
                                </div>
                                <div style="margin-top:12px; padding-top:12px; border-top:1px solid {T['border']};">
                                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                                        <div>
                                            <div style="font-size:10px; color:{T['text3']}; text-transform:uppercase; letter-spacing:0.06em;">Sebelum</div>
                                            <div style="font-size:13px; color:#ef4444; font-weight:500;">❌ {row.get('data_lama','-')}</div>
                                        </div>
                                        <div>
                                            <div style="font-size:10px; color:{T['text3']}; text-transform:uppercase; letter-spacing:0.06em;">Sesudah</div>
                                            <div style="font-size:13px; color:#22c55e; font-weight:500;">✅ {row.get('data_baru','-')}</div>
                                        </div>
                                    </div>
                                </div>
                                <div style="margin-top:12px; padding-top:12px; border-top:1px solid {T['border']};">
                                    <div style="font-size:10px; color:{T['text3']}; text-transform:uppercase; letter-spacing:0.06em;">Alasan</div>
                                    <div style="font-size:13px; color:{T['text2']};">{row.get('alasan','-')}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col_action:
                            st.markdown(f"""
                            <div style="font-size:12px; font-weight:700; color:{T['text3']};
                                text-transform:uppercase; letter-spacing:0.06em; margin-bottom:8px;">
                                Tindakan
                            </div>
                            """, unsafe_allow_html=True)

                            reviewer = st.text_input("Nama Reviewer *",
                                key=f"reviewer_{row.get('request_id','')}",
                                placeholder="Nama Anda")
                            catatan_review = st.text_area("Catatan (opsional)",
                                key=f"catatan_{row.get('request_id','')}",
                                height=80, placeholder="Catatan untuk requester...")

                            req_id_key = row.get('request_id','').replace('-','_')
                            st.markdown(f"""
                            <style>
                            [data-testid="stButton"][key="approve_{req_id_key}"] button {{
                                background: #059669 !important; color: white !important;
                                border: none !important; border-radius: 10px !important;
                                font-weight: 600 !important;
                            }}
                            [data-testid="stButton"][key="reject_{req_id_key}"] button {{
                                background: #dc2626 !important; color: white !important;
                                border: none !important; border-radius: 10px !important;
                                font-weight: 600 !important;
                            }}
                            </style>
                            """, unsafe_allow_html=True)
                            col_a, col_r = st.columns(2)
                            with col_a:
                                if st.button("✅ Approve",
                                    key=f"approve_{row.get('request_id','')}",
                                    use_container_width=True):
                                    if not reviewer.strip():
                                        st.error("Nama reviewer harus diisi")
                                    else:
                                        if update_cr_status(
                                            row.get("request_id",""), "Approved",
                                            reviewer.strip(), catatan_review.strip()
                                        ):
                                            st.success("✅ Approved!")
                                            st.rerun()
                            with col_r:
                                if st.button("❌ Reject",
                                    key=f"reject_{row.get('request_id','')}",
                                    use_container_width=True):
                                    if not reviewer.strip():
                                        st.error("Nama reviewer harus diisi")
                                    else:
                                        if update_cr_status(
                                            row.get("request_id",""), "Rejected",
                                            reviewer.strip(), catatan_review.strip()
                                        ):
                                            st.warning("❌ Rejected")
                                            st.rerun()

    # ══════════════════════════════════
    # SUB-TAB 3 — HISTORY
    # ══════════════════════════════════
    with cr_tab3:
        col_rl, _ = st.columns([1, 5])
        with col_rl:
            if st.button("🔄 Refresh", key="refresh_hist"):
                st.rerun()

        cr_hist = load_change_requests()

        if cr_hist.empty:
            st.info("📭 Belum ada history request.")
        else:
            processed = cr_hist[cr_hist["status"].isin(["Approved","Rejected"])].copy()

            if processed.empty:
                st.info("Belum ada request yang telah diproses.")
            else:
                # Metrics
                h1m, h2m, h3m = st.columns(3)
                h1m.metric("📊 Total Diproses", len(processed))
                h2m.metric("✅ Approved",  len(processed[processed["status"]=="Approved"]))
                h3m.metric("❌ Rejected",  len(processed[processed["status"]=="Rejected"]))

                st.markdown(f"<div style='height:1px; background:{T['border']}; margin:16px 0;'></div>", unsafe_allow_html=True)

                # Filter
                col_hf1, col_hf2, col_hf3 = st.columns(3)
                with col_hf1:
                    hist_type = st.selectbox("Filter Jenis", ["Semua"] + sorted(processed["change_type"].unique().tolist()), key="hf_type")
                with col_hf2:
                    hist_status = st.selectbox("Filter Status", ["Semua", "Approved", "Rejected"], key="hf_status")
                with col_hf3:
                    hist_search = st.text_input("Cari nama karyawan", key="hf_search")

                view_hist = processed.copy()
                if hist_type   != "Semua": view_hist = view_hist[view_hist["change_type"] == hist_type]
                if hist_status != "Semua": view_hist = view_hist[view_hist["status"] == hist_status]
                if hist_search: view_hist = view_hist[view_hist["employee_name"].str.contains(hist_search, case=False, na=False)]

                # Style status
                def style_status(val):
                    if val == "Approved": return "background-color:#d1fae5; color:#065f46; font-weight:600;"
                    if val == "Rejected": return "background-color:#fee2e2; color:#991b1b; font-weight:600;"
                    return ""

                display_cols = ["request_id","submitted_date","requester_name","change_type",
                                "employee_name","employee_id","data_lama","data_baru",
                                "status","reviewed_by","reviewed_date","catatan"]
                available_cols = [c for c in display_cols if c in view_hist.columns]

                st.caption(f"Menampilkan **{len(view_hist)}** request")
                st.dataframe(
                    view_hist[available_cols].reset_index(drop=True),
                    use_container_width=True, height=480
                )

                st.divider()
                st.markdown("**⬇️ Download History**")
                col_hd1, col_hd2, _ = st.columns([1,1,3])
                with col_hd1:
                    st.download_button("📄 CSV", view_hist.to_csv(index=False).encode("utf-8"),
                        "cr_history.csv", "text/csv", use_container_width=True)
                with col_hd2:
                    st.download_button("📊 Excel", to_excel(view_hist),
                        "cr_history.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)

st.markdown(section_body_end(), unsafe_allow_html=True)

# ══════════════════════════════════════════
# AUTO-NAVIGATE via JS — click tab by index
# ══════════════════════════════════════════
if st.session_state.active_tab > 0:
    tab_index = st.session_state.active_tab
    # JS robust: coba beberapa selector dan retry lebih lama
    st.markdown(f"""
    <script>
    (function() {{
        function clickTab() {{
            // Coba selector di berbagai level parent
            let found = false;
            for (let win of [window, window.parent, window.top]) {{
                try {{
                    const tabs = win.document.querySelectorAll('[data-testid="stTabs"] button[role="tab"]');
                    if (tabs.length > {tab_index}) {{
                        tabs[{tab_index}].click();
                        found = true;
                        break;
                    }}
                }} catch(e) {{}}
            }}
            return found;
        }}
        // Retry beberapa kali sampai berhasil
        let attempts = 0;
        const interval = setInterval(function() {{
            if (clickTab() || attempts > 15) clearInterval(interval);
            attempts++;
        }}, 150);
    }})();
    </script>
    """, unsafe_allow_html=True)
    st.session_state.active_tab = 0
