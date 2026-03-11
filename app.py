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

from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors
from reportlab.lib.units import mm

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
st.set_page_config(page_title="OrgChart HR", layout="wide", page_icon="🏢")

# ══════════════════════════════════════════
# LOAD DATA — Google Sheets via Service Account, CSV fallback
# ══════════════════════════════════════════
import gspread
from google.oauth2.service_account import Credentials
import os

SHEET_ID   = "1LaZpDfmFZJvIARf0RYoX-DtcbkjgOMlwT74nbamnvqM"
CREDS_FILE = "credentials.json"
SCOPES     = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

def clean_df(df):
    df.columns = df.columns.str.strip()
    df["Employee ID"] = df["Employee ID"].astype(str).str.strip()
    df["Manager ID"]  = df["Manager ID"].fillna("").astype(str).str.strip()
    df["SBU/Tribe"]   = df["SBU/Tribe"].fillna("").astype(str).str.strip()
    return df

@st.cache_data(ttl=300)
def load_data():
    # ── Coba via Service Account ──
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

if df is None:
    st.error("❌ Tidak ada data yang bisa dimuat. Pastikan credentials.json dan employee_data.csv tersedia.")
    st.stop()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .block-container { padding-top: 1.2rem; }
    div[data-testid="stMetric"] {
        background: #1e2433; border-radius: 12px;
        padding: 14px 18px; border: 1px solid #2d3448;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏢 OrgChart HR Dashboard")

# ── Status sumber data ──
col_status, col_refresh = st.columns([5, 1])
with col_status:
    if data_source == "google_sheets":
        st.success("🟢 Data terhubung ke Google Sheets — otomatis refresh setiap 5 menit")
    else:
        st.warning("🟡 Menggunakan data lokal (CSV). Periksa koneksi internet atau akses Google Sheets.")
with col_refresh:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

col1, col2, col3, col4 = st.columns(4)
col1.metric("👥 Total Karyawan", len(df))
col2.metric("🏢 Business Unit", df["Business Unit"].nunique())
col3.metric("📁 Divisi", df["Division"].nunique())
col4.metric("👔 Total Manager", df[df["Employee ID"].isin(df["Manager ID"].unique())]["Employee ID"].nunique())

st.divider()

tab1, tab2, tab3 = st.tabs(["🌳 Org Chart", "📋 Data Karyawan", "⚠️ Tanpa Direct Report"])

# ══════════════════════════════════════════
# ORG CHART HTML
# ══════════════════════════════════════════
def render_org_chart(tree_json_str, chart_height=700, initial_level="all"):
    level_map = {"all": "999", "top": "0", "level1": "1"}
    init_depth = level_map.get(initial_level, "999")

    html_code = f"""
<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f1117; font-family: 'Plus Jakarta Sans', sans-serif; overflow: hidden; width: 100%; height: {chart_height}px; }}
  .toolbar {{ position: fixed; top: 12px; right: 16px; display: flex; flex-direction: column; gap: 6px; z-index: 100; }}
  .tb-btn {{ width: 36px; height: 36px; background: #1e2433; border: 1px solid #3d4160; border-radius: 8px; color: #a0a8c0; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s; user-select: none; }}
  .tb-btn:hover {{ background: #2d3448; color: white; border-color: #4a90d9; }}
  .zoom-label {{ background: #1e2433; border: 1px solid #3d4160; border-radius: 8px; color: #6b7280; font-size: 11px; font-weight: 600; text-align: center; padding: 4px 0; }}
  #canvas {{ width: 100%; height: 100%; overflow: hidden; cursor: grab; position: relative; }}
  #canvas:active {{ cursor: grabbing; }}
  #tree-root {{ position: absolute; top: 40px; left: 50%; transform-origin: top center; display: flex; flex-direction: row; gap: 24px; align-items: flex-start; }}
  .node-wrapper {{ display: flex; flex-direction: column; align-items: center; }}
  .node-box {{ padding: 10px 14px; border-radius: 10px; text-align: center; min-width: 155px; max-width: 200px; cursor: pointer; border: 2px solid transparent; transition: all 0.18s ease; position: relative; user-select: none; }}
  .node-box:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.5); }}
  .node-box.in-div {{ background: #CCCCFF; border-color: #9999ee; color: #1a1a2e; }}
  .node-box.out-div {{ background: #2a2d3e; border-color: #3d4160; color: #a0a8c0; }}
  .node-box.company-mode {{ background: linear-gradient(135deg, #1e3a5f, #2d6a9f); border-color: #4a90d9; color: white; }}
  .badge {{ position: absolute; top: -8px; right: -8px; background: #f59e0b; color: #000; border-radius: 999px; font-size: 9px; font-weight: 700; padding: 2px 6px; min-width: 18px; }}
  .node-name {{ font-weight: 700; font-size: 12px; line-height: 1.3; margin-bottom: 2px; }}
  .node-pos {{ font-size: 10px; opacity: 0.85; line-height: 1.3; margin-bottom: 2px; }}
  .node-div {{ font-size: 9px; opacity: 0.65; margin-bottom: 1px; }}
  .node-sbu {{ font-size: 9px; opacity: 0.45; font-style: italic; }}
  .connector-v {{ width: 2px; background: #3d4160; flex-shrink: 0; }}
  .children-row {{ display: flex; flex-direction: row; align-items: flex-start; position: relative; }}
  .children-row::before {{ content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%); height: 2px; background: #3d4160; width: calc(100% - 100px); pointer-events: none; }}
  .single-child::before {{ display: none !important; }}
  .child-col {{ display: flex; flex-direction: column; align-items: center; padding: 0 10px; }}
  .collapsed-hint {{ font-size: 10px; color: #5a6080; margin-top: 4px; text-align: center; }}
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
with tab1:

    view_mode = st.radio("📌 Mode Tampilan", ["Per Divisi", "Seluruh Perusahaan"], horizontal=True)

    if view_mode == "Per Divisi":

        col_a, col_b, col_c = st.columns([2, 2, 2])
        with col_a:
            bu_list = sorted(df["Business Unit"].dropna().unique().tolist())
            selected_bu = st.selectbox("🏢 Business Unit", bu_list, key="sel_bu")
        with col_b:
            div_list = sorted(df[df["Business Unit"] == selected_bu]["Division"].dropna().unique().tolist())
            selected_div = st.selectbox("📁 Divisi", div_list, key="sel_div")

        filtered = df[(df["Business Unit"] == selected_bu) & (df["Division"] == selected_div)].copy()
        all_leaders = filtered[filtered["Employee ID"].isin(df["Manager ID"].unique())]["Employee Name"].tolist()

        with col_c:
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
        chart_html = render_org_chart(json.dumps(tree_data), chart_height=680, initial_level=selected_level)
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
            pdf_title = f"Org Chart — {selected_div} ({selected_bu})"
            pdf_data = generate_pdf(tree_data, pdf_title)
            st.download_button("📑 PDF (Full)", pdf_data, f"{selected_div}_full.pdf", "application/pdf", use_container_width=True)
        with col_dl4:
            pdf_title_sum = f"Org Chart Summary — {selected_div} ({selected_bu})"
            pdf_data_sum = generate_pdf_summary(tree_data, pdf_title_sum)
            st.download_button("📑 PDF (Summary)", pdf_data_sum, f"{selected_div}_summary.pdf", "application/pdf", use_container_width=True)

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
        chart_html2 = render_org_chart(json.dumps(tree_data2), chart_height=750, initial_level=selected_level2)
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
            pdf_data2 = generate_pdf(tree_data2, "Org Chart — Seluruh Perusahaan")
            st.download_button("📑 PDF (Full)", pdf_data2, "orgchart_perusahaan_full.pdf", "application/pdf", use_container_width=True)
        with col_dl7:
            pdf_sum2 = generate_pdf_summary(tree_data2, "Org Chart Summary — Seluruh Perusahaan")
            st.download_button("📑 PDF (Summary)", pdf_sum2, "orgchart_perusahaan_summary.pdf", "application/pdf", use_container_width=True)

# ══════════════════════════════════════════
# TAB 2 — DATA KARYAWAN
# ══════════════════════════════════════════
with tab2:
    st.subheader("📋 Data Karyawan")
    c1, c2, c3 = st.columns(3)
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

    data_view = df.copy()
    if search:
        data_view = data_view[data_view["Employee Name"].str.contains(search, case=False, na=False)]
    if bu_f != "Semua":
        data_view = data_view[data_view["Business Unit"] == bu_f]
    if div_f != "Semua":
        data_view = data_view[data_view["Division"] == div_f]

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
with tab3:
    st.subheader("⚠️ Karyawan dengan Manager ID Tidak Ditemukan")
    st.caption("Daftar karyawan yang Manager ID-nya kosong atau tidak terdaftar di sistem. Data ini perlu diperbaiki di backend.")

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
    st.subheader("📊 Breakdown per Divisi")
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
