import streamlit as st
import pandas as pd
import json
from io import BytesIO
import os
from datetime import datetime

# ── ReportLab (opsional — tidak tersedia di Python 3.14 Streamlit Cloud) ──
try:
    import _md5
except ImportError:
    pass

try:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib import colors
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════
SHEET_ID   = "1LaZpDfmFZJvIARf0RYoX-DtcbkjgOMlwT74nbamnvqM"
CREDS_FILE = "credentials.json"
SCOPES     = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
CHIEF_ROOT = "SLKR001"


# ══════════════════════════════════════════════════════════════════
# DATA HELPERS
# ══════════════════════════════════════════════════════════════════
def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    df["Employee ID"] = df["Employee ID"].astype(str).str.strip()
    df["Manager ID"]  = df["Manager ID"].fillna("").astype(str).str.strip()
    df["SBU/Tribe"] = df["SBU/Tribe"].fillna("").astype(str).str.strip() if "SBU/Tribe" in df.columns else ""
    if "Career Stage" not in df.columns:
        df["Career Stage"] = ""
    return df


def get_gspread_client():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
        elif os.path.exists(CREDS_FILE):
            creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
        else:
            return None
        return gspread.authorize(creds)
    except Exception:
        return None


@st.cache_data(ttl=300)
def load_data():
    client = get_gspread_client()
    if client:
        try:
            sheet = client.open_by_key(SHEET_ID).sheet1
            df = pd.DataFrame(sheet.get_all_records())
            return clean_df(df), "google_sheets"
        except Exception as e:
            st.warning(f"⚠️ Gagal membaca dari Google Sheets: {str(e)[:80]}")
    try:
        df = pd.read_csv("employee_data.csv")
        return clean_df(df), "local_csv"
    except Exception:
        return None, "error"


@st.cache_data(ttl=60)
def load_change_requests():
    client = get_gspread_client()
    if not client:
        return pd.DataFrame()
    try:
        ws   = client.open_by_key(SHEET_ID).worksheet("change_requests")
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame(columns=[
                "request_id","submitted_date","requester_name","requester_email",
                "change_type","employee_id","employee_name","data_lama","data_baru",
                "alasan","status","reviewed_by","reviewed_date","catatan",
            ])
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def get_cr_sheet():
    client = get_gspread_client()
    if not client:
        return None
    try:
        return client.open_by_key(SHEET_ID).worksheet("change_requests")
    except Exception:
        return None


def save_change_request(row_data: dict) -> bool:
    ws = get_cr_sheet()
    if not ws:
        return False
    cols = ["request_id","submitted_date","requester_name","requester_email",
            "change_type","employee_id","employee_name","data_lama","data_baru",
            "alasan","status","reviewed_by","reviewed_date","catatan"]
    try:
        ws.append_row([str(row_data.get(c, "")) for c in cols], value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        st.error(f"Gagal menyimpan: {e}")
        return False


def update_cr_status(request_id: str, status: str, reviewed_by: str, catatan: str) -> bool:
    ws = get_cr_sheet()
    if not ws:
        return False
    try:
        cell = ws.find(request_id)
        if not cell:
            return False
        row = cell.row
        ws.update_cell(row, 11, status)
        ws.update_cell(row, 12, reviewed_by)
        ws.update_cell(row, 13, datetime.now().strftime("%Y-%m-%d %H:%M"))
        ws.update_cell(row, 14, catatan)
        return True
    except Exception as e:
        st.error(f"Gagal update: {e}")
        return False


def generate_request_id() -> str:
    import time
    return f"REQ-{int(time.time())}"


# ══════════════════════════════════════════════════════════════════
# ORG CHART HELPERS
# ══════════════════════════════════════════════════════════════════
def get_all_managers(emp_ids: list, all_data: pd.DataFrame) -> set:
    result   = set(emp_ids)
    to_check = set(emp_ids)
    while to_check:
        mgr_ids  = set(all_data[all_data["Employee ID"].isin(to_check)]["Manager ID"].tolist()) - {"", "nan"}
        new_mgrs = mgr_ids - result
        if not new_mgrs:
            break
        result.update(new_mgrs)
        to_check = new_mgrs
    return result


def build_tree_json(full_data: pd.DataFrame, selected_div: str, root_ids: list, mode: str = "division") -> list:
    valid = full_data[full_data["Manager ID"].notna() & (full_data["Manager ID"] != "") & (full_data["Manager ID"] != "nan")]
    children_map: dict = valid.groupby("Manager ID")["Employee ID"].apply(list).to_dict()

    info_map: dict = (
        full_data
        .set_index("Employee ID")[["Employee Name", "Job Position", "Division", "SBU/Tribe", "Business Unit"]]
        .rename(columns={"Employee Name": "name", "Job Position": "position",
                         "Division": "division", "SBU/Tribe": "sbu", "Business Unit": "bu"})
        .to_dict(orient="index")
    )

    def build_node(emp_id: str, visited: set | None = None) -> dict | None:
        if visited is None:
            visited = set()
        if emp_id in visited or emp_id not in info_map:
            return None
        visited.add(emp_id)
        info = info_map[emp_id]
        node = {
            "id":       emp_id,
            "name":     info["name"],
            "position": info["position"],
            "division": info["division"],
            "sbu":      info.get("sbu", ""),
            "bu":       info["bu"],
            "in_div":   bool(info["division"] == selected_div) if mode == "division" else True,
            "children": [],
        }
        for child_id in children_map.get(emp_id, []):
            child_node = build_node(child_id, visited)
            if child_node:
                node["children"].append(child_node)
        return node

    return [n for rid in root_ids if (n := build_node(rid))]


def to_excel(dataframe: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Data")
    return output.getvalue()


# ══════════════════════════════════════════════════════════════════
# PDF GENERATORS 
# ══════════════════════════════════════════════════════════════════
def generate_pdf(tree_nodes, title_text):
    if not REPORTLAB_OK:
        raise ImportError("ReportLab tidak tersedia")
    NODE_W, NODE_H, H_GAP, V_GAP = 150, 60, 30, 50
    positions, draw_order = {}, []

    def calc_subtree_width(node):
        if not node["children"]:
            return NODE_W
        total = sum(calc_subtree_width(c) for c in node["children"]) + H_GAP * (len(node["children"]) - 1)
        return max(total, NODE_W)

    def assign_positions(node, x_center, y):
        positions[node["id"]] = (x_center, y)
        draw_order.append(node)
        if not node["children"]:
            return
        total_w = sum(calc_subtree_width(c) for c in node["children"]) + H_GAP * (len(node["children"]) - 1)
        x_start = x_center - total_w / 2
        for child in node["children"]:
            cw = calc_subtree_width(child)
            assign_positions(child, x_start + cw / 2, y - (NODE_H + V_GAP))
            x_start += cw + H_GAP

    total_w  = sum(calc_subtree_width(r) for r in tree_nodes) + H_GAP * (len(tree_nodes) - 1)
    max_depth = [0]
    def get_depth(node, d=0):
        max_depth[0] = max(max_depth[0], d)
        for c in node["children"]:
            get_depth(c, d + 1)
    for r in tree_nodes:
        get_depth(r)
    total_h = (max_depth[0] + 1) * (NODE_H + V_GAP) + 120
    page_w  = max(total_w + 100, landscape(A3)[0])
    page_h  = max(total_h + 100, landscape(A3)[1])

    x_start = page_w / 2 - total_w / 2
    y_top   = page_h - 80
    for root in tree_nodes:
        rw = calc_subtree_width(root)
        assign_positions(root, x_start + rw / 2, y_top)
        x_start += rw + H_GAP

    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=(page_w, page_h))
    c.setFillColor(colors.HexColor("#0f1117"))
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(page_w / 2, page_h - 45, title_text)
    c.setFont("Helvetica", 10); c.setFillColor(colors.HexColor("#6b7280"))
    c.drawCentredString(page_w / 2, page_h - 62, f"Total: {len(draw_order)} karyawan ditampilkan")
    c.setStrokeColor(colors.HexColor("#3d4160")); c.setLineWidth(1.5)
    for node in draw_order:
        if node["id"] not in positions:
            continue
        nx, ny = positions[node["id"]]
        for child in node["children"]:
            if child["id"] not in positions:
                continue
            cx, cy = positions[child["id"]]
            mid_y = (ny - NODE_H / 2 + cy + NODE_H / 2) / 2
            c.line(nx, ny - NODE_H/2, nx, mid_y)
            c.line(nx, mid_y, cx, mid_y)
            c.line(cx, mid_y, cx, cy + NODE_H/2)
    for node in draw_order:
        if node["id"] not in positions:
            continue
        nx, ny = positions[node["id"]]
        x_left, y_bottom = nx - NODE_W / 2, ny - NODE_H / 2
        if node.get("in_div", True):
            fill_c, txt_c, bdr_c = colors.HexColor("#CCCCFF"), colors.HexColor("#1a1a2e"), colors.HexColor("#9999ee")
        else:
            fill_c, txt_c, bdr_c = colors.HexColor("#2a2d3e"), colors.HexColor("#a0a8c0"), colors.HexColor("#3d4160")
        c.setFillColor(fill_c); c.setStrokeColor(bdr_c); c.setLineWidth(1.5)
        c.roundRect(x_left, y_bottom, NODE_W, NODE_H, 8, fill=1, stroke=1)
        c.setFillColor(txt_c); c.setFont("Helvetica-Bold", 8)
        name = node["name"][:21] + "…" if len(node["name"]) > 22 else node["name"]
        c.drawCentredString(nx, y_bottom + NODE_H - 16, name)
        c.setFont("Helvetica", 7)
        pos_text = node["position"][:25] + "…" if len(node["position"]) > 26 else node["position"]
        c.drawCentredString(nx, y_bottom + NODE_H - 28, pos_text)
    legend_y, legend_x = 30, 40
    c.setFillColor(colors.HexColor("#CCCCFF")); c.setStrokeColor(colors.HexColor("#9999ee"))
    c.roundRect(legend_x, legend_y, 14, 14, 3, fill=1, stroke=1)
    c.setFillColor(colors.white); c.setFont("Helvetica", 8)
    c.drawString(legend_x + 18, legend_y + 3, "Karyawan divisi ini")
    c.setFillColor(colors.HexColor("#2a2d3e")); c.setStrokeColor(colors.HexColor("#3d4160"))
    c.roundRect(legend_x + 140, legend_y, 14, 14, 3, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#a0a8c0"))
    c.drawString(legend_x + 158, legend_y + 3, "Atasan dari divisi lain")
    c.save(); buffer.seek(0)
    return buffer.getvalue()


def generate_pdf_summary(tree_nodes, title_text):
    if not REPORTLAB_OK:
        raise ImportError("ReportLab tidak tersedia")
    NODE_W_FULL, NODE_H_FULL = 170, 68
    NODE_W_DIV,  NODE_H_DIV  = 130, 32
    H_GAP, V_GAP = 28, 45

    def trim_tree(node, depth=0):
        if depth > 2:
            return None
        trimmed = dict(node)
        trimmed["_depth"]   = depth
        trimmed["children"] = [] if depth == 2 else [
            c for c in [trim_tree(ch, depth + 1) for ch in node.get("children", [])] if c
        ]
        return trimmed

    trimmed_roots = [t for t in [trim_tree(r) for r in tree_nodes] if t]

    def node_w(n): return NODE_W_FULL if n["_depth"] < 2 else NODE_W_DIV
    def node_h(n): return NODE_H_FULL if n["_depth"] < 2 else NODE_H_DIV

    def subtree_width(n):
        if not n["children"]:
            return node_w(n)
        return max(sum(subtree_width(c) for c in n["children"]) + H_GAP * (len(n["children"]) - 1), node_w(n))

    positions, draw_list = {}, []

    def assign_pos(node, x_center, y):
        positions[node["id"]] = (x_center, y, node["_depth"])
        draw_list.append(node)
        if not node["children"]:
            return
        total_w = sum(subtree_width(c) for c in node["children"]) + H_GAP * (len(node["children"]) - 1)
        x_start = x_center - total_w / 2
        child_y = y - node_h(node) / 2 - V_GAP - (NODE_H_DIV / 2 if node["_depth"] == 1 else NODE_H_FULL / 2)
        for child in node["children"]:
            cw = subtree_width(child)
            assign_pos(child, x_start + cw / 2, child_y)
            x_start += cw + H_GAP

    def max_depth_tree(node):
        if not node["children"]:
            return node["_depth"]
        return max(max_depth_tree(c) for c in node["children"])

    actual_max = max((max_depth_tree(r) for r in trimmed_roots), default=0)
    total_w    = sum(subtree_width(r) for r in trimmed_roots) + H_GAP * (len(trimmed_roots) - 1)
    h_levels   = [NODE_H_FULL, NODE_H_FULL, NODE_H_DIV]
    total_h    = sum(h_levels[:actual_max + 1]) + V_GAP * actual_max + 130
    page_w = max(total_w + 120, landscape(A3)[0])
    page_h = max(total_h + 80,  landscape(A3)[1])
    x_start = page_w / 2 - total_w / 2
    y_top   = page_h - 90
    for root in trimmed_roots:
        rw = subtree_width(root)
        assign_pos(root, x_start + rw / 2, y_top)
        x_start += rw + H_GAP

    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=(page_w, page_h))
    c.setFillColor(colors.HexColor("#0f1117")); c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(page_w / 2, page_h - 40, title_text)
    c.setFont("Helvetica", 9); c.setFillColor(colors.HexColor("#6b7280"))
    c.drawCentredString(page_w / 2, page_h - 56, f"Ditampilkan hingga Level 2 · {len(draw_list)} node")
    y_seen = {}
    for node in draw_list:
        nx, ny, depth = positions[node["id"]]
        if depth not in y_seen:
            y_seen[depth] = ny
    for depth, label in {0: "Top Level", 1: "Level 1", 2: "Level 2"}.items():
        if depth in y_seen:
            c.setFillColor(colors.HexColor("#4b5563")); c.setFont("Helvetica-Bold", 8)
            c.drawString(12, y_seen[depth] - 4, label)
    c.setStrokeColor(colors.HexColor("#3d4160")); c.setLineWidth(1.2)
    for node in draw_list:
        nx, ny, depth = positions[node["id"]]
        nh = node_h(node)
        for child in node["children"]:
            if child["id"] not in positions:
                continue
            cx, cy, _ = positions[child["id"]]
            ch  = node_h(child)
            mid = (ny - nh / 2 + cy + ch / 2) / 2
            c.line(nx, ny - nh/2, nx, mid); c.line(nx, mid, cx, mid); c.line(cx, mid, cx, cy + ch/2)
    for node in draw_list:
        nx, ny, depth = positions[node["id"]]
        nw, nh = node_w(node), node_h(node)
        x_left, y_bottom = nx - nw / 2, ny - nh / 2
        if depth < 2:
            if node.get("in_div", True):
                fill, txt, bdr = colors.HexColor("#CCCCFF"), colors.HexColor("#1a1a2e"), colors.HexColor("#9999ee")
            else:
                fill, txt, bdr = colors.HexColor("#2a2d3e"), colors.HexColor("#c0c8e0"), colors.HexColor("#3d4160")
            c.setFillColor(fill); c.setStrokeColor(bdr); c.setLineWidth(1.5)
            c.roundRect(x_left, y_bottom, nw, nh, 7, fill=1, stroke=1)
            c.setFillColor(txt); c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(nx, y_bottom + nh - 15, node["name"][:24] + "…" if len(node["name"]) > 24 else node["name"])
            c.setFont("Helvetica", 7)
            c.drawCentredString(nx, y_bottom + nh - 27, node["position"][:28] + "…" if len(node["position"]) > 28 else node["position"])
            c.setFont("Helvetica", 6.5)
            c.drawCentredString(nx, y_bottom + nh - 39, node["division"][:30] + "…" if len(node["division"]) > 30 else node["division"])
        else:
            c.setFillColor(colors.HexColor("#1e2433")); c.setStrokeColor(colors.HexColor("#3d4160")); c.setLineWidth(1)
            c.roundRect(x_left, y_bottom, nw, nh, 5, fill=1, stroke=1)
            c.setFillColor(colors.HexColor("#94a3b8")); c.setFont("Helvetica", 7)
            c.drawCentredString(nx, y_bottom + nh / 2 - 4, node["division"][:22] + "…" if len(node["division"]) > 22 else node["division"])
    c.save(); buffer.seek(0)
    return buffer.getvalue()


# ══════════════════════════════════════════════════════════════════
# ORG CHART HTML RENDERER
# ══════════════════════════════════════════════════════════════════
def render_org_chart(tree_json_str, chart_height=700, initial_level="all", theme=None):
    level_map = {"all": "999", "top": "0", "level1": "1"}
    init_depth = level_map.get(initial_level, "999")
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

    return f"""
<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: {bg}; font-family: 'DM Sans', sans-serif; overflow: hidden; width: 100%; height: {chart_height}px; }}
  .toolbar {{ position: fixed; top: 12px; right: 16px; display: flex; flex-direction: column; gap: 6px; z-index: 100; }}
  .tb-btn {{ width: 34px; height: 34px; background: {tb_bg}; border: 1.5px solid {tb_border}; border-radius: 10px; color: {tb_color}; font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s; user-select: none; box-shadow: 0 2px 8px rgba(91,79,207,0.08); }}
  .tb-btn:hover {{ background: {node_in_bg}; border-color: {node_in_bdr}; box-shadow: 0 4px 16px rgba(91,79,207,0.16); transform: translateY(-1px); }}
  .zoom-label {{ background: {tb_bg}; border: 1.5px solid {tb_border}; border-radius: 8px; color: {hint_color}; font-size: 10px; font-weight: 700; text-align: center; padding: 4px 0; letter-spacing: 0.04em; }}
  #canvas {{ width: 100%; height: 100%; overflow: hidden; cursor: grab; position: relative; }}
  #canvas:active {{ cursor: grabbing; }}
  #tree-root {{ position: absolute; top: 40px; left: 50%; transform-origin: top center; display: flex; flex-direction: row; gap: 24px; align-items: flex-start; }}
  .node-wrapper {{ display: flex; flex-direction: column; align-items: center; }}
  .node-box {{ padding: 12px 16px; border-radius: 14px; text-align: center; min-width: 160px; max-width: 210px; cursor: pointer; border: 1.5px solid transparent; transition: all 0.2s cubic-bezier(0.34,1.56,0.64,1); position: relative; user-select: none; box-shadow: 0 2px 12px rgba(91,79,207,0.08); }}
  .node-box:hover {{ transform: translateY(-3px) scale(1.02); box-shadow: 0 12px 32px rgba(91,79,207,0.18); }}
  .node-box.in-div {{ background: {node_in_bg}; border-color: {node_in_bdr}; color: {node_in_txt}; }}
  .node-box.out-div {{ background: {node_out_bg}; border-color: {node_out_bdr}; color: {node_out_txt}; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
  .node-box.company-mode {{ background: linear-gradient(135deg,#5b4fcf,#7c6fcd); border-color: #4a3fb8; color: white; box-shadow: 0 4px 20px rgba(91,79,207,0.3); }}
  .badge {{ position: absolute; top: -8px; right: -8px; background: {badge_bg}; color: white; border-radius: 999px; font-size: 9px; font-weight: 700; padding: 2px 7px; min-width: 20px; border: 2px solid #f8f7ff; box-shadow: 0 2px 8px rgba(91,79,207,0.3); }}
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
  <div class="legend-item" style="color:#5a6080">💡 Klik node · Scroll zoom · Drag geser</div>
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
  scale = Math.min(canvas.clientWidth / (treeRoot.scrollWidth + 60), canvas.clientHeight / (treeRoot.scrollHeight + 60), 1);
  translateX = 0; translateY = 20; applyTransform();
}}
canvas.addEventListener('wheel', (e) => {{ e.preventDefault(); scale = Math.max(0.2, Math.min(3, scale + (e.deltaY > 0 ? -0.1 : 0.1))); applyTransform(); }}, {{ passive: false }});
canvas.addEventListener('mousedown', (e) => {{ if (e.target.closest('.node-box')) return; isDragging = true; dragStartX = e.clientX; dragStartY = e.clientY; dragStartTX = translateX; dragStartTY = translateY; }});
window.addEventListener('mousemove', (e) => {{ if (!isDragging) return; translateX = dragStartTX + (e.clientX - dragStartX); translateY = dragStartTY + (e.clientY - dragStartY); applyTransform(); }});
window.addEventListener('mouseup', () => {{ isDragging = false; }});
function countDescendants(node) {{ let c = 0; for (const ch of node.children || []) c += 1 + countDescendants(ch); return c; }}
function applyInitialCollapse(node, depth) {{
  if (initDepth < 999 && depth >= initDepth && node.children && node.children.length > 0) collapsed[node.id] = true;
  for (const child of node.children || []) applyInitialCollapse(child, depth + 1);
}}
function renderNode(node) {{
  const isCollapsed = collapsed[node.id] || false;
  const hasChildren = node.children && node.children.length > 0;
  const descCount   = countDescendants(node);
  const wrapper = document.createElement('div'); wrapper.className = 'node-wrapper';
  const box     = document.createElement('div');
  box.className = `node-box ${{node.company_mode ? 'company-mode' : node.in_div ? 'in-div' : 'out-div'}}`;
  if (hasChildren && descCount > 0) {{
    const badge = document.createElement('div'); badge.className = 'badge';
    badge.textContent = isCollapsed ? descCount : node.children.length; box.appendChild(badge);
  }}
  ['name','position','division'].forEach(k => {{ const el = document.createElement('div'); el.className = `node-${{k}}`; el.textContent = node[k]; box.appendChild(el); }});
  if (node.sbu && node.sbu !== '' && node.sbu !== 'nan') {{
    const sbuEl = document.createElement('div'); sbuEl.className = 'node-sbu'; sbuEl.textContent = node.sbu; box.appendChild(sbuEl);
  }}
  if (hasChildren) {{ box.addEventListener('click', () => {{ collapsed[node.id] = !collapsed[node.id]; rerenderTree(); }}); box.title = isCollapsed ? 'Klik untuk expand' : 'Klik untuk collapse'; }}
  wrapper.appendChild(box);
  if (hasChildren && !isCollapsed) {{
    const connV = document.createElement('div'); connV.className = 'connector-v'; connV.style.height = '20px'; wrapper.appendChild(connV);
    const childRow = document.createElement('div'); childRow.className = 'children-row' + (node.children.length <= 1 ? ' single-child' : '');
    node.children.forEach(child => {{
      const col   = document.createElement('div'); col.className = 'child-col';
      const connT = document.createElement('div'); connT.className = 'connector-v'; connT.style.height = '20px';
      col.appendChild(connT); col.appendChild(renderNode(child)); childRow.appendChild(col);
    }});
    wrapper.appendChild(childRow);
  }} else if (hasChildren && isCollapsed) {{
    const hint = document.createElement('div'); hint.className = 'collapsed-hint'; hint.textContent = `▼ ${{descCount}} tersembunyi`; wrapper.appendChild(hint);
  }}
  return wrapper;
}}
function rerenderTree() {{ const r = document.getElementById('tree-root'); r.innerHTML = ''; treeData.forEach(n => r.appendChild(renderNode(n))); }}
treeData.forEach(n => applyInitialCollapse(n, 0)); rerenderTree(); setTimeout(fitView, 300);
</script></body></html>"""


# ══════════════════════════════════════════════════════════════════
# STREAMLIT PAGE CONFIG
# ══════════════════════════════════════════════════════════════════
st.set_page_config(page_title="HRIS", layout="wide", page_icon="🏢", initial_sidebar_state="expanded")

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "nav_filter" not in st.session_state:
    st.session_state.nav_filter = {}

df, data_source = load_data()

if df is None:
    st.error("❌ Tidak ada data yang bisa dimuat. Pastikan credentials.json dan employee_data.csv tersedia.")
    st.stop()


# ══════════════════════════════════════════════════════════════════
# THEME
# ══════════════════════════════════════════════════════════════════
dm = st.session_state.dark_mode
T = {
    "bg":              "#0f1117"   if dm else "#faf8ff",
    "surface_low":     "#1a1d2e"   if dm else "#f4f3fb",
    "surface_lowest":  "#252840"   if dm else "#ffffff",
    "surface_highest": "#2e3255"   if dm else "#e2e2e9",
    "primary":         "#7c6fcd"   if dm else "#4234b6",
    "primary_cont":    "#9b8fef"   if dm else "#5b4fcf",
    "primary_fixed":   "#1e1a3a"   if dm else "#e4dfff",
    "on_primary":      "#ffffff"   if dm else "#ffffff",
    "text":            "#e8e6ff"   if dm else "#1a1b21",
    "text_variant":    "#9e9ec8"   if dm else "#46464f",
    "text3":           "#6b6b9e"   if dm else "#76767f",
    "outline":         "rgba(200,196,214,0.20)" if dm else "rgba(200,196,214,0.35)",
    "outline_hover":   "rgba(200,196,214,0.60)" if dm else "rgba(66,52,182,0.40)",
    "sidebar_bg":      "#13151f"   if dm else "#CCCCFF",
    "sidebar_text":    "#c4b5fd"   if dm else "#1a1040",
    "sidebar_text2":   "#6b5fa0"   if dm else "#4a3fa0",
    "sidebar_active":  "#ffffff"   if dm else "#1a1040",
    "sidebar_pill":    "#252840"   if dm else "#ffffff",
    "success_bg":      "#0f2a1a"   if dm else "#f0fff4",
    "success_bdr":     "#166534"   if dm else "#86efac",
    "success_txt":     "#86efac"   if dm else "#166534",
    "warn_bg":         "#2a1f00"   if dm else "#fffbeb",
    "warn_bdr":        "#92400e"   if dm else "#fde68a",
    "warn_txt":        "#fde68a"   if dm else "#92400e",
    "node_in_bg":      "linear-gradient(135deg,#2a2060,#3d2f8a)" if dm else "linear-gradient(135deg,#ede9fe,#ddd6fe)",
    "node_in_txt":     "#e0d8ff"   if dm else "#2e1a6e",
    "node_in_bdr":     "#5b4fcf"   if dm else "#c4b5fd",
    "node_out_bg":     "#1a1d2e"   if dm else "#ffffff",
    "node_out_txt":    "#9e9ec8"   if dm else "#4b5563",
    "node_out_bdr":    "#2d3160"   if dm else "#e5e7eb",
    "connector":       "#2d3160"   if dm else "#ddd6fe",
    "badge_bg":        "#7c6fcd"   if dm else "#4234b6",
    "chart_bg":        "#0f1117"   if dm else "#faf8ff",
    "tb_bg":           "#1a1d2e"   if dm else "#ffffff",
    "tb_color":        "#9b8fef"   if dm else "#4234b6",
    "tb_border":       "#2d3160"   if dm else "#ede9fe",
    "bg2":             "#1a1d2e"   if dm else "#ffffff",
    "bg3":             "#252840"   if dm else "#f4f3fb",
    "border":          "rgba(200,196,214,0.25)" if dm else "rgba(200,196,214,0.40)",
    "border2":         "#3d4180"   if dm else "#c4b5fd",
    "accent":          "#7c6fcd"   if dm else "#4234b6",
    "accent2":         "#9b8fef"   if dm else "#5b4fcf",
    "accent_bg":       "#1e1a3a"   if dm else "#e4dfff",
    "metric_shadow":   "rgba(66,52,182,0.18)"  if dm else "rgba(66,52,182,0.07)",
    "dl_btn_bg":       "#1a1d2e"   if dm else "#ffffff",
    "dl_btn_color":    "#9b8fef"   if dm else "#4234b6",
    "input_bg":        "#1a1d2e"   if dm else "#ffffff",
    "tab_active":      "#9b8fef"   if dm else "#4234b6",
    "tab_inactive":    "#4a4a7a"   if dm else "#76767f",
    "divider":         "rgba(200,196,214,0.20)" if dm else "rgba(200,196,214,0.30)",
    "radio_txt":       "#c4b5fd"   if dm else "#46464f",
    "label_txt":       "#6b6b9e"   if dm else "#76767f",
}

CHART_COLORS = {
    "primary":   "#4234b6",
    "secondary": "#5b4fcf",
    "success":   "#059669",
    "warning":   "#d97706",
    "danger":    "#dc2626",
    "info":      "#0284c7",
    "scale":     ["#dc2626","#f59e0b","#6b7280","#3b82f6","#059669"],  
    "bars":      ["#4234b6","#5b4fcf","#7c6fcd","#9b8fef","#c4b5fd","#e4dfff","#ddd6fe","#ede9fe"],
}


# ══════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════════════════════════════
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}
html, body, [class*="css"] {{
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    color: {T["text"]} !important;
    -webkit-font-smoothing: antialiased;
}}
.stApp {{ background-color: {T["bg"]} !important; transition: background-color 0.35s ease, color 0.35s ease; }}
#MainMenu, footer {{ visibility: hidden !important; }}
header {{ visibility: hidden !important; }}
[data-testid="stToolbar"] {{ display: none !important; }}
.block-container {{
    padding-top: 2rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 100% !important;
    background-color: {T["bg"]} !important;
}}
[data-testid="stSidebar"] {{
    background: {T["sidebar_bg"]} !important;
    border-right: none !important;
    box-shadow: 4px 0 32px rgba(66,52,182,0.10) !important;
    transition: background 0.35s ease !important;
}}
[data-testid="stSidebar"] .block-container {{ padding: 0 !important; background: transparent !important; }}
[data-testid="stSidebar"] * {{ color: {T["sidebar_text"]} !important; font-family: 'Plus Jakarta Sans', sans-serif !important; }}
[data-testid="stSidebar"] label {{
    font-size: 11px !important; font-weight: 600 !important;
    text-transform: uppercase !important; letter-spacing: 0.07em !important;
    color: {T["sidebar_text2"]} !important;
}}
h1, h2, h3 {{ font-family: 'Manrope', sans-serif !important; color: {T["text"]} !important; letter-spacing: -0.02em !important; }}

/* TABS */
[data-testid="stTabs"] {{ background: transparent !important; border-bottom: 1px solid {T["outline"]} !important; }}
[data-testid="stTabs"] button {{
    font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 600 !important;
    font-size: 13.5px !important; color: {T["tab_inactive"]} !important;
    border-radius: 0 !important; padding: 12px 22px !important;
    background: transparent !important; transition: color 0.2s, background 0.2s !important;
}}
[data-testid="stTabs"] button[aria-selected="true"] {{
    color: {T["primary"]} !important; border-bottom: 2.5px solid {T["primary"]} !important; font-weight: 700 !important;
}}
[data-testid="stTabs"] button:hover {{ color: {T["primary"]} !important; background: {T["primary_fixed"]} !important; }}
[data-testid="stTabs"] [data-testid="stTabs"] button {{ font-size: 12.5px !important; padding: 8px 16px !important; }}

/* METRIC CARDS */
div[data-testid="stMetric"] {{
    background: {T["surface_lowest"]} !important; border-radius: 16px !important;
    padding: 22px 24px !important; border: none !important;
    box-shadow: 0 2px 24px {T["metric_shadow"]}, 0 0 0 1px {T["outline"]} !important;
    transition: box-shadow 0.25s ease, transform 0.25s ease !important;
    position: relative !important; overflow: hidden !important;
}}
div[data-testid="stMetric"]::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, {T["primary"]}, {T["primary_cont"]}); opacity: 0.7;
}}
div[data-testid="stMetric"]:hover {{
    box-shadow: 0 8px 40px {T["metric_shadow"]}, 0 0 0 1px {T["outline_hover"]} !important;
    transform: translateY(-2px) scale(1.01) !important;
}}
div[data-testid="stMetric"] label {{
    font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 11px !important;
    font-weight: 700 !important; text-transform: uppercase !important;
    letter-spacing: 0.07em !important; color: {T["text3"]} !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    font-family: 'Manrope', sans-serif !important; font-size: 34px !important;
    font-weight: 800 !important; color: {T["primary"]} !important;
    letter-spacing: -0.03em !important; line-height: 1.1 !important;
}}

/* BUTTONS */
[data-testid="stButton"] button {{
    background: linear-gradient(135deg, {T["primary"]}, {T["primary_cont"]}) !important;
    color: {T["on_primary"]} !important; border: none !important; border-radius: 9999px !important;
    font-weight: 600 !important; font-size: 13px !important; padding: 8px 20px !important;
    transition: all 0.2s ease !important; letter-spacing: 0.01em !important;
    box-shadow: 0 2px 12px rgba(66,52,182,0.25) !important;
}}
[data-testid="stButton"] button:hover {{
    transform: scale(1.02) !important; box-shadow: 0 6px 24px rgba(66,52,182,0.35) !important;
    filter: brightness(1.08) !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button {{
    background: transparent !important; color: {T["sidebar_text"]} !important;
    border: none !important; border-radius: 9999px !important; text-align: left !important;
    font-size: 13.5px !important; font-weight: 500 !important; padding: 10px 18px !important;
    box-shadow: none !important; margin-bottom: 2px !important; width: 100% !important;
    transition: all 0.18s ease !important; font-family: 'Plus Jakarta Sans', sans-serif !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {{
    background: {T["sidebar_pill"]} !important; color: {T["sidebar_active"]} !important;
    transform: none !important; box-shadow: 0 2px 16px rgba(66,52,182,0.15) !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {{
    background: {T["sidebar_pill"]} !important; color: {T["sidebar_active"]} !important;
    border: none !important; border-radius: 9999px !important;
    font-size: 13.5px !important; font-weight: 700 !important; padding: 10px 18px !important;
    box-shadow: 0 2px 16px rgba(66,52,182,0.20) !important;
    transform: none !important; filter: none !important;
}}
[data-testid="stDownloadButton"] button {{
    background: transparent !important; color: {T["primary"]} !important;
    border: 1.5px solid {T["outline"]} !important; border-radius: 9999px !important;
    font-weight: 600 !important; font-size: 13px !important;
    transition: all 0.2s !important; box-shadow: none !important;
}}
[data-testid="stDownloadButton"] button:hover {{
    border-color: {T["primary"]} !important; background: {T["primary_fixed"]} !important; transform: scale(1.02) !important;
}}
[data-testid="stFormSubmitButton"] button {{
    background: linear-gradient(135deg, {T["primary"]}, {T["primary_cont"]}) !important;
    color: white !important; border: none !important; border-radius: 9999px !important;
    font-weight: 700 !important; font-size: 14px !important; padding: 14px 28px !important;
    width: 100% !important; transition: all 0.2s !important;
    box-shadow: 0 4px 20px rgba(66,52,182,0.3) !important;
}}
[data-testid="stFormSubmitButton"] button:hover {{
    transform: scale(1.02) !important; box-shadow: 0 8px 32px rgba(66,52,182,0.4) !important;
}}

/* INPUTS */
[data-testid="stSelectbox"] > div > div {{
    background: {T["surface_lowest"]} !important; border: 1.5px solid {T["outline"]} !important;
    border-radius: 12px !important; font-size: 13.5px !important; color: {T["text"]} !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
    box-shadow: 0 1px 8px {T["metric_shadow"]} !important;
}}
[data-testid="stSelectbox"] > div > div:focus-within {{
    border-color: {T["primary"]} !important;
    box-shadow: 0 0 0 3px {T["primary_fixed"]}, 0 1px 8px {T["metric_shadow"]} !important;
}}
[data-testid="stSelectbox"] svg {{ fill: {T["text_variant"]} !important; }}
div[data-baseweb="popover"] ul, div[data-baseweb="menu"] {{
    background: {T["surface_lowest"]} !important; border: none !important;
    border-radius: 14px !important;
    box-shadow: 0 8px 40px rgba(66,52,182,0.15), 0 0 0 1px {T["outline"]} !important;
    backdrop-filter: blur(12px) !important;
}}
div[data-baseweb="popover"] li, [role="option"] {{
    background: transparent !important; color: {T["text"]} !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 13.5px !important;
    border-radius: 8px !important; margin: 2px 6px !important;
}}
div[data-baseweb="popover"] li:hover, [role="option"]:hover {{
    background: {T["primary_fixed"]} !important; color: {T["primary"]} !important;
}}
div[data-baseweb="popover"] {{ background: transparent !important; }}
[data-testid="stTextInput"] input {{
    background: {T["surface_lowest"]} !important; border: 1.5px solid {T["outline"]} !important;
    border-radius: 12px !important; font-size: 13.5px !important; color: {T["text"]} !important;
    padding: 10px 14px !important; transition: border-color 0.2s, box-shadow 0.2s !important;
}}
[data-testid="stTextInput"] input:focus {{
    border-color: {T["primary"]} !important; box-shadow: 0 0 0 3px {T["primary_fixed"]} !important; outline: none !important;
}}
[data-testid="stTextInput"] input::placeholder {{ color: {T["text3"]} !important; }}
[data-testid="stTextArea"] textarea {{
    background: {T["surface_lowest"]} !important; border: 1.5px solid {T["outline"]} !important;
    border-radius: 12px !important; font-size: 13.5px !important; color: {T["text"]} !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important; transition: border-color 0.2s, box-shadow 0.2s !important;
}}
[data-testid="stTextArea"] textarea:focus {{
    border-color: {T["primary"]} !important; box-shadow: 0 0 0 3px {T["primary_fixed"]} !important;
}}
[data-testid="stTextArea"] textarea::placeholder {{ color: {T["text3"]} !important; }}
[data-testid="stNumberInput"] input {{
    background: {T["surface_lowest"]} !important; border: 1.5px solid {T["outline"]} !important;
    border-radius: 12px !important; color: {T["text"]} !important; font-size: 13.5px !important;
}}
[data-testid="stNumberInput"] button {{
    background: {T["surface_low"]} !important; border: none !important;
    color: {T["text_variant"]} !important; border-radius: 8px !important;
}}
[data-testid="stDateInput"] > div > div {{
    background: {T["surface_lowest"]} !important; border: 1.5px solid {T["outline"]} !important; border-radius: 12px !important;
}}
[data-testid="stDateInput"] input {{ color: {T["text"]} !important; background: transparent !important; }}

/* DATAFRAME */
[data-testid="stDataFrame"] {{
    border-radius: 14px !important; overflow: hidden !important; border: none !important;
    box-shadow: 0 2px 20px {T["metric_shadow"]}, 0 0 0 1px {T["outline"]} !important;
}}
[data-testid="stDataFrame"] th {{
    background: {T["surface_low"]} !important; color: {T["text3"]} !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 11px !important;
    font-weight: 700 !important; text-transform: uppercase !important;
    letter-spacing: 0.07em !important; border: none !important;
}}
[data-testid="stDataFrame"] td {{
    background: {T["surface_lowest"]} !important; color: {T["text"]} !important;
    border: none !important; font-size: 13px !important;
}}

/* FORM & EXPANDER */
[data-testid="stForm"] {{
    background: {T["surface_low"]} !important; border: none !important;
    border-radius: 20px !important; padding: 28px !important;
    box-shadow: 0 2px 20px {T["metric_shadow"]}, 0 0 0 1px {T["outline"]} !important;
}}
[data-testid="stExpander"] {{
    background: {T["surface_lowest"]} !important; border: none !important;
    border-radius: 14px !important; margin-bottom: 8px !important;
    box-shadow: 0 1px 12px {T["metric_shadow"]}, 0 0 0 1px {T["outline"]} !important;
}}
[data-testid="stExpander"] summary {{
    color: {T["text"]} !important; font-weight: 600 !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}}

/* ALERTS & MISC */
[data-testid="stAlert"] {{
    border-radius: 14px !important; font-size: 13px !important;
    background: {T["surface_lowest"]} !important; border: none !important;
    box-shadow: 0 0 0 1px {T["outline"]} !important;
}}
[data-testid="stCaptionContainer"] p {{ color: {T["text3"]} !important; font-size: 12px !important; }}
small {{ color: {T["text3"]} !important; }}
[data-testid="stRadio"] label {{
    font-size: 13.5px !important; font-weight: 500 !important; color: {T["text_variant"]} !important;
}}
hr {{ border: none !important; border-top: 1px solid {T["outline"]} !important; }}
[data-testid="stCheckbox"] label {{
    font-size: 13.5px !important; color: {T["text_variant"]} !important; font-weight: 500 !important;
}}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    toggle_icon  = "☀️" if dm else "🌙"
    status_dot   = "🟢" if data_source == "google_sheets" else "🟡"
    status_txt   = "Live · Google Sheets" if data_source == "google_sheets" else "Lokal · CSV"
    total_karyawan = len(df)
    total_bu       = df["Business Unit"].nunique()
    total_div      = df["Division"].nunique()
    total_mgr      = df[df["Employee ID"].isin(df["Manager ID"].unique())]["Employee ID"].nunique()

    st.markdown(f"""
    <div style="padding:28px 20px 20px 20px; border-bottom:1px solid {T['outline']}; margin-bottom:8px;">
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:14px;">
            <div style="width:44px;height:44px;border-radius:14px;
                background:linear-gradient(135deg,{T['primary']},{T['primary_cont']});
                display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0;
                box-shadow:0 4px 20px rgba(66,52,182,0.35);">🏢</div>
            <div>
                <div style="font-size:16px;font-weight:800;color:{T['sidebar_active']};
                    font-family:'Manrope',sans-serif;line-height:1.2;letter-spacing:-0.02em;">HRIS</div>
                <div style="font-size:11px;color:{T['sidebar_text2']};font-weight:500;
                    letter-spacing:0.04em;text-transform:uppercase;margin-top:2px;">People Analytics</div>
            </div>
        </div>
        <div style="background:rgba(255,255,255,0.15);border-radius:8px;padding:7px 12px;
            display:flex;align-items:center;gap:7px;">
            <span style="font-size:9px;">{status_dot}</span>
            <span style="font-size:11px;color:{T['sidebar_text2']};font-weight:500;">{status_txt}</span>
        </div>
    </div>
    <div style="padding:14px 20px 10px 20px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <div style="background:rgba(255,255,255,0.12);border-radius:12px;padding:10px 12px;text-align:center;">
                <div style="font-size:20px;font-weight:800;color:{T['sidebar_active']};
                    font-family:'Manrope',sans-serif;letter-spacing:-0.03em;">{total_karyawan:,}</div>
                <div style="font-size:10px;color:{T['sidebar_text2']};font-weight:600;
                    text-transform:uppercase;letter-spacing:0.05em;margin-top:2px;">Karyawan</div>
            </div>
            <div style="background:rgba(255,255,255,0.12);border-radius:12px;padding:10px 12px;text-align:center;">
                <div style="font-size:20px;font-weight:800;color:{T['sidebar_active']};
                    font-family:'Manrope',sans-serif;letter-spacing:-0.03em;">{total_mgr}</div>
                <div style="font-size:10px;color:{T['sidebar_text2']};font-weight:600;
                    text-transform:uppercase;letter-spacing:0.05em;margin-top:2px;">Manager</div>
            </div>
            <div style="background:rgba(255,255,255,0.12);border-radius:12px;padding:10px 12px;text-align:center;">
                <div style="font-size:20px;font-weight:800;color:{T['sidebar_active']};
                    font-family:'Manrope',sans-serif;letter-spacing:-0.03em;">{total_bu}</div>
                <div style="font-size:10px;color:{T['sidebar_text2']};font-weight:600;
                    text-transform:uppercase;letter-spacing:0.05em;margin-top:2px;">Business Unit</div>
            </div>
            <div style="background:rgba(255,255,255,0.12);border-radius:12px;padding:10px 12px;text-align:center;">
                <div style="font-size:20px;font-weight:800;color:{T['sidebar_active']};
                    font-family:'Manrope',sans-serif;letter-spacing:-0.03em;">{total_div}</div>
                <div style="font-size:10px;color:{T['sidebar_text2']};font-weight:600;
                    text-transform:uppercase;letter-spacing:0.05em;margin-top:2px;">Divisi</div>
            </div>
        </div>
    </div>
    <div style="padding:8px 20px;margin-bottom:4px;"><div style="height:1px;background:{T['outline']};"></div></div>
    <div style="padding:4px 20px 8px 20px;">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;
            letter-spacing:0.09em;color:{T['sidebar_text2']};">Menu</div>
    </div>
    """, unsafe_allow_html=True)

    if "active_tab" not in st.session_state:
        st.session_state.active_tab = 0

    nav_items = [
        ("🌳", "Org Chart",          0),
        ("👥", "Data Karyawan",      1),
        ("⚠️", "Manager ID Hilang",  2),
        ("👔", "Daftar Manager",     3),
        ("📝", "Change Request",     4),
    ]
    active_idx = st.session_state.active_tab
    for icon_nav, label_nav, tab_idx in nav_items:
        is_active = (active_idx == tab_idx)
        if st.button(f"{icon_nav}  {label_nav}", key=f"nav_{tab_idx}",
                     use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.active_tab = tab_idx
            st.rerun()

    st.markdown(f"""
    <div style="padding:8px 20px;margin:4px 0;"><div style="height:1px;background:{T['outline']};"></div></div>
    """, unsafe_allow_html=True)

    col_sb1, col_sb2 = st.columns(2)
    with col_sb1:
        if st.button("🔄 Refresh", use_container_width=True, key="refresh_btn"):
            st.cache_data.clear(); st.rerun()
    with col_sb2:
        if st.button(f"{toggle_icon} Mode", use_container_width=True, key="toggle_btn"):
            st.session_state.dark_mode = not st.session_state.dark_mode; st.rerun()

    st.markdown(f"""
    <div style="padding:12px 20px;font-size:10px;color:{T['sidebar_text2']};text-align:center;letter-spacing:0.03em;">
        Auto-refresh setiap 5 menit
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# MAIN HEADER
# ══════════════════════════════════════════════════════════════════
st.markdown(f"""
<div style="padding:0 0 28px 0;margin-bottom:32px;border-bottom:1px solid {T['outline']};
    display:flex;align-items:flex-end;justify-content:space-between;">
    <div>
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;
            letter-spacing:0.09em;color:{T['text3']};margin-bottom:6px;">HR · People Analytics</div>
        <div style="font-size:32px;font-weight:800;color:{T['text']};
            font-family:'Manrope',sans-serif;line-height:1.1;letter-spacing:-0.03em;">Org Chart Dashboard</div>
        <div style="font-size:14px;color:{T['text_variant']};margin-top:6px;font-weight:400;line-height:1.6;">
            Visualisasi & analitik struktur organisasi real-time
        </div>
    </div>
    <div style="background:linear-gradient(135deg,{T['primary']},{T['primary_cont']});
        border-radius:14px;padding:12px 20px;text-align:right;
        box-shadow:0 4px 20px rgba(66,52,182,0.3);min-width:140px;">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;
            letter-spacing:0.07em;color:rgba(255,255,255,0.7);margin-bottom:4px;">Total Karyawan</div>
        <div style="font-size:28px;font-weight:800;color:white;
            font-family:'Manrope',sans-serif;letter-spacing:-0.03em;line-height:1.1;">{len(df):,}</div>
    </div>
</div>
""", unsafe_allow_html=True)


_active = st.session_state.get("active_tab", 0)


# ══════════════════════════════════════════════════════════════════
# TAB 1 — ORG CHART
# ══════════════════════════════════════════════════════════════════
if _active == 0:
    st.markdown(f"""
    <div style="font-size:10px;font-weight:700;text-transform:uppercase;
        letter-spacing:0.09em;color:{T['text3']};margin-bottom:10px;">MODE TAMPILAN</div>
    """, unsafe_allow_html=True)
    view_mode = st.radio("", ["Per Divisi", "Seluruh Perusahaan"], horizontal=True, label_visibility="collapsed")

    if view_mode == "Per Divisi":
        st.markdown(f"""
        <div style="font-size:12px;font-weight:600;color:{T['text3']};text-transform:uppercase;
            letter-spacing:0.06em;margin:16px 0 10px 0;">Filter</div>
        """, unsafe_allow_html=True)
        col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 2])
        with col_a:
            bu_list    = sorted(df["Business Unit"].dropna().unique().tolist())
            selected_bu = st.selectbox("🏢 Business Unit", bu_list, key="sel_bu")
        with col_b:
            div_list    = sorted(df[df["Business Unit"] == selected_bu]["Division"].dropna().unique().tolist())
            selected_div = st.selectbox("📁 Divisi", div_list, key="sel_div")
        with col_c:
            sbu_opts_raw = [s for s in df[
                (df["Business Unit"] == selected_bu) & (df["Division"] == selected_div)
            ]["SBU/Tribe"].dropna().unique().tolist() if s.strip() != ""]
            selected_sbu = st.selectbox("🏷️ SBU/Tribe", ["Semua SBU"] + sorted(sbu_opts_raw), key="sel_sbu")

        filtered = df[(df["Business Unit"] == selected_bu) & (df["Division"] == selected_div)].copy()
        if selected_sbu != "Semua SBU":
            filtered = filtered[filtered["SBU/Tribe"] == selected_sbu].copy()

        all_leaders = filtered[filtered["Employee ID"].isin(df["Manager ID"].unique())]["Employee Name"].tolist()
        with col_d:
            selected_leader = st.selectbox("👤 Filter by Leader",
                                           ["Semua (divisi penuh)"] + sorted(all_leaders), key="sel_leader")

        if selected_leader != "Semua (divisi penuh)":
            leader_id = filtered[filtered["Employee Name"] == selected_leader]["Employee ID"].values
            if len(leader_id) > 0:
                lid      = leader_id[0]
                sub_ids  = set()
                to_visit = [lid]
                while to_visit:
                    curr = to_visit.pop()
                    sub_ids.add(curr)
                    to_visit.extend(df[df["Manager ID"] == curr]["Employee ID"].tolist())
                filtered = df[df["Employee ID"].isin(sub_ids)].copy()

        col_lv, col_info = st.columns([2, 4])
        with col_lv:
            level_opt = st.selectbox("📶 Expand Level", ["All Level", "Top Level", "Level 1"],
                                     help="Atur berapa level yang ditampilkan secara default")
        with col_info:
            st.caption(f"📊 Menampilkan **{len(filtered)}** karyawan di divisi ini")

        selected_level  = {"All Level": "all", "Top Level": "top", "Level 1": "level1"}[level_opt]
        all_ids_needed  = get_all_managers(filtered["Employee ID"].tolist(), df)
        full_data       = df[df["Employee ID"].isin(all_ids_needed)].copy()
        all_ids_set     = set(full_data["Employee ID"].tolist())

        root_ids = full_data[
            ~full_data["Manager ID"].isin(all_ids_set) | full_data["Manager ID"].isin({"", "nan"})
        ]["Employee ID"].astype(str).tolist()

        tree_data  = build_tree_json(full_data, selected_div, root_ids, mode="division")
        chart_html = render_org_chart(json.dumps(tree_data), chart_height=680, initial_level=selected_level, theme=T)
        st.components.v1.html(chart_html, height=680, scrolling=False)

        st.markdown("**⬇️ Download Data**")
        col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)
        with col_dl1:
            st.download_button("📄 CSV", filtered.to_csv(index=False).encode("utf-8"),
                               f"{selected_div}.csv", "text/csv", use_container_width=True)
        with col_dl2:
            st.download_button("📊 Excel", to_excel(filtered), f"{selected_div}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_dl3:
            try:
                pdf_data = generate_pdf(tree_data, f"Org Chart — {selected_div} ({selected_bu})")
                st.download_button("📑 PDF (Full)", pdf_data, f"{selected_div}_full.pdf", "application/pdf", use_container_width=True)
            except Exception:
                st.button("📑 PDF (N/A)", disabled=True, use_container_width=True)
        with col_dl4:
            try:
                pdf_sum = generate_pdf_summary(tree_data, f"Org Chart Summary — {selected_div} ({selected_bu})")
                st.download_button("📑 PDF (Summary)", pdf_sum, f"{selected_div}_summary.pdf", "application/pdf", use_container_width=True)
            except Exception:
                st.button("📑 Summary (N/A)", disabled=True, use_container_width=True)

    else:
        st.info("⚠️ Mode seluruh perusahaan menampilkan semua karyawan. Gunakan zoom out dan collapse untuk navigasi.")
        col_lv2, col_inf2 = st.columns([2, 4])
        with col_lv2:
            level_opt2 = st.selectbox("📶 Expand Level", ["All Level", "Top Level", "Level 1"], key="lv2")
        with col_inf2:
            st.caption(f"📊 Menampilkan **{len(df)}** karyawan")

        selected_level2 = {"All Level": "all", "Top Level": "top", "Level 1": "level1"}[level_opt2]
        root_ids2   = df[(df["Manager ID"] == "") | (df["Manager ID"].isna())]["Employee ID"].tolist()
        tree_data2  = build_tree_json(df, "", root_ids2, mode="company")
        chart_html2 = render_org_chart(json.dumps(tree_data2), chart_height=750, initial_level=selected_level2, theme=T)
        st.components.v1.html(chart_html2, height=750, scrolling=False)

        st.markdown("**⬇️ Download Data**")
        col_dl4, col_dl5, col_dl6, col_dl7 = st.columns(4)
        with col_dl4:
            st.download_button("📄 CSV", df.to_csv(index=False).encode("utf-8"),
                               "all_employees.csv", "text/csv", use_container_width=True)
        with col_dl5:
            st.download_button("📊 Excel", to_excel(df), "all_employees.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_dl6:
            try:
                pdf2 = generate_pdf(tree_data2, "Org Chart — Seluruh Perusahaan")
                st.download_button("📑 PDF (Full)", pdf2, "orgchart_perusahaan_full.pdf", "application/pdf", use_container_width=True)
            except Exception:
                st.button("📑 PDF (N/A)", disabled=True, use_container_width=True)
        with col_dl7:
            try:
                pdf_sum2 = generate_pdf_summary(tree_data2, "Org Chart Summary — Seluruh Perusahaan")
                st.download_button("📑 PDF (Summary)", pdf_sum2, "orgchart_perusahaan_summary.pdf", "application/pdf", use_container_width=True)
            except Exception:
                st.button("📑 Summary (N/A)", disabled=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════
# TAB 2 — DATA KARYAWAN
# ══════════════════════════════════════════════════════════════════
elif _active == 1:
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:20px;font-weight:700;color:{T['text']};">Data Karyawan</div>
        <div style="font-size:13px;color:{T['text_variant']};margin-top:4px;">Seluruh data karyawan dengan filter dan pencarian</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1: search = st.text_input("🔍 Cari nama karyawan")
    with c2: bu_f   = st.selectbox("Filter BU", ["Semua"] + sorted(df["Business Unit"].unique().tolist()), key="t2bu")
    with c3:
        div_opts = ["Semua"] + sorted(
            df[df["Business Unit"] == bu_f]["Division"].unique().tolist() if bu_f != "Semua"
            else df["Division"].unique().tolist()
        )
        div_f = st.selectbox("Filter Divisi", div_opts, key="t2div")
    with c4:
        sbu_src = df.copy()
        if bu_f != "Semua": sbu_src = sbu_src[sbu_src["Business Unit"] == bu_f]
        if div_f != "Semua": sbu_src = sbu_src[sbu_src["Division"] == div_f]
        sbu_opts_t2 = ["Semua"] + sorted([s for s in sbu_src["SBU/Tribe"].dropna().unique().tolist() if s.strip() != ""])
        sbu_f = st.selectbox("Filter SBU/Tribe", sbu_opts_t2, key="t2sbu")

    data_view = df.copy()
    if search:       data_view = data_view[data_view["Employee Name"].str.contains(search, case=False, na=False)]
    if bu_f  != "Semua": data_view = data_view[data_view["Business Unit"] == bu_f]
    if div_f != "Semua": data_view = data_view[data_view["Division"] == div_f]
    if sbu_f != "Semua": data_view = data_view[data_view["SBU/Tribe"] == sbu_f]

    st.caption(f"Menampilkan **{len(data_view)}** karyawan")
    st.dataframe(data_view, use_container_width=True, height=480)

    col_dl7, col_dl8, _ = st.columns([1, 1, 3])
    with col_dl7:
        st.download_button("📄 CSV", data_view.to_csv(index=False).encode("utf-8"),
                           "filtered.csv", "text/csv", use_container_width=True)
    with col_dl8:
        st.download_button("📊 Excel", to_excel(data_view), "filtered.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


# ══════════════════════════════════════════════════════════════════
# TAB 3 — MANAGER ID HILANG
# ══════════════════════════════════════════════════════════════════
elif _active == 2:
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:20px;font-weight:700;color:{T['text']};">Manager ID Hilang</div>
        <div style="font-size:13px;color:{T['text_variant']};margin-top:4px;">
            Karyawan yang Manager ID-nya kosong atau tidak terdaftar — perlu diperbaiki di backend
        </div>
    </div>
    """, unsafe_allow_html=True)

    missing_mgr_df = df[
        (df["Manager ID"] == "") | (df["Manager ID"].isna()) | (df["Manager ID"] == "nan")
    ].copy()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("⚠️ Total Data Bermasalah", len(missing_mgr_df))
    m2.metric("🏢 Tersebar di BU", missing_mgr_df["Business Unit"].nunique())
    m3.metric("📁 Tersebar di Divisi", missing_mgr_df["Division"].nunique())
    m4.metric("📊 % dari Total", f"{len(missing_mgr_df)/len(df)*100:.1f}%")
    st.divider()

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        bu_nr = st.selectbox("Filter Business Unit",
                             ["Semua"] + sorted(missing_mgr_df["Business Unit"].dropna().unique().tolist()), key="bu_nr")
    with col_f2:
        div_opts_nr = (sorted(missing_mgr_df[missing_mgr_df["Business Unit"] == bu_nr]["Division"].dropna().unique().tolist())
                       if bu_nr != "Semua" else sorted(missing_mgr_df["Division"].dropna().unique().tolist()))
        div_nr = st.selectbox("Filter Divisi", ["Semua"] + div_opts_nr, key="div_nr")

    view_nr = missing_mgr_df.copy()
    if bu_nr != "Semua": view_nr = view_nr[view_nr["Business Unit"] == bu_nr]
    if div_nr != "Semua": view_nr = view_nr[view_nr["Division"] == div_nr]

    st.caption(f"Menampilkan **{len(view_nr)}** karyawan dengan Manager ID kosong")
    display_cols = ["Employee ID", "Employee Name", "Job Position", "Division", "Business Unit", "SBU/Tribe", "Manager ID"]
    st.dataframe(view_nr[display_cols], use_container_width=True, height=450)
    st.divider()
    st.markdown(f"""<div style="font-size:15px;font-weight:700;color:{T['text']};margin-bottom:12px;">Breakdown per Divisi</div>""", unsafe_allow_html=True)
    breakdown = view_nr.groupby(["Business Unit", "Division"]).size().reset_index(name="Jumlah").sort_values("Jumlah", ascending=False)
    st.dataframe(breakdown, use_container_width=True, height=250)
    st.divider()
    col_d1, col_d2, _ = st.columns([1, 1, 3])
    with col_d1:
        st.download_button("📄 CSV", view_nr.to_csv(index=False).encode("utf-8"),
                           "missing_manager_id.csv", "text/csv", use_container_width=True)
    with col_d2:
        st.download_button("📊 Excel", to_excel(view_nr), "missing_manager_id.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


# ══════════════════════════════════════════════════════════════════
# TAB 4 — DAFTAR MANAGER
# ══════════════════════════════════════════════════════════════════
elif _active == 3:
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:20px;font-weight:700;color:{T['text']};">Daftar Manager</div>
        <div style="font-size:13px;color:{T['text_variant']};margin-top:4px;">Seluruh karyawan yang memiliki bawahan langsung beserta analisis Span of Control</div>
    </div>
    """, unsafe_allow_html=True)

    def get_level_from_root(root_id: str, all_df: pd.DataFrame, max_depth: int = 2) -> dict:
        levels: dict = {}
        current = [root_id]
        for depth in range(max_depth + 1):
            next_lvl = []
            for mgr_id in current:
                children = all_df[all_df["Manager ID"] == mgr_id]["Employee ID"].tolist()
                for child in children:
                    if child not in levels:
                        levels[child] = depth
                        next_lvl.append(child)
            current = next_lvl
            if not current:
                break
        return levels

    hierarchy_levels = get_level_from_root(CHIEF_ROOT, df, max_depth=2)

    level0_ids = set(df[df["Career Stage"].astype(str).str.strip().str.lower() == "level 0"]["Employee ID"].tolist())

    mgr_ids = df[df["Manager ID"] != ""]["Manager ID"].unique().tolist()
    mgr_df  = df[df["Employee ID"].isin(mgr_ids)].copy()
    
    sub_count = df[df["Manager ID"] != ""].groupby("Manager ID").size().reset_index(name="Bawahan Langsung")
    sub_count.rename(columns={"Manager ID": "Employee ID"}, inplace=True)
    mgr_df = mgr_df.merge(sub_count, on="Employee ID", how="left")
    mgr_df["Bawahan Langsung"] = mgr_df["Bawahan Langsung"].fillna(0).astype(int)
    
    # [FIX-2] BFS global satu kali — hitung total span semua manager sekaligus
    # Sebelumnya: .apply(get_total_span) = BFS per-manager = O(n²) untuk 1,600 karyawan
    # Sekarang: satu BFS dari tiap root, hasilnya di-map → O(n) total
    children_map = df[df["Manager ID"] != ""].groupby("Manager ID")["Employee ID"].apply(list).to_dict()

    def _compute_all_spans(children_map: dict) -> dict:
        """Hitung total descendant count untuk setiap node dalam satu traversal."""
        span: dict = {}
        # Post-order BFS: hitung dari leaf ke atas
        # Gunakan iterative DFS dengan visited set
        all_nodes = set(children_map.keys()) | {c for ch in children_map.values() for c in ch}
        for node in all_nodes:
            if node in span:
                continue
            # DFS iteratif
            stack = [(node, False)]
            while stack:
                cur, processed = stack.pop()
                if processed:
                    span[cur] = sum(1 + span.get(ch, 0) for ch in children_map.get(cur, []))
                else:
                    stack.append((cur, True))
                    for ch in children_map.get(cur, []):
                        if ch not in span:
                            stack.append((ch, False))
        return span

    _all_spans = _compute_all_spans(children_map)
    mgr_df["Total Span (Semua Bawahan)"] = mgr_df["Employee ID"].map(_all_spans).fillna(0).astype(int)

    mgr_df["Level Hierarki"] = mgr_df["Employee ID"].apply(
        lambda eid: {0: "Chief", 1: "C-1", 2: "C-2"}.get(hierarchy_levels.get(eid), "-")
    )
    direct_subs_map = df[df["Manager ID"] != ""].groupby("Manager ID")["Employee ID"].apply(set).to_dict()
    mgr_df["Ada Bawahan Level 0"] = mgr_df["Employee ID"].apply(
        lambda eid: bool(direct_subs_map.get(eid, set()) & level0_ids)
    )
    
    mgr_df = mgr_df.sort_values("Total Span (Semua Bawahan)", ascending=False)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👔 Total Manager", len(mgr_df))
    m2.metric("📊 Rata-rata Bawahan Langsung", f"{mgr_df['Bawahan Langsung'].mean():.1f}")
    m3.metric("🏆 Max Bawahan Langsung", int(mgr_df["Bawahan Langsung"].max()))
    m4.metric("📈 Max Total Span", int(mgr_df["Total Span (Semua Bawahan)"].max()))
    st.divider()

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1: search_mgr = st.text_input("🔍 Cari nama manager", key="search_mgr")
    with col_m2:
        bu_mgr = st.selectbox("Filter BU",
                              ["Semua"] + sorted(mgr_df["Business Unit"].dropna().unique().tolist()), key="bu_mgr")
    with col_m3:
        div_mgr_opts = (["Semua"] + sorted(mgr_df[mgr_df["Business Unit"] == bu_mgr]["Division"].dropna().unique().tolist())
                        if bu_mgr != "Semua" else ["Semua"] + sorted(mgr_df["Division"].dropna().unique().tolist()))
        div_mgr = st.selectbox("Filter Divisi", div_mgr_opts, key="div_mgr")
    with col_m4:
        level_filter = st.selectbox("🎯 Filter Level Hierarki", ["Semua", "Chief", "C-1", "C-2"], key="level_mgr",
                                    help="Chief = bawahan langsung SLKR001 | C-1 = 1 tingkat di bawah Chief | C-2 = 2 tingkat di bawah Chief")

    hide_level0 = st.checkbox("🚫 Sembunyikan manager yang memiliki bawahan Career Stage Level 0",
                               value=True, help="Aktif = hanya tampilkan leader tanpa bawahan Level 0")

    view_mgr = mgr_df.copy()
    if search_mgr:              view_mgr = view_mgr[view_mgr["Employee Name"].str.contains(search_mgr, case=False, na=False)]
    if bu_mgr  != "Semua":     view_mgr = view_mgr[view_mgr["Business Unit"] == bu_mgr]
    if div_mgr != "Semua":     view_mgr = view_mgr[view_mgr["Division"] == div_mgr]
    if level_filter != "Semua": view_mgr = view_mgr[view_mgr["Level Hierarki"] == level_filter]
    if hide_level0:             view_mgr = view_mgr[~view_mgr["Ada Bawahan Level 0"]]

    active_filters = []
    if level_filter != "Semua": active_filters.append(f"Level: **{level_filter}**")
    if hide_level0:             active_filters.append("Tanpa bawahan Level 0")
    if active_filters:
        st.markdown(f"""
        <div style="background:{T['accent_bg']};border:1px solid {T['border2']};
            border-radius:8px;padding:8px 14px;margin-bottom:12px;
            font-size:12px;color:{T['accent']};">
            🔎 Filter aktif: {' · '.join(active_filters)}
        </div>
        """, unsafe_allow_html=True)

    st.caption(f"Menampilkan **{len(view_mgr)}** manager")
    
    display_cols_mgr = ["Employee ID", "Employee Name", "Job Position", "Division",
                        "Business Unit", "SBU/Tribe", "Level Hierarki", "Bawahan Langsung", "Total Span (Semua Bawahan)"]
    available_display = [c for c in display_cols_mgr if c in view_mgr.columns]
    
    st.dataframe(view_mgr[available_display].reset_index(drop=True), use_container_width=True, height=480)
    st.divider()
    st.markdown("**⬇️ Download Data**")
    col_dm1, col_dm2, _ = st.columns([1, 1, 3])
    with col_dm1:
        st.download_button("📄 CSV", view_mgr.to_csv(index=False).encode("utf-8"),
                           "daftar_manager.csv", "text/csv", use_container_width=True)
    with col_dm2:
        st.download_button("📊 Excel", to_excel(view_mgr), "daftar_manager.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


# ══════════════════════════════════════════════════════════════════
# TAB 5 — CHANGE REQUEST
# ══════════════════════════════════════════════════════════════════
elif _active == 4:
    st.markdown(f"""
    <div style="margin-bottom:24px;">
        <div style="font-size:20px;font-weight:700;color:{T['text']};">Structure Change Request</div>
        <div style="font-size:13px;color:{T['text_variant']};margin-top:4px;">
            Kelola permintaan perubahan struktur organisasi — Reporting Line & Divisi
        </div>
    </div>
    """, unsafe_allow_html=True)

    cr_tab1, cr_tab2, cr_tab3 = st.tabs(["➕  Buat Request", "📥  Inbox & Review", "📜  History"])

    def make_template(change_type_tmpl):
        cols = (["Employee ID", "Employee Name", "Previous Manager", "New Manager"]
                if change_type_tmpl == "Reporting Line"
                else ["Employee ID", "Employee Name", "Nama Divisi Lama", "Nama Divisi Baru"])
        return pd.DataFrame(columns=cols)

    def process_and_save(rows_data, req_name, req_email, change_type, alasan, eff_date):
        valid_rows = [(str(eid).strip(), str(en).strip(), str(ov).strip(), str(nv).strip())
                      for eid, en, ov, nv in rows_data if str(eid).strip() or str(en).strip()]
        if not valid_rows:
            return [], [], 0
        warnings_list = []
        for emp_id, emp_name, old_val, new_val in valid_rows:
            if emp_id and emp_id not in df["Employee ID"].values:
                warnings_list.append(f"Employee ID **{emp_id}** tidak ditemukan di data.")
            if change_type == "Reporting Line" and new_val:
                if len(df[df["Employee Name"].str.lower() == new_val.lower()]) == 0:
                    warnings_list.append(f"Manager baru **{new_val}** tidak ditemukan di data.")
        success_count = 0
        for emp_id, emp_name, old_val, new_val in valid_rows:
            row = {
                "request_id":      generate_request_id(),
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
        return valid_rows, warnings_list, success_count

    with cr_tab1:
        st.markdown(f"""<div style="font-size:15px;font-weight:600;color:{T['text']};margin-bottom:16px;">
            Form Permintaan Perubahan Struktur</div>""", unsafe_allow_html=True)

        col_r1, col_r2 = st.columns(2)
        with col_r1: req_name_shared  = st.text_input("Nama Requester *", placeholder="Nama lengkap pengirim request", key="req_name_shared")
        with col_r2: req_email_shared = st.text_input("Email Requester *", placeholder="email@mekari.com", key="req_email_shared")
        st.markdown(f"<div style='height:1px;background:{T['border']};margin:16px 0;'></div>", unsafe_allow_html=True)

        col_ct, col_ed = st.columns(2)
        with col_ct: change_type_shared = st.selectbox("Jenis Perubahan *", ["Reporting Line", "Nama Divisi"], key="ct_shared")
        with col_ed: eff_date_shared    = st.date_input("Effective Date", value=datetime.today(), key="ed_shared")
        st.markdown(f"<div style='height:1px;background:{T['border']};margin:16px 0;'></div>", unsafe_allow_html=True)
        alasan_shared = st.text_area("Alasan / Keterangan *", placeholder="Jelaskan alasan perubahan struktur ini...", height=90, key="alasan_shared")
        st.markdown(f"<div style='height:1px;background:{T['border']};margin:16px 0;'></div>", unsafe_allow_html=True)

        input_mode = st.radio("", ["✏️  Input Manual (1–5 karyawan)", "📤  Upload Spreadsheet (>5 karyawan)"],
                              horizontal=True, label_visibility="collapsed", key="input_mode")

        if input_mode == "✏️  Input Manual (1–5 karyawan)":
            with st.form("cr_form_manual", clear_on_submit=True):
                num_rows = st.number_input("Jumlah karyawan", min_value=1, max_value=5, value=1, step=1)
                h1c, h2c, h3c, h4c = st.columns([1.5, 2, 2.5, 2.5])
                h1c.markdown(f"<div style='font-size:11px;font-weight:700;color:{T['text3']};'>Employee ID</div>", unsafe_allow_html=True)
                h2c.markdown(f"<div style='font-size:11px;font-weight:700;color:{T['text3']};'>Nama Karyawan</div>", unsafe_allow_html=True)
                h3c.markdown(f"<div style='font-size:11px;font-weight:700;color:{T['text3']};'>{'Previous Manager' if change_type_shared=='Reporting Line' else 'Divisi Lama'}</div>", unsafe_allow_html=True)
                h4c.markdown(f"<div style='font-size:11px;font-weight:700;color:{T['text3']};'>{'New Manager' if change_type_shared=='Reporting Line' else 'Divisi Baru'}</div>", unsafe_allow_html=True)
                rows_data_manual = []
                for i in range(int(num_rows)):
                    c1, c2, c3, c4 = st.columns([1.5, 2, 2.5, 2.5])
                    with c1: emp_id = st.text_input("", key=f"eid_{i}", placeholder="EMP001", label_visibility="collapsed")
                    with c2:
                        match = df[df["Employee ID"] == emp_id]["Employee Name"].values
                        emp_name = st.text_input("", key=f"ename_{i}", value=match[0] if len(match) > 0 else "",
                                                 placeholder="Nama lengkap", label_visibility="collapsed")
                    with c3: old_val = st.text_input("", key=f"old_{i}", label_visibility="collapsed",
                                                     placeholder="Manager lama" if change_type_shared=="Reporting Line" else "Divisi saat ini")
                    with c4: new_val = st.text_input("", key=f"new_{i}", label_visibility="collapsed",
                                                     placeholder="Manager baru" if change_type_shared=="Reporting Line" else "Divisi tujuan")
                    rows_data_manual.append((emp_id, emp_name, old_val, new_val))
                submitted_manual = st.form_submit_button("📨  Kirim Request", use_container_width=True)

            if submitted_manual:
                errors = []
                if not req_name_shared.strip(): errors.append("Nama Requester harus diisi")
                if not req_email_shared.strip() or "@" not in req_email_shared: errors.append("Email tidak valid")
                if not alasan_shared.strip(): errors.append("Alasan perubahan harus diisi")
                if errors:
                    for e in errors: st.error(f"❌ {e}")
                else:
                    valid_rows, warnings_list, success_count = process_and_save(
                        rows_data_manual, req_name_shared, req_email_shared,
                        change_type_shared, alasan_shared, eff_date_shared)
                    for w in warnings_list: st.warning(f"⚠️ {w}")
                    if success_count > 0:
                        st.success(f"✅ **{success_count} request** berhasil dikirim!")
                        st.balloons()

        else:
            template_df = make_template(change_type_shared)
            col_tmpl, _ = st.columns([2, 4])
            with col_tmpl:
                st.download_button("⬇️  Download Template", data=to_excel(template_df),
                    file_name=f"template_cr_{change_type_shared.lower().replace(' ','_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

            uploaded_file = st.file_uploader("Upload file Excel (.xlsx) atau CSV (.csv)", type=["xlsx", "csv"], key="cr_upload")
            if uploaded_file:
                try:
                    upload_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
                    upload_df.columns = upload_df.columns.str.strip()
                    upload_df = upload_df.dropna(how="all")
                    if change_type_shared == "Reporting Line":
                        required_cols = ["Employee ID", "Employee Name", "Previous Manager", "New Manager"]
                        old_col, new_col = "Previous Manager", "New Manager"
                    else:
                        required_cols = ["Employee ID", "Employee Name", "Nama Divisi Lama", "Nama Divisi Baru"]
                        old_col, new_col = "Nama Divisi Lama", "Nama Divisi Baru"
                    missing_cols = [c for c in required_cols if c not in upload_df.columns]
                    if missing_cols:
                        st.error(f"❌ Kolom tidak sesuai template. Kurang: {', '.join(missing_cols)}")
                    else:
                        st.caption(f"Preview Data ({len(upload_df)} karyawan)")
                        st.dataframe(upload_df[required_cols], use_container_width=True, height=200)
                        errors_upload = []
                        if not req_name_shared.strip(): errors_upload.append("Nama Requester harus diisi")
                        if not req_email_shared.strip() or "@" not in req_email_shared: errors_upload.append("Email tidak valid")
                        if not alasan_shared.strip(): errors_upload.append("Alasan perubahan harus diisi")
                        if errors_upload:
                            for e in errors_upload: st.error(f"❌ {e}")
                        else:
                            if st.button("📨  Kirim Semua Request dari File", use_container_width=True, key="submit_upload"):
                                # [FIX-3a] Ganti iterrows() dengan to_dict('records') — lebih cepat untuk file besar
                                rows_from_file = [
                                    (
                                        str(r.get("Employee ID","")).strip(),
                                        str(r.get("Employee Name","")).strip(),
                                        str(r.get(old_col,"")).strip(),
                                        str(r.get(new_col,"")).strip()
                                    )
                                    for r in upload_df[required_cols].to_dict("records")
                                ]
                                _, _, success_count = process_and_save(rows_from_file, req_name_shared, req_email_shared,
                                                                       change_type_shared, alasan_shared, eff_date_shared)
                                if success_count > 0:
                                    st.success(f"✅ **{success_count} request** dari file berhasil dikirim!")
                                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Gagal membaca file: {str(e)}")

    with cr_tab2:
        st.markdown(f"""
        <style>
        [data-testid="stButton"] button.approve-btn {{
            background: #059669 !important; color: white !important;
            border: none !important; border-radius: 10px !important; font-weight: 600 !important;
        }}
        [data-testid="stButton"] button.reject-btn {{
            background: #dc2626 !important; color: white !important;
            border: none !important; border-radius: 10px !important; font-weight: 600 !important;
        }}
        </style>
        """, unsafe_allow_html=True)

        col_reload, _ = st.columns([1, 5])
        with col_reload:
            if st.button("🔄 Refresh", key="refresh_cr"):
                st.cache_data.clear(); st.rerun()

        cr_df = load_change_requests()
        if cr_df.empty:
            st.info("📭 Belum ada request yang masuk.")
        else:
            if "status" not in cr_df.columns:
                cr_df["status"] = "Pending"
            pending_df = cr_df[cr_df["status"] == "Pending"].copy()

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📥 Total Masuk",  len(cr_df))
            m2.metric("🟡 Pending",      len(pending_df))
            m3.metric("✅ Approved",     len(cr_df[cr_df["status"] == "Approved"]))
            m4.metric("❌ Rejected",     len(cr_df[cr_df["status"] == "Rejected"]))
            st.markdown(f"<div style='height:1px;background:{T['border']};margin:16px 0;'></div>", unsafe_allow_html=True)

            if len(pending_df) == 0:
                st.success("✅ Semua request sudah diproses!")
            else:
                st.markdown(f"""<div style="font-size:14px;font-weight:700;color:{T['text']};margin-bottom:12px;">
                    🟡 Pending — Perlu Direview ({len(pending_df)} request)</div>""", unsafe_allow_html=True)

                # [FIX-3b] Ganti iterrows() dengan itertuples() — lebih cepat,
                # lalu akses via row._asdict() agar tetap bisa .get() seperti sebelumnya
                for row_t in pending_df.itertuples(index=False):
                    row = row_t._asdict()
                    try:
                        submitted  = datetime.strptime(str(row.get("submitted_date",""))[:16], "%Y-%m-%d %H:%M")
                        age_days   = (datetime.now() - submitted).days
                        age_label  = f"{age_days} hari yang lalu" if age_days > 0 else "Hari ini"
                        age_color  = "#ef4444" if age_days >= 3 else "#f59e0b" if age_days >= 1 else "#22c55e"
                    except Exception:
                        age_label, age_color = "-", T["text3"]

                    with st.expander(
                        f"📋 {row.get('request_id','-')}  ·  {row.get('change_type','-')}  ·  "
                        f"{row.get('employee_name','-')}  ·  dari {row.get('requester_name','-')}", expanded=False):
                        col_info, col_action = st.columns([3, 2])
                        with col_info:
                            st.markdown(f"""
                            <div style="background:{T['bg3']};border-radius:12px;padding:16px;border:1px solid {T['border']};">
                                <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                                    <div><div style="font-size:10px;color:{T['text3']};text-transform:uppercase;letter-spacing:0.06em;">Request ID</div>
                                        <div style="font-size:13px;font-weight:600;color:{T['text']};">{row.get('request_id','-')}</div></div>
                                    <div><div style="font-size:10px;color:{T['text3']};text-transform:uppercase;letter-spacing:0.06em;">Masuk</div>
                                        <div style="font-size:13px;color:{age_color};font-weight:600;">{age_label}</div></div>
                                    <div><div style="font-size:10px;color:{T['text3']};text-transform:uppercase;letter-spacing:0.06em;">Karyawan</div>
                                        <div style="font-size:13px;font-weight:600;color:{T['text']};">{row.get('employee_name','-')} ({row.get('employee_id','-')})</div></div>
                                    <div><div style="font-size:10px;color:{T['text3']};text-transform:uppercase;letter-spacing:0.06em;">Jenis</div>
                                        <div style="font-size:13px;font-weight:600;color:{T['accent']};">{row.get('change_type','-')}</div></div>
                                </div>
                                <div style="margin-top:12px;padding-top:12px;border-top:1px solid {T['border']};">
                                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                                        <div><div style="font-size:10px;color:{T['text3']};text-transform:uppercase;letter-spacing:0.06em;">Sebelum</div>
                                            <div style="font-size:13px;color:#ef4444;font-weight:500;">❌ {row.get('data_lama','-')}</div></div>
                                        <div><div style="font-size:10px;color:{T['text3']};text-transform:uppercase;letter-spacing:0.06em;">Sesudah</div>
                                            <div style="font-size:13px;color:#22c55e;font-weight:500;">✅ {row.get('data_baru','-')}</div></div>
                                    </div>
                                </div>
                                <div style="margin-top:12px;padding-top:12px;border-top:1px solid {T['border']};">
                                    <div style="font-size:10px;color:{T['text3']};text-transform:uppercase;letter-spacing:0.06em;">Alasan</div>
                                    <div style="font-size:13px;color:{T['text_variant']};">{row.get('alasan','-')}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col_action:
                            reviewer       = st.text_input("Nama Reviewer *", key=f"reviewer_{row.get('request_id','')}", placeholder="Nama Anda")
                            catatan_review = st.text_area("Catatan (opsional)", key=f"catatan_{row.get('request_id','')}", height=80)
                            col_a, col_r = st.columns(2)
                            with col_a:
                                if st.button("✅ Approve", key=f"approve_{row.get('request_id','')}", use_container_width=True):
                                    if not reviewer.strip(): st.error("Nama reviewer harus diisi")
                                    else:
                                        if update_cr_status(row.get("request_id",""), "Approved", reviewer.strip(), catatan_review.strip()):
                                            st.success("✅ Approved!"); st.rerun()
                            with col_r:
                                if st.button("❌ Reject", key=f"reject_{row.get('request_id','')}", use_container_width=True):
                                    if not reviewer.strip(): st.error("Nama reviewer harus diisi")
                                    else:
                                        if update_cr_status(row.get("request_id",""), "Rejected", reviewer.strip(), catatan_review.strip()):
                                            st.warning("❌ Rejected"); st.rerun()

    with cr_tab3:
        col_rl, _ = st.columns([1, 5])
        with col_rl:
            if st.button("🔄 Refresh", key="refresh_hist"):
                st.cache_data.clear(); st.rerun()

        cr_hist = load_change_requests()
        if cr_hist.empty:
            st.info("📭 Belum ada history request.")
        else:
            processed = cr_hist[cr_hist["status"].isin(["Approved","Rejected"])].copy()
            if processed.empty:
                st.info("Belum ada request yang telah diproses.")
            else:
                h1m, h2m, h3m = st.columns(3)
                h1m.metric("📊 Total Diproses", len(processed))
                h2m.metric("✅ Approved", len(processed[processed["status"]=="Approved"]))
                h3m.metric("❌ Rejected", len(processed[processed["status"]=="Rejected"]))
                st.markdown(f"<div style='height:1px;background:{T['border']};margin:16px 0;'></div>", unsafe_allow_html=True)

                col_hf1, col_hf2, col_hf3 = st.columns(3)
                with col_hf1: hist_type   = st.selectbox("Filter Jenis", ["Semua"] + sorted(processed["change_type"].unique().tolist()), key="hf_type")
                with col_hf2: hist_status = st.selectbox("Filter Status", ["Semua","Approved","Rejected"], key="hf_status")
                with col_hf3: hist_search = st.text_input("Cari nama karyawan", key="hf_search")

                view_hist = processed.copy()
                if hist_type   != "Semua": view_hist = view_hist[view_hist["change_type"] == hist_type]
                if hist_status != "Semua": view_hist = view_hist[view_hist["status"] == hist_status]
                if hist_search:            view_hist = view_hist[view_hist["employee_name"].str.contains(hist_search, case=False, na=False)]

                display_cols = ["request_id","submitted_date","requester_name","change_type",
                                "employee_name","employee_id","data_lama","data_baru",
                                "status","reviewed_by","reviewed_date","catatan"]
                available_cols = [c for c in display_cols if c in view_hist.columns]
                st.caption(f"Menampilkan **{len(view_hist)}** request")
                st.dataframe(view_hist[available_cols].reset_index(drop=True), use_container_width=True, height=480)
                st.divider()
                col_hd1, col_hd2, _ = st.columns([1,1,3])
                with col_hd1:
                    st.download_button("📄 CSV", view_hist.to_csv(index=False).encode("utf-8"),
                                       "cr_history.csv", "text/csv", use_container_width=True)
                with col_hd2:
                    st.download_button("📊 Excel", to_excel(view_hist), "cr_history.xlsx",
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
