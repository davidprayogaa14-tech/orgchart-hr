import streamlit as st
import pandas as pd
import json
import html
import textwrap
from io import BytesIO
import os
import logging
from datetime import datetime, timezone, timedelta

# Timezone WIB (UTC+7) — dipakai di PDF timestamp
_WIB = timezone(timedelta(hours=7))

# ── Logging (menggantikan print() debug di production path) ──────
# Default level WARNING (silent) — aktifkan DEBUG manual saat troubleshooting lokal.
logger = logging.getLogger("orgchart")

# ── bcrypt (password hashing) — fallback eksplisit jika belum terinstall ──
try:
    import bcrypt
    BCRYPT_OK = True
except ImportError:
    BCRYPT_OK = False

# ── ReportLab (opsional — tidak tersedia di Python 3.14 Streamlit Cloud) ──
try:
    import _md5
except ImportError:
    pass

try:
    from reportlab.lib.pagesizes import A3, A4, landscape
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib import colors
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════
# ── People Database (source of truth resmi) ───────────────────────
SHEET_ID        = "1AHuIlmgUayU9bDMNHuh_z5O4EkZkoG6bvaFafGHRO2M"
SHEET_EMP_NAME  = "Employment Information"   # worksheet utama employee
SHEET_LOG_NAME  = "activity_log"             # worksheet activity log
SHEET_ACL_NAME  = "app_users"                # worksheet ACL
SHEET_CR_NAME   = "change_requests"          # worksheet change requests
SHEET_MPP_NAME  = "mpp_data"                 # worksheet MPP

# ── GCP & Auth ────────────────────────────────────────────────────
# Service Account: orgchartmaker@people-mekari-ai.iam.gserviceaccount.com
# GCP Project    : people-mekari-ai
CREDS_FILE = "credentials.json"
SCOPES     = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
CHIEF_ROOT = "SLKR001"

# ── Logo Mekari (base64 encoded) ─────────────────────────────
_MEKARI_LOGO_B64 = "/9j/4AAQSkZJRgABAQAAAQABAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADb/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAA1ACsDASIAAhEBAxEB/8QAGgAAAgMBAQAAAAAAAAAAAAAAAAgEBQcGA//EADAQAAEDAwQBAgQEBwAAAAAAAAECAwQABREGBxIhMUFRCBMicRQyM2FCQ3KBgpGh/8QAGwEAAQUBAQAAAAAAAAAAAAAAAAEDBAUHBgL/xAAoEQABAwMDAwMFAAAAAAAAAAABAAIEAxEhBRIxBlFhIzJBExRxgfD/2gAMAwEAAhEDEQA/AHLoopb/AIq9Ua105reyGz3ydbLcuEXWBGc4pcfSshzmPCwEqa+lWR34qz0jS36pKEam4NJB58C6cp0zUdtCZCis52Z3RtmudMPSJjjEG625vNxZUoJSlIH6yST+mcHz+Ugg+hODbx71X7UOoi1pK7TrVZYasMORXFNuy1D+YrHfE+iD0R2Rk4FhA6XnzJj4m3aWe4ngdvzf48Z4Xtkd7nFvZN/RUDTZuKtO203gpNyMRr8WUjA+dwHPA9ByzU+uec3a4hMFQL3e7NZIwk3m6wbcyc4clSEtJOPYqIpevie1noDVelYsSz39mfeIMtLrCY7S1oUhQ4uJ+Zx4YwQrz2UCr34hNn9Ta11SxqKwzoTvCImOqJLcU2UcVKOUKCSDnl2DjseT6YLq7bjW2k4jk2/WB6LCQoJMlLrbjeSQB2hRxkkDsCtF6T0nTC+jKMr1Qb7bgZ7Zye2OfhTo9OncO3ZXLNOutc/lOuN/MQW3OCynmg+UnHlJwOj10KutvnbJH1xZZWo3yxaY8tD8lYaU50j60jikEkFSUg4HgmqKplmtk+83Ri12uI7MmyCUssNjKlkAqOPsAT9ga1KSxjqLw920EG54sLc3PbypzuE8ti3J0Fe1JRbdW2lx1fSWlyA04f8ABeFf8rrMj3FJrZdgNx7pxEq3QLW2r8xmy0k49+LfP/RxTbaTtTtj0va7K5MXNXBiNR1SF9KdKEhPI+fOPc1hOv6Zp0Et+ykfUvyMG37GFVVqbGe03VpS6fGZqQoYsukY7gBcUq4S0g98RlDQI9iS4fugUxdZzuds/pzX2oYd7ucu4xX2GRHdEZxID7QUVBJyDxIKldjB7/YYY6clxYWoMkSr7W3OBfNsf3dJQc1r7uS27VbSX7X1oud1jOpgxY7akw3Hk/TLkD+AeyB4UvvBIABIUByVqmXPRms4s56M9GuNmmpcdjrGFgoV9bZ/qTkfuFdU/dpt0K1WyPbbdFbixIzYaZZbGEoSBgAVwe6Oz+mdfXNi6TXpduntpDbj8PgFPoHgL5JIJHofPeOxjHXw+u21pVRk1vovwAMkC1s97/PnjCkNlguO7haBBksTYTE2K4l1iQ2l1pafCkqGQf7g17VFtECNarVEtkJBbiw2EMMpJJ4oQkJSMnz0BUqs1dtudvCgoooopEIooooQiiiihC//2Q=="

# ══════════════════════════════════════════════════════════════════
# LANGUAGE DICTIONARY
# ══════════════════════════════════════════════════════════════════
LANG = {
    "id": {
        "nav_org":"Org Chart","nav_data":"Data Karyawan","nav_compliance":"Compliance Check",
        "nav_manager":"Daftar Manager","nav_cr":"Change Request",
        "btn_refresh":"Refresh","btn_mode":"Mode","btn_logout":"Keluar",
        "lang_toggle":"🇬🇧 English","data_source_live":"Live · Google Sheets",
        "data_source_local":"Lokal · CSV","auto_refresh":"Gunakan Refresh untuk memuat data terbaru",
        "menu_label":"Menu","header_supra":"People","header_title":"Organization Dashboard",
        "header_subtitle":"Dashboard Visualisasi Data Organisasi","header_metric":"Total Karyawan",
        "mode_label":"MODE TAMPILAN","mode_division":"Per Divisi","mode_company":"Seluruh Perusahaan",
        "search_label":"Cari Mekarian","search_ph":"Ketik nama Mekarian...",
        "filter_label":"Filter","filter_bu":"🏢 Business Unit","filter_div":"📁 Divisi",
        "filter_sbu":"🏷️ SBU/Tribe","filter_leader":"👤 Filter by Leader",
        "filter_all_sbu":"Semua SBU","filter_all_div":"Semua (divisi penuh)",
        "expand_level":"📶 Expand Level","download_data":"⬇️ Download Data",
        "showing_emp":"Menampilkan","employees":"karyawan",
        "emp_found":"Ditemukan","emp_not_found":"Tidak ada karyawan bernama",
        "company_warning":"⚠️ Mode seluruh perusahaan menampilkan semua karyawan. Gunakan zoom out dan collapse untuk navigasi.",
        "emp_select_ph":"— Pilih Mekarian —","emp_select_label":"Pilih Mekarian:",
        "emp_more":"lainnya","emp_pick_below":"Pilih salah satu di bawah.",
        "chart_legend_in_div":"Divisi ini","chart_legend_out_div":"Atasan luar divisi",
        "chart_legend_subordinate":"Jml subordinate","chart_legend_searched":"Karyawan dicari",
        "chart_legend_tip":"💡 Klik node · Scroll zoom · Drag geser",
        "chart_tooltip_expand":"Klik untuk expand","chart_tooltip_collapse":"Klik untuk collapse",
        "chart_hidden_suffix":"tersembunyi",
        "pdf_company_title":"Org Chart — Seluruh Perusahaan","pdf_all_div":"Semua Divisi","pdf_all_bu":"Seluruh BU",
        "tab_data_title":"Data Karyawan","tab_data_sub":"Seluruh data karyawan dengan filter dan pencarian",
        "search_name":"🔍 Cari Mekarian","filter_all":"Semua",
        "tab_cc_title":"Compliance Check","tab_cc_sub":"Deteksi inkonsistensi data antara Employee Data dan MPP Data",
        "cc_tab_summary":"📊  Ringkasan Isu","cc_tab_missing":"👤  Missing Manager ID",
        "cc_tab_mismatch":"🔀  Data Tidak Konsisten","cc_tab_ghost":"🔍  Tidak Terpetakan",
        "cc_tab_vacancy":"📋  Master MPP",
        "cc_no_mpp":"Analisis MPP belum tersedia. Periksa koneksi dan isi worksheet mpp_data, lalu klik Refresh. Ini bukan berarti tidak ada isu.",
        "cc_total_anomali":"Total Isu Data","cc_missing_mgr":"Missing Manager ID",
        "cc_mismatch":"Data Tidak Konsisten","cc_ghost":"Tidak Terpetakan","cc_vacancy":"Master MPP",
        "cc_unavailable":"Belum tersedia",
        "cc_clean":"✅ Tidak ada isu ditemukan pada kategori ini.",
        "cc_field":"Field","cc_actual":"Nilai di Employee Data","cc_mpp":"Nilai di MPP Data",
        "severity_high":"High","severity_med":"Medium",
        "tab_mgr_title":"Daftar Manager",
        "tab_mgr_sub":"Seluruh karyawan yang memiliki bawahan langsung beserta analisis Span of Control",
        "tab_cr_title":"Structure Change Request",
        "tab_cr_sub":"Kelola permintaan perubahan struktur organisasi",
        "showing":"Menampilkan","breakdown_div":"Breakdown per Divisi",
        "download_csv":"📄 CSV","download_excel":"📊 Excel",
        "filter_bu_plain":"Filter Business Unit","filter_div_plain":"Filter Divisi",
        "emp_in_div":"karyawan di divisi ini","emp_found_in":"ada di divisi ini",
        "div_emp_count_label":"Karyawan di Divisi","div_mgr_count_label":"Manager di Divisi",
    },
    "en": {
        "nav_org":"Org Chart","nav_data":"Employee Data","nav_compliance":"Compliance Check",
        "nav_manager":"Manager List","nav_cr":"Change Request",
        "btn_refresh":"Refresh","btn_mode":"Mode","btn_logout":"Sign Out",
        "lang_toggle":"🇮🇩 Bahasa","data_source_live":"Live · Google Sheets",
        "data_source_local":"Local · CSV","auto_refresh":"Use Refresh to load the latest data",
        "menu_label":"Menu","header_supra":"People","header_title":"Organization Dashboard",
        "header_subtitle":"Organizational Data Visualization Dashboard","header_metric":"Total Employees",
        "mode_label":"VIEW MODE","mode_division":"By Division","mode_company":"Entire Company",
        "search_label":"Search Mekarian","search_ph":"Type Mekarian name...",
        "filter_label":"Filter","filter_bu":"🏢 Business Unit","filter_div":"📁 Division",
        "filter_sbu":"🏷️ SBU/Tribe","filter_leader":"👤 Filter by Leader",
        "filter_all_sbu":"All SBUs","filter_all_div":"All (full division)",
        "expand_level":"📶 Expand Level","download_data":"⬇️ Download Data",
        "showing_emp":"Showing","employees":"employees",
        "emp_found":"Found","emp_not_found":"No employee named",
        "company_warning":"⚠️ Company-wide mode displays all employees. Use zoom out and collapse to navigate.",
        "emp_select_ph":"— Select Mekarian —","emp_select_label":"Select Mekarian:",
        "emp_more":"more","emp_pick_below":"Select one below.",
        "chart_legend_in_div":"This division","chart_legend_out_div":"Manager outside division",
        "chart_legend_subordinate":"Subordinate count","chart_legend_searched":"Searched employee",
        "chart_legend_tip":"💡 Click node · Scroll to zoom · Drag to pan",
        "chart_tooltip_expand":"Click to expand","chart_tooltip_collapse":"Click to collapse",
        "chart_hidden_suffix":"hidden",
        "pdf_company_title":"Org Chart — Entire Company","pdf_all_div":"All Divisions","pdf_all_bu":"All BUs",
        "tab_data_title":"Employee Data","tab_data_sub":"All employee data with filters and search",
        "search_name":"🔍 Search Mekarian","filter_all":"All",
        "tab_cc_title":"Compliance Check","tab_cc_sub":"Detect data inconsistencies between Employee Data and MPP Data",
        "cc_tab_summary":"📊  Issue Summary","cc_tab_missing":"👤  Missing Manager ID",
        "cc_tab_mismatch":"🔀  Data Inconsistency","cc_tab_ghost":"🔍  Unmapped Employees",
        "cc_tab_vacancy":"📋  Master MPP",
        "cc_no_mpp":"MPP analysis is unavailable. Check the mpp_data worksheet and connection, then click Refresh. This does not mean there are no issues.",
        "cc_total_anomali":"Total Data Issues","cc_missing_mgr":"Missing Manager ID",
        "cc_mismatch":"Data Inconsistency","cc_ghost":"Unmapped Employees","cc_vacancy":"Master MPP",
        "cc_unavailable":"Unavailable",
        "cc_clean":"✅ No issues found in this category.",
        "cc_field":"Field","cc_actual":"Value in Employee Data","cc_mpp":"Value in MPP Data",
        "severity_high":"High","severity_med":"Medium",
        "tab_mgr_title":"Manager List",
        "tab_mgr_sub":"All employees with direct reports and Span of Control analysis",
        "tab_cr_title":"Structure Change Request",
        "tab_cr_sub":"Manage organizational structure change requests",
        "showing":"Showing","breakdown_div":"Breakdown by Division",
        "download_csv":"📄 CSV","download_excel":"📊 Excel",
        "filter_bu_plain":"Filter Business Unit","filter_div_plain":"Filter Division",
        "emp_in_div":"employees in this division","emp_found_in":"found in this division",
        "div_emp_count_label":"Employees in Division","div_mgr_count_label":"Managers in Division",
    },
}


@st.cache_data(ttl=300)
def load_mpp_data():
    client = get_gspread_client()
    if client:
        try:
            ws = client.open_by_key(SHEET_ID).worksheet(SHEET_MPP_NAME)
            df_mpp = pd.DataFrame(ws.get_all_records())
            df_mpp.columns = df_mpp.columns.str.strip()
            return df_mpp
        except Exception:
            pass
    return pd.DataFrame()


def run_compliance_checks(emp_df: pd.DataFrame, mpp_df: pd.DataFrame) -> dict:
    results = {
        "missing_manager": pd.DataFrame(),
        "mismatch":        pd.DataFrame(),
        "ghost":           pd.DataFrame(),
        "vacancy":         pd.DataFrame(),
    }
    # 1. Missing Manager ID
    missing = emp_df[
        (emp_df["Manager ID"].astype(str).str.strip() == "") |
        (emp_df["Manager ID"].isna()) |
        (emp_df["Manager ID"].astype(str).str.strip() == "nan")
    ][["Employee ID","Employee Name","Job Position","Division","Business Unit","SBU/Tribe","Manager ID"]].copy()
    missing["Severity"] = "High"
    results["missing_manager"] = missing

    if mpp_df.empty:
        return results

    mpp = mpp_df.copy()
    mpp["JOBID"] = mpp["JOBID"].astype(str).str.strip()
    emp = emp_df.copy()
    if "Job ID" not in emp.columns:
        emp["Job ID"] = ""
    emp["Job ID"] = emp["Job ID"].astype(str).str.strip()

    emp_valid = emp[emp["Job ID"].notna() & (emp["Job ID"] != "") & (emp["Job ID"] != "nan")].copy()
    mpp_valid = mpp[mpp["JOBID"].notna() & (mpp["JOBID"] != "") & (mpp["JOBID"] != "nan")].copy()

    emp_ids = set(emp_valid["Job ID"].tolist())
    mpp_ids = set(mpp_valid["JOBID"].tolist())

    # Ghost: emp not in mpp
    ghost_ids = emp_ids - mpp_ids
    ghost_cols = [c for c in ["Employee ID","Employee Name","Job ID","Job Position","Division","Business Unit","SBU/Tribe"] if c in emp_valid.columns]
    ghost_df = emp_valid[emp_valid["Job ID"].isin(ghost_ids)][ghost_cols].copy()
    ghost_df["Severity"] = "Medium"
    results["ghost"] = ghost_df

    # Vacancy: mpp not in emp
    vacancy_ids = mpp_ids - emp_ids
    vac_cols = [c for c in ["MPP Status 2026","JOBID","Job Position","MPP Career Stage","Division","BU","SBU","Primary Budget Holder","Fulfillment Status"] if c in mpp_valid.columns]
    vacancy_df = mpp_valid[mpp_valid["JOBID"].isin(vacancy_ids)][vac_cols].copy()
    results["vacancy"] = vacancy_df

    # Mismatch cross-sheet
    merged = emp_valid.merge(mpp_valid, left_on="Job ID", right_on="JOBID", how="inner", suffixes=("_emp","_mpp"))

    FIELD_MAP = [
        ("Business Unit",  "Business Unit",   "BU",                   "High"),
        ("Division",       "Division_emp",    "Division_mpp",          "High"),
        ("SBU/Tribe",      "SBU/Tribe",       "Tribe/Squad/Function",  "Medium"),
        ("Job Position",   "Job Position_emp","Job Position_mpp",      "High"),
        ("Career Stage",   "Career Stage",    "MPP Career Stage",      "Medium"),
    ]
    mismatch_rows = []
    for label, ec, mc, sev in FIELD_MAP:
        # fallback col names without suffix if suffix not applied
        if ec not in merged.columns:
            ec = label if label in merged.columns else None
        if mc not in merged.columns:
            mc = None
        if not ec or not mc:
            continue
        diff = merged[
            merged[ec].astype(str).str.strip().str.lower() !=
            merged[mc].astype(str).str.strip().str.lower()
        ]
        if diff.empty:
            continue
        eid_col = "Employee ID" if "Employee ID" in diff.columns else "Employee ID_emp"
        enm_col = "Employee Name" if "Employee Name" in diff.columns else "Employee Name_emp"
        for _, row in diff.iterrows():
            mismatch_rows.append({
                "Employee ID":   row.get(eid_col,""),
                "Employee Name": row.get(enm_col,""),
                "Job ID":        row.get("Job ID",""),
                "Field":         label,
                "Nilai di Employee Data": str(row.get(ec,"")).strip(),
                "Nilai di MPP":  str(row.get(mc,"")).strip(),
                "Severity":      sev,
            })

    results["mismatch"] = pd.DataFrame(mismatch_rows) if mismatch_rows else pd.DataFrame(
        columns=["Employee ID","Employee Name","Job ID","Field","Nilai di Employee Data","Nilai di MPP","Severity"]
    )
    return results


# ══════════════════════════════════════════════════════════════════
# RBAC MODULE — Email-Based Access Control List
# ══════════════════════════════════════════════════════════════════
#
# ROLE HIERARCHY & TAB VISIBILITY:
#   admin    → Org Chart + semua tab operasional + Admin Panel
#   cxo      → Org Chart only (full data, no filter)
#   leader   → Org Chart only (filtered by allowed_bus / allowed_sbus)
#   employee → Org Chart only (subtree C-1 dari manager mereka)
#
# ACL dikelola sepenuhnya oleh Super Admin (OD Tim) via Admin Panel.
# User login hanya menggunakan EMAIL + PASSWORD yang di-assign admin.
# Primary key: email (lowercase). Password disimpan plaintext di Sheets
# (acceptable untuk fase 1 internal tool; upgrade ke hashed di fase 2).
#
# Google Sheets worksheet: 'app_users'
# Kolom: email | name | role | password | allowed_bus | allowed_sbus |
#         employee_id | is_active | scope_note | created_at | updated_at
# ══════════════════════════════════════════════════════════════════

_ACL_COLS = [
    "email", "name", "role", "password",
    "allowed_bus", "allowed_sbus", "employee_id",
    "is_active", "scope_note", "created_at", "updated_at",
]

# CATATAN (Agustus 2026): _ACL_FALLBACK dengan akun bootstrap
# "od_admin@mekari.com" DIHAPUS setelah audit keamanan membuktikan akun
# ini tidak pernah benar-benar di-seed ke worksheet app_users — murni
# dead code yang tidak pernah melindungi siapa pun (load_acl_table()
# hanya jatuh ke fallback saat sheet kosong/unreachable, dan sheet
# production sudah berisi user real sejak awal). Mempertahankannya
# hanya menyisakan risiko: siapa pun yang tahu credential default di
# atas berpotensi dapat akses admin penuh pada skenario sheet down.
#
# Untuk emergency access yang SUNGGUHAN independen dari Google Sheets,
# gunakan Streamlit Secrets [auth.users] — lihat authenticate_user()
# di bawah, layer lookup #1. Itu tidak bergantung ke _ACL_FALLBACK
# maupun ke koneksi Google Sheets sama sekali.

# Role → tab access mapping
# super_admin : semua tab TERMASUK Admin Panel (0=OrgChart, 1=Data, 2=Compliance, 3=Manager, 4=CR, 5=Offboarding, 99=AdminPanel)
# admin       : Org Chart + Offboarding Tracker
# cxo         : hanya tab 0
# leader      : hanya tab 0
# employee    : hanya tab 0
_ROLE_TAB_ACCESS = {
    "super_admin": {0, 1, 2, 3, 4, 5, 99},
    "od_reviewer": {0, 4},          # OD: review SCR (Offboarding belum diberikan, menunggu keputusan)
    "admin":       {0, 5},
    "cxo":         {0, 4},          # SCR: hanya Buat Request + My Requests
    "hrbp":        {0, 4},          # SCR: hanya Buat Request + My Requests
    "leader":      {0, 4},          # SCR: hanya Buat Request + My Requests
    "employee":    {0},
}

# [SCR Fase 1a] Kapabilitas SCR per role = SATU sumber kebenaran untuk sub-tab
# yang tampil DAN tombol Approve/Reject. Role yang tidak terdaftar = tidak ada akses.
_SCR_CAPS = {
    "super_admin": {"submit", "my", "inbox", "decide", "history"},
    "od_reviewer": {"submit", "my", "inbox", "decide", "history"},
    "cxo":         {"submit", "my"},
    "hrbp":        {"submit", "my"},
    "leader":      {"submit", "my"},
}


def _scr_can(role: str, cap: str) -> bool:
    """Return True jika role memiliki kapabilitas SCR `cap`."""
    return cap in _SCR_CAPS.get(role, set())


def _can_access_tab(role: str, tab_idx: int) -> bool:
    """Return True jika role boleh mengakses tab_idx.
    [QA AUTH-01] FAIL-CLOSED: role yang tidak terdaftar tidak mendapat tab apa pun."""
    return tab_idx in _ROLE_TAB_ACCESS.get(role, set())


def _scr_beta_enabled() -> bool:
    """Runtime-only feature flag; fail closed jika Secrets tidak tersedia/invalid."""
    try:
        raw = st.secrets.get("beta", {}).get("scr_enabled", False)
    except Exception:
        return False
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@st.cache_data(ttl=120)
def load_acl_table() -> dict:
    """
    Load ACL dari worksheet 'app_users' di Google Sheets.
    Return dict keyed by email (lowercase).
    Return dict KOSONG jika sheet belum ada / kosong / tidak bisa diakses —
    ini SENGAJA tidak fallback ke akun bootstrap manapun (lihat catatan
    di atas _ACL_COLS soal _ACL_FALLBACK yang sudah dihapus). Kalau sheet
    down, satu-satunya jalur login yang tetap hidup adalah Streamlit
    Secrets [auth.users] di authenticate_user(), yang tidak lewat fungsi
    ini sama sekali.
    """
    client = get_gspread_client()
    if not client:
        return {}
    try:
        ws   = client.open_by_key(SHEET_ID).worksheet(SHEET_ACL_NAME)
        rows = ws.get_all_records()
        if not rows:
            return {}
        acl: dict = {}
        for r in rows:
            email_key = str(r.get("email", "")).strip().lower()
            if not email_key:
                continue
            acl[email_key] = {
                "name":        str(r.get("name", "")).strip(),
                "role":        str(r.get("role", "employee")).strip().lower(),
                "password":    str(r.get("password", "")).strip(),
                "allowed_bus": str(r.get("allowed_bus", "*")).strip(),
                "allowed_sbus":str(r.get("allowed_sbus", "*")).strip(),
                "employee_id": str(r.get("employee_id", "")).strip(),
                "is_active":   str(r.get("is_active", "TRUE")).strip().upper() in ("TRUE", "1", "YES"),
                "scope_note":  str(r.get("scope_note", "")).strip(),
            }
        return acl
    except Exception:
        return {}


def get_acl_sheet():
    """
    Return worksheet 'app_users'. Buat otomatis jika belum ada.
    """
    client = get_gspread_client()
    if not client:
        return None
    try:
        return client.open_by_key(SHEET_ID).worksheet(SHEET_ACL_NAME)
    except Exception:
        try:
            sh = client.open_by_key(SHEET_ID)
            ws = sh.add_worksheet(title="app_users", rows=500, cols=len(_ACL_COLS))
            ws.append_row(_ACL_COLS, value_input_option="USER_ENTERED")
            return ws
        except Exception:
            return None


def get_user_info(email: str) -> dict | None:
    """
    Lookup user by email. Returns user dict atau None jika tidak
    ditemukan / tidak aktif.
    """
    acl = load_acl_table()
    user = acl.get(email.strip().lower())
    if user and user.get("is_active", True):
        return user
    return None


def hash_password(plain: str) -> str:
    """
    Hash password dengan bcrypt sebelum disimpan ke Google Sheets.
    Fallback ke plaintext HANYA jika package bcrypt belum terinstall — ini
    adalah mode darurat, bukan kondisi normal. Tambahkan `bcrypt` ke
    requirements.txt sesegera mungkin jika BCRYPT_OK == False.
    """
    if not plain:
        return ""
    if BCRYPT_OK:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    logger.warning("bcrypt tidak terinstall — password disimpan plaintext (FIX SEGERA)")
    return plain


def _is_bcrypt_hash(value: str) -> bool:
    return bool(value) and value.startswith(("$2a$", "$2b$", "$2y$"))


def verify_password(plain: str, stored: str) -> bool:
    """
    Verifikasi password dengan dukungan migrasi bertahap:
    - Jika `stored` adalah bcrypt hash      → verifikasi via bcrypt.checkpw.
    - Jika `stored` masih plaintext (legacy data lama) → exact match (sementara,
      sampai user login ulang dan password otomatis di-rehash — lihat authenticate_user).
    """
    if not stored or not plain:
        return False
    if _is_bcrypt_hash(stored) and BCRYPT_OK:
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    return stored == plain


def _ensure_hashed(pw: str) -> str:
    """Hash hanya jika `pw` belum berupa bcrypt hash — mencegah double-hashing saat edit user existing."""
    if not pw:
        return ""
    if _is_bcrypt_hash(pw):
        return pw
    return hash_password(pw)


def authenticate_user(email: str, password: str) -> dict | None:
    """
    Verifikasi email + password. Return user dict atau None.
    Urutan lookup:
    1. Streamlit Secrets [auth][users] — independen dari Google Sheets,
       satu-satunya jalur yang tetap hidup kalau Sheets/OAuth down.
    2. Google Sheets app_users (primary ACL)
    """
    email_lower = email.strip().lower()

    # 1. Streamlit Secrets (production override)
    if "auth" in st.secrets and "users" in st.secrets.get("auth", {}):
        users_secret = st.secrets["auth"]["users"]
        # Key format: email dengan . dan @ diganti _
        email_key = email_lower.replace(".", "_").replace("@", "_at_")
        if email_key in users_secret:
            sec = users_secret[email_key]
            if sec.get("password") == password:
                return {
                    "name":        sec.get("name", email_lower),
                    "role":        sec.get("role", "employee").lower(),
                    "allowed_bus": sec.get("allowed_bus", "*"),
                    "allowed_sbus":sec.get("allowed_sbus", "*"),
                    "employee_id": sec.get("employee_id", ""),
                    "is_active":   True,
                    "scope_note":  "Via Streamlit Secrets",
                }

    # 2. Google Sheets ACL
    acl = load_acl_table()
    user = acl.get(email_lower)
    if user and user.get("is_active", True):
        stored_pw = user.get("password", "").strip()
        if stored_pw and verify_password(password, stored_pw):
            # Migrasi on-the-fly: kalau password masih plaintext (data lama),
            # re-hash & simpan otomatis saat login berhasil — tanpa downtime,
            # tanpa script migrasi terpisah.
            if BCRYPT_OK and not _is_bcrypt_hash(stored_pw):
                try:
                    reset_user_password(email_lower, password)
                except Exception:
                    logger.warning(f"Gagal auto-migrate hash password untuk {email_lower}")
            return user

    return None


def apply_rbac_filter(df: pd.DataFrame, user_info: dict) -> pd.DataFrame:
    """
    Row-Level Security — filter DataFrame berdasarkan role & scope user.

    Mapping:
    - super_admin / admin / cxo   → full access, no filter
    - leader                      → filter by allowed_bus + allowed_sbus
    - employee                    → subtree C-1 (direct reports of their manager only)

    PENTING: fungsi ini hanya dipanggil SETELAH auth berhasil.
    df yang dikembalikan adalah satu-satunya data yang boleh dilihat user.
    """
    role = user_info.get("role", "employee")

    # ── Full access ───────────────────────────────────────────────
    if role in ("super_admin", "admin", "cxo", "od_reviewer"):
        return df

    # ── Leader: BU + SBU scope ────────────────────────────────────
    if role in ("leader", "hrbp"):
        # [QA SEC-01] FAIL-CLOSED: scope yang tidak ada / kosong / tidak terbaca = TIDAK ADA akses.
        # Akses penuh hanya lewat '*' yang ditulis eksplisit di app_users.
        raw_bus  = str(user_info.get("allowed_bus", "")).strip()
        raw_sbus = str(user_info.get("allowed_sbus", "")).strip()
        if raw_bus.lower() in ("", "nan", "none") or raw_sbus.lower() in ("", "nan", "none"):
            return df.iloc[0:0]

        # Parse comma-separated, handle wildcard
        allowed_bus  = [] if raw_bus  == "*" else [b.strip() for b in raw_bus.split(",")  if b.strip()]
        allowed_sbus = [] if raw_sbus == "*" else [s.strip() for s in raw_sbus.split(",") if s.strip()]
        # Nilai bukan '*' tetapi tidak menghasilkan satu pun nama (misal ",") = malformed -> tolak
        if (raw_bus != "*" and not allowed_bus) or (raw_sbus != "*" and not allowed_sbus):
            return df.iloc[0:0]

        filtered = df.copy()

        if allowed_bus:  # non-empty = restricted
            if "Business Unit" not in filtered.columns:
                return df.iloc[0:0]   # kolom pembatas hilang -> tolak, jangan lewati filter
            filtered = filtered[filtered["Business Unit"].isin(allowed_bus)]

        if allowed_sbus:
            if "SBU/Tribe" not in filtered.columns:
                return df.iloc[0:0]
            # Tetap tampilkan node tanpa SBU (atasan lintas unit tetap visible)
            sbu_mask = (
                filtered["SBU/Tribe"].isin(allowed_sbus) |
                filtered["SBU/Tribe"].isin(["", "nan"]) |
                filtered["SBU/Tribe"].isna()
            )
            filtered = filtered[sbu_mask]

        return filtered

    # [QA AUTH-01] Hanya role 'employee' yang boleh sampai ke logika subtree di bawah.
    # Role tidak dikenal -> kosong (sebelumnya jatuh ke aturan employee).
    if role != "employee":
        return df.iloc[0:0]

    # ── Employee: subtree C-1 (hanya bawahan dari manager mereka) ──
    emp_id = user_info.get("employee_id", "").strip()
    if not emp_id or emp_id == "nan":
        return df.iloc[0:0]  # deny: tidak ada EID → empty

    user_row = df[df["Employee ID"] == emp_id]
    if user_row.empty:
        return df.iloc[0:0]

    manager_id = str(user_row.iloc[0].get("Manager ID", "")).strip()
    if not manager_id or manager_id in ("", "nan"):
        return df.iloc[0:0]

    # BFS downward dari manager (max depth 1 = hanya direct reports)
    children_map = (
        df[df["Manager ID"].notna() & (df["Manager ID"] != "")]
        .groupby("Manager ID")["Employee ID"]
        .apply(list)
        .to_dict()
    )
    visible = set()
    queue   = [(manager_id, 0)]
    while queue:
        node, depth = queue.pop(0)
        if node in visible or depth > 1:
            continue
        visible.add(node)
        if depth < 1:
            for child in children_map.get(node, []):
                queue.append((child, depth + 1))

    return df[df["Employee ID"].isin(visible)].copy()


def save_acl_user(user_data: dict) -> bool:
    """
    Upsert user di worksheet app_users.
    Jika email sudah ada → update row. Jika baru → append.
    """
    ws = get_acl_sheet()
    if not ws:
        return False
    try:
        email_clean = user_data["email"].strip().lower()
        now_str     = datetime.now().strftime("%Y-%m-%d %H:%M")

        row_vals = [
            email_clean,
            user_data.get("name", ""),
            user_data.get("role", "employee"),
            _ensure_hashed(user_data.get("password", "")),
            user_data.get("allowed_bus", "*"),
            user_data.get("allowed_sbus", "*"),
            user_data.get("employee_id", ""),
            "TRUE" if user_data.get("is_active", True) else "FALSE",
            user_data.get("scope_note", ""),
            user_data.get("created_at", now_str),
            now_str,  # updated_at always = now
        ]

        # Cek apakah email sudah ada di sheet
        cell = None
        try:
            cell = ws.find(email_clean)
        except Exception:
            pass

        if cell:
            ws.update(f"A{cell.row}", [row_vals])
        else:
            row_vals[9] = now_str  # created_at = now untuk baris baru
            ws.append_row(row_vals, value_input_option="USER_ENTERED")

        load_acl_table.clear()
        return True
    except Exception as e:
        st.error(f"Gagal simpan user: {e}")
        return False


def toggle_acl_user_status(email: str, new_status: bool) -> bool:
    """Aktifkan / nonaktifkan user (soft delete). Tidak hapus row."""
    ws = get_acl_sheet()
    if not ws:
        return False
    try:
        cell = ws.find(email.strip().lower())
        if not cell:
            return False
        # Col 8 = is_active, Col 11 = updated_at (1-indexed)
        ws.update_cell(cell.row, 8, "TRUE" if new_status else "FALSE")
        ws.update_cell(cell.row, 11, datetime.now().strftime("%Y-%m-%d %H:%M"))
        load_acl_table.clear()
        return True
    except Exception as e:
        st.error(f"Gagal update status: {e}")
        return False


def reset_user_password(email: str, new_password: str) -> bool:
    """Reset password user oleh admin."""
    ws = get_acl_sheet()
    if not ws:
        return False
    try:
        cell = ws.find(email.strip().lower())
        if not cell:
            return False
        ws.update_cell(cell.row, 4, hash_password(new_password))   # Col 4 = password (bcrypt hash)
        ws.update_cell(cell.row, 11, datetime.now().strftime("%Y-%m-%d %H:%M"))
        load_acl_table.clear()
        return True
    except Exception as e:
        st.error(f"Gagal reset password: {e}")
        return False


# DATA HELPERS
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# DATA HELPERS — Schema Normalization & Loading
# ══════════════════════════════════════════════════════════════════
#
# SCHEMA MAPPING: People Database → Dashboard internal column names
#
#   People DB Column                      → Dashboard Column
#   ─────────────────────────────────────────────────────────────
#   Employee ID                           → Employee ID       (same)
#   Full Name                             → Employee Name     (rename)
#   Employment Approval Line Employee ID  → Manager ID        (rename)
#   Organization                          → Division          (rename)
#   Career Stage                          → Career Stage      (same)
#   Job ID                                → Job ID            (same)
#   Job Position                          → Job Position      (same)
#   SBU/Tribe                             → SBU/Tribe         (same)
#   Business Unit                         → Business Unit     (same)
#   Email                                 → Email             (new — auth mapping)
#   Employment Type Status                → (filter: Permanent/Intern/Probation/Contract, then drop)
#
#   Employment Approval Line Name            → Manager Name     (rename)
#   Employment Approval Line Email           → Manager Email     (rename)
#
#   DROPPED COLUMNS (tidak relevan untuk org chart):
#   Webhook Timestamp, Webhook ID, user_id,
#   Employment Approval Line User ID, Primary Budget Holder,
#   Secondary Budget Holder, End Date, Resign Date,
#   Original Placement, Notice Period (TBC), Branch, Tenure,
#   HRBP Email, Join Date
# ══════════════════════════════════════════════════════════════════

# Kolom yang di-drop setelah normalisasi
#
# [HoB VIEW — 22 Agt 2026] "Primary Budget Holder" DIKELUARKAN dari drop-list.
# Ini BUKAN opsional — fitur HoB View (brief PM/CEO) secara eksplisit
# menggunakan kolom ini (kolom R di Sheet) sebagai acuan pengelompokan.
# Sebelum perubahan ini, kolom didrop total di Step 4 sehingga tidak
# mungkin membangun HoB tree sama sekali. "Secondary Budget Holder" tetap
# didrop — tidak dipakai brief ini, tidak ada alasan menyimpannya sekarang.
# Impact ke fitur lain: NOL — tab/fitur lain select subset kolom eksplisit.
_PEOPLE_DB_DROP_COLS = [
    "Webhook Timestamp", "Webhook ID", "user_id",
    # Employment Approval Line Name & Email TIDAK di-drop — di-rename ke Manager Name/Email
    "Employment Approval Line User ID",
    "Secondary Budget Holder",
    "End Date", "Resign Date", "Original Placement",
    "Notice Period (TBC)", "Branch", "Tenure",
    "HRBP Email", "Join Date",
    "Employment Status", "Employment Type Status",  # di-drop setelah dipakai untuk filter
]

# Filter kriteria — dua kolom terpisah:
#   Employment Status      : Active, Resigned
#   Employment Type Status : Permanent, Intern, Probation, Contract
_EMPLOYMENT_STATUS_VALUES = {"active"}
_EMPLOYMENT_TYPE_VALUES   = {"permanent", "intern", "probation", "contract"}


def normalize_people_db(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalisasi DataFrame dari People Database ke schema internal dashboard.

    Urutan operasi:
    1. Strip whitespace dari semua nama kolom
    2. Filter hanya karyawan aktif (Employment Status)
    3. Rename kolom sesuai mapping:
         Full Name                            → Employee Name
         Employment Approval Line Employee ID → Manager ID
         Employment Approval Line Name        → Manager Name
         Employment Approval Line Email       → Manager Email
         Organization                         → Division
    4. Drop kolom yang tidak diperlukan
    5. Pastikan semua kolom wajib tersedia
    6. Type-cast dan clean values
    """
    df = df.copy()
    df.columns = df.columns.str.strip()

    # ── Step 2: Filter dua kolom Employment ──────────────────────────
    # Kolom 1: "Employment Status"      → kriteria: Active, Resigned
    # Kolom 2: "Employment Type Status" → kriteria: Permanent, Intern, Probation, Contract
    # Kedua filter diterapkan secara AND (harus lolos keduanya)

    total_before = len(df)

    # Filter kolom "Employment Status"
    if "Employment Status" in df.columns:
        df["Employment Status"] = df["Employment Status"].astype(str).str.strip()
        unique_emp_status = df["Employment Status"].unique().tolist()
        logger.debug(f"[normalize_people_db] 'Employment Status' unique values: {unique_emp_status}")
        mask_status = df["Employment Status"].str.lower().isin(_EMPLOYMENT_STATUS_VALUES)
        df = df[mask_status].copy()
        logger.debug(f"[normalize_people_db] After Employment Status filter: {len(df)} records")
    else:
        logger.warning("[normalize_people_db] 'Employment Status' column not found")

    # Filter kolom "Employment Type Status"
    if "Employment Type Status" in df.columns:
        df["Employment Type Status"] = df["Employment Type Status"].astype(str).str.strip()
        unique_type_status = df["Employment Type Status"].unique().tolist()
        logger.debug(f"[normalize_people_db] 'Employment Type Status' unique values: {unique_type_status}")
        mask_type = df["Employment Type Status"].str.lower().isin(_EMPLOYMENT_TYPE_VALUES)
        df = df[mask_type].copy()
        logger.debug(f"[normalize_people_db] After Employment Type Status filter: {len(df)} records")
    else:
        logger.warning("[normalize_people_db] 'Employment Type Status' column not found")

    logger.debug(f"[normalize_people_db] Total filtered: {total_before} → {len(df)} records")

    # ── Step 3: Rename kolom ──────────────────────────────────────
    rename_map = {
        "Full Name":                             "Employee Name",
        "Employment Approval Line Employee ID":  "Manager ID",
        "Employment Approval Line Name":         "Manager Name",
        "Employment Approval Line Email":        "Manager Email",
        "Organization":                          "Division",
    }
    # Hanya rename kolom yang memang ada (defensive)
    rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # Debug: log sample Manager ID setelah rename agar bisa verify format
    if "Manager ID" in df.columns:
        sample_mgr = df["Manager ID"].dropna().head(5).tolist()
        logger.debug(f"[normalize_people_db] Manager ID sample (post-rename): {sample_mgr}")
    logger.debug(f"[normalize_people_db] Columns after rename: {df.columns.tolist()}")

    # ── Step 4: Drop kolom tidak diperlukan ───────────────────────
    cols_to_drop = [c for c in _PEOPLE_DB_DROP_COLS if c in df.columns]
    df = df.drop(columns=cols_to_drop)

    # ── Step 5: Pastikan kolom wajib tersedia ─────────────────────
    required_cols = {
        "Employee ID":    "",
        "Employee Name":  "",
        "Manager ID":     "",
        "Manager Name":   "",
        "Manager Email":  "",
        "Division":       "",
        "Business Unit":  "",
        "SBU/Tribe":      "",
        "Job Position":   "",
        "Job ID":         "",
        "Career Stage":   "",
        "Email":          "",
        # [HoB VIEW] Dibutuhkan untuk grouping HoB tree — lihat catatan di _PEOPLE_DB_DROP_COLS.
        "Primary Budget Holder": "",
    }
    for col, default in required_cols.items():
        if col not in df.columns:
            df[col] = default

    # ── Step 6: Type-cast & clean ─────────────────────────────────
    df["Employee ID"]   = df["Employee ID"].astype(str).str.strip()
    df["Manager ID"]    = df["Manager ID"].fillna("").astype(str).str.strip()
    df["SBU/Tribe"]     = df["SBU/Tribe"].fillna("").astype(str).str.strip()
    df["Career Stage"]  = df["Career Stage"].fillna("").astype(str).str.strip()
    df["Email"]         = df["Email"].fillna("").astype(str).str.strip().str.lower()
    # Defensive fillna — mencegah TypeError di _wrap_text() saat generate PDF
    # (build_tree_json meneruskan nilai ini apa adanya ke PDF card renderer;
    # cell kosong di Sheet akan jadi NaN float, bukan string, tanpa ini)
    df["Job Position"]  = df["Job Position"].fillna("").astype(str).str.strip()
    df["Division"]      = df["Division"].fillna("").astype(str).str.strip()
    # [HoB VIEW] Sama alasannya seperti Job Position/Division di atas —
    # cegah NaN float nyasar ke string matching saat build HoB mapping.
    df["Primary Budget Holder"] = df["Primary Budget Holder"].fillna("").astype(str).str.strip()

    # Hapus baris tanpa Employee ID valid
    df = df[df["Employee ID"].str.len() > 0]
    df = df[df["Employee ID"] != "nan"]

    # Deduplicate Employee ID — People Database bisa mengandung
    # multiple rows per karyawan (misal: resign + rejoin).
    # Keep last row (data terbaru berdasarkan urutan di sheet).
    dupes = df["Employee ID"].duplicated(keep=False).sum()
    if dupes > 0:
        logger.debug(f"[normalize_people_db] Found {dupes} duplicate Employee ID rows — keeping last occurrence")
        df = df.drop_duplicates(subset=["Employee ID"], keep="last")

    logger.debug(f"[normalize_people_db] Final records loaded: {len(df)}")
    return df.reset_index(drop=True)


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
    """
    Load employee data dari People Database resmi.
    Primary  : Google Sheets → worksheet 'Employment Information'
    Fallback : employee_data.csv (untuk development lokal)
    """
    client = get_gspread_client()
    if client:
        try:
            ws = client.open_by_key(SHEET_ID).worksheet(SHEET_EMP_NAME)
            df = pd.DataFrame(ws.get_all_records())
            return normalize_people_db(df), "google_sheets"
        except Exception as e:
            st.warning(f"⚠️ Gagal membaca dari Google Sheets: {str(e)[:80]}")
    try:
        df = pd.read_csv("employee_data.csv")
        return normalize_people_db(df), "local_csv"
    except Exception:
        return None, "error"


@st.cache_data(ttl=300)
def load_offboarding_data():
    """
    [OFFBOARDING TRACKER — P0 CEO Request]
    Load raw employee data dari People Database TANPA filter Employment Status
    dan TANPA drop Resign Date.

    Kenapa fungsi terpisah, bukan pakai `df` yang sudah ada:
    - `normalize_people_db()` drop kolom 'Resign Date' (ada di _PEOPLE_DB_DROP_COLS)
    - `normalize_people_db()` filter hanya status='active' — kita butuh resigned employees juga
    - Dua alasan ini membuat reuse `df` dari `load_data()` tidak mungkin untuk fitur ini.

    Return:
        tuple(df_resigned, df_active_raw) | tuple(None, None) jika gagal
        df_resigned : DataFrame karyawan yang Resign Date-nya terisi (kandidat offboarding)
        df_active_raw: DataFrame karyawan aktif — dipakai untuk lookup "siapa direct report
                       karyawan yang resign" via kolom 'Employment Approval Line Name'
    """
    client = get_gspread_client()
    if not client:
        return None, None
    try:
        ws  = client.open_by_key(SHEET_ID).worksheet(SHEET_EMP_NAME)
        raw = pd.DataFrame(ws.get_all_records())
    except Exception as e:
        logger.warning(f"[load_offboarding_data] Gagal baca Sheet: {e}")
        return None, None

    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    raw.columns = raw.columns.str.strip()

    # ── Kolom yang dibutuhkan feature ini (raw column names dari Sheet) ──
    # Semua rename dilakukan manual di sini — tidak lewat normalize_people_db()
    # supaya Resign Date dan resigned employees tetap tersedia.
    NEEDED_COLS = [
        "Employee ID",
        "Full Name",
        "Employment Approval Line Name",   # = Manager Name / Reporting Line
        "Organization",                    # = Division
        "Job ID",
        "Job Position",
        "SBU/Tribe",
        "Resign Date",
        "Employment Status",               # dipakai untuk pisah active vs resigned
        "Employment Type Status",          # dipakai filter active pool
    ]
    # Retain hanya kolom yang benar-benar ada (defensive — hindari KeyError
    # kalau Sheet belum punya kolom tertentu, misal Resign Date belum diisi sama sekali)
    available = [c for c in NEEDED_COLS if c in raw.columns]
    raw = raw[available].copy()

    # ── String normalization dasar ─────────────────────────────────
    for col in raw.select_dtypes(include="object").columns:
        raw[col] = raw[col].astype(str).str.strip()

    # ── Split: resigned pool (Resign Date terisi) ──────────────────
    # "Terisi" = ada nilai, bukan "", "nan", atau "None"
    _rd_col = "Resign Date"
    if _rd_col not in raw.columns:
        raw[_rd_col] = ""
    raw[_rd_col] = raw[_rd_col].astype(str).str.strip()
    _resigned_mask = (
        raw[_rd_col].notna() &
        (raw[_rd_col] != "") &
        (raw[_rd_col].str.lower() != "nan") &
        (raw[_rd_col].str.lower() != "none")
    )
    df_resigned = raw[_resigned_mask].copy()

    # ── Active employee pool — untuk lookup "Employee Under" ──────
    # Kriteria aktif: Employment Status = active AND Employment Type Status
    # dalam set yang sama dengan normalize_people_db() (permanent/intern/
    # probation/contract). Ini penting karena brief bilang:
    # "cek dari data aktif — karyawan yang sudah resign tidak dihitung
    # sebagai manager aktif"
    _status_col = "Employment Status"
    _type_col   = "Employment Type Status"
    df_active_pool = raw.copy()
    if _status_col in df_active_pool.columns:
        df_active_pool = df_active_pool[
            df_active_pool[_status_col].str.lower().isin(_EMPLOYMENT_STATUS_VALUES)
        ]
    if _type_col in df_active_pool.columns:
        df_active_pool = df_active_pool[
            df_active_pool[_type_col].str.lower().isin(_EMPLOYMENT_TYPE_VALUES)
        ]

    # Drop status/type kolom dari kedua df — tidak ditampilkan ke user
    for _drop in [_status_col, _type_col]:
        if _drop in df_resigned.columns:
            df_resigned = df_resigned.drop(columns=[_drop])
        if _drop in df_active_pool.columns:
            df_active_pool = df_active_pool.drop(columns=[_drop])

    # Deduplicate Employee ID (sama seperti normalize_people_db)
    df_resigned   = df_resigned.drop_duplicates(subset=["Employee ID"], keep="last")
    df_active_pool = df_active_pool.drop_duplicates(subset=["Employee ID"], keep="last")

    return df_resigned.reset_index(drop=True), df_active_pool.reset_index(drop=True)


def _compute_employee_under(df_resigned: pd.DataFrame, df_active: pd.DataFrame) -> pd.Series:
    """
    Compute kolom 'Employee Under' untuk setiap baris di df_resigned.

    Logic (sesuai brief):
    1. Untuk setiap nama karyawan resign (Full Name), cari siapa saja di df_active
       yang 'Employment Approval Line Name'-nya == nama karyawan resign tsb.
       Matching: case-insensitive + strip whitespace.
    2. Jika ada → return nama-nama direct report dipisah ", "
    3. Jika tidak ada → return "" (kosong, bukan "-" atau "N/A")

    Implementasi: build lookup dict dari df_active terlebih dahulu (O(n))
    supaya tidak O(n²) per-row pada dataset 1.600+ karyawan.
    """
    if df_active.empty or "Employment Approval Line Name" not in df_active.columns:
        return pd.Series([""] * len(df_resigned), index=df_resigned.index)

    # Build dict: normalized_manager_name → list of direct report Full Names
    _mgr_to_directs: dict[str, list[str]] = {}
    for _, row in df_active.iterrows():
        mgr_raw  = str(row.get("Employment Approval Line Name", "")).strip().lower()
        emp_name = str(row.get("Full Name", "")).strip()
        if mgr_raw and emp_name:
            _mgr_to_directs.setdefault(mgr_raw, []).append(emp_name)

    def _lookup(resigning_name: str) -> str:
        key = str(resigning_name).strip().lower()
        directs = _mgr_to_directs.get(key, [])
        return ", ".join(sorted(directs)) if directs else ""

    return df_resigned["Full Name"].apply(_lookup)


_CR_COLS = [
    "request_id","submitted_date","requester_name","requester_email",
    "change_type","employee_id","employee_name","data_lama","data_baru",
    "alasan","status","reviewed_by","reviewed_date","catatan","change_request",
]


@st.cache_data(ttl=60)
def _load_change_requests_cached() -> pd.DataFrame:
    """Baca sheet change_requests. RAISE bila gagal: exception tidak di-cache oleh
    Streamlit, jadi kegagalan sesaat tidak 'menempel' 60 detik sebagai data kosong."""
    client = get_gspread_client()
    if not client:
        raise RuntimeError("Koneksi Google Sheets tidak tersedia")
    ws   = client.open_by_key(SHEET_ID).worksheet(SHEET_CR_NAME)
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame(columns=_CR_COLS)
    _df = pd.DataFrame(data)
    # Header toleran spasi/kapital ("Status " -> "status").
    _df.columns = [str(c).strip().lower() for c in _df.columns]
    # Status dinormalisasi: kosong/NaN dianggap Pending (belum direview).
    if "status" in _df.columns:
        _raw = _df["status"].astype(str).str.strip()
        _map = {"pending": "Pending", "in review": "In Review",
                "approved": "Approved", "rejected": "Rejected",
                "": "Pending", "nan": "Pending"}
        _df["status"] = _raw.str.lower().map(_map).fillna(_raw)
    return _df


def load_change_requests() -> pd.DataFrame:
    """[QA OPS-01] Return DataFrame; bila GAGAL dimuat, DataFrame kosong bertanda
    attrs['load_failed']=True. Pemanggil WAJIB memeriksa cr_load_failed() sebelum
    menampilkan 'belum ada request' — gagal-load BUKAN berarti nol request."""
    try:
        return _load_change_requests_cached()
    except Exception as _e:
        logger.error(f"load_change_requests gagal: {_e}")
        _empty = pd.DataFrame(columns=_CR_COLS)
        _empty.attrs["load_failed"] = True
        return _empty


load_change_requests.clear = _load_change_requests_cached.clear   # kompatibel dengan pemanggil lama


def cr_load_failed(df_) -> bool:
    return bool(getattr(df_, "attrs", {}).get("load_failed"))


def get_cr_sheet():
    """
    [FIX 30 Sep 2026] Sebelumnya exception di-swallow total (bare `except:
    return None`), sehingga kegagalan koneksi/worksheet-not-found tidak
    pernah terlihat oleh user — tombol Submit klik, tidak ada reaksi,
    tidak ada error. Sekarang alasan kegagalan disimpan ke session_state
    agar caller (save_change_request) bisa menampilkannya ke user.
    """
    client = get_gspread_client()
    if not client:
        st.session_state["_cr_sheet_error"] = "Koneksi ke Google Sheets gagal (client tidak tersedia)."
        return None
    try:
        return client.open_by_key(SHEET_ID).worksheet(SHEET_CR_NAME)
    except Exception as e:
        st.session_state["_cr_sheet_error"] = (
            f"Worksheet '{SHEET_CR_NAME}' tidak ditemukan atau tidak bisa diakses: {e}"
        )
        return None



# ══════════════════════════════════════════════════════════════════
# ACTIVITY LOG MODULE
# Mencatat setiap aktivitas user ke worksheet 'activity_log'
# Schema: timestamp | session_id | user_email | user_name | user_role
#         action_type | detail | record_count | filters_applied
#
# action_type values:
#   login          → user berhasil login
#   logout         → user logout
#   view_orgchart  → user melihat/merender org chart
#   search         → user melakukan pencarian karyawan
#   filter_change  → user mengubah filter BU/Division/SBU
#   export         → user mengekspor data (Excel/PDF)
#   view_tab       → user berpindah tab (admin only tabs)
#   acl_change     → admin mengubah ACL user
# ══════════════════════════════════════════════════════════════════

import uuid as _uuid

_LOG_COLS = [
    "timestamp", "session_id", "user_email", "user_name",
    "user_role", "action_type", "detail", "record_count", "filters_applied",
]


def _get_log_sheet():
    """Return worksheet 'activity_log'. Buat otomatis jika belum ada."""
    client = get_gspread_client()
    if not client:
        return None
    try:
        return client.open_by_key(SHEET_ID).worksheet(SHEET_LOG_NAME)
    except Exception:
        try:
            sh = client.open_by_key(SHEET_ID)
            ws = sh.add_worksheet(title=SHEET_LOG_NAME, rows=5000, cols=len(_LOG_COLS))
            ws.append_row(_LOG_COLS, value_input_option="USER_ENTERED")
            return ws
        except Exception:
            return None


def log_activity(
    action_type: str,
    detail: str = "",
    record_count: int = 0,
    filters_applied: dict = None,
) -> None:
    """
    Catat aktivitas user ke worksheet activity_log.
    Dipanggil secara non-blocking — error di sini tidak boleh crash dashboard.

    Args:
        action_type   : tipe aksi (lihat _LOG_COLS di atas)
        detail        : deskripsi singkat (misal: "BU=Technology, Div=Engineering")
        record_count  : jumlah record yang ditampilkan/diakses
        filters_applied: dict filter aktif saat aksi terjadi
    """
    try:
        user_info  = st.session_state.get("acl_user_info",
                      st.session_state.get("user_info", {}))
        session_id = st.session_state.get("session_id", "")

        # Generate session_id sekali per session login
        if not session_id:
            session_id = str(_uuid.uuid4())[:8]
            st.session_state["session_id"] = session_id

        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session_id,
            st.session_state.get("user_email", ""),
            user_info.get("name", ""),
            user_info.get("role", ""),
            action_type,
            str(detail)[:200],          # truncate agar tidak overflow cell
            str(record_count),
            str(filters_applied or {})[:200],
        ]

        ws = _get_log_sheet()
        if ws:
            ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception:
        # Silent fail — log error tidak boleh mengganggu UX
        pass


def get_activity_log(limit: int = 500) -> pd.DataFrame:
    """
    Load activity log untuk ditampilkan di Admin Panel.
    Return DataFrame kosong jika sheet tidak tersedia.
    """
    try:
        ws   = _get_log_sheet()
        if not ws:
            return pd.DataFrame(columns=_LOG_COLS)
        rows = ws.get_all_records()
        if not rows:
            return pd.DataFrame(columns=_LOG_COLS)
        df = pd.DataFrame(rows).astype(str)   # [QA REG-01] hindari tipe campuran (mis. session_id numerik) -> Arrow error
        # Tampilkan terbaru dulu, limit rows
        return df.iloc[::-1].head(limit).reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=_LOG_COLS)


def _parse_appended_row(res) -> "int | None":
    """Ambil nomor baris hasil append_row dari respons Sheets API
    (updates.updatedRange, contoh 'change_requests!A12:O12')."""
    import re as _re
    try:
        rng = (res or {}).get("updates", {}).get("updatedRange", "")
        m = _re.search(r"![A-Z]+(\d+)", rng)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def _assign_final_request_id(ws, row_no: int) -> str:
    """
    [PHASE 0 — 3 Okt 2026] Nomor tiket final ditentukan dari POSISI BARIS.
    Sheets menentukan posisi baris saat append secara atomic, jadi dua
    submission bersamaan SELALU punya posisi berbeda -> nomor berbeda.
    seq = max(jumlah baris di atas dengan prefix hari ini, nomor terbesar
    di atasnya) + 1. max() menjaga nomor tetap unik walau ada baris yang
    pernah dihapus manual.
    """
    today_str = datetime.now(_WIB).strftime("%Y%m%d")
    prefix = f"SCR-{today_str}-"
    above = [str(v) for v in ws.col_values(1)[: row_no - 1]]
    # [QA ID-01] Hitung SEMUA baris berprefix hari ini di atas baris ini (final maupun
    # sementara) supaya submission yang sedang berjalan ikut terhitung.
    n_prefixed = sum(1 for v in above if v.startswith(prefix))
    nums = [int(v[len(prefix):]) for v in above
            if v.startswith(prefix) and v[len(prefix):].isdigit()]
    seq = max(n_prefixed, max(nums) if nums else 0) + 1
    return f"{prefix}{str(seq).zfill(3)}"


def save_change_request(row_data: dict) -> bool:
    """
    [SCR-G2/G3 CHANGE — 26 Agt 2026]
    Kolom "change_request" ditambahkan di POSISI TERAKHIR (kolom ke-15),
    BUKAN disisipkan di tengah. Ini disengaja: update_cr_status() di atas
    hardcode index kolom 11-14 (status/reviewed_by/reviewed_date/catatan)
    saat memanggil ws.update_cell(). Kalau change_request disisipkan di
    tengah, semua index itu geser dan diam-diam merusak fitur
    approve/reject yang sudah production-stable. Menambah di ujung =
    zero risk ke fungsi existing.

    ⚠️ ACTION REQUIRED DI GOOGLE SHEETS (manual, satu kali):
    Buka worksheet `change_requests` di Sheet ID SHEET_ID, tambahkan
    header "change_request" di kolom O (kolom ke-15, setelah "catatan").
    Tanpa ini, append_row tetap jalan (Sheets auto-extend kolom), tapi
    header row akan kosong di kolom O sehingga get_all_records() salah
    mapping nama kolom ke data lain kalau ada yang re-order manual nanti.
    """
    ws = get_cr_sheet()
    if not ws:
        # [FIX 30 Sep 2026] Dulu silent — sekarang tampilkan alasan spesifik
        # yang disimpan get_cr_sheet() di session_state, supaya user (dan
        # kita saat debugging) langsung tahu apa yang gagal.
        reason = st.session_state.pop("_cr_sheet_error", "Sheet 'change_requests' tidak bisa diakses (tidak ada detail lebih lanjut).")
        st.error(f"❌ Gagal menyimpan request: {reason}")
        return False
    cols = ["request_id","submitted_date","requester_name","requester_email",
            "change_type","employee_id","employee_name","data_lama","data_baru",
            "alasan","status","reviewed_by","reviewed_date","catatan","change_request"]
    try:
        res = ws.append_row([str(row_data.get(c, "")) for c in cols], value_input_option="USER_ENTERED")
        # [PHASE 0 — 3 Okt 2026] Ganti nomor sementara dengan nomor final
        # berbasis posisi baris (anti-duplikat). Kalau langkah ini gagal,
        # request TETAP tersimpan dengan nomor sementara — tidak ada data hilang.
        _finalized = False
        _row_no = _parse_appended_row(res)
        if _row_no:
            for _attempt in (1, 2):
                try:
                    _final_id = _assign_final_request_id(ws, _row_no)
                    ws.update_cell(_row_no, 1, _final_id)
                    row_data["request_id"] = _final_id
                    _finalized = True
                    break
                except Exception as _e:
                    logger.warning(f"Finalisasi nomor tiket gagal (percobaan {_attempt}): {_e}")
        if not _finalized:
            logger.error(f"Tiket {row_data.get('request_id')} tersimpan dengan nomor SEMENTARA (finalisasi gagal)")
        return True
    except Exception as e:
        st.error(f"❌ Gagal menyimpan request ke sheet: {e}")
        return False


# ── SCR Module: konstanta tipe perubahan & helper JSON ────────────────
# [SCR-G2/G3] 8 tipe sesuai REQUIREMENTS.md Section 2.1 (v1.1).
CR_CHANGE_TYPES = [
    "Job Title",
    "Reporting Line",
    "Division",
    "SBU",
    "Business Unit",
    "Primary Budget Holder",
    "Secondary Budget Holder",
    "Kombinasi",
]

# Tipe dasar yang bisa dipilih di dalam mode "Kombinasi" (semua kecuali Kombinasi itu sendiri)
CR_BASE_TYPES = [t for t in CR_CHANGE_TYPES if t != "Kombinasi"]

# Mapping tipe perubahan -> nama kolom di `df` untuk ambil "data sebelum"
CR_FIELD_TO_DFCOL = {
    "Job Title":               "Job Position",
    "Reporting Line":          "Manager Name",
    "Division":                "Division",
    "SBU":                     "SBU/Tribe",
    "Business Unit":           "Business Unit",
    "Primary Budget Holder":   "Primary Budget Holder",
    "Secondary Budget Holder": "Secondary Budget Holder",
}


def build_change_request_json(field_changes: list) -> str:
    """
    Serialize list of dict {"field","before","after",...} jadi JSON string
    untuk disimpan di kolom `change_request`. Dipisah dari data_lama/data_baru
    (yang tetap diisi human-readable summary) supaya:
      - History/Inbox lama (existing rows sebelum migrasi ini) tetap bisa
        tampil normal lewat data_lama/data_baru (backward compatible)
      - Fitur ke depan (PDF Proposal Document / G4, status tracking / G5)
        bisa parse struktur per-field tanpa perlu regex string data_lama.
    """
    return json.dumps(field_changes, ensure_ascii=False)


def parse_change_request_json(raw) -> list:
    """
    Parse kolom `change_request`. Selalu return list (kosong kalau invalid/
    legacy row) — caller TIDAK PERLU try/except sendiri di tempat render.
    """
    if raw is None:
        return []
    raw = str(raw).strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _scr_pdf_lines(row: dict) -> list[str]:
    """Susun isi proposal sebagai baris netral untuk ReportLab/fallback PDF."""
    changes = parse_change_request_json(row.get("change_request", ""))
    lines = [
        "STRUCTURE CHANGE REQUEST PROPOSAL",
        f"Nomor Tiket: {row.get('request_id', '-') or '-'}",
        f"Tanggal Submit: {row.get('submitted_date', '-') or '-'}",
        f"Tanggal Approve: {row.get('reviewed_date', '-') or '-'}",
        "",
        "SUBMITTER",
        f"Nama: {row.get('requester_name', '-') or '-'}",
        f"Email: {row.get('requester_email', '-') or '-'}",
        "",
        "EMPLOYEE",
        f"Nama: {row.get('employee_name', '-') or '-'}",
        f"Employee ID: {row.get('employee_id', '-') or '-'}",
        f"Tipe Perubahan: {row.get('change_type', '-') or '-'}",
        "",
        "PERUBAHAN DISETUJUI",
    ]
    if changes:
        for change in changes:
            field = str(change.get("field", "-") or "-")
            before = str(change.get("before", "-") or "-")
            after = str(change.get("after", "-") or "-")
            lines.extend([f"{field}", f"  Sebelum: {before}", f"  Sesudah: {after}"])
            if change.get("jd_filename"):
                lines.append(f"  Job Description: {change.get('jd_filename')}")
    else:
        lines.extend([
            f"Sebelum: {row.get('data_lama', '-') or '-'}",
            f"Sesudah: {row.get('data_baru', '-') or '-'}",
        ])
    lines.extend([
        "",
        "JUSTIFIKASI",
        str(row.get("alasan", "-") or "-"),
        "",
        "REVIEW OD",
        f"Reviewer: {row.get('reviewed_by', '-') or '-'}",
        f"Catatan: {row.get('catatan', '-') or '-'}",
        "",
        "Dokumen internal untuk eksekusi People Ops.",
    ])
    return lines


def _generate_basic_pdf(lines: list[str]) -> bytes:
    """Dependency-free PDF fallback untuk runtime tanpa ReportLab."""
    wrapped = []
    for line in lines:
        wrapped.extend(textwrap.wrap(str(line), width=88, replace_whitespace=False) or [""])
    per_page = 48
    pages = [wrapped[i:i + per_page] for i in range(0, len(wrapped), per_page)] or [[""]]

    objects: dict[int, bytes] = {}
    font_id = 3
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[font_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    page_ids = []
    next_id = 4
    for page_no, page_lines in enumerate(pages, start=1):
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        page_ids.append(page_id)
        commands = ["0.26 0.20 0.71 rg", "50 785 495 32 re f", "0 g", "BT", "/F1 10 Tf", "50 760 Td"]
        for idx, line in enumerate(page_lines):
            safe = str(line).encode("cp1252", "replace").decode("cp1252")
            safe = safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            font_size = 15 if page_no == 1 and idx == 0 else 10
            commands.extend([f"/F1 {font_size} Tf", f"({safe}) Tj", "0 -14 Td"])
        commands.extend(["ET", "BT", "/F1 8 Tf", f"500 24 Td", f"(Page {page_no}/{len(pages)}) Tj", "ET"])
        stream = "\n".join(commands).encode("cp1252", "replace")
        objects[content_id] = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj_id in range(1, max(objects) + 1):
        offsets.append(len(output))
        output.extend(f"{obj_id} 0 obj\n".encode())
        output.extend(objects[obj_id])
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(output)


def generate_scr_proposal_pdf(row: dict) -> bytes:
    """Generate proposal PDF; ReportLab preferred, dependency-free fallback available."""
    lines = _scr_pdf_lines(row)
    if not REPORTLAB_OK:
        return _generate_basic_pdf(lines)

    buf = BytesIO()
    pdf = rl_canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 58

    def new_page(page_no: int):
        nonlocal y
        pdf.setFillColor(PDF_PRIMARY)
        pdf.rect(0, height - 42, width, 42, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawRightString(width - 40, height - 26, f"SCR Proposal · Page {page_no}")
        pdf.setFillColor(PDF_TEXT_DARK)
        y = height - 64

    page_no = 1
    new_page(page_no)
    for idx, line in enumerate(lines):
        is_title = idx == 0
        is_heading = line in {"SUBMITTER", "EMPLOYEE", "PERUBAHAN DISETUJUI", "JUSTIFIKASI", "REVIEW OD"}
        wrapped = textwrap.wrap(str(line), width=92) or [""]
        needed = 22 if is_title else (18 if is_heading else 14 * len(wrapped))
        if y - needed < 48:
            pdf.showPage()
            page_no += 1
            new_page(page_no)
        if is_title:
            pdf.setFont("Helvetica-Bold", 16)
            pdf.setFillColor(PDF_PRIMARY)
            pdf.drawString(42, y, line)
            y -= 26
        elif is_heading:
            pdf.setFont("Helvetica-Bold", 10)
            pdf.setFillColor(PDF_PRIMARY)
            pdf.drawString(42, y, line)
            y -= 17
        else:
            pdf.setFont("Helvetica", 9)
            pdf.setFillColor(PDF_TEXT_DARK)
            for part in wrapped:
                pdf.drawString(50, y, part)
                y -= 13
            if not line:
                y -= 4
    pdf.save()
    return buf.getvalue()


def render_scr_proposal(row: dict, theme: dict, key_prefix: str) -> None:
    """Render safe HTML preview and a PDF download button."""
    esc = lambda value: html.escape(str(value or "-"))
    changes = parse_change_request_json(row.get("change_request", ""))
    if changes:
        change_html = "".join(
            f"<tr><td>{esc(c.get('field'))}</td><td>{esc(c.get('before'))}</td><td>{esc(c.get('after'))}</td></tr>"
            for c in changes
        )
    else:
        change_html = (
            f"<tr><td>{esc(row.get('change_type'))}</td>"
            f"<td>{esc(row.get('data_lama'))}</td><td>{esc(row.get('data_baru'))}</td></tr>"
        )
    st.markdown(f"""
    <div style="background:{theme['bg3']};border:1px solid {theme['border']};border-radius:12px;padding:20px;margin:10px 0 14px 0;">
      <div style="font-size:18px;font-weight:700;color:{theme['text']};">SCR Proposal Document</div>
      <div style="font-size:12px;color:{theme['text_variant']};margin:3px 0 16px 0;">Dokumen internal untuk People Ops</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;color:{theme['text']};">
        <div><b>Nomor tiket:</b> {esc(row.get('request_id'))}</div><div><b>Tanggal submit:</b> {esc(row.get('submitted_date'))}</div>
        <div><b>Tanggal approve:</b> {esc(row.get('reviewed_date'))}</div><div><b>Tipe:</b> {esc(row.get('change_type'))}</div>
        <div><b>Submitter:</b> {esc(row.get('requester_name'))}</div><div><b>Email:</b> {esc(row.get('requester_email'))}</div>
        <div><b>Employee:</b> {esc(row.get('employee_name'))}</div><div><b>Employee ID:</b> {esc(row.get('employee_id'))}</div>
      </div>
      <table style="width:100%;border-collapse:collapse;margin-top:16px;font-size:12px;color:{theme['text']};">
        <thead><tr><th style="text-align:left;padding:8px;border-bottom:1px solid {theme['border']};">Field</th><th style="text-align:left;padding:8px;border-bottom:1px solid {theme['border']};">Sebelum</th><th style="text-align:left;padding:8px;border-bottom:1px solid {theme['border']};">Sesudah</th></tr></thead>
        <tbody>{change_html}</tbody>
      </table>
      <div style="font-size:12px;color:{theme['text']};margin-top:14px;"><b>Justifikasi:</b> {esc(row.get('alasan'))}</div>
      <div style="font-size:12px;color:{theme['text']};margin-top:8px;"><b>Reviewer OD:</b> {esc(row.get('reviewed_by'))}</div>
      <div style="font-size:12px;color:{theme['text']};margin-top:8px;"><b>Catatan OD:</b> {esc(row.get('catatan'))}</div>
    </div>
    """, unsafe_allow_html=True)
    request_id = str(row.get("request_id", "SCR")).replace("/", "-")
    st.download_button(
        "⬇️ Download Proposal PDF",
        data=generate_scr_proposal_pdf(dict(row)),
        file_name=f"{request_id}_proposal.pdf",
        mime="application/pdf",
        key=f"{key_prefix}_{request_id}",
        use_container_width=True,
    )


def update_cr_status(request_id: str, status: str, reviewed_by: str, catatan: str) -> bool:
    ws = get_cr_sheet()
    if not ws:
        return False
    try:
        # [QA ID-01] Cari persis di kolom A dan WAJIB unik. find() lama mengambil kecocokan
        # pertama, sehingga nomor ganda bisa meng-update baris yang salah.
        _cells = [c for c in ws.findall(request_id, in_column=1)
                  if str(c.value).strip() == str(request_id).strip()]
        if len(_cells) != 1:
            st.error(f"Nomor tiket {request_id} "
                     + ("tidak ditemukan." if not _cells else "ganda di sheet; keputusan diblokir sampai nomor dinormalkan."))
            return False
        row = _cells[0].row
        ws.batch_update(
        [{"range": f"K{row}:N{row}",
        "values": [[status, reviewed_by,
        datetime.now(_WIB).strftime("%Y-%m-%d %H:%M"), catatan]]}],
        value_input_option="USER_ENTERED",
        )
        return True
    except Exception as e:
        st.error(f"Gagal update: {e}")
        return False


def generate_request_id() -> str:
    """
    [QA ID-01] Nomor SEMENTARA yang UNIK-BY-CONSTRUCTION: SCR-YYYYMMDD-Txxxxxxxxxx
    (xxxxxxxxxx = 10 heks acak). Tidak membaca sheet, jadi dua submission bersamaan tidak
    pernah mendapat nomor sementara yang sama. Nomor FINAL (SCR-YYYYMMDD-NNN) ditetapkan
    di save_change_request() dari POSISI BARIS setelah append. Bila finalisasi gagal,
    tiket tetap unik dengan nomor sementara ini (tidak ada duplikat).
    """
    import uuid as _uuid_t
    return f"SCR-{datetime.now(_WIB).strftime('%Y%m%d')}-T{_uuid_t.uuid4().hex[:10].upper()}"


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


@st.cache_data(ttl=300, show_spinner=False)
def build_tree_json(full_data: pd.DataFrame, selected_div: str, root_ids: list, mode: str = "division") -> list:
    valid = full_data[full_data["Manager ID"].notna() & (full_data["Manager ID"] != "") & (full_data["Manager ID"] != "nan")]
    children_map: dict = valid.groupby("Manager ID")["Employee ID"].apply(list).to_dict()

    # Deduplicate sebelum set_index — mencegah ValueError jika masih
    # ada duplikat Employee ID yang lolos dari normalize_people_db
    _tree_df = full_data.drop_duplicates(subset=["Employee ID"], keep="last")
    info_map: dict = (
        _tree_df
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


# ══════════════════════════════════════════════════════════════════
# HoB VIEW — 22 Agt 2026 (Brief PM/CEO, P0)
# ══════════════════════════════════════════════════════════════════
# Mapping short-name di kolom "Primary Budget Holder" (kolom R Sheet)
# -> Employee ID HoB yang sesungguhnya. WAJIB manual-update dict ini
# kalau ada HoB baru atau short-name di kolom R berubah — tidak ada
# cara otomatis untuk derive ini dari data yang ada (itulah kenapa
# brief PM menyediakan tabel mapping terpisah).
HOB_MAPPING = {
    "ANTHONY":  {"name": "Anthony Johanes Kosasih",   "id": "SLKR304"},
    "SANDY":    {"name": "Sandy Suryanto",             "id": "SLKR115"},
    "JANSEN":   {"name": "Jansen Jumino",              "id": "MKR1240"},
    "AVIANDRI": {"name": "Aviandri Hidayat",           "id": "MKR639"},
    "SUWANDI":  {"name": "Suwandi Soh",                "id": "SLKR001"},
    "STEVENS":  {"name": "Stevens Jethefer",           "id": "SLKR474"},
    "STANDIE":  {"name": "Standie Nagadi",             "id": "MKR4066"},
    "ARVY":     {"name": "Arvy Egadipoera",            "id": "MKR581"},
    "SHREY":    {"name": "Shrey Shukla",               "id": "MKR1829"},
    "BRENDAN":  {"name": "Brendan Limn Rakphongpha",   "id": "MKR1132"},
}


def _normalize_hob_key(raw) -> str:
    """'  anthony ' -> 'ANTHONY'. Dipakai supaya matching kolom R tidak
    gagal cuma gara-gara beda kapitalisasi/spasi."""
    return str(raw).strip().upper()


@st.cache_data(ttl=300, show_spinner=False)
def build_hob_tree_json(full_data: pd.DataFrame, hob_ids_filter: tuple = ()) -> list:
    """
    Bangun tree untuk HoB View. Struktur (per brief PM):
        Level 0 (root) : HoB (10 orang, fixed dari HOB_MAPPING)
        Level 1        : employee yang "Primary Budget Holder"-nya (kolom R)
                         cocok dengan HoB tsb — DITENTUKAN BUKAN dari
                         Manager ID, tapi dari kolom Budget Holder.
        Level 2+       : dari titik itu turun, ikut Manager ID normal
                         (reporting line asli) — sama seperti Functional.

    Kenapa dua mekanisme digabung: brief eksplisit bilang level pertama
    dari HoB itu "C-1/Leader yang Budget Holder-nya = HoB ini", lalu
    "dst..." — tidak ada kolom Budget Holder berjenjang untuk tiap level,
    jadi begitu ketemu leader itu, sisanya ikut hierarki manager biasa.

    Known limitation (data quality, BUKAN bug logic):
    Kalau kolom Primary Budget Holder di data tidak konsisten dengan
    Manager ID asli (misal seorang staff level bawah ke-tag Budget Holder
    yang beda dari manager langsungnya), staff itu BISA muncul di 2 HoB
    sekaligus: sekali sebagai turunan wajar manager-nya, sekali lagi
    sebagai "root palsu" di HoB lain karena tag Budget Holder-nya salah.
    Ini sinyal untuk audit data, bukan sesuatu yang bisa "diperbaiki
    diam-diam" di kode — kalau ketemu kasus begini, cek data Primary
    Budget Holder karyawan tsb, jangan asumsikan kode salah.
    """
    _tree_df = full_data.drop_duplicates(subset=["Employee ID"], keep="last")
    manager_of: dict = _tree_df.set_index("Employee ID")["Manager ID"].to_dict()

    valid = full_data[full_data["Manager ID"].notna() & (full_data["Manager ID"] != "") & (full_data["Manager ID"] != "nan")]
    children_map: dict = valid.groupby("Manager ID")["Employee ID"].apply(list).to_dict()

    info_map: dict = (
        _tree_df
        .set_index("Employee ID")[["Employee Name", "Job Position", "Division", "SBU/Tribe", "Business Unit", "Primary Budget Holder"]]
        .rename(columns={"Employee Name": "name", "Job Position": "position", "Division": "division",
                         "SBU/Tribe": "sbu", "Business Unit": "bu", "Primary Budget Holder": "bh"})
        .to_dict(orient="index")
    )

    def build_node(emp_id: str, visited: set) -> dict | None:
        if emp_id in visited or emp_id not in info_map:
            return None
        visited.add(emp_id)
        info = info_map[emp_id]
        node = {
            "id": emp_id, "name": info["name"], "position": info["position"],
            "division": info["division"], "sbu": info.get("sbu", ""), "bu": info["bu"],
            "in_div": True, "children": [],
        }
        for cid in children_map.get(emp_id, []):
            child = build_node(cid, visited)
            if child:
                node["children"].append(child)
        return node

    hob_items = list(HOB_MAPPING.items())
    if hob_ids_filter:
        hob_items = [(k, v) for k, v in hob_items if v["id"] in hob_ids_filter]

    trees = []
    for short_key, hob_info in hob_items:
        hob_id = hob_info["id"]
        if hob_id not in info_map:
            # HoB-nya sendiri tidak ada di scope full_data (misal ke-filter
            # keluar oleh BU/Div/SBU filter di UI) — skip, jangan crash.
            continue

        # Kandidat level-1: siapapun yang Primary Budget Holder-nya cocok.
        candidate_ids = {
            eid for eid, info in info_map.items()
            if eid != hob_id and _normalize_hob_key(info.get("bh", "")) == short_key
        }
        # True root dari kandidat = yang manager LANGSUNG-nya BUKAN bagian
        # dari kandidat yang sama (menghindari orang yang sebenarnya cucu/
        # cicit organisasi ikut nangkring jadi "anak langsung" HoB hanya
        # karena kolom Budget Holder-nya kebetulan sama — pola yang sama
        # persis dipakai buat cari root_ids di Functional/company-wide).
        true_roots = sorted(cid for cid in candidate_ids if manager_of.get(cid, "") not in candidate_ids)

        hob_node = {
            "id": hob_id, "name": info_map[hob_id]["name"], "position": info_map[hob_id]["position"],
            "division": info_map[hob_id]["division"], "sbu": info_map[hob_id].get("sbu", ""),
            "bu": info_map[hob_id]["bu"], "in_div": True, "children": [],
        }
        _visited = {hob_id}
        for rid in true_roots:
            child = build_node(rid, _visited)
            if child:
                hob_node["children"].append(child)
        trees.append(hob_node)

    return trees


def flatten_tree_ids(node: dict) -> set:
    """Kumpulkan semua Employee ID dalam satu subtree (termasuk node itu sendiri)."""
    ids = {node["id"]}
    for c in node.get("children", []):
        ids |= flatten_tree_ids(c)
    return ids


@st.cache_data(ttl=300, show_spinner=False)
def get_hob_membership_map(full_data: pd.DataFrame) -> dict:
    """
    [HoB VIEW BUGFIX — 27 Agt 2026] emp_id -> nama HoB lengkap.
    Dipakai untuk fitur "search by name" di HoB View: begitu user cari
    seseorang, kita perlu tahu dia ada di tree HoB yang mana supaya
    filter "Filter HoB" bisa auto-select ke situ (Search harus BISA
    lintas-HoB, karena karyawan biasa TIDAK TAHU dia masuk HoB siapa
    dari data mentah — itu justru salah satu alasan HoB View ini ada).

    Dihitung dari build_hob_tree_json TANPA filter (company-wide penuh)
    supaya hasil pencarian tidak bergantung pada filter BU/Div/SBU/HoB
    yang sedang aktif di UI saat ini.
    """
    trees = build_hob_tree_json(full_data, hob_ids_filter=())
    membership = {}
    for hob_node in trees:
        for eid in flatten_tree_ids(hob_node):
            membership[eid] = hob_node["name"]
    return membership


@st.cache_data(ttl=300, show_spinner=False)
def get_level_from_root(root_id: str, all_df: pd.DataFrame, max_depth: int = 5) -> dict:
    """
    [Diekstrak ke module-level — 27 Agt 2026, fix bug overlay HoB]
    Definisi RESMI "Chief/C-1/C-2" di aplikasi ini: BFS level dari
    CHIEF_ROOT yang FIXED (SLKR001), BUKAN dari root lokal tree yang
    kebetulan sedang dirender di layar (yang berubah-ubah tergantung
    filter Divisi/BU aktif). Sebelumnya fungsi ini cuma didefinisikan
    inline di dalam tab Daftar Manager — sekarang jadi module-level
    supaya HoB Overlay bisa pakai definisi C-1 yang PERSIS SAMA. Kalau
    dua tempat ini sampai punya definisi "C-1" yang beda, itu bug kelas
    berat (data leadership yang salah ditampilkan ke CEO).
    """
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


@st.cache_data(ttl=300, show_spinner=False)
def annotate_hob_overlay(tree_nodes: list, scope_data: pd.DataFrame) -> list:
    """
    [HoB OVERLAY — 27 Agt 2026, brief PM/CEO]
    [FIX #5 — FINAL, konfirmasi eksplisit Dave 27 Agt 2026]

    "C-1" = employee yang berada PERSIS di local depth 2 dari CEO
    (CHIEF_ROOT), FIXED/SERAGAM di SELURUH cabang organisasi — Dave
    mengonfirmasi eksplisit ini FIXED, bukan bervariasi per cabang.
    "Depth 2" di sini pakai terminologi yang SAMA dengan dropdown
    "Expand Level" yang sudah ada di UI org chart (Top Level=depth0,
    Level 1=depth1, Level 2=depth2, dst) — CEO sendiri = Top Level,
    direct report CEO = Level 1, dan cucu-report (Level 2) = C-1.

    Riwayat 4 iterasi sebelum versi final ini (didokumentasikan supaya
    ada yang buka kode ini nanti tidak bingung kenapa ada v1-v5):
      v1 (salah): "C-1" = anak langsung root LOKAL yang sedang
        ditampilkan — gagal di mode Per Divisi / cabang dengan Chief
        tambahan (CEO -> CTO -> VP, VP-nya yang harusnya C-1).
      v2 (ditolak PM saat itu): "C-1" = hierarchy level generik dari
        CHIEF_ROOT (get_level_from_root level==1) — PM bilang ini
        konsepnya salah, definisi Chief/C-1/C-2 itu milik tab Daftar
        Manager, bukan cara yang tepat untuk overlay ini.
      v3 (ditolak juga): overlay ditempel ke SIAPAPUN yang Primary
        Budget Holder-nya terisi, di depth manapun — muncul di banyak
        node sekaligus (termasuk staff), bukan cuma satu label per C-1.
      v4 (ditolak juga setelah screenshot lanjutan): definisi structural
        murni (manager_id chain via C-Level ber-BU=Management) — secara
        konsep benar tapi ternyata BUKAN yang dimaksud Dave.
    v5/final (versi ini): Dave eksplisit mengonfirmasi definisinya balik
    ke "depth FIXED dari CEO" — SECARA MATEMATIS ini SAMA dengan v2
    (get_level_from_root level==1 = Level 2 versi UI, lihat catatan
    off-by-one di bawah), bedanya kali ini dikonfirmasi eksplisit oleh
    Dave sebagai aturan yang FIXED di semua cabang (bukan asumsi generik
    yang jadi alasan v2 ditolak dulu). Definisi structural v4 (fungsi
    get_c1_employee_ids, BU=Management) SUDAH TIDAK DIPAKAI di sini —
    kalau butuh riwayatnya, cek versi file sebelumnya.

    ⚠️ CATATAN OFF-BY-ONE: get_level_from_root() (dipakai bareng tab
    Daftar Manager) mulai hitung dari 0 untuk ANAK LANGSUNG CEO —
    artinya level==0 di fungsi itu = "Level 1" versi UI, level==1 =
    "Level 2" versi UI. Makanya syarat di bawah cek `level == 1`, BUKAN
    `level == 2` — kalau bingung kenapa angkanya beda dari kata
    "Level 2" yang diucapkan Dave, inilah alasannya.
    """
    hierarchy_levels = get_level_from_root(CHIEF_ROOT, df, max_depth=6)   # SELALU company-wide, bukan scope_data yang sudah difilter
    bh_map = (
        scope_data.drop_duplicates(subset=["Employee ID"], keep="last")
        .set_index("Employee ID")["Primary Budget Holder"]
        .to_dict()
    )

    def walk(node: dict) -> None:
        if hierarchy_levels.get(node["id"]) == 1:   # "Level 2" versi UI — lihat catatan off-by-one di atas
            hob_key  = _normalize_hob_key(bh_map.get(node["id"], ""))
            hob_info = HOB_MAPPING.get(hob_key)
            if hob_info:
                node["hob_overlay"] = hob_info["name"]
        for child in node.get("children", []):
            walk(child)

    for root in tree_nodes:
        walk(root)
    return tree_nodes


def _render_chart_iframe(html: str, height: int = 680, scrolling: bool = False) -> None:
    """
    Wrapper kompatibel untuk render HTML org chart di iframe.
    `st.components.v1.html` resmi deprecated, deadline removal 2026-06-01 (sudah lewat).
    API baru `st.iframe` punya signature berbeda (mungkin tidak menerima `scrolling`),
    jadi wrapper ini mencoba st.iframe dulu dengan beberapa fallback signature,
    dan baru fallback ke st.components.v1.html kalau semuanya gagal — org chart
    tidak boleh crash total hanya karena perbedaan versi Streamlit.
    """
    if hasattr(st, "iframe"):
        try:
            st.iframe(html, height=height, scrolling=scrolling)
            return
        except TypeError:
            pass
        except Exception:
            logger.warning("st.iframe gagal render, fallback ke components.v1.html")
        try:
            st.iframe(html, height=height)
            return
        except Exception:
            logger.warning("st.iframe (tanpa scrolling) gagal render, fallback ke components.v1.html")
    st.components.v1.html(html, height=height, scrolling=scrolling)


def to_excel(dataframe: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Data")
    return output.getvalue()


# ══════════════════════════════════════════════════════════════════
# PDF GENERATORS
# ══════════════════════════════════════════════════════════════════

# ── Palette PDF (light/print-friendly) ─────────────────────────
PDF_BG          = colors.HexColor("#FFFFFF")
PDF_PAGE_BG     = colors.HexColor("#F5F4FF")
PDF_PRIMARY     = colors.HexColor("#4234b6")
PDF_PRIMARY_LT  = colors.HexColor("#EDE9FE")
PDF_PRIMARY_MID = colors.HexColor("#7C6FCD")
PDF_TEXT_DARK   = colors.HexColor("#1a1b21")
PDF_TEXT_MID    = colors.HexColor("#3a3a4a")
PDF_TEXT_MUTED  = colors.HexColor("#6b6b80")
PDF_OUT_BG      = colors.HexColor("#E8EAF0")
PDF_OUT_BDR     = colors.HexColor("#9098B8")
PDF_OUT_TXT     = colors.HexColor("#2a2d40")
PDF_CONNECTOR   = colors.HexColor("#A89FE0")
PDF_ACCENT_BAR  = colors.HexColor("#4234b6")


def _draw_pdf_header(c, page_w, page_h, title_text, subtitle, total_nodes, downloaded_at, div_name, bu_name):
    """
    Header profesional:
    - Bar ungu di atas
    - Logo placeholder "mekari" teks
    - Judul chart (nama divisi)
    - Metadata: BU, Divisi, Tanggal unduh, Total karyawan
    """
    HEADER_H = 100

    # Bar aksen atas
    c.setFillColor(PDF_PRIMARY)
    c.rect(0, page_h - 6, page_w, 6, fill=1, stroke=0)

    # Header background putih
    c.setFillColor(PDF_BG)
    c.rect(0, page_h - HEADER_H - 6, page_w, HEADER_H, fill=1, stroke=0)

    # Garis bawah header
    c.setStrokeColor(PDF_PRIMARY_MID)
    c.setLineWidth(0.5)
    c.line(0, page_h - HEADER_H - 6, page_w, page_h - HEADER_H - 6)

    # Logo "mekari" teks + bintang
    logo_x, logo_y = 36, page_h - 36
    c.setFillColor(PDF_PRIMARY)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(logo_x + 16, logo_y - 12, "mekari")
    # bintang sederhana: lingkaran kecil
    c.circle(logo_x + 5, logo_y - 8, 5, fill=1, stroke=0)

    # Judul utama (nama chart)
    c.setFillColor(PDF_TEXT_DARK)
    c.setFont("Helvetica-Bold", 14)
    # Potong jika terlalu panjang
    t = title_text if len(title_text) <= 90 else title_text[:87] + "..."
    c.drawString(logo_x, logo_y - 28, t)

    # Metadata baris: Divisi · BU · Tanggal · Total
    meta_parts = []
    if div_name:  meta_parts.append(f"Divisi: {div_name}")
    if bu_name:   meta_parts.append(f"BU: {bu_name}")
    meta_parts.append(f"Diunduh: {downloaded_at}")
    meta_parts.append(f"Total ditampilkan: {total_nodes} karyawan")

    c.setFillColor(PDF_TEXT_MUTED)
    c.setFont("Helvetica", 8)
    meta_str = "   ·   ".join(meta_parts)
    c.drawString(logo_x, logo_y - 44, meta_str)

    if subtitle:
        c.setFont("Helvetica", 8)
        c.setFillColor(PDF_TEXT_MUTED)
        c.drawString(logo_x, logo_y - 56, subtitle)


def _draw_pdf_footer(c, page_w, downloaded_at):
    """Footer tipis dengan timestamp dan konfidensialitas."""
    c.setStrokeColor(PDF_PRIMARY_MID)
    c.setLineWidth(0.5)
    c.line(36, 28, page_w - 36, 28)
    c.setFillColor(PDF_TEXT_MUTED)
    c.setFont("Helvetica", 7)
    c.drawString(36, 18, f"Dokumen ini bersifat konfidensial — dicetak {downloaded_at} — Mekari People Dashboard")
    c.drawRightString(page_w - 36, 18, "People Organization Dashboard")


def _wrap_text(text: str, max_chars: int) -> list:
    """Potong teks menjadi baris-baris maks max_chars karakter, tidak potong kata."""
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines if lines else [text[:max_chars]]


def generate_pdf(tree_nodes, title_text, div_name="", bu_name="", max_level="all"):
    """
    PDF Full — node lebih besar, nama+posisi+SBU lengkap,
    header profesional dengan metadata waktu & divisi.

    `max_level` menyesuaikan dokumen dengan filter "Expand Level" yang
    sedang aktif di layar ("all" / "top" / "level1") — konsisten dengan
    `level_map` yang dipakai render_org_chart(), agar isi PDF selalu
    mencerminkan struktur yang sedang dicek user, bukan selalu full tree.
    """
    if not REPORTLAB_OK:
        raise ImportError("ReportLab tidak tersedia")

    # Node dimensions — lebih besar untuk muat 4 baris teks
    NODE_W, NODE_H = 180, 76
    H_GAP, V_GAP   = 20, 52
    HEADER_H        = 100  # ruang header di atas
    FOOTER_H        = 44   # ruang footer di bawah

    downloaded_at = datetime.now(_WIB).strftime("%d %B %Y, %H:%M WIB")

    # ── Trim tree sesuai Expand Level filter yang aktif di layar ──────
    _level_depth_map = {"all": None, "top": 0, "level1": 1, "level2": 2, "level3": 3}
    _max_d = _level_depth_map.get(max_level, None)

    def _trim_by_level(node, depth=0):
        if _max_d is not None and depth > _max_d:
            return None
        trimmed = dict(node)
        trimmed["children"] = [
            ch2 for ch2 in [_trim_by_level(ch, depth + 1) for ch in node.get("children", [])] if ch2
        ] if (_max_d is None or depth < _max_d) else []
        return trimmed

    tree_nodes = [t for t in [_trim_by_level(r) for r in tree_nodes] if t]

    _level_subtitle_map = {
        "all": "Organization Chart — Full Structure",
        "top": "Organization Chart — Top Level Only",
        "level1": "Organization Chart — s/d Level 1",
        "level2": "Organization Chart — s/d Level 2",
        "level3": "Organization Chart — s/d Level 3",
    }

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

    total_w   = sum(calc_subtree_width(r) for r in tree_nodes) + H_GAP * (len(tree_nodes) - 1)
    max_depth = [0]

    def get_depth(node, d=0):
        max_depth[0] = max(max_depth[0], d)
        for ch in node["children"]:
            get_depth(ch, d + 1)
    for r in tree_nodes:
        get_depth(r)

    total_h = (max_depth[0] + 1) * (NODE_H + V_GAP) + HEADER_H + FOOTER_H + 60
    page_w  = max(total_w + 120, landscape(A3)[0])
    page_h  = max(total_h, landscape(A3)[1])

    x_start = page_w / 2 - total_w / 2
    y_top   = page_h - HEADER_H - NODE_H / 2 - 28
    for root in tree_nodes:
        rw = calc_subtree_width(root)
        assign_positions(root, x_start + rw / 2, y_top)
        x_start += rw + H_GAP

    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=(page_w, page_h))

    # Background halaman
    c.setFillColor(PDF_PAGE_BG)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Header & Footer
    _draw_pdf_header(c, page_w, page_h, title_text,
                     subtitle=_level_subtitle_map.get(max_level, "Organization Chart — Full Structure"),
                     total_nodes=len(draw_order),
                     downloaded_at=downloaded_at,
                     div_name=div_name, bu_name=bu_name)
    _draw_pdf_footer(c, page_w, downloaded_at)

    # Konektor antar node
    c.setStrokeColor(PDF_CONNECTOR)
    c.setLineWidth(1.2)
    for node in draw_order:
        if node["id"] not in positions:
            continue
        nx, ny = positions[node["id"]]
        for child in node["children"]:
            if child["id"] not in positions:
                continue
            cx, cy  = positions[child["id"]]
            mid_y   = (ny - NODE_H / 2 + cy + NODE_H / 2) / 2
            c.line(nx, ny - NODE_H / 2, nx, mid_y)
            c.line(nx, mid_y, cx, mid_y)
            c.line(cx, mid_y, cx, cy + NODE_H / 2)

    # Node cards
    for node in draw_order:
        if node["id"] not in positions:
            continue
        nx, ny    = positions[node["id"]]
        x_left    = nx - NODE_W / 2
        y_bottom  = ny - NODE_H / 2
        in_div    = node.get("in_div", True)
        emp_id    = node.get("id", "")
        name      = node.get("name", "")
        position  = node.get("position", "")
        sbu       = node.get("sbu", "")
        division  = node.get("division", "")

        if in_div:
            fill_c = PDF_PRIMARY_LT
            txt_c  = PDF_TEXT_DARK
            bdr_c  = PDF_PRIMARY_MID
            bar_c  = PDF_PRIMARY
        else:
            fill_c = PDF_OUT_BG
            txt_c  = PDF_OUT_TXT
            bdr_c  = PDF_OUT_BDR
            bar_c  = PDF_OUT_BDR

        # Card background
        c.setFillColor(fill_c)
        c.setStrokeColor(bdr_c)
        c.setLineWidth(0.8)
        c.roundRect(x_left, y_bottom, NODE_W, NODE_H, 6, fill=1, stroke=1)

        # Accent bar kiri
        c.setFillColor(bar_c)
        c.roundRect(x_left, y_bottom, 3, NODE_H, 3, fill=1, stroke=0)

        # Teks dalam card — y dari atas ke bawah
        text_x  = nx          # center

        # Baris 1: Nama (bold, bisa 2 baris jika panjang)
        name_lines = _wrap_text(name, 22)
        c.setFillColor(txt_c)
        c.setFont("Helvetica-Bold", 9)
        if len(name_lines) >= 2:
            c.drawCentredString(text_x, y_bottom + NODE_H - 16, name_lines[0])
            c.drawCentredString(text_x, y_bottom + NODE_H - 27, name_lines[1])
            pos_y = y_bottom + NODE_H - 40
        else:
            c.drawCentredString(text_x, y_bottom + NODE_H - 20, name_lines[0])
            pos_y = y_bottom + NODE_H - 33

        # Baris 2: Posisi (wrap 2 baris maks)
        pos_lines = _wrap_text(position, 24)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(PDF_TEXT_MID if in_div else PDF_TEXT_MUTED)
        for li, pl in enumerate(pos_lines[:2]):
            c.drawCentredString(text_x, pos_y - li * 10, pl)
        sbu_y = pos_y - len(pos_lines[:2]) * 10 - 5

        # Baris 3: SBU/Tribe (jika ada)
        sbu_clean = sbu.strip() if sbu and sbu.strip() not in ("", "nan") else ""
        if sbu_clean and sbu_y > y_bottom + 6:
            c.setFont("Helvetica-Oblique", 6.5)
            c.setFillColor(PDF_PRIMARY if in_div else PDF_OUT_BDR)
            sbu_disp = sbu_clean[:30] + "…" if len(sbu_clean) > 30 else sbu_clean
            c.drawCentredString(text_x, sbu_y, sbu_disp)


    # Legend
    leg_x, leg_y = 36, FOOTER_H + 8
    items = [
        (PDF_PRIMARY_LT, PDF_PRIMARY_MID, "Karyawan divisi ini"),
        (PDF_OUT_BG,     PDF_OUT_BDR,     "Atasan dari divisi lain"),
    ]
    for li, (f, b, lbl) in enumerate(items):
        ox = leg_x + li * 170
        c.setFillColor(f); c.setStrokeColor(b); c.setLineWidth(0.7)
        c.roundRect(ox, leg_y, 12, 9, 2, fill=1, stroke=1)
        c.setFillColor(PDF_TEXT_MUTED); c.setFont("Helvetica", 7)
        c.drawString(ox + 16, leg_y + 1, lbl)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def generate_pdf_summary(tree_nodes, title_text, div_name="", bu_name=""):
    """
    PDF Summary — tampilkan hingga Level 3, node lebih informatif,
    header profesional, nama + posisi + SBU lengkap (Level 0-2),
    posisi-only compact card untuk Level 3.
    """
    if not REPORTLAB_OK:
        raise ImportError("ReportLab tidak tersedia")

    NODE_W_FULL, NODE_H_FULL = 190, 82
    NODE_W_L2,   NODE_H_L2   = 160, 72
    NODE_W_L3,   NODE_H_L3   = 130, 46   # depth 3 — position-only card
    H_GAP, V_GAP = 18, 48
    HEADER_H     = 100
    FOOTER_H     = 44

    downloaded_at = datetime.now(_WIB).strftime("%d %B %Y, %H:%M WIB")

    def trim_tree(node, depth=0):
        if depth > 3:
            return None
        trimmed = dict(node)
        trimmed["_depth"]   = depth
        trimmed["children"] = [] if depth >= 3 else [
            ch2 for ch2 in [trim_tree(ch, depth + 1) for ch in node.get("children", [])] if ch2
        ]
        return trimmed

    trimmed_roots = [t for t in [trim_tree(r) for r in tree_nodes] if t]

    def node_w(n): return NODE_W_FULL if n["_depth"] < 2 else (NODE_W_L2 if n["_depth"] == 2 else NODE_W_L3)
    def node_h(n): return NODE_H_FULL if n["_depth"] < 2 else (NODE_H_L2 if n["_depth"] == 2 else NODE_H_L3)

    def subtree_width(n):
        if not n["children"]:
            return node_w(n)
        return max(
            sum(subtree_width(ch) for ch in n["children"]) + H_GAP * (len(n["children"]) - 1),
            node_w(n)
        )

    positions, draw_list = {}, []

    def assign_pos(node, x_center, y):
        positions[node["id"]] = (x_center, y, node["_depth"])
        draw_list.append(node)
        if not node["children"]:
            return
        total_w = sum(subtree_width(ch) for ch in node["children"]) + H_GAP * (len(node["children"]) - 1)
        x_start = x_center - total_w / 2
        child_y = y - node_h(node) / 2 - V_GAP - node_h(node) / 2
        for child in node["children"]:
            cw = subtree_width(child)
            assign_pos(child, x_start + cw / 2, child_y)
            x_start += cw + H_GAP

    def max_depth_tree(node):
        if not node["children"]:
            return node["_depth"]
        return max(max_depth_tree(ch) for ch in node["children"])

    actual_max = max((max_depth_tree(r) for r in trimmed_roots), default=0)
    total_w    = sum(subtree_width(r) for r in trimmed_roots) + H_GAP * (len(trimmed_roots) - 1)
    total_h    = (actual_max + 1) * (NODE_H_FULL + V_GAP) + HEADER_H + FOOTER_H + 60
    page_w = max(total_w + 120, landscape(A3)[0])
    page_h = max(total_h, landscape(A3)[1])

    x_start = page_w / 2 - total_w / 2
    y_top   = page_h - HEADER_H - NODE_H_FULL / 2 - 28
    for root in trimmed_roots:
        rw = subtree_width(root)
        assign_pos(root, x_start + rw / 2, y_top)
        x_start += rw + H_GAP

    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=(page_w, page_h))

    # Background
    c.setFillColor(PDF_PAGE_BG)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Header & Footer
    _draw_pdf_header(c, page_w, page_h, title_text,
                     subtitle=f"Organization Chart — Summary (s/d Level 3)",
                     total_nodes=len(draw_list),
                     downloaded_at=downloaded_at,
                     div_name=div_name, bu_name=bu_name)
    _draw_pdf_footer(c, page_w, downloaded_at)

    # Level labels di sisi kiri
    y_seen = {}
    for node in draw_list:
        _, ny, depth = positions[node["id"]]
        if depth not in y_seen:
            y_seen[depth] = ny
    for depth, lbl in {0: "Top Level", 1: "Level 1", 2: "Level 2", 3: "Level 3"}.items():
        if depth in y_seen:
            c.setFillColor(PDF_TEXT_MUTED)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(8, y_seen[depth] - 4, lbl)

    # Konektor
    c.setStrokeColor(PDF_CONNECTOR)
    c.setLineWidth(1.2)
    for node in draw_list:
        nx, ny, _ = positions[node["id"]]
        nh = node_h(node)
        for child in node["children"]:
            if child["id"] not in positions:
                continue
            cx, cy, _ = positions[child["id"]]
            ch2 = node_h(child)
            mid = (ny - nh / 2 + cy + ch2 / 2) / 2
            c.line(nx, ny - nh / 2, nx, mid)
            c.line(nx, mid, cx, mid)
            c.line(cx, mid, cx, cy + ch2 / 2)

    # Node cards
    for node in draw_list:
        nx, ny, depth = positions[node["id"]]
        nw, nh  = node_w(node), node_h(node)
        x_left  = nx - nw / 2
        y_bot   = ny - nh / 2
        in_div  = node.get("in_div", True)
        emp_id  = node.get("id", "")
        name    = node.get("name", "")
        position = node.get("position", "")
        sbu     = node.get("sbu", "")
        division = node.get("division", "")

        if in_div:
            fill_c, bdr_c, bar_c = PDF_PRIMARY_LT, PDF_PRIMARY_MID, PDF_PRIMARY
            name_c = PDF_TEXT_DARK
            pos_c  = PDF_TEXT_MID
        else:
            fill_c, bdr_c, bar_c = PDF_OUT_BG, PDF_OUT_BDR, PDF_OUT_BDR
            name_c = PDF_OUT_TXT
            pos_c  = PDF_TEXT_MUTED

        # Card
        c.setFillColor(fill_c)
        c.setStrokeColor(bdr_c)
        c.setLineWidth(0.8)
        c.roundRect(x_left, y_bot, nw, nh, 6, fill=1, stroke=1)

        # Accent bar kiri
        c.setFillColor(bar_c)
        c.roundRect(x_left, y_bot, 3, nh, 3, fill=1, stroke=0)

        if depth >= 3:
            # ── Depth 3: hanya tampilkan Job Position ───────────────────────
            # Satu baris posisi di tengah card — nama tidak ditampilkan
            # agar card tetap compact dan terbaca di halaman.
            pos_lines_l3 = _wrap_text(position, 20)
            c.setFillColor(pos_c)
            c.setFont("Helvetica", 7)
            card_mid_y = y_bot + nh / 2
            if len(pos_lines_l3) >= 2:
                c.drawCentredString(nx, card_mid_y + 5, pos_lines_l3[0])
                c.drawCentredString(nx, card_mid_y - 5, pos_lines_l3[1])
            else:
                c.drawCentredString(nx, card_mid_y - 3, pos_lines_l3[0])
        else:
            # ── Depth 0-2: nama + posisi + SBU (layout existing) ─────────────
            name_lines = _wrap_text(name, 24 if depth < 2 else 20)
            c.setFillColor(name_c)
            font_size_name = 9.5 if depth < 2 else 9
            c.setFont("Helvetica-Bold", font_size_name)
            line_h_name = 11
            if len(name_lines) >= 2:
                c.drawCentredString(nx, y_bot + nh - 17, name_lines[0])
                c.drawCentredString(nx, y_bot + nh - 17 - line_h_name, name_lines[1])
                pos_y = y_bot + nh - 17 - line_h_name - 13
            else:
                c.drawCentredString(nx, y_bot + nh - 20, name_lines[0])
                pos_y = y_bot + nh - 20 - 13

            # Posisi (italic, wrap)
            pos_lines = _wrap_text(position, 26 if depth < 2 else 22)
            c.setFillColor(pos_c)
            c.setFont("Helvetica", 7.5 if depth < 2 else 7)
            for li, pl in enumerate(pos_lines[:2]):
                c.drawCentredString(nx, pos_y - li * 10, pl)
            sbu_y = pos_y - len(pos_lines[:2]) * 10 - 6

            # Divisi (jika out-of-div, tampilkan divisi aslinya)
            if not in_div and division and sbu_y > y_bot + 16:
                div_short = division[:24] + "…" if len(division) > 24 else division
                c.setFont("Helvetica", 6)
                c.setFillColor(PDF_TEXT_MUTED)
                c.drawCentredString(nx, sbu_y, div_short)
                sbu_y -= 9

            # SBU
            sbu_clean = sbu.strip() if sbu and sbu.strip() not in ("", "nan") else ""
            if sbu_clean and sbu_y > y_bot + 7:
                c.setFont("Helvetica-Oblique", 6.5)
                c.setFillColor(PDF_PRIMARY if in_div else PDF_OUT_BDR)
                sbu_disp = sbu_clean[:26] + "…" if len(sbu_clean) > 26 else sbu_clean
                c.drawCentredString(nx, sbu_y, sbu_disp)


    # Legend
    leg_x, leg_y = 36, FOOTER_H + 8
    for li, (f, b, lbl) in enumerate([
        (PDF_PRIMARY_LT, PDF_PRIMARY_MID, "Karyawan divisi ini"),
        (PDF_OUT_BG,     PDF_OUT_BDR,     "Atasan dari divisi lain"),
    ]):
        ox = leg_x + li * 170
        c.setFillColor(f); c.setStrokeColor(b); c.setLineWidth(0.7)
        c.roundRect(ox, leg_y, 12, 9, 2, fill=1, stroke=1)
        c.setFillColor(PDF_TEXT_MUTED); c.setFont("Helvetica", 7)
        c.drawString(ox + 16, leg_y + 1, lbl)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ══════════════════════════════════════════════════════════════════
# ORG CHART HTML RENDERER
# ══════════════════════════════════════════════════════════════════
def render_org_chart(tree_json_str, chart_height=700, initial_level="all", theme=None, highlight_id=None, labels=None):
    # Convert highlight_id ke JS literal
    highlight_id_js = f'"{highlight_id}"' if highlight_id else 'null'
    level_map = {"all": "999", "top": "0", "level1": "1", "level2": "2", "level3": "3"}
    init_depth = level_map.get(initial_level, "999")
    th          = theme or {}
    lb          = labels or {}
    lbl_in_div      = lb.get("chart_legend_in_div",      "Divisi ini")
    lbl_out_div     = lb.get("chart_legend_out_div",     "Atasan luar divisi")
    lbl_subordinate = lb.get("chart_legend_subordinate", "Jml subordinate")
    lbl_searched    = lb.get("chart_legend_searched",    "Karyawan dicari")
    lbl_tip         = lb.get("chart_legend_tip",         "💡 Klik node · Scroll zoom · Drag geser")
    lbl_expand      = lb.get("chart_tooltip_expand",     "Klik untuk expand")
    lbl_collapse    = lb.get("chart_tooltip_collapse",   "Klik untuk collapse")
    lbl_hidden      = lb.get("chart_hidden_suffix",      "tersembunyi")
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
    hint_color  = th.get("text_variant",  "#9e9ec0")

    return f"""
<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: {bg}; font-family: 'Inter', sans-serif; overflow: hidden; width: 100%; height: {chart_height}px; }}
  .toolbar {{ position: fixed; top: 12px; right: 16px; display: flex; flex-direction: column; gap: 6px; z-index: 100; }}
  .tb-btn {{ width: 34px; height: 34px; background: {tb_bg}; border: 1px solid {tb_border}; border-radius: 8px; color: {tb_color}; font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s; user-select: none; box-shadow: 0 1px 4px rgba(142,148,242,0.08); }}
  .tb-btn:hover {{ background: {node_in_bg}; border-color: {node_in_bdr}; box-shadow: 0 2px 12px rgba(142,148,242,0.16); transform: translateY(-1px); }}
  .zoom-label {{ background: {tb_bg}; border: 1px solid {tb_border}; border-radius: 6px; color: {hint_color}; font-size: 10px; font-weight: 600; text-align: center; padding: 4px 0; letter-spacing: 0.04em; }}
  #canvas {{ width: 100%; height: 100%; overflow: hidden; cursor: grab; position: relative; }}
  #canvas:active {{ cursor: grabbing; }}
  #tree-root {{ position: absolute; top: 40px; left: 50%; transform-origin: top center; display: flex; flex-direction: row; gap: 24px; align-items: flex-start; }}
  .node-wrapper {{ display: flex; flex-direction: column; align-items: center; }}
  .node-box {{ padding: 12px 16px; border-radius: 8px; text-align: center; min-width: 160px; max-width: 210px; cursor: pointer; border: 1px solid transparent; transition: all 0.18s ease; position: relative; user-select: none; box-shadow: 0 1px 8px rgba(142,148,242,0.08); }}
  .node-box:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(142,148,242,0.18); }}
  .node-box.in-div {{ background: {node_in_bg}; border-color: {node_in_bdr}; color: {node_in_txt}; }}
  .node-box.out-div {{ background: {node_out_bg}; border-color: {node_out_bdr}; color: {node_out_txt}; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
  .node-box.company-mode {{ background: linear-gradient(135deg,#5b4fcf,#7c6fcd); border-color: #4a3fb8; color: white; box-shadow: 0 4px 20px rgba(91,79,207,0.3); }}
  .node-box.highlighted {{
    background: linear-gradient(135deg,#fbbf24,#f59e0b) !important;
    border-color: #d97706 !important;
    color: #1a1a00 !important;
    box-shadow: 0 0 0 3px #fde68a, 0 8px 32px rgba(245,158,11,0.5) !important;
    animation: pulse-highlight 1.6s ease-in-out infinite !important;
    z-index: 10;
    position: relative;
  }}
  .node-box.highlighted .node-name {{ color: #1a1a00 !important; font-weight: 800 !important; }}
  .node-box.highlighted .node-pos,
  .node-box.highlighted .node-div,
  .node-box.highlighted .node-sbu {{ color: #3a2800 !important; opacity: 0.85 !important; }}
  @keyframes pulse-highlight {{
    0%   {{ box-shadow: 0 0 0 3px #fde68a, 0 8px 32px rgba(245,158,11,0.5); transform: scale(1); }}
    50%  {{ box-shadow: 0 0 0 8px rgba(253,230,138,0.3), 0 12px 40px rgba(245,158,11,0.7); transform: scale(1.04); }}
    100% {{ box-shadow: 0 0 0 3px #fde68a, 0 8px 32px rgba(245,158,11,0.5); transform: scale(1); }}
  }}
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
  .legend {{ position: fixed; bottom: 16px; left: 16px; display: flex; gap: 16px; font-size: 11px; color: {hint_color}; background: {tb_bg}; padding: 8px 14px; border-radius: 8px; border: 1px solid {tb_border}; box-shadow: 0 1px 8px rgba(142,148,242,0.10); }}
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
  <div class="legend-item"><div class="legend-dot" style="background:{node_in_bdr};border:1px solid {node_in_bdr}"></div><span>{lbl_in_div}</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:{node_out_bdr};border:1px solid {node_out_bdr}"></div><span>{lbl_out_div}</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:#f59e0b;border-radius:999px"></div><span>{lbl_subordinate}</span></div>
  <div class="legend-item" id="legend-highlight" style="display:none;">
    <div class="legend-dot" style="background:#f59e0b;border:2px solid #d97706;border-radius:3px;"></div>
    <span style="color:{hint_color}">{lbl_searched}</span>
  </div>
  <div class="legend-item" style="color:{hint_color}">{lbl_tip}</div>
</div>
<script>
const treeData = {tree_json_str};
const collapsed = {{}};
let initDepth = {init_depth};
const highlightId = {highlight_id_js};  // null or "EMP_ID" 
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
canvas.addEventListener('wheel', (e) => {{ e.preventDefault(); const delta = e.deltaY > 0 ? -0.04 : 0.04; scale = Math.max(0.2, Math.min(3, scale + delta)); applyTransform(); }}, {{ passive: false }});
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
  const isHighlight = highlightId && node.id === highlightId;
  const wrapper = document.createElement('div'); wrapper.className = 'node-wrapper';
  const box     = document.createElement('div');
  const baseClass = node.company_mode ? 'company-mode' : node.in_div ? 'in-div' : 'out-div';
  box.className = `node-box ${{baseClass}}${{isHighlight ? ' highlighted' : ''}}`;
  box.dataset.nodeId = node.id;  // [HoB OVERLAY] dipakai drawHobOverlay() buat cari posisi node
  if (isHighlight) {{ box.id = 'highlighted-node'; }}
  if (hasChildren && descCount > 0) {{
    const badge = document.createElement('div'); badge.className = 'badge';
    badge.textContent = isCollapsed ? descCount : node.children.length; box.appendChild(badge);
  }}
  ['name','position','division'].forEach(k => {{ const el = document.createElement('div'); el.className = `node-${{k}}`; el.textContent = node[k]; box.appendChild(el); }});
  if (node.sbu && node.sbu !== '' && node.sbu !== 'nan') {{
    const sbuEl = document.createElement('div'); sbuEl.className = 'node-sbu'; sbuEl.textContent = node.sbu; box.appendChild(sbuEl);
  }}
  if (hasChildren) {{ box.addEventListener('click', () => {{ collapsed[node.id] = !collapsed[node.id]; rerenderTree(); }}); box.title = isCollapsed ? '{lbl_expand}' : '{lbl_collapse}'; }}
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
    const hint = document.createElement('div'); hint.className = 'collapsed-hint'; hint.textContent = `▼ ${{descCount}} {lbl_hidden}`; wrapper.appendChild(hint);
  }}
  return wrapper;
}}
function scrollToHighlighted() {{
  const el = document.getElementById('highlighted-node');
  if (!el) return;

  function doPan() {{
    // offsetLeft/Top = posisi natural SEBELUM transform — lebih akurat
    // dari getBoundingClientRect() yang mengembalikan posisi SETELAH scale.
    const elNaturalX = el.offsetLeft + el.offsetWidth  / 2;
    const elNaturalY = el.offsetTop  + el.offsetHeight / 2;
    // Fallback ke window.innerWidth/Height jika canvas belum ter-layout
    // (terjadi di iframe yang belum selesai paint saat timeout pertama)
    const canvasW = canvas.offsetWidth  || window.innerWidth;
    const canvasH = canvas.offsetHeight || window.innerHeight;
    if (canvasW === 0) return false;  // layout belum siap, signal retry
    scale      = 1.0;
    translateX = canvasW / 2 - elNaturalX * scale;
    translateY = canvasH / 2 - elNaturalY * scale - 60;
    treeRoot.style.transition = 'transform 0.6s cubic-bezier(0.4,0,0.2,1)';
    applyTransform();
    setTimeout(() => {{ treeRoot.style.transition = ''; }}, 700);
    const legEl = document.getElementById('legend-highlight');
    if (legEl) legEl.style.display = 'flex';
    return true;
  }}

  // Tunggu layout selesai: delay + double requestAnimationFrame
  // memastikan browser sudah selesai paint sebelum baca dimensi.
  setTimeout(() => {{
    requestAnimationFrame(() => {{
      requestAnimationFrame(() => {{
        const ok = doPan();
        if (!ok) {{
          // Canvas belum siap — retry satu kali setelah 500ms lagi
          setTimeout(() => doPan(), 500);
        }}
      }});
    }});
  }}, 700);
}}
function rerenderTree() {{
  const r = document.getElementById('tree-root');
  r.innerHTML = '';
  treeData.forEach(n => r.appendChild(renderNode(n)));
  if (highlightId) {{ scrollToHighlighted(); }}
  drawHobOverlay();
}}

// ══════════════════════════════════════════════════════════════════
// [HoB OVERLAY — 27 Agt 2026, brief PM/CEO]
// Digambar SEBAGAI CHILD dari #tree-root (bukan layer terpisah di
// canvas) supaya otomatis ikut transform pan/zoom yang sama — tidak
// perlu recompute apapun saat user drag/scroll/zoom, cuma perlu
// digambar ulang tiap kali struktur DOM berubah (collapse/expand),
// makanya dipanggil dari dalam rerenderTree(), bukan dari event
// zoom/pan. Sepenuhnya no-op (tidak menggambar apapun) kalau tidak
// ada node dengan field `hob_overlay` di data — jadi toggle OFF di
// Python = fitur ini otomatis tidak aktif, tanpa perlu flag terpisah.
//
// Known limitation (didokumentasikan, bukan disembunyikan): kalau
// label HoB yang di-stack di sisi kanan lebih panjang dari sisa ruang
// kosong sebelum subtree C-Level lain di sebelahnya (kasus banyak
// root/Chief berdampingan), label BISA tumpang tindih visual dengan
// node/subtree tetangga. SVG ini punya overflow:visible supaya label
// tidak terpotong, tapi tidak otomatis menambah jarak antar root untuk
// menghindari itu — kalau ketemu kasus ini di data riil, perlu
// keputusan lanjutan (reserve margin ekstra antar root, atau batasi
// overlay ke root yang di-scroll ke tengah viewport).
function getOffsetRelativeTo(el, ancestor) {{
  // [FIX ROOT CAUSE — 27 Agt 2026] `offsetLeft`/`offsetTop` langsung TIDAK
  // BISA dipakai di sini. JS mengukur keduanya relatif ke `offsetParent` =
  // nearest ancestor ber-`position` non-static. Di tree ini, BAIK `.node-box`
  // MAUPUN `.children-row` punya `position: relative` — artinya tiap level
  // nesting punya `offsetParent`-nya sendiri, dan koordinat yang terbaca
  // untuk node di depth >= 2 SELALU salah (diukur dari parent terdekat,
  // bukan dari `#tree-root` yang kita mau). Itulah kenapa semua garis
  // seolah-olah "bertolak dari Suwandi" di screenshot Dave — Suwandi kebetulan
  // ada di depth pertama jadi koordinatnya tepat, sedangkan node di bawahnya
  // nilainya kecil-kecil (karena di-reset di setiap `position:relative` layer).
  // Fix: jalan naik via rantai `.offsetParent` sambil akumulasi posisi,
  // berhenti ketika sampai di `ancestor` (#tree-root) atau null.
  let x = 0, y = 0, cur = el;
  while (cur && cur !== ancestor) {{
    x += cur.offsetLeft;
    y += cur.offsetTop;
    cur = cur.offsetParent;
  }}
  return {{ x, y }};
}}

function collectHobTargets(node, parentId, acc) {{
  // [FIX 27 Agt 2026] TIDAK LAGI syarat "depth === 1". Python
  // (annotate_hob_overlay) sudah menentukan node mana yang benar-benar
  // "C-1" (definisi structural PM) — bukan berdasar local depth di tree
  // yang lagi dirender. Di sini kita cuma perlu percaya field
  // `hob_overlay`, muncul di local depth berapapun node itu.
  if (node.hob_overlay) {{
    // [FIX 27 Agt 2026, screenshot Dave] anchorId = PARENT LANGSUNG node
    // ini (bukan root paling atas di tree). Sebelumnya rootId diwariskan
    // TETAP dari root teratas sepanjang rekursi — akibatnya SEMUA C-1 di
    // seluruh tree (walau tersebar di banyak C-Level berbeda: Shrey/CTO,
    // C-Level lain, dst) numpuk jadi SATU kolom label di sebelah CEO,
    // padahal seharusnya tiap C-1 label-nya nempel di sebelah C-Level-nya
    // MASING-MASING. Karena parent langsung dari sebuah C-1 di struktur
    // tree INI SENDIRI adalah C-Level-nya (persis definisi PM: C-1 =
    // manager_id-nya = Employee ID C-Level), pakai parentId di sini sudah
    // otomatis benar tanpa perlu logic tambahan.
    acc.push({{ c1Id: node.id, anchorId: parentId, hobName: node.hob_overlay }});
  }}
  (node.children || []).forEach(child => collectHobTargets(child, node.id, acc));
}}
function drawHobOverlay() {{
  const old = document.getElementById('hob-overlay-svg');
  if (old) old.remove();

  const targets = [];
  treeData.forEach(root => collectHobTargets(root, root.id, targets));
  if (targets.length === 0) return;

  // Grouping per anchorId (C-Level langsung dari tiap C-1) — stacking
  // label independen PER C-LEVEL, sesuai jawaban PM: "Setiap C-1 punya
  // garis putus-putus sendiri ke label HoB-nya masing-masing. Label
  // di-stack vertikal di sisi kanan [C-Level-nya masing-masing]."
  const byAnchor = {{}};
  targets.forEach(t => {{ (byAnchor[t.anchorId] = byAnchor[t.anchorId] || []).push(t); }});

  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.id = 'hob-overlay-svg';
  svg.setAttribute('width', treeRoot.scrollWidth + 280);
  svg.setAttribute('height', treeRoot.scrollHeight);
  svg.style.position = 'absolute';
  svg.style.top = '0'; svg.style.left = '0';
  svg.style.overflow = 'visible';
  svg.style.pointerEvents = 'none';
  svg.style.zIndex = '5';

  const LABEL_H = 24, LABEL_GAP = 6, LABEL_W = 170, OFFSET_X = 36;

  Object.keys(byAnchor).forEach(anchorId => {{
    const anchorEl = treeRoot.querySelector(`[data-node-id="${{anchorId}}"]`);
    if (!anchorEl) return;
    const anchorPos  = getOffsetRelativeTo(anchorEl, treeRoot);
    const anchorRightX = anchorPos.x + anchorEl.offsetWidth;
    const labelsX      = anchorRightX + OFFSET_X;
    const anchorMidY   = anchorPos.y + anchorEl.offsetHeight / 2;

    const withY = byAnchor[anchorId]
      .map(t => {{
        const c1El = treeRoot.querySelector(`[data-node-id="${{t.c1Id}}"]`);
        if (!c1El) return null;
        const c1Pos = getOffsetRelativeTo(c1El, treeRoot);
        return {{ ...t, c1El, c1Pos }};
      }})
      .filter(Boolean);
    withY.sort((a, b) => a.c1Pos.x - b.c1Pos.x);

    const stackTopY = anchorMidY - (withY.length * (LABEL_H + LABEL_GAP)) / 2;
    withY.forEach((t, idx) => {{
      t.labelY = stackTopY + idx * (LABEL_H + LABEL_GAP);
    }});

    withY.forEach(t => {{
      const c1X = t.c1Pos.x + t.c1El.offsetWidth / 2;
      const c1Y = t.c1Pos.y;
      const labelY    = t.labelY;
      const labelMidY = labelY + LABEL_H / 2;
      const midY      = (c1Y + labelMidY) / 2;

      const path = document.createElementNS(svgNS, 'path');
      path.setAttribute('d', `M ${{c1X}} ${{c1Y}} L ${{c1X}} ${{midY}} L ${{labelsX}} ${{midY}} L ${{labelsX}} ${{labelMidY}}`);
      path.setAttribute('stroke', '#f59e0b');
      path.setAttribute('stroke-width', '1.5');
      path.setAttribute('stroke-dasharray', '4,4');
      path.setAttribute('fill', 'none');
      svg.appendChild(path);

      const dot = document.createElementNS(svgNS, 'circle');
      dot.setAttribute('cx', c1X); dot.setAttribute('cy', c1Y);
      dot.setAttribute('r', 3); dot.setAttribute('fill', '#f59e0b');
      svg.appendChild(dot);

      const fo = document.createElementNS(svgNS, 'foreignObject');
      fo.setAttribute('x', labelsX);
      fo.setAttribute('y', labelY);
      fo.setAttribute('width', LABEL_W);
      fo.setAttribute('height', LABEL_H);
      const lbl = document.createElement('div');
      lbl.style.cssText = 'font-size:10px;font-weight:700;background:#fef3c7;border:1px solid #f59e0b;' +
        'border-radius:6px;padding:0 8px;color:#92400e;white-space:nowrap;overflow:hidden;' +
        'text-overflow:ellipsis;display:flex;align-items:center;height:100%;box-sizing:border-box;';
      lbl.textContent = 'HoB: ' + t.hobName;
      fo.appendChild(lbl);
      svg.appendChild(fo);
    }});
  }});

  treeRoot.appendChild(svg);
}}

treeData.forEach(n => applyInitialCollapse(n, 0));
rerenderTree();
if (!highlightId) {{ setTimeout(fitView, 300); }}
</script></body></html>"""


# ══════════════════════════════════════════════════════════════════
# STREAMLIT PAGE CONFIG
# ══════════════════════════════════════════════════════════════════
# ── Favicon: SVG periwinkle icon ─────────────────────────────────
import base64 as _b64
_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#8E94F2"/>
  <text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle"
        font-size="36" font-family="Arial" fill="white">M</text>
</svg>"""
_favicon_b64 = "data:image/svg+xml;base64," + _b64.b64encode(_FAVICON_SVG.encode()).decode()

st.set_page_config(page_title="Mekari", layout="wide", page_icon=_favicon_b64, initial_sidebar_state="auto")

# ══════════════════════════════════════════════════════════════════
# AUTH GATE — Login Page
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# GOOGLE OAUTH AUTH GATE
# ══════════════════════════════════════════════════════════════════
# Alur:
# 1. User klik "Login dengan Google"
# 2. Google konfirmasi identitas (SSO — tidak perlu login ulang
#    jika sudah login Google di People Database)
# 3. Dashboard baca email dari Google session
# 4. Cek email di app_users sheet
# 5. Ada & aktif → masuk sesuai role | Tidak ada → ditolak
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# AUTH GATE — streamlit-google-auth
# Menggunakan library streamlit-google-auth sebagai pengganti
# st.login() bawaan Streamlit yang bermasalah di Community Cloud
# (known bug: "Missing provider for OAuth callback" di multi-instance)
#
# Cara kerja:
# 1. Authenticator baca credentials dari Streamlit Secrets
# 2. check_authentification() tangkap callback dari Google
# 3. Jika belum login → tampilkan halaman login + tombol Google
# 4. Jika sudah login → baca email dari session_state['user_info']
# 5. Validasi email @mekari.com + cek di app_users sheet
# ══════════════════════════════════════════════════════════════════

from streamlit_google_auth import Authenticate as _GoogleAuth
import json as _json
import tempfile as _tempfile

# streamlit-google-auth hanya support file JSON untuk credentials
# Solusi: tulis credentials dari Streamlit Secrets ke temp file saat runtime
#
# ── app_url dibaca dari secrets agar satu codebase bisa dipakai di
#    beberapa environment (dev, staging, prod) tanpa edit code.
#    Isi di secrets.toml:
#      [auth]
#      app_url = "https://<url-deployment-anda>.streamlit.app"
# ──────────────────────────────────────────────────────────────────
def _init_google_auth():
    """
    Inisialisasi Google OAuth authenticator.

    Dibungkus dalam fungsi agar st.secrets diakses SETELAH Streamlit
    selesai inisialisasi context-nya — mencegah StreamlitAPIException
    saat cold start di Streamlit Cloud.

    Return: instance _GoogleAuth yang siap dipakai.
    """
    auth_secrets = st.secrets.get("auth", {})
    app_url      = auth_secrets.get("app_url", "")

    if not app_url:
        st.error(
            "⚠️ Konfigurasi tidak lengkap: `app_url` belum diisi di Streamlit Secrets.\n\n"
            "Tambahkan baris berikut di bagian `[auth]` pada Secrets:\n"
            "```\napp_url = \"https://<url-deployment-anda>.streamlit.app\"\n```"
        )
        st.stop()

    google_creds = {
        "web": {
            "client_id":          auth_secrets.get("client_id", ""),
            "client_secret":      auth_secrets.get("client_secret", ""),
            "auth_uri":           "https://accounts.google.com/o/oauth2/auth",
            "token_uri":          "https://oauth2.googleapis.com/token",
            "redirect_uris":      [app_url],
            "javascript_origins": [app_url],
        }
    }
    creds_tmp = _tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    )
    _json.dump(google_creds, creds_tmp)
    creds_tmp.flush()

    return _GoogleAuth(
        secret_credentials_path = creds_tmp.name,
        cookie_name             = "mekari_od_auth",
        cookie_key              = auth_secrets.get("cookie_secret", "mekari_od_2026_fallback"),
        redirect_uri            = app_url,
    )

# Dipanggil di sini — setelah set_page_config() dan dalam flow normal Streamlit
_google_auth = _init_google_auth()

# Tangkap callback dari Google (harus dipanggil sebelum check login)
# Wrapped dengan error handler untuk menangani:
# 1. InvalidGrantError — PKCE conflict / expired code (google-auth-oauthlib >= 1.0)
# 2. Stale callback — user pakai browser back/forward setelah login
try:
    _google_auth.check_authentification()
except Exception as _auth_exc:
    _auth_exc_str = str(_auth_exc).lower()
    _is_grant_err   = "invalid_grant" in _auth_exc_str or "missing code verifier" in _auth_exc_str
    _is_stale_err   = "missing provider" in _auth_exc_str or "stale" in _auth_exc_str or "mismatch" in _auth_exc_str
    if _is_grant_err or _is_stale_err:
        # Bersihkan session OAuth yang corrupt lalu redirect ke login bersih
        for _k in ["connected", "oauth_state", "user_info", "token", "google_email"]:
            st.session_state.pop(_k, None)
        st.query_params.clear()
        st.rerun()
    else:
        # Error lain yang tidak dikenal — tampilkan pesan informatif
        st.error(f"Terjadi kesalahan autentikasi. Silakan coba lagi atau hubungi OD Admin. ({type(_auth_exc).__name__})")
        st.stop()

# Belum login — tampilkan halaman login
if not st.session_state.get("connected", False):
    # Login-only styling. OAuth and all post-login routes remain unchanged.
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    html, body, .stApp { font-family: 'DM Sans', sans-serif !important; }
    .stApp { background: #111421 !important; color: #f8f8ff !important; }
    .stApp::before {
        content: ''; position: fixed; inset: 0; pointer-events: none;
        background: radial-gradient(ellipse 52% 70% at 88% 12%, rgba(118, 106, 232, .12), transparent 78%);
    }
    [data-testid="stSidebar"], header, #MainMenu, footer { display: none !important; }
    .block-container {
        max-width: 1600px !important; padding: 0 clamp(24px, 5.4vw, 92px) !important;
        margin: auto !important;
    }
    .st-key-login_screen { min-height: 100vh; min-height: 100svh; display: flex; flex-direction: column; justify-content: center; }
    .st-key-login_screen > div { width: 100%; }
    .st-key-login_screen [data-testid="stHorizontalBlock"] { align-items: stretch; gap: clamp(28px, 5.5vw, 90px); }
    .st-key-login_screen [data-testid="stColumn"] { min-width: 0; }
    .login-left { padding: clamp(38px, 7vh, 78px) 0 clamp(16px, 4vh, 40px); }
    .login-brand { display: flex; gap: 14px; align-items: center; margin-bottom: clamp(99px, 14vh, 153px); }
    .login-logo {
        display: block; flex: 0 0 48px; width: 48px; height: 48px;
        border-radius: 14px; background: #fff; overflow: hidden;
    }
    .login-logo img { display: block; width: 100%; height: 100%; object-fit: cover; object-position: center 35%; }
    .login-brand-name { color: #fff; font: 800 21px/1.1 'Manrope', sans-serif; letter-spacing: -.05em; }
    .login-brand-caption { color: #a9afc4; font-size: 10px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; margin-top: 5px; }
    .stApp .login-headline {
        color: #fff !important; font: 800 clamp(56px, 6vw, 94px)/1.045 'Manrope', sans-serif !important;
        letter-spacing: -.075em !important; max-width: 780px; margin: 0 !important;
    }
    .login-headline span { color: #a6a0ff; }
    .login-signin { max-width: 420px; margin-top: clamp(55px, 8vh, 90px); }
    .login-signin-title { color: #f9f9ff; font-size: 15px; font-weight: 700; margin-bottom: 7px; }
    .login-signin-help { color: #a9afc4; font-size: 13px; line-height: 1.5; margin-bottom: 16px; }
    .login-signin-help strong { color: #d8d5ff; font-weight: 700; }
    .st-key-login_action { max-width: 420px; }
    .st-key-login_action a {
        display: flex !important; justify-content: center !important; align-items: center !important;
        min-height: 54px !important; width: 100% !important; border-radius: 13px !important;
        background: #f6f6ff !important; border: 1px solid #f6f6ff !important;
        color: #181a2b !important; font: 700 15px 'DM Sans', sans-serif !important;
        text-decoration: none !important; box-shadow: 0 8px 30px rgba(0,0,0,.2) !important;
        transition: background .18s ease, transform .18s ease, box-shadow .18s ease !important;
    }
    .st-key-login_action a:hover {
        background: #e9e7ff !important; transform: translateY(-2px);
        box-shadow: 0 14px 30px rgba(0,0,0,.27) !important;
    }
    .st-key-login_action a:focus-visible { outline: 3px solid #aba5ff !important; outline-offset: 3px; }
    .login-access { color: #858ca5; font-size: 11px; line-height: 1.55; margin: 15px 0 0; }
    .login-right {
        min-height: min(770px, 85vh); display: grid; place-items: center;
        padding: 14px 0;
    }
    .login-values {
        list-style: none; margin: 0; padding: 0; width: min(100%, 520px);
        display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
        column-gap: clamp(24px, 3vw, 48px);
    }
    .login-value {
        min-height: 96px; padding: 16px 8px;
        display: flex; align-items: center; justify-content: center; text-align: center;
        border-top: 1px solid rgba(170,164,255,.24);
        color: #d7d5ee; font: 600 16px/1.45 'DM Sans', sans-serif;
    }
    .login-value:nth-last-child(-n+2) { border-bottom: 1px solid rgba(170,164,255,.24); }
    .login-footer { color: #747c97; font-size: 11px; letter-spacing: .01em; margin: 16px 0 30px; }
    @media (max-width: 900px) {
        .st-key-login_screen { justify-content: flex-start; }
        .st-key-login_screen [data-testid="stHorizontalBlock"] { flex-direction: column; gap: 18px; }
        .st-key-login_screen [data-testid="stColumn"] { width: 100% !important; flex: unset !important; }
        .login-left { padding: 38px 0 0; }
        .login-brand { margin-bottom: 92px; }
        .stApp .login-headline { font-size: clamp(46px, 11vw, 72px) !important; }
        .login-signin { margin-top: 54px; max-width: 100%; }
        .login-right { min-height: 320px; padding: 16px 0 20px; }
        .login-value { min-height: 82px; }
        .login-footer { margin-bottom: 28px; }
    }
    @media (max-width: 480px) {
        .block-container { padding: 0 20px !important; }
        .login-brand { margin-bottom: 88px; }
        .stApp .login-headline { font-size: clamp(38px, 11.5vw, 56px) !important; }
        .login-right { min-height: 292px; }
        .login-values { column-gap: 14px; }
        .login-value { min-height: 82px; padding: 14px 2px; font-size: 12px; }
    }
    @media (prefers-reduced-motion: reduce) {
        .st-key-login_action a { transition: none !important; }
        .st-key-login_action a:hover { transform: none !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container(key="login_screen"):
        _login_left, _login_right = st.columns([1.12, 0.88], gap="large")
        with _login_left:
            st.markdown(f"""
            <div class="login-left">
              <div class="login-brand">
                <span class="login-logo"><img src="data:image/jpeg;base64,{_MEKARI_LOGO_B64}" alt="Mekari" /></span>
                <span><span class="login-brand-name">Mekari</span><br><span class="login-brand-caption">People Dashboard</span></span>
              </div>
              <h1 class="login-headline">Move as one.<br><span>Go further.</span></h1>
              <div class="login-signin">
                <div class="login-signin-title">Masuk untuk melanjutkan</div>
                <div class="login-signin-help">Gunakan akun Google perusahaan <strong>@mekari.com</strong>.</div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            _auth_url = _google_auth.get_authorization_url()
            with st.container(key="login_action"):
                st.link_button("Masuk dengan Google", _auth_url, use_container_width=True)
            st.markdown('<p class="login-access">Akses dikelola oleh OD Team</p>', unsafe_allow_html=True)
        with _login_right:
            st.markdown("""
            <div class="login-right" aria-label="Nilai-nilai Mekari">
              <ul class="login-values">
                <li class="login-value">Move As One</li>
                <li class="login-value">Elevate Every Standard</li>
                <li class="login-value">Keep Pushing Forward</li>
                <li class="login-value">Accelerate Customer Success</li>
                <li class="login-value">Reimagine Possibilities</li>
                <li class="login-value">Inspire Positive Change</li>
              </ul>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('<div class="login-footer">© Mekari</div>', unsafe_allow_html=True)
    st.stop()

# User sudah login — ambil email dari session_state
# Ambil email dari Google OAuth session
# streamlit-google-auth menyimpan di session_state["user_info"]["email"]
# Kita juga simpan backup di session_state["google_email"] agar tidak hilang saat overwrite
_google_email = (
    st.session_state.get("google_email", "")
    or st.session_state.get("user_info", {}).get("email", "")
    or st.session_state.get("email", "")
)
# Simpan ke dedicated key agar tidak hilang saat user_info di-overwrite ACL lookup
if _google_email:
    st.session_state["google_email"] = _google_email.strip().lower()
_google_email = st.session_state.get("google_email", "")

# Validasi domain — hanya @mekari.com
if not _google_email or not _google_email.endswith("@mekari.com"):
    st.markdown("""
    <style>
    .stApp { background: #f5f5ff !important; }
    .block-container { max-width: 480px !important; padding-top: 14vh !important; margin: 0 auto !important; }
    header, #MainMenu, footer { visibility: hidden !important; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:#fff;border:1.5px solid #ffd0d0;border-radius:12px;
        padding:32px;text-align:center;margin-top:8vh;">
        <div style="font-size:32px;margin-bottom:16px;">🚫</div>
        <div style="font-size:18px;font-weight:700;color:#1a1a2e;margin-bottom:8px;">
            Domain Tidak Diizinkan
        </div>
        <div style="font-size:13px;color:#666;line-height:1.6;margin-bottom:20px;">
            Email <b>{_google_email}</b> bukan akun @mekari.com.<br>
            Dashboard ini hanya untuk karyawan Mekari.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("↩  Logout", key="btn_domain_logout"):
        _google_auth.logout()
    st.stop()

# Cek email di app_users sheet
_user_info = get_user_info(_google_email)

if not _user_info:
    st.markdown("""
    <style>
    .stApp { background: #f5f5ff !important; }
    .block-container { max-width: 480px !important; padding-top: 14vh !important; margin: 0 auto !important; }
    header, #MainMenu, footer { visibility: hidden !important; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:#fff;border:1.5px solid #ffd0d0;border-radius:12px;
        padding:32px;text-align:center;margin-top:8vh;">
        <div style="font-size:32px;margin-bottom:16px;">🚫</div>
        <div style="font-size:18px;font-weight:700;color:#1a1a2e;margin-bottom:8px;">
            Akses Tidak Ditemukan
        </div>
        <div style="font-size:13px;color:#666;line-height:1.6;margin-bottom:20px;">
            Email <b>{_google_email}</b> belum terdaftar di sistem.<br>
            Hubungi OD Team untuk mendapatkan akses.
        </div>
        <div style="font-size:12px;color:#9e9ea0;">
            Mekari People Analytics · OD Team
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("↩  Logout", key="btn_denied_logout"):
        log_activity(action_type="logout", detail=f"Akses ditolak: {_google_email}")
        _google_auth.logout()
    st.stop()

# User valid — set session state
# PENTING: gunakan key "acl_user_info" agar tidak konflik dengan
# session_state["user_info"] milik streamlit-google-auth library
if st.session_state.get("user_email") != _google_email:
    st.session_state.pop("scr_approved_proposal", None)
    st.session_state.pop("my_selected_proposal", None)
    st.session_state.pop("cr_submit_success", None)
    st.session_state.user_email    = _google_email
    st.session_state.google_email  = _google_email
    st.session_state.acl_user_info = _user_info   # key terpisah dari library
    st.session_state.session_id    = str(_uuid.uuid4())[:8]
    log_activity(
        action_type="login",
        detail=f"Google OAuth login · role={_user_info.get('role','')}",
    )

_user_info = st.session_state.get("acl_user_info", _user_info)
_user_role = _user_info.get("role", "employee")

# [QA AUTH-01] Role di ACL yang salah ketik / tidak terdaftar -> akses ditolak (fail-closed).
if _user_role not in _ROLE_TAB_ACCESS:
    st.error("🚫 Role akun Anda tidak dikenali. Hubungi OD Team untuk memperbarui akses.")
    if st.button("Keluar", key="logout_unknown_role"):
        st.session_state.clear()
        st.rerun()
    st.stop()

_is_admin  = _user_role in ("super_admin", "admin")
_is_cxo    = _user_role in ("super_admin", "admin", "cxo")

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "lang" not in st.session_state:
    st.session_state.lang = "en"
if "nav_filter" not in st.session_state:
    st.session_state.nav_filter = {}

L = LANG[st.session_state.lang]

df, data_source = load_data()

if df is None:
    st.error("Tidak ada data yang bisa dimuat. Pastikan credentials.json dan employee_data.csv tersedia.")
    st.stop()

# Apply Row-Level Security — filter df sesuai akses user
# [SCR Fase 1a] df_all = data TANPA RLS, HANYA untuk pilihan tujuan perubahan SCR.
# Jangan dipakai di tempat lain.
df_all = df
df = apply_rbac_filter(df, _user_info)


# ══════════════════════════════════════════════════════════════════
# THEME
# ══════════════════════════════════════════════════════════════════
dm = st.session_state.dark_mode
# ── Design System: PRD "Mekari HR Platform" ──────────────────────
# Primary: Periwinkle #8E94F2 | Background: White | Accent: Soft Lavender/Indigo
# Typography: Inter | Components: ROUND_EIGHT (border-radius 8px)
T = {
    # Core backgrounds — light: white-led, dark: deep navy
    "bg":              "#111827"   if dm else "#ffffff",
    "surface_low":     "#1e2536"   if dm else "#f7f7ff",
    "surface_lowest":  "#28304a"   if dm else "#ffffff",
    "surface_highest": "#343d60"   if dm else "#eeecfc",
    # Periwinkle primary system
    "primary":         "#a5aaf5"   if dm else "#8E94F2",
    "primary_cont":    "#bcc0f8"   if dm else "#7a80e8",
    "primary_fixed":   "#1e2036"   if dm else "#ebebff",
    "on_primary":      "#ffffff"   if dm else "#ffffff",
    # Text scale — WCAG compliant
    "text":            "#f0f0ff"   if dm else "#1a1a2e",
    "text_variant":    "#a0a0c8"   if dm else "#3d3d5c",
    "text3":           "#6868a0"   if dm else "#7b7b9d",
    # Borders
    "outline":         "rgba(162,168,240,0.15)" if dm else "rgba(142,148,242,0.18)",
    "outline_hover":   "rgba(162,168,240,0.40)" if dm else "rgba(142,148,242,0.40)",
    # Sidebar — soft lavender in light mode (PRD spec), deep navy dark mode
    "sidebar_bg":      "#161929"   if dm else "#eeeeff",
    "sidebar_text":    "#b0b4f4"   if dm else "#2a2a6e",
    "sidebar_text2":   "#5a5e8c"   if dm else "#5a5e9e",
    "sidebar_active":  "#ffffff"   if dm else "#1a1a2e",
    "sidebar_pill":    "#28304a"   if dm else "#ffffff",
    # Status colors
    "success_bg":      "#0d2218"   if dm else "#f0fdf4",
    "success_bdr":     "#15803d"   if dm else "#86efac",
    "success_txt":     "#86efac"   if dm else "#15803d",
    "warn_bg":         "#231b00"   if dm else "#fffbeb",
    "warn_bdr":        "#854d0e"   if dm else "#fde68a",
    "warn_txt":        "#fde68a"   if dm else "#854d0e",
    # Org chart node colors — periwinkle theme
    "node_in_bg":      "linear-gradient(135deg,#1e2654,#2c3478)" if dm else "linear-gradient(135deg,#ebebff,#dcdeff)",
    "node_in_txt":     "#d8dcff"   if dm else "#2a2e7e",
    "node_in_bdr":     "#5a60c8"   if dm else "#b0b4f0",
    "node_out_bg":     "#1e2536"   if dm else "#ffffff",
    "node_out_txt":    "#8888b8"   if dm else "#4b5563",
    "node_out_bdr":    "#2a3058"   if dm else "#e5e7eb",
    "connector":       "#2a3058"   if dm else "#c8caee",
    "badge_bg":        "#8E94F2"   if dm else "#8E94F2",
    "chart_bg":        "#111827"   if dm else "#f7f7ff",
    "tb_bg":           "#1e2536"   if dm else "#ffffff",
    "tb_color":        "#a5aaf5"   if dm else "#8E94F2",
    "tb_border":       "#2a3058"   if dm else "#ebebff",
    # Component surfaces
    "bg2":             "#1e2536"   if dm else "#ffffff",
    "bg3":             "#28304a"   if dm else "#f7f7ff",
    "border":          "rgba(162,168,240,0.18)" if dm else "rgba(142,148,242,0.20)",
    "border2":         "#4a50a8"   if dm else "#b0b4f0",
    "accent":          "#a5aaf5"   if dm else "#8E94F2",
    "accent2":         "#bcc0f8"   if dm else "#7a80e8",
    "accent_bg":       "#1e2036"   if dm else "#ebebff",
    "metric_shadow":   "rgba(142,148,242,0.15)" if dm else "rgba(142,148,242,0.08)",
    "dl_btn_bg":       "#1e2536"   if dm else "#ffffff",
    "dl_btn_color":    "#a5aaf5"   if dm else "#8E94F2",
    "input_bg":        "#1e2536"   if dm else "#ffffff",
    "tab_active":      "#a5aaf5"   if dm else "#8E94F2",
    "tab_inactive":    "#4a4a7a"   if dm else "#6868a0",
    "divider":         "rgba(162,168,240,0.15)" if dm else "rgba(142,148,242,0.18)",
    "radio_txt":       "#b0b4f4"   if dm else "#1a1a2e",
    "label_txt":       "#6868a0"   if dm else "#3d3d5c",
}

CHART_COLORS = {
    "primary":   "#8E94F2",
    "secondary": "#7a80e8",
    "success":   "#059669",
    "warning":   "#d97706",
    "danger":    "#dc2626",
    "info":      "#6366f1",
    "scale":     ["#dc2626","#f59e0b","#6b7280","#6366f1","#059669"],
    "bars":      ["#8E94F2","#7a80e8","#a5aaf5","#bcc0f8","#d4d6fc","#e8e9fe","#c7c9f8","#f0f0ff"],
}


# ══════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════════════════════════════
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}
/* ── ROOT CAUSE FIX: color-scheme sinkron dengan dm toggle ── */
html, body, .stApp, [data-testid="stApp"] {{
    color-scheme: {"dark" if dm else "light"} !important;
}}
/* Direct fix: target <input> asli di dalam selectbox (confirmed DevTools).
   Streamlit inject color-scheme:dark via .stApp CSS yang spesifisitasnya
   lebih tinggi dari html/body — rule di atas kadang kalah. Target input
   langsung dengan tiga properti untuk menutup semua jalur. */
[data-baseweb="select"] input,
[data-baseweb="select"] input[type="text"],
[data-testid="stSelectbox"] input {{
    color-scheme: {"dark" if dm else "light"} !important;
    color: {"#f0f0ff" if dm else "#1a1a2e"} !important;
    -webkit-text-fill-color: {"#f0f0ff" if dm else "#1a1a2e"} !important;
    opacity: 1 !important;
}}
html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif !important;
    color: {T["text"]} !important;
    -webkit-font-smoothing: antialiased;
    letter-spacing: -0.01em;
}}
/* ── FIX: Kecualikan Material Symbols icon dari override font ────────
   Streamlit 1.6x+ render icon (termasuk tombol collapse sidebar)
   sebagai [data-testid="stIconMaterial"] ligature-text, bukan <svg>.
   Tanpa exclusion ini, font-family 'Inter' di atas menimpa font icon
   dan glyph gagal render — muncul raw text nama icon-nya. */
[data-testid="stIconMaterial"] {{
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
                 'Material Icons' !important;
    letter-spacing: normal !important;
}}
.stApp {{ background-color: {T["bg"]} !important; transition: background-color 0.3s ease, color 0.3s ease; }}
#MainMenu, footer {{ visibility: hidden !important; }}
header {{ visibility: hidden !important; }}
[data-testid="stToolbar"] {{ visibility: hidden !important; }}
/* ── FIX: collapsedControl mungkin ter-nest di dalam stToolbar di
   Streamlit versi baru. `display:none` di atas akan menghapus total
   descendant-nya tanpa bisa di-override — makanya diganti ke
   `visibility:hidden`, lalu collapsedControl override balik ke
   visible di bawah ini (visibility, tidak seperti display, BISA
   di-override oleh descendant). */
[data-testid="stToolbar"] [data-testid="collapsedControl"] {{
    visibility: visible !important;
}}
[data-testid="collapsedControl"] {{
    visibility: visible !important;
    display: flex !important;
    position: fixed !important;
    top: 14px !important;
    left: 14px !important;
    z-index: 999999 !important;
    background: {T["sidebar_bg"]} !important;
    border-radius: 8px !important;
    padding: 4px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.28) !important;
    transition: background 0.2s !important;
}}
[data-testid="collapsedControl"]:hover {{
    background: {T["sidebar_pill"]} !important;
}}
[data-testid="collapsedControl"] svg {{
    fill: {T["sidebar_text"]} !important;
    width: 18px !important; height: 18px !important;
}}
/* ── FIX: dukung struktur icon baru (span, bukan svg) ───────────────── */
[data-testid="collapsedControl"] [data-testid="stIconMaterial"] {{
    color: {T["sidebar_text"]} !important;
    font-size: 20px !important;
}}
/* ── FIX: testid baru Streamlit 1.6x untuk tombol expand sidebar.
   "collapsedControl" sudah diganti nama jadi "stExpandSidebarButton"
   (mirip "stSidebarCollapseButton" untuk tombol hide). Duplikasi
   styling collapsedControl di atas untuk testid baru ini. ── */
[data-testid="stExpandSidebarButton"] {{
    visibility: visible !important;
    display: flex !important;
    position: fixed !important;
    top: 14px !important;
    left: 14px !important;
    z-index: 999999 !important;
    background: {T["sidebar_bg"]} !important;
    border-radius: 8px !important;
    padding: 4px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.28) !important;
    transition: background 0.2s !important;
}}
[data-testid="stExpandSidebarButton"]:hover {{
    background: {T["sidebar_pill"]} !important;
}}
[data-testid="stExpandSidebarButton"] svg {{
    fill: {T["sidebar_text"]} !important;
    width: 18px !important; height: 18px !important;
}}
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {{
    color: {T["sidebar_text"]} !important;
    font-size: 20px !important;
}}
/* Pastikan tombol ini menang meski nested di dalam header/toolbar
   yang di-set visibility:hidden */
header [data-testid="stExpandSidebarButton"],
[data-testid="stToolbar"] [data-testid="stExpandSidebarButton"] {{
    visibility: visible !important;
}}
.block-container {{
    padding-top: 2rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 100% !important;
    background-color: {T["bg"]} !important;
}}
/* Sidebar styling is scoped in the SIDEBAR section below. */
h1, h2, h3 {{ font-family: 'Inter', sans-serif !important; color: {T["text"]} !important; letter-spacing: -0.02em !important; font-weight: 700 !important; }}

/* TABS */
[data-testid="stTabs"] {{ background: transparent !important; border-bottom: 1px solid {T["outline"]} !important; }}
[data-testid="stTabs"] button {{
    font-family: 'Inter', sans-serif !important; font-weight: 500 !important;
    font-size: 13.5px !important; color: {T["tab_inactive"]} !important;
    border-radius: 0 !important; padding: 12px 20px !important;
    background: transparent !important; transition: color 0.2s !important;
}}
[data-testid="stTabs"] button[aria-selected="true"] {{
    color: {T["primary"]} !important; border-bottom: 2px solid {T["primary"]} !important; font-weight: 600 !important;
}}
[data-testid="stTabs"] button:hover {{ color: {T["primary"]} !important; background: {T["primary_fixed"]} !important; border-radius: 6px 6px 0 0 !important; }}
[data-testid="stTabs"] [data-testid="stTabs"] button {{ font-size: 12.5px !important; padding: 8px 14px !important; }}

/* METRIC CARDS — layered surface, ROUND_EIGHT 8px */
div[data-testid="stMetric"] {{
    background: {T["surface_lowest"]} !important; border-radius: 8px !important;
    padding: 20px 22px !important; border: none !important;
    box-shadow: 0 1px 0 0 {T["outline"]}, 0 2px 16px {T["metric_shadow"]} !important;
    transition: box-shadow 0.2s ease, transform 0.2s ease !important;
    position: relative !important; overflow: hidden !important;
}}
div[data-testid="stMetric"]::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: {T["primary"]}; opacity: 0.5;
}}
div[data-testid="stMetric"]:hover {{
    box-shadow: 0 1px 0 0 {T["outline"]}, 0 4px 24px {T["metric_shadow"]} !important;
    transform: translateY(-1px) !important;
}}
div[data-testid="stMetric"] label {{
    font-size: 11px !important; font-weight: 600 !important; text-transform: uppercase !important;
    letter-spacing: 0.08em !important; color: {T["text3"]} !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    font-size: 26px !important; font-weight: 700 !important;
    color: {T["text"]} !important; letter-spacing: -0.02em !important;
}}

/* UI foundation: preserve keyboard focus and reduced-motion preferences. */
[data-testid="stButton"] button:focus-visible,
[data-testid="stTabs"] button:focus-visible,
[data-testid="stSelectbox"] input:focus-visible {{
    outline: 2px solid {T["primary_cont"]} !important;
    outline-offset: 2px !important;
}}
@media (prefers-reduced-motion: reduce) {{
    .stApp, [data-testid="stSidebar"],
    [data-testid="stButton"] button,
    [data-testid="stTabs"] button,
    div[data-testid="stMetric"] {{
        transition-duration: 0.01ms !important;
        animation-duration: 0.01ms !important;
    }}
}}

/* BUTTONS — ROUND_EIGHT */
[data-testid="stButton"] button {{
    font-family: 'Inter', sans-serif !important; font-weight: 500 !important;
    border-radius: 8px !important; font-size: 13.5px !important;
    transition: all 0.2s ease !important;
}}
[data-testid="stButton"] button[kind="secondary"] {{
    background: transparent !important; color: {T["text_variant"]} !important;
    border: 1px solid {T["outline"]} !important;
}}
[data-testid="stButton"] button[kind="secondary"]:hover {{
    border-color: {T["primary"]} !important; color: {T["primary"]} !important;
    background: {T["primary_fixed"]} !important;
}}
[data-testid="stDownloadButton"] button {{
    background: transparent !important; color: {T["primary"]} !important;
    border: 1px solid {T["outline"]} !important; border-radius: 8px !important;
    font-weight: 500 !important; font-size: 13px !important;
    transition: all 0.2s !important; box-shadow: none !important;
}}
[data-testid="stDownloadButton"] button:hover {{
    border-color: {T["primary"]} !important; background: {T["primary_fixed"]} !important;
}}
[data-testid="stFormSubmitButton"] button {{
    background: {T["primary"]} !important;
    color: white !important; border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; font-size: 14px !important; padding: 12px 28px !important;
    width: 100% !important; transition: all 0.2s !important;
    box-shadow: 0 2px 12px rgba(142,148,242,0.3) !important;
}}
[data-testid="stFormSubmitButton"] button:hover {{
    background: {T["primary_cont"]} !important; box-shadow: 0 4px 20px rgba(142,148,242,0.4) !important;
}}

/* INPUTS — ROUND_EIGHT */
[data-testid="stSelectbox"] > div > div {{
    background: {T["surface_lowest"]} !important; border: 1px solid {T["outline"]} !important;
    border-radius: 8px !important; font-size: 13.5px !important; color: {T["text"]} !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
    box-shadow: 0 1px 4px {T["metric_shadow"]} !important;
}}
[data-testid="stSelectbox"] > div > div:focus-within {{
    border-color: {T["primary"]} !important;
    box-shadow: 0 0 0 3px {T["primary_fixed"]}, 0 1px 4px {T["metric_shadow"]} !important;
}}
[data-testid="stSelectbox"] svg {{ fill: {T["text_variant"]} !important; }}
/* ── BaseWeb POPOVER/DROPDOWN — warna FIXED, TIDAK ikut dm ───────────
   [FIX — Sept 2026, ronde ke-3] Root cause ditemukan: config.toml
   mengunci base theme Streamlit ke "light" secara PERMANEN untuk semua
   widget native (lihat catatan di [data-baseweb="calendar"] di bawah).
   Sebelumnya blok ini pakai T[...] yang berubah ikut dm — itu SALAH,
   karena container popover sesungguhnya (dari BaseWeb, portal-rendered)
   tetap mengikuti base=light yang fixed, terlepas dari nilai dm.
   Akibatnya: di dark mode, teks ikut berubah terang (ikut dm) tapi
   background TIDAK ikut berubah (tetap terang dari base theme) —
   teks terang di atas background terang = tidak terbaca (terbalik
   dari bug sebelumnya di light mode, root cause sama).
   Fix: SEMUA elemen popover pakai warna FIXED yang cocok untuk base
   light — tidak peduli dm. Popover akan selalu terlihat "terang"
   walau app dalam dark mode; trade-off yang disengaja demi keterbacaan
   konsisten di kedua mode, daripada mengejar konsistensi visual yang
   ternyata tidak reliable untuk portal-rendered component ini. */
[data-baseweb="layer"], div[data-baseweb="popover"] {{
    background: transparent !important;
    /* Popups are rendered outside the app's custom dark theme. Keep their
       browser color scheme aligned with Streamlit's fixed light base. */
    color-scheme: light !important;
}}
[data-baseweb="layer"] ul, [data-baseweb="layer"] div[data-baseweb="menu"],
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] div[data-baseweb="menu"],
ul[data-baseweb="menu"], [role="listbox"] {{
    background: #ffffff !important;
    background-color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 24px rgba(142,148,242,0.15), 0 0 0 1px rgba(142,148,242,0.18) !important;
}}
[data-baseweb="layer"] li, [data-baseweb="layer"] [role="option"],
div[data-baseweb="popover"] li, [role="option"] {{
    background: transparent !important;
    background-color: transparent !important;
    color: #1a1a2e !important;
    -webkit-text-fill-color: #1a1a2e !important;
    font-family: 'Inter', sans-serif !important; font-size: 13.5px !important;
    border-radius: 6px !important; margin: 2px 4px !important;
}}
[data-baseweb="layer"] li *, [data-baseweb="layer"] [role="option"] *,
div[data-baseweb="popover"] li *, [role="option"] * {{
    color: #1a1a2e !important;
    -webkit-text-fill-color: #1a1a2e !important;
}}
[data-baseweb="layer"] li:hover, [data-baseweb="layer"] [role="option"]:hover,
div[data-baseweb="popover"] li:hover, [role="option"]:hover,
[role="option"][aria-selected="true"] {{
    background: #ebebff !important;
    background-color: #ebebff !important;
    color: #8E94F2 !important;
}}
[data-baseweb="layer"] li:hover *, [data-baseweb="layer"] [role="option"]:hover *,
div[data-baseweb="popover"] li:hover *, [role="option"]:hover *,
[role="option"][aria-selected="true"] * {{
    color: #8E94F2 !important;
    -webkit-text-fill-color: #8E94F2 !important;
}}
[data-testid="stTextInput"] input {{
    background: {T["surface_lowest"]} !important; border: 1px solid {T["outline"]} !important;
    border-radius: 8px !important; font-size: 13.5px !important; color: {T["text"]} !important;
    padding: 10px 14px !important; transition: border-color 0.2s, box-shadow 0.2s !important;
    font-family: 'Inter', sans-serif !important;
}}
[data-testid="stTextInput"] input:focus {{
    border-color: {T["primary"]} !important; box-shadow: 0 0 0 3px {T["primary_fixed"]} !important; outline: none !important;
}}
[data-testid="stTextInput"] input::placeholder {{ color: {T["text3"]} !important; }}
[data-testid="stTextArea"] textarea {{
    background: {T["surface_lowest"]} !important; border: 1px solid {T["outline"]} !important;
    border-radius: 8px !important; font-size: 13.5px !important; color: {T["text"]} !important;
    font-family: 'Inter', sans-serif !important; transition: border-color 0.2s, box-shadow 0.2s !important;
}}
[data-testid="stTextArea"] textarea:focus {{
    border-color: {T["primary"]} !important; box-shadow: 0 0 0 3px {T["primary_fixed"]} !important;
}}
[data-testid="stTextArea"] textarea::placeholder {{ color: {T["text3"]} !important; }}
[data-testid="stNumberInput"] input {{
    background: {T["surface_lowest"]} !important; border: 1px solid {T["outline"]} !important;
    border-radius: 8px !important; color: {T["text"]} !important; font-size: 13.5px !important;
}}
[data-testid="stNumberInput"] button {{
    background: {T["surface_low"]} !important; border: none !important;
    color: {T["text_variant"]} !important; border-radius: 6px !important;
}}
/* ── DATE INPUT — container, input field, calendar popup ────────────
   Fix light-mode bug: input teks nyaru (perlu -webkit-text-fill-color)
   dan kalender portal angka tidak terbaca karena background tidak di-set.

   Root cause: BaseWeb date picker render kalender di portal terpisah —
   CSS global tidak otomatis menjangkau; perlu [data-baseweb="calendar"]
   catch-all yang eksplisit set background + color + -webkit-text-fill-color.
   Tanpa -webkit-text-fill-color, Chromium mengabaikan `color` pada input
   dengan color-scheme override — bug yang sama sudah di-fix di selectbox. */

/* Input field container — TETAP ikut T[...]/dm karena ini bukan portal,
   elemen dalam document flow normal, CSS cascade reliable di sini. */
[data-testid="stDateInput"] > div > div {{
    background: {T["surface_lowest"]} !important;
    border: 1px solid {T["outline"]} !important;
    border-radius: 8px !important;
}}
/* Input field text — TETAP ikut T[...]/dm, sama alasan di atas */
[data-testid="stDateInput"] input,
[data-testid="stDateInput"] input[type="text"],
[data-testid="stDateInput"] input[data-testid="stDateInputField"] {{
    color: {T["text"]} !important;
    -webkit-text-fill-color: {T["text"]} !important;
    color-scheme: {"dark" if dm else "light"} !important;
    opacity: 1 !important;
    background: transparent !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13.5px !important;
}}
/* Calendar popup — outer container (portal-rendered) */
/* [FIX — Sept 2026, ronde ke-3] SAMA seperti popover selectbox di atas:
   warna di sini SENGAJA di-fixed, TIDAK ikut dm. config.toml mengunci
   base theme Streamlit ke "light" permanen untuk semua widget native
   (termasuk date picker) — kalender akan SELALU render dengan asumsi
   base light, terlepas dm. CSS sebelumnya pakai T[...] (ikut dm) untuk
   teks tapi background BaseWeb tetap ikut base=light yang fixed →
   di dark mode: teks jadi terang (ikut dm) di atas background yang
   tetap terang (base fixed) = tidak terbaca. Fix: SEMUA warna di
   kalender di-hardcode cocok untuk base light, konsisten di kedua
   mode aplikasi — trade-off yang disengaja demi keterbacaan. */
[data-baseweb="calendar"] {{
    background: #ffffff !important;
    background-color: #ffffff !important;
    border: 1px solid rgba(142,148,242,0.18) !important;
    border-radius: 10px !important;
    box-shadow: 0 8px 32px rgba(142,148,242,0.18) !important;
    font-family: 'Inter', sans-serif !important;
    color-scheme: light !important;
}}
/* In some Streamlit versions, the portal wrapper sits between the layer and
   the calendar. Give it the same light scheme so headers inherit dark text. */
[data-baseweb="layer"]:has([data-baseweb="calendar"]),
[data-baseweb="popover"]:has([data-baseweb="calendar"]) {{
    color-scheme: light !important;
}}
/* Catch-all: semua elemen di dalam kalender inherit background benar. */
[data-baseweb="calendar"] * {{
    background-color: transparent !important;
    color: #1a1a2e !important;
    -webkit-text-fill-color: #1a1a2e !important;
    font-family: 'Inter', sans-serif !important;
}}
/* Month/year header & navigation arrows */
[data-baseweb="calendar"] [data-testid="calendar-header"],
[data-baseweb="calendar"] button,
[data-baseweb="calendar"] [role="heading"] {{
    color: #1a1a2e !important;
    -webkit-text-fill-color: #1a1a2e !important;
    background: transparent !important;
}}
[data-baseweb="calendar"] button svg,
[data-baseweb="calendar"] button svg path {{
    fill: #1a1a2e !important;
}}
/* Day-of-week labels (S M T W T F S) */
[data-baseweb="calendar"] [role="columnheader"],
[data-baseweb="calendar"] [role="columnheader"] *,
[data-baseweb="calendar"] [alt="Sunday"],
[data-baseweb="calendar"] [alt="Monday"],
[data-baseweb="calendar"] [alt="Tuesday"],
[data-baseweb="calendar"] [alt="Wednesday"],
[data-baseweb="calendar"] [alt="Thursday"],
[data-baseweb="calendar"] [alt="Friday"],
[data-baseweb="calendar"] [alt="Saturday"] {{
    color: #7b7b9d !important;
    -webkit-text-fill-color: #7b7b9d !important;
    font-weight: 600 !important;
    font-size: 11px !important;
    letter-spacing: 0.06em !important;
}}
/* Day number cells — default state */
[data-baseweb="calendar"] [role="gridcell"],
[data-baseweb="calendar"] [role="gridcell"] *,
[data-baseweb="calendar"] [data-baseweb="calendar-day"] {{
    color: #1a1a2e !important;
    -webkit-text-fill-color: #1a1a2e !important;
    background: transparent !important;
}}
/* Preserve BaseWeb's selected-day shape when it identifies the day by label.
   In newer markup with aria-selected, apply the brand background directly. */
[data-baseweb="calendar"] [role="gridcell"][aria-selected="true"],
[data-baseweb="calendar"] [data-baseweb="calendar-day"][aria-selected="true"] {{
    background: #8E94F2 !important;
    background-color: #8E94F2 !important;
    border-radius: 6px !important;
}}
[data-baseweb="calendar"] [role="gridcell"][aria-label^="Selected."],
[data-baseweb="calendar"] [role="gridcell"][aria-label^="Selected."] *,
[data-baseweb="calendar"] [role="gridcell"][aria-selected="true"] *,
[data-baseweb="calendar"] [data-baseweb="calendar-day"][aria-selected="true"] * {{
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 700 !important;
}}
/* Days outside current month */
[data-baseweb="calendar"] [aria-disabled="true"],
[data-baseweb="calendar"] [aria-disabled="true"] * {{
    color: #686b80 !important;
    -webkit-text-fill-color: #686b80 !important;
    opacity: 1 !important;
}}
/* Hover state */
[data-baseweb="calendar"] [data-baseweb="calendar-day"]:not([aria-selected="true"]):hover,
[data-baseweb="calendar"] [role="gridcell"]:not([aria-selected="true"]):hover {{
    background: #ebebff !important;
    background-color: #ebebff !important;
    border-radius: 6px !important;
}}
[data-baseweb="calendar"] [data-baseweb="calendar-day"]:not([aria-selected="true"]):hover *,
[data-baseweb="calendar"] [role="gridcell"]:not([aria-selected="true"]):hover * {{
    color: #8E94F2 !important;
    -webkit-text-fill-color: #8E94F2 !important;
}}
/* Selected day — override catch-all background di sini */
[data-baseweb="calendar"] [aria-selected="true"],
[data-baseweb="calendar"] [data-baseweb="calendar-day"][aria-selected="true"] {{
    background: #8E94F2 !important;
    background-color: #8E94F2 !important;
    border-radius: 6px !important;
}}
[data-baseweb="calendar"] [aria-selected="true"],
[data-baseweb="calendar"] [aria-selected="true"] * {{
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 700 !important;
}}
/* Today marker underline dot */
[data-baseweb="calendar"] [data-today="true"]::after {{
    background: #8E94F2 !important;
    background-color: #8E94F2 !important;
}}

/* DATAFRAME — layered surface */
[data-testid="stDataFrame"] {{
    border-radius: 8px !important; overflow: hidden !important; border: none !important;
    box-shadow: 0 1px 0 0 {T["outline"]}, 0 2px 12px {T["metric_shadow"]} !important;
}}
[data-testid="stDataFrame"] th {{
    background: {T["surface_low"]} !important; color: {T["text3"]} !important;
    font-family: 'Inter', sans-serif !important; font-size: 11px !important;
    font-weight: 600 !important; text-transform: uppercase !important;
    letter-spacing: 0.07em !important; border: none !important;
}}
[data-testid="stDataFrame"] td {{
    background: {T["surface_lowest"]} !important; color: {T["text"]} !important;
    border: none !important; font-size: 13px !important;
    font-family: 'Inter', sans-serif !important;
}}

/* FORM & EXPANDER — ROUND_EIGHT */
[data-testid="stForm"] {{
    background: {T["surface_low"]} !important; border: none !important;
    border-radius: 8px !important; padding: 24px !important;
    box-shadow: 0 1px 0 0 {T["outline"]}, 0 2px 12px {T["metric_shadow"]} !important;
}}
[data-testid="stExpander"] {{
    background: {T["surface_lowest"]} !important; border: none !important;
    border-radius: 8px !important; margin-bottom: 6px !important;
    box-shadow: 0 1px 0 0 {T["outline"]} !important;
}}
[data-testid="stExpander"] summary {{
    color: {T["text"]} !important; font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
}}

/* ALERTS */
[data-testid="stAlert"] {{
    border-radius: 8px !important; font-size: 13px !important;
    background: {T["surface_lowest"]} !important; border: none !important;
    box-shadow: 0 0 0 1px {T["outline"]} !important;
}}
[data-testid="stAlert"] p {{ color: {T["text"]} !important; font-family: 'Inter', sans-serif !important; }}
[data-testid="stCaptionContainer"] p {{ color: {T["text_variant"]} !important; font-size: 12px !important; }}
small {{ color: {T["text_variant"]} !important; }}

/* WIDGET LABELS */
[data-testid="stWidgetLabel"] {{
    color: {T["text"]} !important; font-size: 13px !important; font-weight: 500 !important;
}}
[data-testid="stWidgetLabel"] p {{
    color: {T["text"]} !important; font-size: 13px !important; font-weight: 500 !important;
}}
label, .stSelectbox label, .stTextInput label, .stTextArea label,
.stNumberInput label, .stDateInput label, .stSlider label {{
    color: {T["text"]} !important; font-weight: 500 !important; font-size: 13px !important;
    font-family: 'Inter', sans-serif !important;
}}

/* MARKDOWN */
[data-testid="stMarkdownContainer"] p {{ color: {T["text"]} !important; font-family: 'Inter', sans-serif !important; }}
[data-testid="stMarkdownContainer"] li {{ color: {T["text"]} !important; }}

/* RADIO */
[data-testid="stRadio"] label {{ font-size: 13.5px !important; font-weight: 500 !important; color: {T["text"]} !important; }}
[data-testid="stRadio"] div[role="radiogroup"] label p {{ color: {T["text"]} !important; font-weight: 500 !important; }}
[data-testid="stRadio"] > label {{ color: {T["text"]} !important; }}

/* CHECKBOX */
[data-testid="stCheckbox"] label {{ font-size: 13.5px !important; color: {T["text"]} !important; font-weight: 400 !important; }}
[data-testid="stCheckbox"] label p {{ color: {T["text"]} !important; }}

/* SELECT OPTIONS */
[data-baseweb="select"] span {{ color: {T["text"]} !important; }}
/* ── FIX round 2: paksa warna teks dropdown berdasarkan mode ───────────
   Force ke SEMUA elemen (bukan hanya span/div tertentu), cover color,
   -webkit-text-fill-color (bisa override visual di Chromium terlepas
   dari `color`), dan opacity — untuk menutup semua kemungkinan
   penyebab teks pudar, bukan hanya menebak satu properti saja. */
[data-testid="stSelectbox"] [data-baseweb="select"] * {{
    color: {"#ffffff" if dm else "#000000"} !important;
    -webkit-text-fill-color: {"#ffffff" if dm else "#000000"} !important;
    opacity: 1 !important;
}}
[data-testid="stSelectbox"] [data-baseweb="select"] svg {{
    fill: {"#ffffff" if dm else "#000000"} !important;
}}
/* ── FIX: value terpilih di kotak dropdown tertutup tidak terbaca ──────
   BaseWeb versi baru mungkin render value container sebagai <div>,
   bukan <span> saja — selector di atas tidak cukup luas. */
[data-baseweb="select"] > div,
[data-baseweb="select"] > div > div,
[data-testid="stSelectbox"] [data-baseweb="select"] div:not(:has(svg)) {{
    color: {T["text"]} !important;
}}
[data-baseweb="select"] [class*="ValueContainer"],
[data-baseweb="select"] [class*="SingleValue"] {{
    color: {T["text"]} !important;
}}
[data-testid="stTooltipIcon"] {{ color: {T["text_variant"]} !important; }}

hr {{ border: none !important; border-top: 1px solid {T["outline"]} !important; }}
</style>
""", unsafe_allow_html=True)



# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
# Sidebar-only design tokens. Native buttons retain Streamlit keyboard behavior.
_sb = {
    "bg": "#171b29" if dm else "#f5f5fa",
    "surface": "#202638" if dm else "#ffffff",
    "text": "#eff0fa" if dm else "#272a3e",
    "muted": "#abb2c9" if dm else "#62697e",
    "line": "#30374c" if dm else "#e4e6ef",
    "hover": "#262d42" if dm else "#ebecf4",
    "active": "#333453" if dm else "#e7e5fb",
    "accent": "#cbc6ff" if dm else "#5145a6",
    "focus": "#c3bcff" if dm else "#6254bc",
}
_sb_copy = {
    "id": {
        "workspace": "Organisasi", "workflows": "Operasional",
        "admin": "Administrasi", "overview": "Ringkasan data",
        "scope": "Sesuai akses akun Anda", "employees": "Karyawan",
        "managers": "Manager", "divisions": "Divisi", "business_units": "Business unit",
        "refresh": "Perbarui", "refresh_help": "Muat ulang data dashboard",
        "light": "Terang", "dark": "Gelap",
        "theme_help": "Ganti ke tampilan {mode}",
        "sheets": "Data dari Google Sheets", "local": "Data dari CSV lokal",
    },
    "en": {
        "workspace": "Organization", "workflows": "Workflows",
        "admin": "Administration", "overview": "Data overview",
        "scope": "Within your account access", "employees": "Employees",
        "managers": "Managers", "divisions": "Divisions", "business_units": "Business units",
        "refresh": "Refresh", "refresh_help": "Reload dashboard data",
        "light": "Light", "dark": "Dark",
        "theme_help": "Switch to {mode} mode",
        "sheets": "Data from Google Sheets", "local": "Data from local CSV",
    },
}.get(st.session_state.lang, {})

st.markdown(f"""
<style>
/* SIDEBAR REDESIGN — scoped; do not style the module content. */
[data-testid="stSidebar"] {{
    background: {_sb['bg']} !important;
    border-right: 1px solid {_sb['line']} !important;
    box-shadow: none !important;
}}
[data-testid="stSidebar"][aria-expanded="true"] {{
        min-width: min(288px, calc(100vw - 24px)) !important;
        max-width: calc(100vw - 24px) !important;
    }}
    [data-testid="stSidebar"] .block-container {{ padding: 0 !important; background: transparent !important; }}
[data-testid="stSidebarContent"] {{ padding-left: 0 !important; padding-right: 0 !important; }}
    [data-testid="stSidebarUserContent"] {{ padding: 8px 14px 22px !important; }}
[data-testid="stSidebarUserContent"] > [data-testid="stVerticalBlock"],
    [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {{ gap: 12px !important; }}
/* Streamlit HTML markdown uses a negative bottom margin; avoid clipped group labels. */
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] summary {{
    font-family: 'Inter', sans-serif !important;
}}
[data-testid="stSidebar"] [data-testid="stIconMaterial"] {{
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
    font-weight: 400 !important; font-size: 20px !important;
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 20;
    letter-spacing: normal !important; flex-shrink: 0;
}}
[data-testid="stSidebarCollapseButton"] {{ opacity: 1 !important; visibility: visible !important; }}
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"] {{ color: {_sb["muted"]} !important; }}
    [data-testid="stSidebarCollapseButton"] button {{ background: transparent !important; color: {_sb['muted']} !important; }}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind] {{
    min-height: 44px !important; padding: 10px 12px !important;
    border: 1px solid transparent !important; border-radius: 12px !important;
    background: transparent !important; color: {_sb['muted']} !important;
    display: flex !important; justify-content: flex-start !important; align-items: center !important;
    gap: 10px !important; text-align: left !important;
    box-shadow: none !important; transform: none !important; filter: none !important;
    transition: background-color 140ms ease, color 140ms ease, border-color 140ms ease !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button p {{
    font-size: 14px !important; font-weight: 500 !important;
    line-height: 1.4 !important; color: inherit !important;
    margin: 0 !important; letter-spacing: -0.01em !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button [data-testid="stIconMaterial"] {{ color: inherit !important; }}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {{
    background: {_sb['hover']} !important; color: {_sb['text']} !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {{
    background: {_sb['active']} !important; color: {_sb['accent']} !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] p {{ font-weight: 650 !important; }}
[data-testid="stSidebar"] .st-key-sb_navigation button[kind="primary"]::after {{
    content: ''; width: 6px; height: 6px; border-radius: 50%;
    background: currentColor; flex: 0 0 6px; margin-left: auto;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button:focus-visible,
[data-testid="stSidebar"] summary:focus-visible {{
    outline: 2px solid {_sb['focus']} !important; outline-offset: 2px !important;
}}
/* Navigation alignment: cover both direct and nested button content layouts. */
[data-testid="stSidebar"] .st-key-sb_navigation button[kind],
[data-testid="stSidebar"] .st-key-sb_navigation button[kind] div,
[data-testid="stSidebar"] .st-key-sb_navigation button[kind] p {{
    justify-content: flex-start !important;
    text-align: left !important;
}}
[data-testid="stSidebar"] .st-key-sb_navigation button[kind] > div:has([data-testid="stMarkdownContainer"]),
[data-testid="stSidebar"] .st-key-sb_navigation button[kind] > [data-testid="stMarkdownContainer"] {{
    flex: 1 1 auto !important; min-width: 0 !important;
    width: 100% !important;
}}
[data-testid="stSidebar"] .st-key-sb_navigation button[kind] > :is(div, span):has([data-testid="stIconMaterial"]):has([data-testid="stMarkdownContainer"]) {{
    display: flex !important; align-items: center !important;
    justify-content: flex-start !important; gap: 10px !important;
    flex: 1 1 auto !important; min-width: 0 !important;
    width: 100% !important;
}}
[data-testid="stSidebar"] .st-key-sb_navigation button[kind] [data-testid="stMarkdownContainer"] {{
    flex: 1 1 auto !important; min-width: 0 !important;
    margin-left: 0 !important; margin-right: 0 !important;
}}
[data-testid="stSidebar"] .st-key-sb_navigation,
    [data-testid="stSidebar"] .st-key-sb_navigation [data-testid="stVerticalBlock"] {{ gap: 4px !important; }}
[data-testid="stSidebar"] .od-sb-heading {{
    margin: 0; padding: 16px 12px 5px; color: {_sb['muted']};
    font: 600 11px/1.4 'Inter', sans-serif; letter-spacing: .05em; text-transform: uppercase;
}}
[data-testid="stSidebar"] .od-sb-heading-first {{ padding-top: 2px; }}
[data-testid="stSidebar"] .od-sb-brand {{ display: flex; gap: 11px; align-items: center; padding: 0 10px; }}
[data-testid="stSidebar"] .od-sb-logo {{
    width: 40px; height: 40px; padding: 7px; border-radius: 12px; flex-shrink: 0;
    background: white; border: 1px solid {_sb['line']}; object-fit: contain;
}}
[data-testid="stSidebar"] .od-sb-brand-name {{ font: 700 18px/1.25 'Inter', sans-serif; letter-spacing: -.04em; color: {_sb['text']}; }}
[data-testid="stSidebar"] .od-sb-brand-sub {{ font: 400 12px/1.5 'Inter', sans-serif; color: {_sb['muted']}; margin-top: 1px; }}
[data-testid="stSidebar"] .od-sb-source {{
    display: flex; gap: 7px; align-items: center; margin: 0; padding: 15px 10px 8px;
    font: 400 11px/1.5 'Inter', sans-serif; color: {_sb['muted']};
}}
[data-testid="stSidebar"] .od-sb-dot {{
    width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
    background: {('#69d6ab' if dm else '#2d8a67') if data_source == 'google_sheets' else ('#edc773' if dm else '#946e22')};
}}
[data-testid="stSidebar"] .st-key-sb_overview [data-testid="stExpander"] {{
        background: transparent !important; border: none !important;
    }}
    [data-testid="stSidebar"] .st-key-sb_overview [data-testid="stExpander"] details {{
    background: {_sb["surface"]}; border: 1px solid {_sb['line']} !important; border-radius: 12px !important;
}}
[data-testid="stSidebar"] .st-key-sb_overview summary {{
    min-height: 44px; padding: 10px 12px !important; color: {_sb['muted']} !important;
}}
[data-testid="stSidebar"] .st-key-sb_overview summary p {{ font-size: 12px !important; font-weight: 500 !important; color: inherit !important; }}
[data-testid="stSidebar"] .od-sb-metrics {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px 12px; }}
[data-testid="stSidebar"] .od-sb-metric-value {{ font: 650 21px/1.3 'Inter', sans-serif; color: {_sb['text']}; font-variant-numeric: tabular-nums; }}
[data-testid="stSidebar"] .od-sb-metric-label, [data-testid="stSidebar"] .od-sb-scope {{ font: 400 11px/1.5 'Inter', sans-serif; color: {_sb['muted']}; }}
[data-testid="stSidebar"] .od-sb-scope {{ margin: 14px 0 0; }}
[data-testid="stSidebar"] .st-key-sb_actions_row [data-testid="stHorizontalBlock"] {{ gap: 8px !important; }}
[data-testid="stSidebar"] .st-key-sb_actions_row [data-testid="stColumn"] {{ min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }}
[data-testid="stSidebar"] .st-key-sb_actions_row [data-testid="stButton"] button {{
    justify-content: center !important; gap: 7px !important;
    padding: 8px !important; border-color: {_sb['line']} !important; background: {_sb['surface']} !important;
}}
[data-testid="stSidebar"] .st-key-sb_actions_row [data-testid="stButton"] button p {{ font-size: 12px !important; }}
[data-testid="stSidebar"] .st-key-sb_actions_row [data-testid="stButton"] button:hover {{ background: {_sb['hover']} !important; }}
[data-testid="stSidebar"] .st-key-sb_account {{ border-top: 1px solid {_sb['line']}; padding-top: 16px; margin-top: 4px; }}
[data-testid="stSidebar"] .st-key-sb_account,
    [data-testid="stSidebar"] .st-key-sb_account [data-testid="stVerticalBlock"] {{ gap: 8px !important; }}
[data-testid="stSidebar"] .od-sb-profile {{ display: flex; gap: 10px; align-items: center; padding: 0 10px; }}
[data-testid="stSidebar"] .od-sb-avatar {{
    width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    background: {_sb['active']}; color: {_sb['accent']}; font: 600 12px/1 'Inter', sans-serif;
}}
[data-testid="stSidebar"] .od-sb-identity {{ min-width: 0; }}
[data-testid="stSidebar"] .od-sb-name {{
    font: 600 13px/1.5 'Inter', sans-serif; color: {_sb['text']};
    overflow-wrap: anywhere;
}}
[data-testid="stSidebar"] .od-sb-role {{ font: 400 11px/1.5 'Inter', sans-serif; color: {_sb['muted']}; }}
[data-testid="stSidebar"] .st-key-sb_account [data-testid="stButton"] button {{ padding-left: 14px !important; }}
[data-testid="stSidebar"] .st-key-sb_account [data-testid="stButton"] button p {{ font-size: 12px !important; }}
@media (prefers-reduced-motion: reduce) {{
    [data-testid="stSidebar"] [data-testid="stButton"] button[kind] {{ transition: none !important; }}
}}
</style>
""", unsafe_allow_html=True)


with st.sidebar:
    _source_label = _sb_copy["sheets"] if data_source == "google_sheets" else _sb_copy["local"]
    st.markdown(f"""
    <div class="od-sb-brand">
        <img class="od-sb-logo" src="data:image/jpeg;base64,{_MEKARI_LOGO_B64}" alt="" />
        <div><div class="od-sb-brand-name">Mekari</div><div class="od-sb-brand-sub">People Dashboard</div></div>
    </div>
    <div class="od-sb-source"><span class="od-sb-dot" aria-hidden="true"></span>{_source_label}</div>
    """, unsafe_allow_html=True)

    if "active_tab" not in st.session_state:
        st.session_state.active_tab = 0

    # Owner decision: operational tabs stay super_admin-only; SCR also requires beta.
    _scr_enabled = _scr_beta_enabled()
    _pending_scr_count = 0
    _nav_cr_failed = False
    if _scr_enabled and _scr_can(_user_role, "inbox"):
        _nav_cr_df = load_change_requests()
        _nav_cr_failed = cr_load_failed(_nav_cr_df)
        if not _nav_cr_df.empty and "status" in _nav_cr_df.columns:
            _pending_scr_count = int(
                _nav_cr_df["status"].astype(str).str.strip().str.lower().eq("pending").sum()
            )
    _scr_nav_label = L["nav_cr"] + (f" ({_pending_scr_count})" if _pending_scr_count else "") \
        + (" ⚠️" if _nav_cr_failed else "")

    # Stable tab IDs and widget keys; only presentation and grouping change.
    nav_items = [
        ("account_tree", L["nav_org"], 0),
        ("groups", L["nav_data"], 1),
        ("supervisor_account", L["nav_manager"], 3),
        ("fact_check", L["nav_compliance"], 2),
    ]
    if _scr_enabled:
        nav_items.append(("edit_note", _scr_nav_label, 4))
    nav_items.extend([
        ("person_remove", "Offboarding Tracker", 5),
        ("admin_panel_settings", "Admin Panel", 99),
    ])

    active_idx = st.session_state.active_tab
    if not _can_access_tab(_user_role, active_idx) or (active_idx == 4 and not _scr_enabled):
        st.session_state.active_tab = 0
        active_idx = 0

    with st.container(key="sb_navigation"):
        _first_group = True
        for _group_label, _group_tabs in [
            (_sb_copy["workspace"], {0, 1, 3}),
            (_sb_copy["workflows"], {2, 4, 5}),
            (_sb_copy["admin"], {99}),
        ]:
            _visible_items = [
                item for item in nav_items
                if item[2] in _group_tabs and _can_access_tab(_user_role, item[2])
            ]
            if not _visible_items:
                continue
            _heading_class = "od-sb-heading od-sb-heading-first" if _first_group else "od-sb-heading"
            st.markdown(f'<div class="{_heading_class}">{_group_label}</div>', unsafe_allow_html=True)
            _first_group = False
            for icon_nav, label_nav, tab_idx in _visible_items:
                is_active = (active_idx == tab_idx)
                if st.button(label_nav, icon=f":material/{icon_nav}:", key=f"nav_{tab_idx}",
                             use_container_width=True,
                             type="primary" if is_active else "secondary"):
                    st.session_state.active_tab = tab_idx
                    st.rerun()

    # Counts retain the existing access-filtered dataset; secondary to navigation.
    total_karyawan = len(df)
    total_bu = df["Business Unit"].nunique()
    total_div = df["Division"].nunique()
    total_mgr = df[df["Employee ID"].isin(df["Manager ID"].unique())]["Employee ID"].nunique()
    with st.container(key="sb_overview"):
        with st.expander(_sb_copy["overview"], expanded=False):
            _metrics = [
                (total_karyawan, _sb_copy["employees"]), (total_mgr, _sb_copy["managers"]),
                (total_bu, _sb_copy["business_units"]), (total_div, _sb_copy["divisions"]),
            ]
            _metric_html = "".join(
                f'<div><div class="od-sb-metric-value">{value:,}</div>'
                f'<div class="od-sb-metric-label">{label}</div></div>'
                for value, label in _metrics
            )
            st.markdown(f'<div class="od-sb-metrics">{_metric_html}</div>'
                        f'<p class="od-sb-scope">{_sb_copy["scope"]}</p>', unsafe_allow_html=True)

    with st.container(key="sb_actions_row"):
        col_sb1, col_sb2 = st.columns(2)
        with col_sb1:
            if st.button(_sb_copy["refresh"], icon=":material/refresh:",
                         help=_sb_copy["refresh_help"], use_container_width=True, key="refresh_btn"):
                st.cache_data.clear(); st.rerun()
        with col_sb2:
            _mode_label = _sb_copy["light"] if dm else _sb_copy["dark"]
            _mode_icon = ":material/light_mode:" if dm else ":material/dark_mode:"
            if st.button(_mode_label, icon=_mode_icon,
                         help=_sb_copy["theme_help"].format(mode=_mode_label.lower()),
                         use_container_width=True, key="toggle_btn"):
                st.session_state.dark_mode = not st.session_state.dark_mode; st.rerun()

    with st.container(key="sb_account"):
        _uname = str(_user_info.get("name") or "User")
        _initials = "".join(w[0].upper() for w in _uname.split()[:2]) or "U"
        _role_display = str(_user_role).replace("_", " ").capitalize()
        if _user_role in ("cxo", "hrbp"):
            _role_display = _user_role.upper()
        st.markdown(f"""
        <div class="od-sb-profile">
            <div class="od-sb-avatar" aria-hidden="true">{html.escape(_initials)}</div>
            <div class="od-sb-identity">
                <div class="od-sb-name">{html.escape(_uname)}</div>
                <div class="od-sb-role">{html.escape(_role_display)}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button(L['btn_logout'], icon=":material/logout:", use_container_width=True, key="logout_btn"):
            log_activity(action_type="logout", detail="User logout")
            for k in ["authenticated","user_email","user_info","acl_user_info","active_tab","session_id","connected","oauth_state","token","google_email","scr_approved_proposal","my_selected_proposal","cr_submit_success"]:
                st.session_state.pop(k, None)
            st.query_params.clear()
            try:
                _google_auth.logout()
            except Exception:
                pass
            st.rerun()

    # Existing reload policy retained.
    st.markdown("""
    <script>
    (function() {
        var RELOAD_MS = 12 * 60 * 60 * 1000;
        function scheduleReload() {
            setTimeout(function() {
                if (document.visibilityState === 'visible') {
                    window.location.reload();
                } else {
                    setTimeout(scheduleReload, 30 * 60 * 1000);
                }
            }, RELOAD_MS);
        }
        scheduleReload();
    })();
    </script>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# MAIN HEADER
# ══════════════════════════════════════════════════════════════════
if st.session_state.get("active_tab", 0) == 0:
    st.markdown(f"""
    <div style="padding:0 0 24px 0;margin-bottom:28px;border-bottom:1px solid {T['outline']};
        display:flex;align-items:flex-end;justify-content:space-between;">
        <div>
            <div style="font-size:11px;font-weight:600;text-transform:uppercase;
                letter-spacing:0.09em;color:{T['text3']};margin-bottom:6px;font-family:'Inter',sans-serif;">{L["header_supra"]}</div>
            <div style="font-size:28px;font-weight:700;color:{T['text']};
                font-family:'Inter',sans-serif;line-height:1.15;letter-spacing:-0.025em;">{L["header_title"]}</div>
            <div style="font-size:13.5px;color:{T['text_variant']};margin-top:6px;font-weight:400;line-height:1.6;font-family:'Inter',sans-serif;">
                {L["header_subtitle"]}
            </div>
        </div>
        <div style="background:{T['primary']};
            border-radius:8px;padding:12px 20px;text-align:right;
            box-shadow:0 2px 16px rgba(142,148,242,0.3);min-width:140px;">
            <div style="font-size:10px;font-weight:600;text-transform:uppercase;
                letter-spacing:0.08em;color:rgba(255,255,255,0.75);margin-bottom:4px;font-family:'Inter',sans-serif;">{L["header_metric"]}</div>
            <div style="font-size:26px;font-weight:700;color:white;
                font-family:'Inter',sans-serif;letter-spacing:-0.03em;line-height:1.1;">{len(df):,}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


_active = st.session_state.get("active_tab", 0)


# ══════════════════════════════════════════════════════════════════
# TAB 1 — ORG CHART
# ══════════════════════════════════════════════════════════════════
if _active == 0:
    # Log activity view org chart — sekali per session
    if not st.session_state.get("_logged_orgchart_view", False):
        log_activity(
            action_type="view_orgchart",
            detail=f"Org Chart dibuka · role={_user_role}",
            record_count=len(df),
        )
        st.session_state["_logged_orgchart_view"] = True

    # [HoB VIEW — 22 Agt 2026] Toggle level-atas per brief PM/CEO. "Functional" = seluruh
    # perilaku org chart yang SUDAH ADA (Per Divisi + Seluruh Perusahaan di bawahnya) —
    # TIDAK DIUBAH SAMA SEKALI, cuma dibungkus di dalam blok if ini. "HoB View" = mode baru.
    #
    # [ROLE-GATE — deploy langsung ke main, 27 Agt 2026, atas keputusan Dave]
    # Brief PM awalnya minta develop di branch `dev`. Karena keterbatasan
    # branch-switching Streamlit Cloud (satu app cuma listen 1 branch),
    # fitur ini di-deploy ke `main` TAPI dikunci role `super_admin` —
    # user lain (admin/leader/employee/cxo) tidak pernah melihat toggle
    # ini sama sekali; behavior mereka identik dengan sebelum fitur ini
    # ada. Kalau HoB View sudah tervalidasi & mau dibuka lebih luas,
    # tinggal ganti kondisi di bawah — jangan hapus role-gate ini
    # diam-diam tanpa keputusan eksplisit soal siapa yang boleh akses.
    if _user_role == "super_admin":
        st.markdown(f"""
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;
            letter-spacing:0.09em;color:{T['text3']};margin-bottom:10px;">TAMPILAN</div>
        """, unsafe_allow_html=True)
        top_mode = st.radio("Tampilan", ["Functional", "HoB View"], horizontal=True,
                            label_visibility="collapsed", key="top_mode_orgchart")
    else:
        top_mode = "Functional"

    if top_mode == "Functional":
        st.markdown(f"""
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;
            letter-spacing:0.09em;color:{T['text3']};margin-bottom:10px;">{L["mode_label"]}</div>
        """, unsafe_allow_html=True)
        view_mode = st.radio("Mode Tampilan", [L["mode_division"], L["mode_company"]], horizontal=True, label_visibility="collapsed")

        # ── [HoB OVERLAY — 27 Agt 2026] Toggle khusus mode Functional ──
        # [FIX AKSES — 27 Agt 2026, konfirmasi Dave: development feature
        # ini jalan di branch `main` dengan kategori app_users super_admin
        # ONLY, sama seperti pola HoB View di atas]. Checkbox ini SEBELUMNYA
        # tidak pernah di-gate — kelewat, cuma toggle "Functional/HoB View"
        # yang di atas yang ke-gate. Sekarang digate juga: non-super_admin
        # tidak pernah lihat checkbox ini sama sekali, show_hob_overlay
        # otomatis False untuk mereka — behavior identik dengan sebelum
        # fitur HoB Overlay ada.
        if _user_role == "super_admin":
            st.markdown(f"""
            <div style="font-size:12px;font-weight:600;color:{T['text3']};text-transform:uppercase;
                letter-spacing:0.06em;margin:4px 0 8px 0;">🔒 SUPER ADMIN ONLY</div>
            """, unsafe_allow_html=True)
            show_hob_overlay = st.checkbox(
                "🏛️ Tampilkan HoB — garis penghubung C-1 ke Head of Business masing-masing",
                value=False, key="show_hob_overlay",
            )
        else:
            show_hob_overlay = False

        # ── Search Name ──────────────────────────────────────────────
        # [FIX] Search sekarang cari di seluruh df, auto-set filter BU/Divisi
        st.markdown(f"""
        <div style="font-size:12px;font-weight:600;color:{T['text3']};text-transform:uppercase;
            letter-spacing:0.06em;margin:16px 0 8px 0;">{L["search_label"]}</div>
        """, unsafe_allow_html=True)

        col_search, col_search_info = st.columns([3, 5])
        with col_search:
            name_search = st.text_input(
                L["search_label"], placeholder=L["search_ph"],
                key="org_name_search", label_visibility="collapsed"
            )

        # Cari di SELURUH df — bukan hanya divisi aktif
        matched_global = pd.DataFrame()
        if name_search.strip():
            matched_global = df[
                df["Employee Name"].str.contains(name_search.strip(), case=False, na=False)
            ].copy()

        with col_search_info:
            if name_search.strip():
                if len(matched_global) == 0:
                    st.markdown(f"""<div style="padding:8px 12px;background:#fee2e2;border-radius:8px;
                        font-size:12px;color:#991b1b;margin-top:4px;">
                        ❌ {L["emp_not_found"]} "<b>{name_search}</b>"</div>""",
                        unsafe_allow_html=True)
                elif len(matched_global) == 1:
                    emp = matched_global.iloc[0]
                    st.markdown(f"""<div style="padding:8px 12px;background:#dcfce7;border-radius:8px;
                        font-size:12px;color:#166534;margin-top:4px;">
                        ✅ {L['emp_found']}: <b>{emp['Employee Name']}</b> — {emp.get('Job Position','')},
                        <b>{emp.get('Division','')}</b> ({emp.get('Business Unit','')})</div>""",
                        unsafe_allow_html=True)
                else:
                    names_list = ", ".join(matched_global["Employee Name"].tolist()[:4])
                    suffix = f" +{len(matched_global)-4} {L['emp_more']}" if len(matched_global) > 4 else ""
                    st.markdown(f"""<div style="padding:8px 12px;background:#fef9c3;border-radius:8px;
                        font-size:12px;color:#854d0e;margin-top:4px;">
                        ⚠️ {L["emp_found"]} <b>{len(matched_global)}</b> {L["employees"]}: {names_list}{suffix}.
                        {L["emp_pick_below"]}</div>""", unsafe_allow_html=True)

        # Jika >1 hasil → selectbox pilih karyawan spesifik
        selected_emp_row = None
        if len(matched_global) > 1:
            emp_choices = [L["emp_select_ph"]] + [
                f"{r['Employee Name']}  ·  {r.get('Division','')}  ·  {r.get('Business Unit','')}"
                for _, r in matched_global.iterrows()
            ]
            chosen_emp = st.selectbox(L["emp_select_label"], emp_choices,
                                      key="search_emp_choice", label_visibility="collapsed")
            if chosen_emp != L["emp_select_ph"]:
                idx_c = emp_choices.index(chosen_emp) - 1
                selected_emp_row = matched_global.iloc[idx_c]
        elif len(matched_global) == 1:
            selected_emp_row = matched_global.iloc[0]

        # AUTO-SET filter BU & Divisi berdasarkan karyawan yang ditemukan/dipilih
        if selected_emp_row is not None:
            _tbu  = str(selected_emp_row.get("Business Unit", ""))
            _tdiv = str(selected_emp_row.get("Division", ""))
            _bu_list_all = sorted(df["Business Unit"].dropna().unique().tolist())
            if _tbu in _bu_list_all:
                st.session_state["sel_bu"] = _tbu
            _div_list_for = sorted(df[df["Business Unit"] == _tbu]["Division"].dropna().unique().tolist())
            if _tdiv in _div_list_for:
                st.session_state["sel_div"] = _tdiv
            st.session_state["sel_sbu"]    = L["filter_all_sbu"]
            st.session_state["sel_leader"] = L["filter_all_div"]

        # ── Auto-highlight: lookup Employee ID dari email login ─────────
        # Jika user belum search manual, otomatis highlight node mereka sendiri
        _login_email      = st.session_state.get("google_email", "")
        _auto_highlight_id = None
        if _login_email and "Email" in df.columns:
            _self_row = df[df["Email"].str.lower() == _login_email.lower()]
            if not _self_row.empty:
                _auto_highlight_id = str(_self_row.iloc[0].get("Employee ID", ""))
                # Auto-set filter ke divisi user sendiri saat pertama kali buka
                if not st.session_state.get("_auto_filter_set", False) and selected_emp_row is None:
                    _tbu_self  = str(_self_row.iloc[0].get("Business Unit", ""))
                    _tdiv_self = str(_self_row.iloc[0].get("Division", ""))
                    _bu_list_all = sorted(df["Business Unit"].dropna().unique().tolist())
                    if _tbu_self in _bu_list_all:
                        st.session_state["sel_bu"]  = _tbu_self
                        st.session_state["sel_div"] = _tdiv_self
                    st.session_state["_auto_filter_set"] = True

        # ID karyawan target untuk highlight di tree
        # Prioritas: search manual > auto-highlight dari login
        search_highlight_id = (
            str(selected_emp_row.get("Employee ID", "")) if selected_emp_row is not None
            else _auto_highlight_id
        )
        if view_mode == L["mode_division"]:
            st.markdown(f"""
            <div style="font-size:12px;font-weight:600;color:{T['text3']};text-transform:uppercase;
                letter-spacing:0.06em;margin:16px 0 10px 0;">{L["filter_label"]}</div>
            """, unsafe_allow_html=True)
            col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 2])
            with col_a:
                bu_list    = sorted(df["Business Unit"].dropna().unique().tolist())
                selected_bu = st.selectbox(L["filter_bu"], bu_list, key="sel_bu")
            with col_b:
                div_list    = sorted(df[df["Business Unit"] == selected_bu]["Division"].dropna().unique().tolist())
                selected_div = st.selectbox(L["filter_div"], div_list, key="sel_div")
            with col_c:
                sbu_opts_raw = [s for s in df[
                    (df["Business Unit"] == selected_bu) & (df["Division"] == selected_div)
                ]["SBU/Tribe"].dropna().unique().tolist() if s.strip() != ""]
                selected_sbu = st.selectbox(L["filter_sbu"], [L["filter_all_sbu"]] + sorted(sbu_opts_raw), key="sel_sbu")

            filtered = df[(df["Business Unit"] == selected_bu) & (df["Division"] == selected_div)].copy()
            if selected_sbu != L["filter_all_sbu"]:
                filtered = filtered[filtered["SBU/Tribe"] == selected_sbu].copy()

            all_leaders = filtered[filtered["Employee ID"].isin(df["Manager ID"].unique())]["Employee Name"].tolist()
            with col_d:
                selected_leader = st.selectbox(L["filter_leader"],
                                               [L["filter_all_div"]] + sorted(all_leaders), key="sel_leader")

            if selected_leader != L["filter_all_div"]:
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

            # ── Cross-division subordinate fix ────────────────────────────
            # Ketika user search nama seseorang, subordinate mereka yang ada
            # di divisi lain tidak masuk ke filtered (karena filter by Division).
            # Fix: BFS downward dari search target di SELURUH df, lalu gabungkan
            # hasilnya dengan filtered agar semua subordinate lintas divisi muncul.
            if search_highlight_id and selected_emp_row is not None:
                _cross_ids  = set()
                _cross_q    = [search_highlight_id]
                while _cross_q:
                    _curr = _cross_q.pop()
                    _cross_ids.add(_curr)
                    _cross_q.extend(df[df["Manager ID"] == _curr]["Employee ID"].tolist())
                # Gabungkan dengan filtered (union), bukan replace
                _cross_df   = df[df["Employee ID"].isin(_cross_ids)].copy()
                filtered    = pd.concat([filtered, _cross_df]).drop_duplicates(
                                  subset=["Employee ID"], keep="last").reset_index(drop=True)

            # ── Metric Cards: dihitung SETELAH semua filter aktif ─────────────
            # (leader filter + cross-division fix sudah diaplikasikan ke `filtered`)
            _ldr_active  = selected_leader != L["filter_all_div"]
            _scope_label = (
                selected_leader if _ldr_active
                else (selected_div if selected_sbu == L["filter_all_sbu"]
                      else f"{selected_div} — {selected_sbu}")
            )
            _count_emp   = len(filtered)
            _count_mgr   = filtered[filtered["Employee ID"].isin(df["Manager ID"].unique())]["Employee ID"].nunique()
            _count_ic    = _count_emp - _count_mgr
            st.markdown(f"""
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0 20px 0;">
                <div style="background:{T['surface_lowest']};border-radius:10px;padding:14px 16px;
                    box-shadow:0 1px 0 0 {T['outline']},0 2px 16px {T['metric_shadow']};position:relative;overflow:hidden;">
                    <div style="position:absolute;top:0;left:0;right:0;height:3px;
                        background:{T['primary']};opacity:0.7;border-radius:10px 10px 0 0;"></div>
                    <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;
                        color:{T['text3']};margin-bottom:6px;">👥 {L['div_emp_count_label']}</div>
                    <div style="font-size:26px;font-weight:700;color:{T['text']};letter-spacing:-0.03em;line-height:1;">{_count_emp:,}</div>
                    <div style="font-size:10px;color:{T['text3']};margin-top:4px;">{_scope_label}</div>
                </div>
                <div style="background:{T['surface_lowest']};border-radius:10px;padding:14px 16px;
                    box-shadow:0 1px 0 0 {T['outline']},0 2px 16px {T['metric_shadow']};position:relative;overflow:hidden;">
                    <div style="position:absolute;top:0;left:0;right:0;height:3px;
                        background:#8b5cf6;opacity:0.7;border-radius:10px 10px 0 0;"></div>
                    <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;
                        color:{T['text3']};margin-bottom:6px;">📋 {L['div_mgr_count_label']}</div>
                    <div style="font-size:26px;font-weight:700;color:{T['text']};letter-spacing:-0.03em;line-height:1;">{_count_mgr:,}</div>
                    <div style="font-size:10px;color:{T['text3']};margin-top:4px;">IC: {_count_ic:,}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_lv, col_info = st.columns([2, 4])
            with col_lv:
                level_opt = st.selectbox(L["expand_level"], ["All Level", "Top Level", "Level 1", "Level 2", "Level 3"])
            with col_info:
                if search_highlight_id and search_highlight_id in filtered["Employee ID"].values:
                    # Ambil nama dari selected_emp_row (search manual) atau lookup dari df (auto-highlight)
                    if selected_emp_row is not None:
                        _emp_name_hl = selected_emp_row["Employee Name"]
                    else:
                        _hl_row = df[df["Employee ID"] == search_highlight_id]
                        _emp_name_hl = _hl_row.iloc[0]["Employee Name"] if not _hl_row.empty else search_highlight_id
                    st.caption(f"📊 {L['showing_emp']} **{len(filtered)}** {L['employees']} — 🎯 **{_emp_name_hl}** {L['emp_found_in']}")
                else:
                    st.caption(f"📊 {L['showing_emp']} **{len(filtered)}** {L['employees']} {L['emp_in_div']}")

            selected_level  = {"All Level": "all", "Top Level": "top", "Level 1": "level1", "Level 2": "level2", "Level 3": "level3"}[level_opt]
            all_ids_needed  = get_all_managers(filtered["Employee ID"].tolist(), df)
            full_data       = df[df["Employee ID"].isin(all_ids_needed)].copy()
            all_ids_set     = set(full_data["Employee ID"].tolist())

            root_ids = full_data[
                ~full_data["Manager ID"].isin(all_ids_set) | full_data["Manager ID"].isin({"", "nan"})
            ]["Employee ID"].astype(str).tolist()

            tree_data  = build_tree_json(full_data, selected_div, root_ids, mode="division")
            if show_hob_overlay:
                # full_data (parameter scope_data) SUDAH ter-filter BU/Div/SBU
                # aktif — dipakai untuk lookup Primary Budget Holder siapa
                # saja yang sedang tampil. Penentuan overlay MURNI dari
                # kolom itu (lihat docstring annotate_hob_overlay) — tidak
                # ada lagi ketergantungan ke CHIEF_ROOT/hierarchy level.
                tree_data = annotate_hob_overlay(tree_data, full_data)
            chart_html = render_org_chart(json.dumps(tree_data), chart_height=680, initial_level=selected_level, theme=T, highlight_id=search_highlight_id, labels=L)
            _render_chart_iframe(chart_html, height=680, scrolling=False)

            st.markdown(f"**{L['download_data']}**")
            col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)
            with col_dl1:
                st.download_button("📄 CSV", filtered.to_csv(index=False).encode("utf-8"),
                                   f"{selected_div}.csv", "text/csv", use_container_width=True)
            with col_dl2:
                st.download_button("📊 Excel", to_excel(filtered), f"{selected_div}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col_dl3:
                if st.button("📑 Generate PDF (Full)", key="gen_pdf_full_div", use_container_width=True):
                    try:
                        st.session_state["pdf_full_div_bytes"] = generate_pdf(
                            tree_data, f"Org Chart — {selected_div} ({selected_bu})",
                            div_name=selected_div, bu_name=selected_bu, max_level=selected_level)
                    except Exception:
                        st.session_state["pdf_full_div_bytes"] = None
                        st.error("Gagal generate PDF.")
                if st.session_state.get("pdf_full_div_bytes"):
                    st.download_button("⬇️ Download PDF (Full)", st.session_state["pdf_full_div_bytes"],
                                       f"{selected_div}_full.pdf", "application/pdf", use_container_width=True)
            with col_dl4:
                if st.button("📑 Generate PDF (Summary)", key="gen_pdf_sum_div", use_container_width=True):
                    try:
                        st.session_state["pdf_sum_div_bytes"] = generate_pdf_summary(
                            tree_data, f"Org Chart Summary — {selected_div} ({selected_bu})",
                            div_name=selected_div, bu_name=selected_bu)
                    except Exception:
                        st.session_state["pdf_sum_div_bytes"] = None
                        st.error("Gagal generate PDF summary.")
                if st.session_state.get("pdf_sum_div_bytes"):
                    st.download_button("⬇️ Download PDF (Summary)", st.session_state["pdf_sum_div_bytes"],
                                       f"{selected_div}_summary.pdf", "application/pdf", use_container_width=True)

        else:
            st.info(L["company_warning"])
            col_lv2, col_inf2 = st.columns([2, 4])
            with col_lv2:
                level_opt2 = st.selectbox(L["expand_level"], ["All Level", "Top Level", "Level 1", "Level 2", "Level 3"], key="lv2")
            with col_inf2:
                st.caption(f"📊 {L['showing_emp']} **{len(df)}** {L['employees']}")

            selected_level2 = {"All Level": "all", "Top Level": "top", "Level 1": "level1", "Level 2": "level2", "Level 3": "level3"}[level_opt2]
            # Mode perusahaan: tampilkan seluruh tree (search sudah auto-switch ke Per Divisi)
            root_ids2  = df[(df["Manager ID"] == "") | (df["Manager ID"].isna())]["Employee ID"].tolist()
            tree_data2 = build_tree_json(df, "", root_ids2, mode="company")
            if show_hob_overlay:
                tree_data2 = annotate_hob_overlay(tree_data2, df)
            chart_html2 = render_org_chart(json.dumps(tree_data2), chart_height=750, initial_level=selected_level2, theme=T, labels=L)
            _render_chart_iframe(chart_html2, height=750, scrolling=False)

            st.markdown(f"**{L['download_data']}**")
            col_dl4, col_dl5, col_dl6, col_dl7 = st.columns(4)
            with col_dl4:
                st.download_button("📄 CSV", df.to_csv(index=False).encode("utf-8"),
                                   "all_employees.csv", "text/csv", use_container_width=True)
            with col_dl5:
                st.download_button("📊 Excel", to_excel(df), "all_employees.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col_dl6:
                if st.button("📑 Generate PDF (Full)", key="gen_pdf_full_co", use_container_width=True):
                    try:
                        st.session_state["pdf_full_co_bytes"] = generate_pdf(
                            tree_data2, L["pdf_company_title"],
                            div_name=L["pdf_all_div"], bu_name=L["pdf_all_bu"], max_level=selected_level2)
                    except Exception:
                        st.session_state["pdf_full_co_bytes"] = None
                        st.error("Gagal generate PDF.")
                if st.session_state.get("pdf_full_co_bytes"):
                    st.download_button("⬇️ Download PDF (Full)", st.session_state["pdf_full_co_bytes"],
                                       "orgchart_perusahaan_full.pdf", "application/pdf", use_container_width=True)
            with col_dl7:
                if st.button("📑 Generate PDF (Summary)", key="gen_pdf_sum_co", use_container_width=True):
                    try:
                        st.session_state["pdf_sum_co_bytes"] = generate_pdf_summary(
                            tree_data2, f"{L['pdf_company_title']} (Summary)",
                            div_name=L["pdf_all_div"], bu_name=L["pdf_all_bu"])
                    except Exception:
                        st.session_state["pdf_sum_co_bytes"] = None
                        st.error("Gagal generate PDF summary.")
                if st.session_state.get("pdf_sum_co_bytes"):
                    st.download_button("⬇️ Download PDF (Summary)", st.session_state["pdf_sum_co_bytes"],
                                       "orgchart_perusahaan_summary.pdf", "application/pdf", use_container_width=True)

    else:  # top_mode == "HoB View"
        st.info(
            "🏛️ **HoB View** — struktur dikelompokkan berdasarkan **Primary Budget Holder**, "
            "bukan reporting line langsung. HoB (Head of Business) sebagai root, C-1/Leader di "
            "bawahnya adalah yang Budget Holder-nya = HoB tsb; dari situ ke bawah mengikuti "
            "reporting line normal."
        )

        # ── [BUGFIX 27 Agt 2026] Search by name — sebelumnya tidak ada
        # sama sekali di HoB View. Pola sengaja disamakan persis dengan
        # search di Functional mode (baris ~3050-3070 di atas) supaya
        # UX konsisten antar mode; bedanya, di sini hasil search JUGA
        # auto-select "Filter HoB" ke HoB yang menaungi orang tsb.
        st.markdown(f"""
        <div style="font-size:12px;font-weight:600;color:{T['text3']};text-transform:uppercase;
            letter-spacing:0.06em;margin:16px 0 8px 0;">{L["search_label"]}</div>
        """, unsafe_allow_html=True)

        col_search_h, col_search_info_h = st.columns([3, 5])
        with col_search_h:
            name_search_h = st.text_input(
                L["search_label"], placeholder=L["search_ph"],
                key="hob_name_search", label_visibility="collapsed",
            )

        matched_global_h = pd.DataFrame()
        if name_search_h.strip():
            matched_global_h = df[
                df["Employee Name"].str.contains(name_search_h.strip(), case=False, na=False)
            ].copy()

        with col_search_info_h:
            if name_search_h.strip():
                if len(matched_global_h) == 0:
                    st.markdown(f"""<div style="padding:8px 12px;background:#fee2e2;border-radius:8px;
                        font-size:12px;color:#991b1b;margin-top:4px;">
                        ❌ {L["emp_not_found"]} "<b>{name_search_h}</b>"</div>""", unsafe_allow_html=True)
                elif len(matched_global_h) == 1:
                    _emp_h = matched_global_h.iloc[0]
                    st.markdown(f"""<div style="padding:8px 12px;background:#dcfce7;border-radius:8px;
                        font-size:12px;color:#166534;margin-top:4px;">
                        ✅ {L['emp_found']}: <b>{_emp_h['Employee Name']}</b> — {_emp_h.get('Job Position','')},
                        <b>{_emp_h.get('Division','')}</b> ({_emp_h.get('Business Unit','')})</div>""", unsafe_allow_html=True)
                else:
                    _names_h = ", ".join(matched_global_h["Employee Name"].tolist()[:4])
                    _suffix_h = f" +{len(matched_global_h)-4} {L['emp_more']}" if len(matched_global_h) > 4 else ""
                    st.markdown(f"""<div style="padding:8px 12px;background:#fef9c3;border-radius:8px;
                        font-size:12px;color:#854d0e;margin-top:4px;">
                        ⚠️ {L["emp_found"]} <b>{len(matched_global_h)}</b> {L["employees"]}: {_names_h}{_suffix_h}.
                        {L["emp_pick_below"]}</div>""", unsafe_allow_html=True)

        selected_emp_row_h = None
        if len(matched_global_h) > 1:
            emp_choices_h = [L["emp_select_ph"]] + [
                f"{r['Employee Name']}  ·  {r.get('Division','')}  ·  {r.get('Business Unit','')}"
                for _, r in matched_global_h.iterrows()
            ]
            chosen_emp_h = st.selectbox(L["emp_select_label"], emp_choices_h,
                                        key="hob_search_emp_choice", label_visibility="collapsed")
            if chosen_emp_h != L["emp_select_ph"]:
                selected_emp_row_h = matched_global_h.iloc[emp_choices_h.index(chosen_emp_h) - 1]
        elif len(matched_global_h) == 1:
            selected_emp_row_h = matched_global_h.iloc[0]

        # Auto-set filter BU/Div/SBU + Filter HoB — HARUS dilakukan
        # SEBELUM widget selectbox filter di bawah (col_h1..col_h4)
        # diinstansiasi di run ini, kalau tidak Streamlit lempar
        # StreamlitAPIException "cannot be modified after widget created".
        search_highlight_id_h = None
        if selected_emp_row_h is not None:
            search_highlight_id_h = str(selected_emp_row_h.get("Employee ID", ""))
            _tbu_h  = str(selected_emp_row_h.get("Business Unit", ""))
            _tdiv_h = str(selected_emp_row_h.get("Division", ""))
            _bu_list_all_h = sorted(df["Business Unit"].dropna().unique().tolist())
            if _tbu_h in _bu_list_all_h:
                st.session_state["hob_bu"] = _tbu_h
            _div_list_for_h = sorted(df[df["Business Unit"] == _tbu_h]["Division"].dropna().unique().tolist())
            if _tdiv_h in _div_list_for_h:
                st.session_state["hob_div"] = _tdiv_h
            st.session_state["hob_sbu"] = "Semua"

            # Cari HoB mana yang menaungi orang ini — supaya "Filter HoB"
            # auto-pindah ke situ. Fallback: kalau orang ini tidak
            # ketemu di tree HoB manapun (misal data Budget Holder-nya
            # putus di tengah rantai manager), biarkan "Filter HoB" apa
            # adanya — jangan paksa "Semua HoB" karena itu bisa nutupin
            # fakta bahwa ada masalah data untuk orang ini.
            _membership_h = get_hob_membership_map(df)
            _owner_hob_name = _membership_h.get(search_highlight_id_h)
            if _owner_hob_name:
                st.session_state["hob_sel"] = _owner_hob_name

        st.markdown(f"""
        <div style="font-size:12px;font-weight:600;color:{T['text3']};text-transform:uppercase;
            letter-spacing:0.06em;margin:16px 0 10px 0;">{L["filter_label"]}</div>
        """, unsafe_allow_html=True)

        col_h1, col_h2, col_h3, col_h4 = st.columns([2, 2, 2, 2])
        with col_h1:
            hob_name_opts = ["Semua HoB"] + [v["name"] for v in HOB_MAPPING.values()]
            hob_name_sel  = st.selectbox("Filter HoB", hob_name_opts, key="hob_sel")
        with col_h2:
            bu_h = st.selectbox(L["filter_bu"], ["Semua"] + sorted(df["Business Unit"].dropna().unique().tolist()), key="hob_bu")
        with col_h3:
            div_h_opts = (["Semua"] + sorted(df[df["Business Unit"] == bu_h]["Division"].dropna().unique().tolist())
                          if bu_h != "Semua" else ["Semua"] + sorted(df["Division"].dropna().unique().tolist()))
            div_h = st.selectbox(L["filter_div"], div_h_opts, key="hob_div")
        with col_h4:
            sbu_h_src = df.copy()
            if bu_h  != "Semua": sbu_h_src = sbu_h_src[sbu_h_src["Business Unit"] == bu_h]
            if div_h != "Semua": sbu_h_src = sbu_h_src[sbu_h_src["Division"] == div_h]
            sbu_h_opts = ["Semua"] + sorted([s for s in sbu_h_src["SBU/Tribe"].dropna().unique().tolist() if s.strip() != ""])
            sbu_h = st.selectbox(L["filter_sbu"], sbu_h_opts, key="hob_sbu")

        # ── Scope data untuk HoB tree ───────────────────────────────
        # Filter BU/Div/SBU MENYEMPITKAN siapa saja yang boleh muncul
        # sebagai node (baik HoB root maupun turunannya) — konsisten
        # dengan constraint brief "semua filter existing tetap berfungsi".
        # PENTING: filter ini diterapkan ke seluruh `df`, BUKAN cuma ke
        # kandidat C-1 — supaya turunan lintas-BU/Divisi di bawah C-1
        # tetap ikut ketampung (sama prinsipnya dengan get_all_managers
        # di mode Functional, cuma arahnya ke bawah bukan ke atas).
        hob_scope = df.copy()
        if bu_h  != "Semua": hob_scope = hob_scope[hob_scope["Business Unit"] == bu_h]
        if div_h != "Semua": hob_scope = hob_scope[hob_scope["Division"] == div_h]
        if sbu_h != "Semua": hob_scope = hob_scope[hob_scope["SBU/Tribe"] == sbu_h]

        # HoB node sendiri harus selalu ikut kebawa meski dia sendiri
        # secara kebetulan ke-filter keluar oleh BU/Div/SBU (biar root
        # tetap muncul, walau kosong tanpa anak — user jadi tahu filter
        # kombinasi ini "menutup" HoB tsb, bukan aplikasi yang error).
        _hob_ids_all = [v["id"] for v in HOB_MAPPING.values()]
        hob_scope = pd.concat([hob_scope, df[df["Employee ID"].isin(_hob_ids_all)]]).drop_duplicates(
            subset=["Employee ID"], keep="last").reset_index(drop=True)

        hob_ids_filter = ()
        if hob_name_sel != "Semua HoB":
            hob_ids_filter = tuple(v["id"] for v in HOB_MAPPING.values() if v["name"] == hob_name_sel)

        col_lv_h, col_info_h = st.columns([2, 4])
        with col_lv_h:
            # [Definisi Done] Default expand = "Level 3" sesuai brief PM
            # ("Default expand HoB View di Level 3 / C-1").
            level_opts_h = ["All Level", "Top Level", "Level 1", "Level 2", "Level 3"]
            level_opt_h  = st.selectbox(L["expand_level"], level_opts_h, index=level_opts_h.index("Level 3"), key="hob_level")
        with col_info_h:
            st.caption(f"📊 Menampilkan **{len(hob_scope)}** karyawan dalam scope filter saat ini")

        selected_level_h = {"All Level": "all", "Top Level": "top", "Level 1": "level1",
                            "Level 2": "level2", "Level 3": "level3"}[level_opt_h]

        tree_data_hob  = build_hob_tree_json(hob_scope, hob_ids_filter=hob_ids_filter)
        if not tree_data_hob:
            st.warning(
                "⚠️ Tidak ada HoB yang cocok dengan kombinasi filter ini. Coba longgarkan filter "
                "BU/Divisi/SBU, atau cek apakah HoB yang dipilih memang berada di scope tsb."
            )
        else:
            chart_html_hob = render_org_chart(json.dumps(tree_data_hob), chart_height=750,
                                              initial_level=selected_level_h, theme=T,
                                              highlight_id=search_highlight_id_h, labels=L)
            _render_chart_iframe(chart_html_hob, height=750, scrolling=False)

            st.markdown(f"**{L['download_data']}**")
            col_hd1, col_hd2, col_hd3, col_hd4 = st.columns(4)
            with col_hd1:
                st.download_button("📄 CSV", hob_scope.to_csv(index=False).encode("utf-8"),
                                   "hob_view.csv", "text/csv", use_container_width=True)
            with col_hd2:
                st.download_button("📊 Excel", to_excel(hob_scope), "hob_view.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col_hd3:
                if st.button("📑 Generate PDF (Full)", key="gen_pdf_full_hob", use_container_width=True):
                    try:
                        st.session_state["pdf_full_hob_bytes"] = generate_pdf(
                            tree_data_hob, f"Org Chart — HoB View ({hob_name_sel})",
                            div_name=hob_name_sel, bu_name="HoB View", max_level=selected_level_h)
                    except Exception:
                        st.session_state["pdf_full_hob_bytes"] = None
                        st.error("Gagal generate PDF.")
                if st.session_state.get("pdf_full_hob_bytes"):
                    st.download_button("⬇️ Download PDF (Full)", st.session_state["pdf_full_hob_bytes"],
                                       "hob_view_full.pdf", "application/pdf", use_container_width=True)
            with col_hd4:
                if st.button("📑 Generate PDF (Summary)", key="gen_pdf_sum_hob", use_container_width=True):
                    try:
                        st.session_state["pdf_sum_hob_bytes"] = generate_pdf_summary(
                            tree_data_hob, f"Org Chart Summary — HoB View ({hob_name_sel})",
                            div_name=hob_name_sel, bu_name="HoB View")
                    except Exception:
                        st.session_state["pdf_sum_hob_bytes"] = None
                        st.error("Gagal generate PDF summary.")
                if st.session_state.get("pdf_sum_hob_bytes"):
                    st.download_button("⬇️ Download PDF (Summary)", st.session_state["pdf_sum_hob_bytes"],
                                       "hob_view_summary.pdf", "application/pdf", use_container_width=True)


# ══════════════════════════════════════════════════════════════════
# TAB 2 — DATA KARYAWAN
# ══════════════════════════════════════════════════════════════════
elif _active == 1:
    if not _can_access_tab(_user_role, 1):
        st.error("🚫 Akses ditolak — fitur ini hanya untuk Super Admin.")
        st.stop()
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
# TAB 3 — COMPLIANCE CHECK
# ══════════════════════════════════════════════════════════════════
elif _active == 2:
    if not _can_access_tab(_user_role, 2):
        st.error("🚫 Akses ditolak — fitur ini hanya untuk Super Admin.")
        st.stop()
    _title_cc = L["tab_cc_title"]
    _sub_cc   = L["tab_cc_sub"]
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:20px;font-weight:700;color:{T['text']};">{_title_cc}</div>
        <div style="font-size:13px;color:{T['text_variant']};margin-top:4px;">{_sub_cc}</div>
    </div>
    """, unsafe_allow_html=True)

    mpp_df = load_mpp_data()
    checks = run_compliance_checks(df, mpp_df)

    miss_df  = checks["missing_manager"]
    mis_df   = checks["mismatch"]
    ghost_df = checks["ghost"]
    vac_df   = checks["vacancy"]

    # ── KPI Cards — 4 kategori, tanpa "Total Anomali" yang misleading ──
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        L["cc_missing_mgr"],
        len(miss_df),
        help="Karyawan yang tidak memiliki Manager ID — perlu segera dilengkapi karena mempengaruhi struktur hierarki."
    )
    k2.metric(
        L["cc_mismatch"],
        L["cc_unavailable"] if mpp_df.empty else len(mis_df),
        help="Karyawan yang Job ID-nya cocok di Employee Data & MPP, namun ada field yang berbeda (contoh: nama divisi, career stage). Indikasi data tidak sinkron antar sistem."
    )
    k3.metric(
        L["cc_ghost"],
        L["cc_unavailable"] if mpp_df.empty else len(ghost_df),
        help="Karyawan terdaftar di Employee Data namun Job ID-nya tidak ada di MPP. Kemungkinan posisi belum di-plot di MPP atau Job ID belum diinput."
    )
    k4.metric(
        L["cc_vacancy"],
        L["cc_unavailable"] if mpp_df.empty else len(vac_df),
        help="Job ID terdaftar di Master MPP namun belum terisi di Employee Data — posisi yang direncanakan namun belum terpenuhi (open headcount)."
    )

    if mpp_df.empty:
        st.warning(L["cc_no_mpp"])

    st.divider()

    cc_t1, cc_t2, cc_t3, cc_t4 = st.tabs([
        L["cc_tab_missing"], L["cc_tab_mismatch"],
        L["cc_tab_ghost"],   L["cc_tab_vacancy"],
    ])

    # ── Missing Manager ID ────────────────────────────────────────
    with cc_t1:
        if miss_df.empty:
            st.success(L["cc_clean"])
        else:
            _all_txt = L["filter_all"]
            col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
            with col_f1:
                bu_nr = st.selectbox(L["filter_bu_plain"],
                    [_all_txt] + sorted(miss_df["Business Unit"].dropna().unique().tolist()), key="cc_bu_nr")
            with col_f2:
                _div_opts = sorted(miss_df[miss_df["Business Unit"]==bu_nr]["Division"].dropna().unique().tolist()) if bu_nr != _all_txt else sorted(miss_df["Division"].dropna().unique().tolist())
                div_nr = st.selectbox(L["filter_div_plain"], [_all_txt] + _div_opts, key="cc_div_nr")
            with col_f3:
                jobid_search_nr = st.text_input("🔑 Cari Job ID", placeholder="Ketik Job ID...", key="cc_nr_jobid_search")

            view_miss = miss_df.copy()
            if bu_nr  != _all_txt: view_miss = view_miss[view_miss["Business Unit"] == bu_nr]
            if div_nr != _all_txt: view_miss = view_miss[view_miss["Division"] == div_nr]
            if jobid_search_nr.strip() and "Job ID" in view_miss.columns:
                view_miss = view_miss[view_miss["Job ID"].astype(str).str.contains(jobid_search_nr.strip(), case=False, na=False)]

            st.caption(f"{L['showing']} **{len(view_miss)}** {L['employees']}")
            st.dataframe(view_miss, use_container_width=True, height=400)

            _bkd_title = L["breakdown_div"]
            st.markdown(f"<div style='font-size:14px;font-weight:600;color:{T['text']};margin:16px 0 8px 0;'>{_bkd_title}</div>", unsafe_allow_html=True)
            bkd = view_miss.groupby(["Business Unit","Division"]).size().reset_index(name="Count").sort_values("Count",ascending=False)
            st.dataframe(bkd, use_container_width=True, height=220)
            st.divider()
            c1, c2, _ = st.columns([1,1,3])
            with c1: st.download_button(L["download_csv"], view_miss.to_csv(index=False).encode("utf-8"), "missing_manager.csv","text/csv",use_container_width=True)
            with c2: st.download_button(L["download_excel"], to_excel(view_miss),"missing_manager.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)

    # ── Data Tidak Konsisten ──────────────────────────────────────
    with cc_t2:
        if mpp_df.empty:
            st.info(L["cc_no_mpp"])
        else:
            if st.session_state.lang == "id":
                _mis_note = "Karyawan dengan Job ID yang <b>cocok</b> antara Employee Data dan MPP, namun terdapat <b>perbedaan nilai pada field tertentu</b> (contoh: Divisi di Employee Data berbeda dengan Divisi di MPP). Ini mengindikasikan data tidak sinkron — perlu direkonsiliasi."
            else:
                _mis_note = "Employees whose Job ID <b>matches</b> between Employee Data and MPP, but have <b>field-level differences</b> (e.g., Division in Employee Data differs from MPP). This indicates out-of-sync data that needs reconciliation."
            st.markdown(f"<div style='background:{T['warn_bg']};border:1px solid {T['warn_bdr']};border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:13px;color:{T['warn_txt']};'>🔀 <b>{'Data Tidak Konsisten' if st.session_state.lang == 'id' else 'Data Inconsistency'}</b> — {_mis_note}</div>", unsafe_allow_html=True)

            if mis_df.empty:
                st.success(L["cc_clean"])
            else:
                col_mf1, col_mf2, col_mf3 = st.columns([2, 2, 2])
                with col_mf1:
                    _field_opts = sorted(mis_df["Field"].unique().tolist())
                    sel_fields = st.multiselect("Filter Field", _field_opts, default=_field_opts, key="cc_mismatch_fields")
                with col_mf2:
                    _jobid_opts_mis = ["Semua"] + sorted(mis_df["Job ID"].dropna().unique().tolist()) if "Job ID" in mis_df.columns else ["Semua"]
                    sel_jobid_mis = st.selectbox("🔑 Filter Job ID", _jobid_opts_mis, key="cc_mis_jobid")
                with col_mf3:
                    jobid_search_mis = st.text_input("🔍 Cari Job ID (manual)", placeholder="Ketik Job ID...", key="cc_mis_jobid_search")

                view_mis = mis_df.copy()
                if sel_fields: view_mis = view_mis[view_mis["Field"].isin(sel_fields)]
                if "Job ID" in view_mis.columns:
                    if sel_jobid_mis != "Semua": view_mis = view_mis[view_mis["Job ID"] == sel_jobid_mis]
                    if jobid_search_mis.strip(): view_mis = view_mis[view_mis["Job ID"].astype(str).str.contains(jobid_search_mis.strip(), case=False, na=False)]

                st.caption(f"{L['showing']} **{len(view_mis)}** isu")
                st.dataframe(view_mis, use_container_width=True, height=400)

                st.divider()
                _bkd2_title = "Breakdown by Field" if st.session_state.lang == "en" else "Breakdown per Field"
                st.markdown(f"<div style='font-size:14px;font-weight:600;color:{T['text']};margin-bottom:8px;'>{_bkd2_title}</div>", unsafe_allow_html=True)
                field_bkd = view_mis.groupby(["Field","Severity"]).size().reset_index(name="Count").sort_values("Count",ascending=False)
                st.dataframe(field_bkd, use_container_width=True, height=200)
                st.divider()
                c1, c2, _ = st.columns([1,1,3])
                with c1: st.download_button(L["download_csv"], view_mis.to_csv(index=False).encode("utf-8"),"data_inconsistency.csv","text/csv",use_container_width=True)
                with c2: st.download_button(L["download_excel"], to_excel(view_mis),"data_inconsistency.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)

    # ── Tidak Terpetakan (sebelumnya: Ghost Employee) ─────────────
    with cc_t3:
        if mpp_df.empty:
            st.info(L["cc_no_mpp"])
        else:
            if st.session_state.lang == "id":
                _ghost_note = "Karyawan terdaftar di <b>Employee Data</b> namun <b>Job ID-nya tidak ditemukan di MPP</b>. Kemungkinan posisi belum di-plot di MPP, atau Job ID belum diinput di sistem."
            else:
                _ghost_note = "Employee exists in <b>Employee Data</b> but their <b>Job ID has no match in MPP Data</b>. Position may not be plotted in MPP, or Job ID not yet entered."
            st.markdown(f"<div style='background:{T['warn_bg']};border:1px solid {T['warn_bdr']};border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:13px;color:{T['warn_txt']};'>🔍 <b>{'Karyawan Tidak Terpetakan' if st.session_state.lang == 'id' else 'Unmapped Employees'}</b> — {_ghost_note}</div>", unsafe_allow_html=True)

            if ghost_df.empty:
                st.success(L["cc_clean"])
            else:
                col_g1, col_g2, col_g3 = st.columns([2, 2, 2])
                with col_g1:
                    _bu_g_opts = ["Semua"] + sorted(ghost_df["Business Unit"].dropna().unique().tolist()) if "Business Unit" in ghost_df.columns else ["Semua"]
                    bu_g = st.selectbox(L["filter_bu_plain"], _bu_g_opts, key="cc_ghost_bu")
                with col_g2:
                    _jobid_opts_g = ["Semua"] + sorted(ghost_df["Job ID"].dropna().unique().tolist()) if "Job ID" in ghost_df.columns else ["Semua"]
                    sel_jobid_g = st.selectbox("🔑 Filter Job ID", _jobid_opts_g, key="cc_ghost_jobid")
                with col_g3:
                    jobid_search_g = st.text_input("🔍 Cari Job ID (manual)", placeholder="Ketik Job ID...", key="cc_ghost_jobid_search")

                view_ghost = ghost_df.copy()
                if "Business Unit" in view_ghost.columns and bu_g != "Semua":
                    view_ghost = view_ghost[view_ghost["Business Unit"] == bu_g]
                if "Job ID" in view_ghost.columns:
                    if sel_jobid_g != "Semua": view_ghost = view_ghost[view_ghost["Job ID"] == sel_jobid_g]
                    if jobid_search_g.strip(): view_ghost = view_ghost[view_ghost["Job ID"].astype(str).str.contains(jobid_search_g.strip(), case=False, na=False)]

                st.caption(f"{L['showing']} **{len(view_ghost)}** {L['employees']}")
                st.dataframe(view_ghost, use_container_width=True, height=430)
                st.divider()
                c1, c2, _ = st.columns([1,1,3])
                with c1: st.download_button(L["download_csv"], view_ghost.to_csv(index=False).encode("utf-8"),"unmapped_employees.csv","text/csv",use_container_width=True)
                with c2: st.download_button(L["download_excel"], to_excel(view_ghost),"unmapped_employees.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)

    # ── Master MPP (sebelumnya: Vacancy) ─────────────────────────
    with cc_t4:
        if mpp_df.empty:
            st.info(L["cc_no_mpp"])
        else:
            if st.session_state.lang == "id":
                _vac_note = "Seluruh Job ID yang terdaftar di <b>Master MPP</b>. Posisi yang <b>belum terisi</b> di Employee Data merupakan open headcount — perlu diisi rekrutmen atau ditinjau validitasnya."
            else:
                _vac_note = "All Job IDs registered in <b>Master MPP</b>. Positions <b>not yet filled</b> in Employee Data are open headcount — requires recruitment action or validity review."
            st.markdown(f"<div style='background:{T['accent_bg']};border:1px solid {T['border2']};border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:13px;color:{T['accent']};'>📋 <b>Master MPP</b> — {_vac_note}</div>", unsafe_allow_html=True)

            if vac_df.empty:
                st.success(L["cc_clean"])
            else:
                col_v1, col_v2, col_v3, col_v4 = st.columns([2, 2, 2, 2])
                with col_v1:
                    _bu_v_opts = ["Semua"] + sorted(vac_df["BU"].dropna().unique().tolist()) if "BU" in vac_df.columns else ["Semua"]
                    bu_v = st.selectbox("Filter BU", _bu_v_opts, key="cc_vac_bu")
                with col_v2:
                    _div_v_opts = ["Semua"] + sorted(vac_df["Division"].dropna().unique().tolist()) if "Division" in vac_df.columns else ["Semua"]
                    div_v = st.selectbox("Filter Divisi", _div_v_opts, key="cc_vac_div")
                with col_v3:
                    _status_v_opts = ["Semua"] + sorted(vac_df["Fulfillment Status"].dropna().unique().tolist()) if "Fulfillment Status" in vac_df.columns else ["Semua"]
                    status_v = st.selectbox("Filter Fulfillment Status", _status_v_opts, key="cc_vac_status")
                with col_v4:
                    jobid_search_v = st.text_input("🔑 Cari Job ID", placeholder="Ketik Job ID atau sebagian...", key="cc_vac_jobid_search")

                view_vac = vac_df.copy()
                if "BU" in view_vac.columns and bu_v != "Semua":          view_vac = view_vac[view_vac["BU"] == bu_v]
                if "Division" in view_vac.columns and div_v != "Semua":    view_vac = view_vac[view_vac["Division"] == div_v]
                if "Fulfillment Status" in view_vac.columns and status_v != "Semua":
                    view_vac = view_vac[view_vac["Fulfillment Status"] == status_v]
                if jobid_search_v.strip() and "JOBID" in view_vac.columns:
                    view_vac = view_vac[view_vac["JOBID"].astype(str).str.contains(jobid_search_v.strip(), case=False, na=False)]

                st.caption(f"{L['showing']} **{len(view_vac)}** posisi MPP")
                st.dataframe(view_vac, use_container_width=True, height=430)
                st.divider()
                c1, c2, _ = st.columns([1,1,3])
                with c1: st.download_button(L["download_csv"], view_vac.to_csv(index=False).encode("utf-8"),"master_mpp.csv","text/csv",use_container_width=True)
                with c2: st.download_button(L["download_excel"], to_excel(view_vac),"master_mpp.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
# ══════════════════════════════════════════════════════════════════
# TAB 4 — DAFTAR MANAGER
# ══════════════════════════════════════════════════════════════════
elif _active == 3:
    if not _can_access_tab(_user_role, 3):
        st.error("🚫 Akses ditolak — fitur ini hanya untuk Super Admin.")
        st.stop()
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <div style="font-size:20px;font-weight:700;color:{T['text']};">Daftar Manager</div>
        <div style="font-size:13px;color:{T['text_variant']};margin-top:4px;">Seluruh karyawan yang memiliki bawahan langsung beserta analisis Span of Control</div>
    </div>
    """, unsafe_allow_html=True)

    # [REFACTOR 27 Agt 2026] get_level_from_root() dipindah ke module-level
    # (dekat HOB_MAPPING) supaya HoB Overlay bisa pakai definisi "Chief/
    # C-1/C-2" yang SAMA PERSIS dengan tab ini — sebelumnya fungsi ini
    # cuma didefinisikan inline di sini, dan HoB Overlay sempat punya
    # definisi "C-1" versinya sendiri yang salah (lihat docstring
    # annotate_hob_overlay). Definisi lokal duplikat dihapus dari sini.
    hierarchy_levels = get_level_from_root(CHIEF_ROOT, df, max_depth=2)

    level0_ids = set(df[df["Career Stage"].astype(str).str.strip().str.lower() == "level 0"]["Employee ID"].tolist())

    mgr_ids = df[df["Manager ID"] != ""]["Manager ID"].unique().tolist()
    mgr_df  = df[df["Employee ID"].isin(mgr_ids)].copy()
    
    sub_count = df[df["Manager ID"] != ""].groupby("Manager ID").size().reset_index(name="Bawahan Langsung")
    sub_count.rename(columns={"Manager ID": "Employee ID"}, inplace=True)
    mgr_df = mgr_df.merge(sub_count, on="Employee ID", how="left")
    mgr_df["Bawahan Langsung"] = mgr_df["Bawahan Langsung"].fillna(0).astype(int)
    
    children_map = df[df["Manager ID"] != ""].groupby("Manager ID")["Employee ID"].apply(list).to_dict()
    
    def get_total_span(mgr_id):
        total = 0
        to_visit = children_map.get(mgr_id, [])[:]
        while to_visit:
            curr = to_visit.pop(0)
            total += 1
            to_visit.extend(children_map.get(curr, [])) 
        return total

    mgr_df["Total Span (Semua Bawahan)"] = mgr_df["Employee ID"].apply(get_total_span)

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
    # Defense in depth: URL/session manipulation tidak boleh melewati beta + RBAC gate.
    if not _scr_beta_enabled() or not _can_access_tab(_user_role, 4):
        st.error("🚫 Akses ditolak — modul SCR belum aktif atau role Anda tidak memiliki akses.")
        st.stop()

    st.markdown(f"""
    <div style="margin-bottom:24px;">
        <div style="font-size:20px;font-weight:700;color:{T['text']};">Structure Change Request</div>
        <div style="font-size:13px;color:{T['text_variant']};margin-top:4px;">
            Kelola permintaan perubahan struktur organisasi — 8 tipe perubahan
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.get("scr_approved_proposal"):
        st.success("✅ Request berhasil disetujui. Proposal People Ops telah dibuat otomatis.")
        render_scr_proposal(
            st.session_state["scr_approved_proposal"], T, "just_approved_proposal"
        )
        if st.button("Tutup preview proposal", key="close_approved_proposal"):
            st.session_state.pop("scr_approved_proposal", None)
            st.rerun()

    # [SCR Fase 1a] Sub-tab dibangun dari kapabilitas role. Sub-tab yang tidak
    # diizinkan bernilai None dan isinya TIDAK PERNAH dieksekusi (lihat `if ... is not None` di bawah).
    _scr_tab_defs = [
        ("submit",  "➕  Buat Request"),
        ("my",      "🔎  My Requests"),
        ("inbox",   "📥  Inbox & Review"),
        ("history", "📜  History"),
    ]
    _scr_tab_vis = [(k, lbl) for k, lbl in _scr_tab_defs if _scr_can(_user_role, k)]
    if not _scr_tab_vis:
        st.error("🚫 Akses ditolak — role Anda tidak memiliki akses ke fitur SCR.")
        st.stop()
    _scr_tab_objs = dict(zip([k for k, _ in _scr_tab_vis], st.tabs([lbl for _, lbl in _scr_tab_vis])))
    cr_tab1   = _scr_tab_objs.get("submit")
    cr_tab_my = _scr_tab_objs.get("my")
    cr_tab2   = _scr_tab_objs.get("inbox")
    cr_tab3   = _scr_tab_objs.get("history")

    # [SCR-G2/G3 — 26 Agt 2026] Form single-request, name-first, dengan
    # autocomplete + auto-fill. Bulk-submit (banyak employee dalam 1 form)
    # SENGAJA DIHAPUS — REQUIREMENTS.md Section 3 eksplisit menyatakan
    # Bulk SCR di luar scope MVP. Kalau butuh proses banyak employee
    # sekaligus, submit satu-satu; ini juga lebih konsisten dengan model
    # audit trail per-tiket (1 SCR number = 1 keputusan approve/reject).
    def _cr_field_options(col_name: str, company_wide: bool = False) -> list:
        """Unique non-blank values untuk dropdown 'after'. company_wide=True memakai
        data seluruh perusahaan (tujuan perubahan), False memakai data sesuai scope user."""
        _src = df_all if company_wide else df
        if col_name not in _src.columns:
            return []
        vals = _src[col_name].dropna().astype(str).str.strip()
        return sorted([v for v in vals.unique().tolist() if v and v.lower() != "nan"])

    def _cr_employee_options(exclude_id: str = None, company_wide: bool = False) -> list:
        """List 'Nama (Employee ID)' untuk dropdown pilih karyawan/manager/budget holder.
        company_wide=True = seluruh perusahaan (tujuan perubahan); False = sesuai scope user."""
        _src = df_all if company_wide else df
        opt_df = _src[["Employee ID", "Employee Name"]].dropna().drop_duplicates(subset=["Employee ID"])
        if exclude_id:
            opt_df = opt_df[opt_df["Employee ID"] != exclude_id]
        opt_df = opt_df.sort_values("Employee Name")
        return [f"{r['Employee Name']} ({r['Employee ID']})" for _, r in opt_df.iterrows()]

    def _cr_parse_id_from_display(display_str: str) -> str:
        """'Budi Santoso (EMP001)' -> 'EMP001'"""
        if "(" in display_str and display_str.endswith(")"):
            return display_str.rsplit("(", 1)[1][:-1].strip()
        return ""

    def _cr_parse_name_from_display(display_str: str) -> str:
        """'Budi Santoso (EMP001)' -> 'Budi Santoso'"""
        if "(" in display_str:
            return display_str.rsplit("(", 1)[0].strip()
        return display_str.strip()

    def render_cr_field_input(field_name: str, emp_row: pd.Series, fv: int) -> dict:
        """
        Render input 'after' untuk satu tipe perubahan, return dict
        {"field","before","after", ...} siap masuk ke change_request JSON.
        `fv` = form_version, dipakai sebagai key-suffix supaya widget
        reset bersih setiap form berhasil submit (lihat cr_form_version).
        """
        before_col = CR_FIELD_TO_DFCOL[field_name]
        before_val = str(emp_row.get(before_col, "")).strip()
        st.markdown(f"**{field_name}**  ·  saat ini: `{before_val or '-'}`")

        if field_name == "Job Title":
            jt_mode = st.radio(
                "Sumber Job Title Baru", ["Pilih dari daftar existing", "Buat Baru (belum ada di data)"],
                horizontal=True, key=f"cr_jt_mode_{fv}", label_visibility="collapsed",
            )
            if jt_mode == "Pilih dari daftar existing":
                jt_options = ["-- Pilih Job Title --"] + [o for o in _cr_field_options("Job Position", company_wide=True) if o != before_val]
                after_sel = st.selectbox("Job Title Baru", jt_options, key=f"cr_jt_after_{fv}", label_visibility="collapsed")
                after_val = "" if after_sel == "-- Pilih Job Title --" else after_sel
                return {"field": field_name, "before": before_val, "after": after_val}
            else:
                new_title = st.text_input("Nama Job Title Baru *", key=f"cr_jt_new_{fv}", placeholder="cth: Senior Product Analyst")
                jd_file = st.file_uploader(
                    "Upload Job Description (wajib untuk Job Title baru) *",
                    type=["pdf", "doc", "docx"], key=f"cr_jt_jd_{fv}",
                )
                st.caption(
                    "⚠️ File JD belum otomatis tersimpan ke storage manapun (belum ada integrasi Drive di "
                    "aplikasi ini). Nama file akan dicatat di tiket, tapi **kirim file fisiknya manual ke "
                    "email OD** sampai G4/penyimpanan file dibangun."
                )
                return {
                    "field": field_name, "before": before_val,
                    "after": f"{new_title.strip()} (NEW)" if new_title.strip() else "",
                    "jd_filename": jd_file.name if jd_file else "",
                }

        elif field_name == "Reporting Line":
            mgr_options = ["-- Pilih Manager Baru --"] + _cr_employee_options(exclude_id=emp_row.get("Employee ID", ""), company_wide=True)
            after_sel = st.selectbox("Manager Baru", mgr_options, key=f"cr_mgr_after_{fv}", label_visibility="collapsed")
            after_val = "" if after_sel == "-- Pilih Manager Baru --" else _cr_parse_name_from_display(after_sel)
            return {"field": field_name, "before": before_val, "after": after_val}

        elif field_name in ("Division", "SBU", "Business Unit"):
            opts = ["-- Pilih --"] + [o for o in _cr_field_options(before_col, company_wide=True) if o != before_val]
            after_sel = st.selectbox(f"{field_name} Baru", opts, key=f"cr_{field_name}_after_{fv}", label_visibility="collapsed")
            after_val = "" if after_sel == "-- Pilih --" else after_sel
            return {"field": field_name, "before": before_val, "after": after_val}

        else:  # Primary Budget Holder / Secondary Budget Holder
            # [Asumsi — perlu dikonfirmasi Dave] Budget Holder diperlakukan
            # sebagai nama orang, konsisten dengan Reporting Line. Kalau di
            # data aktual Budget Holder ternyata bukan nama karyawan
            # (misal kode cost-center), field ini perlu diganti jadi
            # text_input bebas, bukan dropdown employee.
            bh_options = ["-- Pilih --"] + _cr_employee_options(company_wide=True)
            after_sel = st.selectbox(f"{field_name} Baru", bh_options, key=f"cr_bh_{field_name}_{fv}", label_visibility="collapsed")
            after_val = "" if after_sel == "-- Pilih --" else _cr_parse_name_from_display(after_sel)
            return {"field": field_name, "before": before_val, "after": after_val}

    if cr_tab1 is not None:
      with cr_tab1:
        # form_version naik setiap sukses submit -> semua widget key di
        # bawah pakai suffix ini, jadi form otomatis "reset" tanpa perlu
        # manual clear session_state satu-satu.
        _fv = st.session_state.get("cr_form_version", 0)
        _submitted_id = st.session_state.pop("cr_submit_success", None)
        if _submitted_id:
            st.success(f"Request **{_submitted_id}** berhasil dikirim. Pantau statusnya di tab My Requests.")
            import re as _re_t
            if _re_t.search(r"-T[0-9A-F]{10}$", str(_submitted_id)):
                st.warning("⚠️ Request tersimpan dengan nomor SEMENTARA. Catat nomor ini; OD akan menormalkannya.")

        st.markdown(f"""<div style="font-size:15px;font-weight:600;color:{T['text']};margin-bottom:12px;">
            Form Permintaan Perubahan Struktur</div>""", unsafe_allow_html=True)

        # ── Step 1: Cari Karyawan (autocomplete via searchable selectbox) ──
        st.markdown(f"""<div style="font-size:13px;font-weight:700;color:{T['text']};margin-bottom:8px;">
            1️⃣ Cari Karyawan yang Akan Diubah *</div>""", unsafe_allow_html=True)
        emp_display_options = ["-- Ketik nama untuk mencari --"] + _cr_employee_options()
        selected_emp_display = st.selectbox(
            "Cari Karyawan", emp_display_options, key=f"cr_emp_select_{_fv}", label_visibility="collapsed",
        )

        # Identity comes from OAuth, shown as context rather than disabled fields.
        req_name_shared = _user_info.get("name", "") or "-"
        req_email_shared = st.session_state.get("user_email", "-")
        _req_name_display = html.escape(str(req_name_shared))
        _req_email_display = html.escape(str(req_email_shared))
        st.markdown(f"""
        <div style="border:1px solid {T['outline']};background:{T['bg3']};
            border-radius:10px;padding:12px 16px;margin:8px 0 18px 0;
            color:{T['text_variant']};font-size:13px;line-height:1.5;">
            <span style="font-weight:600;color:{T['text']};">Diajukan oleh {_req_name_display}</span>
            <span style="margin-left:8px;overflow-wrap:anywhere;">{_req_email_display}</span>
            <div style="font-size:12px;margin-top:2px;">Identitas diambil dari akun login.</div>
        </div>
        """, unsafe_allow_html=True)

        if selected_emp_display == "-- Ketik nama untuk mencari --":
            st.caption("Pilih karyawan untuk melihat data saat ini dan mengisi detail perubahan.")
        else:
            emp_id_sel = _cr_parse_id_from_display(selected_emp_display)
            emp_match  = df[df["Employee ID"] == emp_id_sel]
            if emp_match.empty:
                st.error("❌ Data karyawan tidak ditemukan — coba pilih ulang.")
            else:
                emp_row = emp_match.iloc[0]

                # Auto-fill card — current data
                st.markdown(f"""
                <div style="background:{T['bg3']};border:1px solid {T['border']};border-radius:10px;padding:14px 16px;margin:8px 0 16px 0;">
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
                        <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;">Job Title</div>
                            <div style="font-size:13px;font-weight:600;color:{T['text']};">{emp_row.get('Job Position','-') or '-'}</div></div>
                        <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;">Division</div>
                            <div style="font-size:13px;font-weight:600;color:{T['text']};">{emp_row.get('Division','-') or '-'}</div></div>
                        <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;">Business Unit</div>
                            <div style="font-size:13px;font-weight:600;color:{T['text']};">{emp_row.get('Business Unit','-') or '-'}</div></div>
                        <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;">SBU/Tribe</div>
                            <div style="font-size:13px;font-weight:600;color:{T['text']};">{emp_row.get('SBU/Tribe','-') or '-'}</div></div>
                        <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;">Manager</div>
                            <div style="font-size:13px;font-weight:600;color:{T['text']};">{emp_row.get('Manager Name','-') or '-'}</div></div>
                        <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;">Employee ID</div>
                            <div style="font-size:13px;font-weight:600;color:{T['text']};">{emp_row.get('Employee ID','-')}</div></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"""<div style="font-size:13px;font-weight:700;color:{T['text']};margin-bottom:8px;">
                    2️⃣ Jenis Perubahan *</div>""", unsafe_allow_html=True)
                change_type_shared = st.selectbox("Jenis Perubahan", CR_CHANGE_TYPES, key=f"cr_ct_{_fv}", label_visibility="collapsed")
                st.markdown(f"<div style='height:1px;background:{T['border']};margin:12px 0;'></div>", unsafe_allow_html=True)

                st.markdown(f"""<div style="font-size:13px;font-weight:700;color:{T['text']};margin-bottom:8px;">
                    3️⃣ Detail Perubahan *</div>""", unsafe_allow_html=True)

                field_changes = []
                if change_type_shared != "Kombinasi":
                    field_changes = [render_cr_field_input(change_type_shared, emp_row, _fv)]
                else:
                    combo_fields = st.multiselect(
                        "Pilih minimal 2 field yang berubah bersamaan",
                        CR_BASE_TYPES, key=f"cr_combo_{_fv}",
                    )
                    if len(combo_fields) < 2:
                        st.warning("⚠️ Pilih minimal **2 field** untuk Kombinasi. Kalau hanya 1 field, pilih tipe itu langsung tanpa 'Kombinasi'.")
                    else:
                        for cf in combo_fields:
                            st.markdown(f"<div style='height:1px;background:{T['border']};margin:10px 0;'></div>", unsafe_allow_html=True)
                            field_changes.append(render_cr_field_input(cf, emp_row, f"{_fv}_{cf.replace(' ','_')}"))

                st.markdown(f"<div style='height:1px;background:{T['border']};margin:16px 0;'></div>", unsafe_allow_html=True)
                col_al, col_ed = st.columns([3, 1])
                with col_al:
                    alasan_shared = st.text_area("Justifikasi / Alasan Perubahan *", placeholder="Jelaskan alasan perubahan struktur ini...",
                                                 height=90, key=f"cr_alasan_{_fv}")
                with col_ed:
                    eff_date_shared = st.date_input("Effective Date", value=datetime.today(), key=f"cr_ed_{_fv}")

                if st.button("📨  Kirim Request", use_container_width=True, key=f"cr_submit_{_fv}"):
                    errors = []
                    if not alasan_shared.strip():
                        errors.append("Justifikasi/alasan wajib diisi.")
                    if not field_changes:
                        errors.append("Belum ada detail perubahan yang valid.")
                    for fc in field_changes:
                        if not fc.get("after"):
                            errors.append(f"Nilai baru untuk **{fc['field']}** belum dipilih/diisi.")
                        if fc["field"] == "Job Title" and "jd_filename" in fc and not fc["jd_filename"]:
                            errors.append("Job Title baru wajib disertai upload Job Description.")

                    # [SCR-RULE — 3 Okt 2026] Requester tidak boleh mengajukan SCR untuk dirinya sendiri.
                    _me_email = str(req_email_shared).strip().lower()
                    _me_empid = str(_user_info.get("employee_id", "")).strip().upper()
                    _emp_email = str(emp_row.get("Email", "")).strip().lower()
                    _emp_id    = str(emp_row.get("Employee ID", "")).strip().upper()
                    if (_me_email and _emp_email and _me_email == _emp_email) or \
                       (_me_empid and _emp_id and _me_empid == _emp_id):
                        errors.append("Anda tidak dapat mengajukan perubahan struktur untuk diri sendiri. "
                                      "Minta atasan atau HRBP Anda untuk mengajukannya.")

                    if errors:
                        for e in errors:
                            st.error(f"❌ {e}")
                    else:
                        request_id = generate_request_id()
                        summary_lama = "; ".join(f"{fc['field']}: {fc['before'] or '-'}" for fc in field_changes)
                        summary_baru = "; ".join(f"{fc['field']}: {fc['after'] or '-'}" for fc in field_changes)
                        row = {
                            "request_id":      request_id,
                            "submitted_date":  datetime.now(_WIB).strftime("%Y-%m-%d %H:%M"),
                            "requester_name":  req_name_shared,
                            "requester_email": req_email_shared,
                            "change_type":     (change_type_shared if change_type_shared != "Kombinasi"
                            else "Kombinasi: " + " + ".join(fc["field"] for fc in field_changes)),
                            "employee_id":     emp_row.get("Employee ID", ""),
                            "employee_name":   emp_row.get("Employee Name", ""),
                            "data_lama":       summary_lama,
                            "data_baru":       summary_baru,
                            "alasan":          f"{alasan_shared.strip()} | Effective: {eff_date_shared}",
                            "status":          "Pending",
                            "reviewed_by":     "",
                            "reviewed_date":   "",
                            "catatan":         "",
                            "change_request":  build_change_request_json(field_changes),
                        }
                        if save_change_request(row):
                            request_id = row["request_id"]   # nomor final dari save_change_request()
                            log_activity(
                                action_type="submit_scr",
                                detail=f"{request_id} · {change_type_shared} · {emp_row.get('Employee Name','')}",
                            )
                            st.session_state["cr_submit_success"] = request_id
                            load_change_requests.clear()
                            st.session_state["cr_form_version"] = _fv + 1
                            st.rerun()
                        else:
                            # [FIX 30 Sep 2026] Dulu tidak ada else sama sekali —
                            # kalau save_change_request() gagal, tombol diklik dan
                            # TIDAK ADA REAKSI APAPUN (persis bug yang dilaporkan
                            # Dave di testing 30 Sep 2026). save_change_request()
                            # sudah menampilkan st.error dengan alasan spesifik;
                            # baris ini cuma jaring pengaman terakhir.
                            st.warning("⚠️ Request tidak tersimpan. Lihat pesan error di atas, perbaiki, lalu coba kirim ulang.")

    if cr_tab_my is not None:
      with cr_tab_my:
        my_email = st.session_state.get("user_email", "").strip().lower()
        my_cr_df = load_change_requests()
        if cr_load_failed(my_cr_df):
            st.error("❌ Gagal memuat data request dari Google Sheets. Ini BUKAN berarti tidak ada request. "
                     "Klik Refresh atau coba lagi sebentar lagi; bila berulang hubungi OD Team.")
        elif my_cr_df.empty or "requester_email" not in my_cr_df.columns:
            st.info("📭 Anda belum memiliki request.")
        else:
            my_requests = my_cr_df[
                my_cr_df["requester_email"].astype(str).str.strip().str.lower().eq(my_email)
            ].copy()
            if my_requests.empty:
                st.info("📭 Anda belum memiliki request.")
            else:
                if "submitted_date" in my_requests.columns:
                    my_requests = my_requests.sort_values("submitted_date", ascending=False)
                st.caption(f"Menampilkan **{len(my_requests)}** request milik **{my_email}**")
                status_icons = {
                    "Pending": "🟡", "In Review": "🔵", "Approved": "✅", "Rejected": "❌"
                }
                for my_idx, (_, my_row) in enumerate(my_requests.iterrows()):
                    my_request_id = str(my_row.get("request_id", "-"))
                    my_status = str(my_row.get("status", "Pending") or "Pending").strip()
                    icon = status_icons.get(my_status, "⚪")
                    is_selected_proposal = st.session_state.get("my_selected_proposal") == my_request_id
                    with st.expander(
                        f"{icon} {my_request_id} · {my_row.get('employee_name', '-')} · {my_status}",
                        expanded=is_selected_proposal,
                    ):
                        c_my1, c_my2 = st.columns(2)
                        c_my1.write(f"**Tipe perubahan:** {my_row.get('change_type', '-')}")
                        c_my1.write(f"**Tanggal submit:** {my_row.get('submitted_date', '-')}")
                        c_my2.write(f"**Employee ID:** {my_row.get('employee_id', '-')}")
                        c_my2.write(f"**Status:** {my_status}")
                        st.write(f"**Justifikasi:** {my_row.get('alasan', '-')}")
                        if my_status == "Rejected":
                            st.error(f"Alasan penolakan OD: {my_row.get('catatan', '-') or '-'}")
                        elif my_status == "Approved":
                            if st.button(
                                "Lihat Proposal Document",
                                key=f"view_my_proposal_{my_idx}_{my_request_id}",
                            ):
                                st.session_state["my_selected_proposal"] = my_request_id
                                st.rerun()
                            if is_selected_proposal:
                                render_scr_proposal(dict(my_row), T, f"my_proposal_{my_idx}")

    if cr_tab2 is not None:
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
        if cr_load_failed(cr_df):
            st.error("❌ Gagal memuat data request dari Google Sheets. Ini BUKAN berarti tidak ada request. "
                     "Klik Refresh atau coba lagi sebentar lagi; bila berulang hubungi OD Team.")
        elif cr_df.empty:
            st.info("📭 Belum ada request yang masuk.")
        else:
            if "status" not in cr_df.columns:
                cr_df["status"] = "Pending"
            pending_df = cr_df[cr_df["status"] == "Pending"].copy()
            # [QA ID-01] Nomor tiket ganda: tampilkan peringatan dan blokir keputusan pada tiket tsb.
            _dup_ids = set()
            if "request_id" in cr_df.columns:
                _rid = cr_df["request_id"].astype(str).str.strip()
                _dup_ids = set(_rid[_rid.duplicated(keep=False)])
            if _dup_ids:
                st.warning("⚠️ Ada nomor tiket ganda: " + ", ".join(sorted(_dup_ids))
                           + ". Approve/Reject untuk tiket ini diblokir sampai nomor dinormalkan di sheet.")

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

                for _, row in pending_df.iterrows():
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
                            # [SCR-G2/G3] Parse change_request JSON untuk render per-field
                            # before/after. Fallback ke data_lama/data_baru (satu baris teks)
                            # untuk tiket lama yang dibuat sebelum kolom ini ada.
                            _fc_list = parse_change_request_json(row.get("change_request", ""))
                            if _fc_list:
                                _diff_rows_html = ""
                                for _fc in _fc_list:
                                    _jd_note = ""
                                    if _fc.get("jd_filename"):
                                        _jd_note = f"<div style='font-size:11px;color:{T['text_variant']};margin-top:2px;'>📎 JD: {_fc['jd_filename']} (kirim manual ke OD)</div>"
                                    _diff_rows_html += f"""
                                    <div style="margin-bottom:10px;padding-bottom:10px;border-bottom:1px dashed {T['border']};">
                                        <div style="font-size:11px;font-weight:700;color:{T['text']};margin-bottom:4px;">{_fc.get('field','-')}</div>
                                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                                            <div style="font-size:13px;color:#ef4444;font-weight:500;">❌ {_fc.get('before','-') or '-'}</div>
                                            <div style="font-size:13px;color:#22c55e;font-weight:500;">✅ {_fc.get('after','-') or '-'}</div>
                                        </div>
                                        {_jd_note}
                                    </div>"""
                                _diff_block = _diff_rows_html
                            else:
                                _diff_block = f"""
                                <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                                    <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;letter-spacing:0.06em;">Sebelum</div>
                                        <div style="font-size:13px;color:#ef4444;font-weight:500;">❌ {row.get('data_lama','-')}</div></div>
                                    <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;letter-spacing:0.06em;">Sesudah</div>
                                        <div style="font-size:13px;color:#22c55e;font-weight:500;">✅ {row.get('data_baru','-')}</div></div>
                                </div>"""

                            _card_html = f"""
                            <div style="background:{T['bg3']};border-radius:12px;padding:16px;border:1px solid {T['border']};">
                                <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                                    <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;letter-spacing:0.06em;">Request ID</div>
                                        <div style="font-size:13px;font-weight:600;color:{T['text']};">{row.get('request_id','-')}</div></div>
                                    <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;letter-spacing:0.06em;">Masuk</div>
                                        <div style="font-size:13px;color:{age_color};font-weight:600;">{age_label}</div></div>
                                    <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;letter-spacing:0.06em;">Karyawan</div>
                                        <div style="font-size:13px;font-weight:600;color:{T['text']};">{row.get('employee_name','-')} ({row.get('employee_id','-')})</div></div>
                                    <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;letter-spacing:0.06em;">Jenis</div>
                                        <div style="font-size:13px;font-weight:600;color:{T['accent']};">{row.get('change_type','-')}</div></div>
                                </div>
                                <div style="margin-top:12px;padding-top:12px;border-top:1px solid {T['border']};">
                                    {_diff_block}
                                </div>
                                <div style="margin-top:12px;padding-top:12px;border-top:1px solid {T['border']};">
                                    <div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;letter-spacing:0.06em;">Alasan</div>
                                    <div style="font-size:13px;color:{T['text_variant']};">{row.get('alasan','-')}</div>
                                </div>
                            </div>
                            """
                            st.markdown(
                                "\n".join(_l.strip() for _l in _card_html.splitlines() if _l.strip()),
                                unsafe_allow_html=True,
                            )

                        with col_action:
                            reviewer = str(_user_info.get("name", "") or st.session_state.get("user_email", "")).strip()
                            # [SCR Fase 1a] Reviewer tidak boleh memutuskan request yang dia ajukan sendiri.
                            # Fail-closed: tanpa email login, keputusan juga diblokir.
                            _me_rv = str(st.session_state.get("user_email", "")).strip().lower()
                            _is_dup = str(row.get("request_id", "")).strip() in _dup_ids
                            _blocked = (
                                (not _scr_can(_user_role, "decide"))
                                or (not _me_rv)
                                or (str(row.get("requester_email", "")).strip().lower() == _me_rv)
                                or _is_dup
                            )
                            if _is_dup:
                                st.caption("🔒 Nomor tiket ini ganda di sheet; keputusan diblokir sampai dinormalkan.")
                            elif _blocked:
                                st.caption("🔒 Anda tidak dapat menyetujui/menolak request yang Anda ajukan sendiri. "
                                           "Request ini perlu direview reviewer lain.")
                            st.text_input(
                                "Reviewer",
                                value=reviewer,
                                disabled=True,
                                key=f"reviewer_{row.get('request_id','')}",
                            )
                            catatan_review = st.text_area(
                                "Catatan OD (wajib untuk Reject)",
                                key=f"catatan_{row.get('request_id','')}",
                                height=80,
                            )
                            col_a, col_r = st.columns(2)
                            with col_a:
                                if st.button("✅ Approve", key=f"approve_{row.get('request_id','')}", use_container_width=True, disabled=_blocked):
                                    if _blocked: st.error("Tidak diizinkan: Anda tidak dapat memutuskan request ini.")
                                    elif not reviewer: st.error("Identitas reviewer tidak tersedia dari sesi login.")
                                    else:
                                        if update_cr_status(row.get("request_id",""), "Approved", reviewer.strip(), catatan_review.strip()):
                                            approved_record = dict(row)
                                            approved_record.update({
                                                "status": "Approved",
                                                "reviewed_by": reviewer,
                                                "reviewed_date": datetime.now(_WIB).strftime("%Y-%m-%d %H:%M"),
                                                "catatan": catatan_review.strip(),
                                            })
                                            st.session_state["scr_approved_proposal"] = approved_record
                                            log_activity(
                                                action_type="approve_scr",
                                                detail=f"{row.get('request_id','')} · {row.get('employee_name','')}",
                                            )
                                            load_change_requests.clear()
                                            st.success("✅ Approved!"); st.rerun()
                            with col_r:
                                if st.button("❌ Reject", key=f"reject_{row.get('request_id','')}", use_container_width=True, disabled=_blocked):
                                    if _blocked: st.error("Tidak diizinkan: Anda tidak dapat memutuskan request ini.")
                                    elif not reviewer: st.error("Identitas reviewer tidak tersedia dari sesi login.")
                                    elif not catatan_review.strip(): st.error("Alasan penolakan wajib diisi.")
                                    else:
                                        if update_cr_status(row.get("request_id",""), "Rejected", reviewer.strip(), catatan_review.strip()):
                                            log_activity(
                                                action_type="reject_scr",
                                                detail=f"{row.get('request_id','')} · {row.get('employee_name','')}",
                                            )
                                            load_change_requests.clear()
                                            st.warning("❌ Rejected"); st.rerun()

    if cr_tab3 is not None:
      with cr_tab3:
        col_rl, _ = st.columns([1, 5])
        with col_rl:
            if st.button("🔄 Refresh", key="refresh_hist"):
                st.cache_data.clear(); st.rerun()

        cr_hist = load_change_requests()
        if cr_load_failed(cr_hist):
            st.error("❌ Gagal memuat data request dari Google Sheets. Ini BUKAN berarti tidak ada request. "
                     "Klik Refresh atau coba lagi sebentar lagi; bila berulang hubungi OD Team.")
        elif cr_hist.empty:
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
                approved_view = view_hist[view_hist["status"] == "Approved"].copy()
                if not approved_view.empty:
                    proposal_ids = approved_view["request_id"].astype(str).tolist()
                    selected_proposal_id = st.selectbox(
                        "Lihat Proposal Document",
                        ["— pilih tiket approved —"] + proposal_ids,
                        key="history_proposal_id",
                    )
                    if selected_proposal_id != "— pilih tiket approved —":
                        selected_row = approved_view[
                            approved_view["request_id"].astype(str) == selected_proposal_id
                        ].iloc[0]
                        render_scr_proposal(dict(selected_row), T, "history_proposal")
                st.divider()
                col_hd1, col_hd2, _ = st.columns([1,1,3])
                with col_hd1:
                    st.download_button("📄 CSV", view_hist.to_csv(index=False).encode("utf-8"),
                                       "cr_history.csv", "text/csv", use_container_width=True)
                with col_hd2:
                    st.download_button("📊 Excel", to_excel(view_hist), "cr_history.xlsx",
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


# ══════════════════════════════════════════════════════════════════
# TAB 99 — ADMIN PANEL (role=super_admin only)
# Diakses via tab_idx=99, hanya muncul di navigasi untuk super_admin.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
elif _active == 5:
    # Role gate — double-check, same pattern as Tab 99
    if not _can_access_tab(_user_role, 5):
        st.error("🚫 Akses ditolak — fitur ini hanya untuk Admin dan Super Admin.")
        st.stop()

    st.markdown(f"""
    <div style="margin-bottom:24px;">
        <div style="font-size:20px;font-weight:700;color:{T['text']};">🚪 Offboarding Tracker</div>
        <div style="font-size:13px;color:{T['text_variant']};margin-top:4px;">
            Pantau karyawan yang akan offboard — identifikasi people manager yang masih memiliki direct reports aktif
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Context banner ─────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:{T['accent_bg']};border:1px solid {T['border2']};border-radius:8px;
        padding:12px 16px;margin-bottom:20px;font-size:13px;color:{T['text_variant']};">
        💡 <b>Cara baca tabel:</b> Kolom <b>Employee Under</b> berisi nama-nama karyawan aktif yang
        masih melapor ke karyawan yang akan resign. Kolom kosong = karyawan resign tersebut bukan people manager.
        OD perlu mengkonfirmasi ke leader di atasnya: subordinate akan dipindah ke mana sebelum offboarding terjadi.
    </div>
    """, unsafe_allow_html=True)

    # ── Date Range Picker ──────────────────────────────────────────
    st.markdown(f"""
    <div style="font-size:12px;font-weight:600;color:{T['text3']};text-transform:uppercase;
        letter-spacing:0.06em;margin-bottom:10px;">RENTANG TANGGAL OFFBOARDING</div>
    """, unsafe_allow_html=True)

    _today     = datetime.now(_WIB).date()
    _default_end = _today + timedelta(days=7)

    col_sd, col_ed, col_info_date = st.columns([2, 2, 4])
    with col_sd:
        ot_start = st.date_input("Start Date", value=_today,        key="ot_start")
    with col_ed:
        ot_end   = st.date_input("End Date",   value=_default_end,  key="ot_end")

    # ── Validation: max 30-day range ──────────────────────────────
    _range_days = (ot_end - ot_start).days

    with col_info_date:
        if ot_end < ot_start:
            st.markdown(f"""
            <div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;
                padding:8px 12px;margin-top:6px;font-size:12px;color:#991b1b;">
                ❌ End Date tidak boleh sebelum Start Date.
            </div>""", unsafe_allow_html=True)
        elif _range_days > 30:
            st.markdown(f"""
            <div style="background:{T['warn_bg']};border:1px solid {T['warn_bdr']};border-radius:8px;
                padding:8px 12px;margin-top:6px;font-size:12px;color:{T['warn_txt']};">
                ⚠️ Rentang maksimal 30 hari. Saat ini: <b>{_range_days} hari</b>.
                Kurangi rentang tanggal untuk melihat data.
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:{T['success_bg']};border:1px solid {T['success_bdr']};border-radius:8px;
                padding:8px 12px;margin-top:6px;font-size:12px;color:{T['success_txt']};">
                ✅ Menampilkan karyawan offboard <b>{ot_start.strftime('%d %b %Y')}</b>
                — <b>{ot_end.strftime('%d %b %Y')}</b> ({_range_days} hari)
            </div>""", unsafe_allow_html=True)

    st.markdown(f"<div style='height:1px;background:{T['border']};margin:16px 0;'></div>", unsafe_allow_html=True)

    # ── Guard: hanya render tabel jika range valid ─────────────────
    if ot_end >= ot_start and _range_days <= 30:

        # ── Load data ──────────────────────────────────────────────
        _df_resigned, _df_active = load_offboarding_data()

        if _df_resigned is None:
            st.error("⚠️ Gagal memuat data dari Google Sheets. Pastikan koneksi aktif dan coba refresh.")
            st.stop()

        if _df_resigned.empty:
            st.info("📭 Tidak ada data karyawan dengan Resign Date di sheet.")
            st.stop()

        # ── Parse & filter Resign Date dalam range ─────────────────
        # Resign Date di sheet bisa dalam berbagai format string.
        # pd.to_datetime dengan errors='coerce' akan handle berbagai
        # format umum; baris yang tidak bisa di-parse jadi NaT (diabaikan).
        _rd_series = pd.to_datetime(
            _df_resigned["Resign Date"], errors="coerce", dayfirst=True
        )
        _df_resigned = _df_resigned.copy()
        _df_resigned["_resign_date_parsed"] = _rd_series

        _mask_range = (
            _df_resigned["_resign_date_parsed"].notna() &
            (_df_resigned["_resign_date_parsed"].dt.date >= ot_start) &
            (_df_resigned["_resign_date_parsed"].dt.date <= ot_end)
        )
        _df_in_range = _df_resigned[_mask_range].copy()

        # ── KPI row ────────────────────────────────────────────────
        _total_offboard = len(_df_in_range)
        _people_mgrs    = 0  # dihitung setelah compute Employee Under

        # ── Compute "Employee Under" ───────────────────────────────
        if not _df_in_range.empty:
            _df_in_range["Employee Under"] = _compute_employee_under(
                _df_in_range, _df_active
            )
            _people_mgrs = (_df_in_range["Employee Under"] != "").sum()

        # ── KPI cards ──────────────────────────────────────────────
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric(
            "🚪 Total Offboarding",
            _total_offboard,
            help=f"Karyawan dengan Resign Date antara {ot_start} — {ot_end}"
        )
        kpi2.metric(
            "👔 People Manager",
            int(_people_mgrs),
            help="Dari total offboarding, berapa yang masih punya direct report aktif"
        )
        kpi3.metric(
            "👤 Bukan Manager",
            int(_total_offboard - _people_mgrs),
            help="Karyawan resign yang tidak punya direct report — tidak perlu tindak lanjut subordinate"
        )

        st.markdown(f"<div style='height:1px;background:{T['border']};margin:16px 0;'></div>", unsafe_allow_html=True)

        if _df_in_range.empty:
            st.success(f"✅ Tidak ada karyawan yang offboard antara {ot_start.strftime('%d %b %Y')} — {ot_end.strftime('%d %b %Y')}.")
        else:
            # ── Optional filter: hanya tampilkan people manager ────
            _show_mgr_only = st.checkbox(
                "🔍 Tampilkan hanya people manager (yang memiliki direct reports)",
                value=False,
                key="ot_mgr_only"
            )

            _display_df = _df_in_range.copy()
            if _show_mgr_only:
                _display_df = _display_df[_display_df["Employee Under"] != ""]

            # ── Build display table dengan kolom sesuai brief ──────
            # Urutan kolom: EID | Name | Reporting Line | Organization |
            #               Job ID | Job Position | SBU/Tribe | Resign Date |
            #               Employee will be resign | Employee Under
            _col_map = {
                "Employee ID":                    "EID",
                "Full Name":                      "Name",
                "Employment Approval Line Name":  "Reporting Line",
                "Organization":                   "Organization",
                "Job ID":                         "Job ID",
                "Job Position":                   "Job Position",
                "SBU/Tribe":                      "SBU/Tribe",
                "Resign Date":                    "Resign Date",
            }
            # Ambil hanya kolom yang tersedia (defensive)
            _src_cols = [c for c in _col_map if c in _display_df.columns]
            _tbl      = _display_df[_src_cols].copy()
            _tbl      = _tbl.rename(columns=_col_map)

            # "Employee will be resign" = sama dengan Name (brief spec)
            if "Name" in _tbl.columns:
                _tbl.insert(
                    _tbl.columns.get_loc("Resign Date") + 1,
                    "Employee will be resign",
                    _tbl["Name"]
                )

            # Tambahkan "Employee Under" di akhir
            _tbl["Employee Under"] = _display_df["Employee Under"].values

            # Sort by Resign Date ascending
            if "Resign Date" in _tbl.columns:
                _tbl["_sort_key"] = pd.to_datetime(_tbl["Resign Date"], errors="coerce", dayfirst=True)
                _tbl = _tbl.sort_values("_sort_key").drop(columns=["_sort_key"])

            st.caption(
                f"Menampilkan **{len(_tbl)}** karyawan"
                + (" (people manager saja)" if _show_mgr_only else "")
                + f" · {int(_people_mgrs)} memerlukan tindak lanjut subordinate"
            )

            # ── Highlight rows: people manager pakai warning color ─
            def _highlight_mgr(row):
                """Style rows dimana Employee Under tidak kosong (= people manager)."""
                if row.get("Employee Under", ""):
                    return [f"background-color: {'#231b00' if dm else '#fffbeb'}; color: {'#fde68a' if dm else '#854d0e'};"] * len(row)
                return [""] * len(row)

            _styled = _tbl.reset_index(drop=True).style.apply(_highlight_mgr, axis=1)

            st.dataframe(
                _styled,
                use_container_width=True,
                height=min(60 + len(_tbl) * 35 + 40, 520),  # dynamic height, cap at 520px
            )

            # ── People manager detail expanders ────────────────────
            _mgr_rows = _tbl[_tbl["Employee Under"] != ""]
            if not _mgr_rows.empty:
                st.markdown(f"""
                <div style="font-size:14px;font-weight:600;color:{T['text']};margin:20px 0 12px 0;">
                    ⚠️ People Manager yang Perlu Tindak Lanjut ({len(_mgr_rows)} orang)
                </div>
                """, unsafe_allow_html=True)

                for _, _mgr_row in _mgr_rows.iterrows():
                    _mgr_name     = _mgr_row.get("Name", "-")
                    _mgr_resign   = _mgr_row.get("Resign Date", "-")
                    _mgr_org      = _mgr_row.get("Organization", "-")
                    _mgr_pos      = _mgr_row.get("Job Position", "-")
                    _mgr_rl       = _mgr_row.get("Reporting Line", "-")
                    _directs_str  = _mgr_row.get("Employee Under", "")
                    _directs_list = [d.strip() for d in _directs_str.split(",") if d.strip()]

                    with st.expander(
                        f"👔 {_mgr_name}  ·  {_mgr_org}  ·  Resign: {_mgr_resign}  ·  {len(_directs_list)} direct report",
                        expanded=False
                    ):
                        col_det1, col_det2 = st.columns([2, 3])
                        with col_det1:
                            st.markdown(f"""
                            <div style="background:{T['bg3']};border-radius:10px;padding:14px 16px;
                                border:1px solid {T['border']};">
                                <div style="margin-bottom:10px;">
                                    <div style="font-size:10px;color:{T['text3']};text-transform:uppercase;
                                        letter-spacing:0.07em;margin-bottom:3px;">Nama</div>
                                    <div style="font-size:14px;font-weight:700;color:{T['text']};">{_mgr_name}</div>
                                </div>
                                <div style="margin-bottom:10px;">
                                    <div style="font-size:10px;color:{T['text3']};text-transform:uppercase;
                                        letter-spacing:0.07em;margin-bottom:3px;">Posisi</div>
                                    <div style="font-size:13px;color:{T['text_variant']};">{_mgr_pos}</div>
                                </div>
                                <div style="margin-bottom:10px;">
                                    <div style="font-size:10px;color:{T['text3']};text-transform:uppercase;
                                        letter-spacing:0.07em;margin-bottom:3px;">Organisasi</div>
                                    <div style="font-size:13px;color:{T['text_variant']};">{_mgr_org}</div>
                                </div>
                                <div style="margin-bottom:10px;">
                                    <div style="font-size:10px;color:{T['text3']};text-transform:uppercase;
                                        letter-spacing:0.07em;margin-bottom:3px;">Reporting Line</div>
                                    <div style="font-size:13px;color:{T['text_variant']};">{_mgr_rl}</div>
                                </div>
                                <div>
                                    <div style="font-size:10px;color:{T['text3']};text-transform:uppercase;
                                        letter-spacing:0.07em;margin-bottom:3px;">Resign Date</div>
                                    <div style="font-size:13px;font-weight:600;color:#dc2626;">{_mgr_resign}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_det2:
                            st.markdown(f"""
                            <div style="background:{T['warn_bg']};border:1px solid {T['warn_bdr']};
                                border-radius:10px;padding:14px 16px;">
                                <div style="font-size:10px;color:{T['warn_txt']};text-transform:uppercase;
                                    letter-spacing:0.07em;font-weight:700;margin-bottom:10px;">
                                    ⚠️ {len(_directs_list)} Direct Report Perlu Dialihkan
                                </div>
                            """, unsafe_allow_html=True)
                            for _d in _directs_list:
                                st.markdown(f"""
                                <div style="background:{T['surface_lowest']};border-radius:6px;
                                    padding:7px 12px;margin-bottom:6px;font-size:13px;
                                    color:{T['text']};border:1px solid {T['border']};">
                                    👤 {_d}
                                </div>
                                """, unsafe_allow_html=True)
                            st.markdown("</div>", unsafe_allow_html=True)

    # ── Version marker — prevents debugging stale deploys ─────────
    st.markdown(f"""
    <div style="text-align:right;font-size:10px;color:{T['text3']};margin-top:16px;opacity:0.5;">
        Offboarding Tracker v1.0 · {datetime.now(_WIB).strftime('%d %b %Y')}
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# TAB 99 — ADMIN PANEL (role=super_admin only)
# Diakses via tab_idx=99, hanya muncul di navigasi untuk super_admin.
# ══════════════════════════════════════════════════════════════════
elif _active == 99:
    # Gate keamanan: double-check role di sini, bukan hanya di nav.
    # Sengaja pakai _can_access_tab() yang sama dengan filter nav —
    # single source of truth, supaya nav dan gate ini tidak pernah
    # desync (sebelumnya pakai flag _is_admin terpisah yang hardcode
    # ke "admin", sehingga role baru "super_admin" akan lolos nav tapi
    # ditolak di sini kalau tidak disamakan).
    if not _can_access_tab(_user_role, 99):
        st.error("🚫 Akses ditolak — fitur ini hanya untuk Super Admin.")
        st.stop()

    admin_email = st.session_state.get("user_email", "system")

    st.markdown(f"""
    <div style="margin-bottom:24px;">
        <div style="font-size:20px;font-weight:700;color:{T['text']};">⚙️ Admin Panel — Manajemen Akses</div>
        <div style="font-size:13px;color:{T['text_variant']};margin-top:4px;">
            Kelola hak akses user dashboard · Perubahan berlaku dalam 2 menit (cache TTL)
        </div>
    </div>
    """, unsafe_allow_html=True)

    ap_tab1, ap_tab2, ap_tab3, ap_tab4 = st.tabs(["👥  Daftar User", "➕  Tambah / Edit User", "🔒  Reset Password", "📋  Activity Log"])

    # Reload ACL fresh untuk admin panel
    acl_dict = load_acl_table()
    acl_rows = []
    for em, info in acl_dict.items():
        acl_rows.append({
            "Email":       em,
            "Nama":        info.get("name", ""),
            "Role":        info.get("role", "employee"),
            "Allowed BU":  info.get("allowed_bus", "*"),
            "Allowed SBU": info.get("allowed_sbus", "*"),
            "Employee ID": info.get("employee_id", ""),
            "Status":      "✅ Aktif" if info.get("is_active", True) else "🔴 Nonaktif",
            "Scope Note":  info.get("scope_note", ""),
        })
    acl_display_df = pd.DataFrame(acl_rows) if acl_rows else pd.DataFrame(
        columns=["Email","Nama","Role","Allowed BU","Allowed SBU","Employee ID","Status","Scope Note"]
    )

    # ── Tab 1: Daftar User ────────────────────────────────────────
    with ap_tab1:
        col_ap_m1, col_ap_m2, col_ap_m3, col_ap_m4 = st.columns(4)
        col_ap_m1.metric("Total User", len(acl_display_df))
        col_ap_m2.metric("Aktif", len(acl_display_df[acl_display_df["Status"] == "✅ Aktif"]) if not acl_display_df.empty else 0)
        col_ap_m3.metric("Admin",  len(acl_display_df[acl_display_df["Role"].isin(["admin", "super_admin"])])  if not acl_display_df.empty else 0)
        col_ap_m4.metric("Nonaktif", len(acl_display_df[acl_display_df["Status"] == "🔴 Nonaktif"]) if not acl_display_df.empty else 0)

        st.markdown("---")

        if not acl_display_df.empty:
            col_af1, col_af2, col_af3 = st.columns(3)
            with col_af1:
                f_role_ap = st.selectbox("Filter Role", ["Semua", "super_admin", "od_reviewer", "admin", "cxo", "hrbp", "leader", "employee"], key="ap_f_role")
            with col_af2:
                f_status_ap = st.selectbox("Filter Status", ["Semua", "✅ Aktif", "🔴 Nonaktif"], key="ap_f_status")
            with col_af3:
                f_search_ap = st.text_input("Cari Email / Nama", placeholder="Ketik...", key="ap_search")

            view_acl = acl_display_df.copy()
            if f_role_ap   != "Semua": view_acl = view_acl[view_acl["Role"]   == f_role_ap]
            if f_status_ap != "Semua": view_acl = view_acl[view_acl["Status"] == f_status_ap]
            if f_search_ap.strip():
                q = f_search_ap.lower()
                view_acl = view_acl[
                    view_acl["Email"].str.lower().str.contains(q) |
                    view_acl["Nama"].str.lower().str.contains(q)
                ]

            st.caption(f"Menampilkan **{len(view_acl)}** dari **{len(acl_display_df)}** user")
            st.dataframe(view_acl, use_container_width=True, height=380)
        else:
            st.info("Belum ada user di ACL. Tambahkan user pertama di tab 'Tambah / Edit User'.")

        # Quick actions
        st.markdown("---")
        st.markdown(f"<div style='font-size:14px;font-weight:600;color:{T['text']};margin-bottom:12px;'>Aksi Cepat</div>", unsafe_allow_html=True)
        col_qa1, col_qa2, col_qa3 = st.columns(3)
        with col_qa1:
            target_deact = st.text_input("Email untuk Nonaktifkan", key="qa_deact", placeholder="user@mekari.com")
        with col_qa2:
            target_react = st.text_input("Email untuk Aktifkan", key="qa_react", placeholder="user@mekari.com")
        with col_qa3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

        col_btn_d, col_btn_r, _ = st.columns([1, 1, 2])
        with col_btn_d:
            if st.button("🔴 Nonaktifkan", use_container_width=True, key="btn_deact_ap"):
                if target_deact.strip():
                    if toggle_acl_user_status(target_deact.strip(), False):
                        st.success(f"✅ {target_deact} dinonaktifkan."); st.rerun()
                    else:
                        st.error("Email tidak ditemukan di ACL.")
        with col_btn_r:
            if st.button("✅ Aktifkan", use_container_width=True, key="btn_react_ap"):
                if target_react.strip():
                    if toggle_acl_user_status(target_react.strip(), True):
                        st.success(f"✅ {target_react} diaktifkan kembali."); st.rerun()
                    else:
                        st.error("Email tidak ditemukan di ACL.")

    # ── Tab 2: Tambah / Edit User ─────────────────────────────────
    with ap_tab2:
        st.markdown(f"""
        <div style="background:{T['accent_bg']};border:1px solid {T['border2']};border-radius:8px;
            padding:12px 16px;margin-bottom:20px;font-size:13px;color:{T['text_variant']};">
            💡 <b>Cara kerja:</b> Masukkan email user → isi data & role → set password sementara →
            user langsung bisa login. Untuk edit user yang sudah ada, centang "Edit existing user"
            dan pilih emailnya.
        </div>
        """, unsafe_allow_html=True)

        is_edit_mode = st.checkbox("✏️ Edit user yang sudah ada", value=False, key="ap_edit_mode")

        prefill = {}
        edit_target_email = None
        if is_edit_mode and not acl_display_df.empty:
            edit_choice = st.selectbox(
                "Pilih email user yang akan diedit",
                ["— pilih —"] + acl_display_df["Email"].tolist(),
                key="ap_edit_choice"
            )
            if edit_choice != "— pilih —":
                edit_target_email = edit_choice
                prefill = acl_dict.get(edit_choice, {})

        VALID_ROLES_AP = ["employee", "leader", "hrbp", "cxo", "admin", "od_reviewer", "super_admin"]

        # Get BU & SBU options from live data
        all_bus_ap  = sorted(df["Business Unit"].dropna().unique().tolist()) if df is not None else []
        all_sbus_ap = sorted([s for s in df["SBU/Tribe"].dropna().unique().tolist()
                              if str(s).strip() not in ("", "nan")]) if df is not None else []

        with st.form("ap_upsert_form", clear_on_submit=not is_edit_mode):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                f_email_ap  = st.text_input("Email *",
                                            value=edit_target_email or "",
                                            placeholder="user@mekari.com",
                                            disabled=is_edit_mode,
                                            key="ap_f_email")
                f_name_ap   = st.text_input("Nama Lengkap *",
                                            value=prefill.get("name", ""),
                                            placeholder="Nama lengkap user",
                                            key="ap_f_name")
                f_role_ap_f = st.selectbox("Role *", VALID_ROLES_AP,
                                           index=VALID_ROLES_AP.index(prefill.get("role", "employee"))
                                           if prefill.get("role") in VALID_ROLES_AP else 0,
                                           key="ap_f_role_form",
                                           help="admin=full access | cxo=org chart full | leader=org chart per BU | employee=org chart C-1")
                f_eid_ap    = st.text_input("Employee ID (opsional, wajib untuk role 'employee')",
                                            value=prefill.get("employee_id", ""),
                                            placeholder="SLKRXXX",
                                            key="ap_f_eid")

            with col_f2:
                f_bus_ap   = st.multiselect(
                    "Allowed Business Unit",
                    options=["*"] + all_bus_ap,
                    default=(prefill.get("allowed_bus", "*").split(",")
                             if prefill.get("allowed_bus") and prefill.get("allowed_bus") != "*"
                             else ["*"]),
                    key="ap_f_bus",
                    help="Pilih '*' untuk semua BU. Hanya relevan untuk role 'leader' dan 'hrbp'."
                )
                f_sbus_ap  = st.multiselect(
                    "Allowed SBU / Tribe",
                    options=["*"] + all_sbus_ap,
                    default=(prefill.get("allowed_sbus", "*").split(",")
                             if prefill.get("allowed_sbus") and prefill.get("allowed_sbus") != "*"
                             else ["*"]),
                    key="ap_f_sbus",
                    help="Pilih '*' untuk semua SBU."
                )
                f_note_ap  = st.text_area("Scope Note (wajib diisi, untuk audit trail) *",
                                          value=prefill.get("scope_note", ""),
                                          placeholder="Contoh: Leader Technology BU, cross-functional access untuk Q2 OKR review",
                                          height=90,
                                          key="ap_f_note")
                if not is_edit_mode:
                    f_pass_ap = st.text_input("Password Awal *",
                                              placeholder="Password sementara untuk user ini",
                                              type="password",
                                              key="ap_f_pass")
                else:
                    f_pass_ap = prefill.get("password", "")  # preserve existing if editing
                    st.caption("🔒 Gunakan tab 'Reset Password' untuk mengubah password user ini.")

            submitted_ap = st.form_submit_button(
                "💾 Simpan Perubahan" if is_edit_mode else "➕ Tambah User",
                use_container_width=True
            )

        if submitted_ap:
            errors_ap = []
            email_clean_ap = (edit_target_email or f_email_ap.strip()).lower()
            if not email_clean_ap or "@" not in email_clean_ap:
                errors_ap.append("Email tidak valid")
            if not f_name_ap.strip():
                errors_ap.append("Nama lengkap harus diisi")
            if not f_note_ap.strip():
                errors_ap.append("Scope Note wajib diisi untuk audit trail")
            if not is_edit_mode and not f_pass_ap.strip():
                errors_ap.append("Password awal harus diisi")
            if f_role_ap_f == "employee" and not f_eid_ap.strip():
                errors_ap.append("Employee ID wajib untuk role 'employee' agar RLS bisa berjalan")
            if f_role_ap_f in ("leader", "hrbp") and (not f_bus_ap or not f_sbus_ap):
                errors_ap.append("Role leader/hrbp wajib memiliki scope BU dan SBU. Pilih '*' secara eksplisit bila memang untuk semua.")
            if f_role_ap_f in ("super_admin", "admin", "cxo", "od_reviewer") and "*" not in f_bus_ap:
                errors_ap.append("Role super_admin, admin, cxo, dan od_reviewer harus memiliki BU scope '*' (full access)")

            if errors_ap:
                for e in errors_ap:
                    st.error(f"❌ {e}")
            else:
                bus_val  = "*" if "*" in f_bus_ap  else ",".join(f_bus_ap)
                sbus_val = "*" if "*" in f_sbus_ap else ",".join(f_sbus_ap)

                user_payload = {
                    "email":       email_clean_ap,
                    "name":        f_name_ap.strip(),
                    "role":        f_role_ap_f,
                    "password":    f_pass_ap.strip() if f_pass_ap else prefill.get("password", ""),
                    "allowed_bus": bus_val,
                    "allowed_sbus":sbus_val,
                    "employee_id": f_eid_ap.strip(),
                    "is_active":   True,
                    "scope_note":  f_note_ap.strip(),
                    "created_at":  prefill.get("created_at", ""),  # preserve jika edit
                }
                if save_acl_user(user_payload):
                    action = "diperbarui" if is_edit_mode else "ditambahkan"
                    st.success(f"✅ User **{email_clean_ap}** berhasil {action}.")
                    st.rerun()

    # ── Tab 3: Reset Password ─────────────────────────────────────
    with ap_tab3:
        st.markdown(f"""
        <div style="background:{T['warn_bg']};border:1px solid {T['warn_bdr']};border-radius:8px;
            padding:12px 16px;margin-bottom:20px;font-size:13px;color:{T['warn_txt']};">
            ⚠️ <b>Perhatian:</b> Reset password akan langsung berlaku. Informasikan password baru
            ke user yang bersangkutan secara aman (misalnya via DM atau email terenkripsi).
            Password disimpan di Google Sheets — pastikan akses ke sheet dibatasi hanya untuk tim OD.
        </div>
        """, unsafe_allow_html=True)

        if acl_display_df.empty:
            st.info("Belum ada user di ACL.")
        else:
            active_users = acl_display_df[acl_display_df["Status"] == "✅ Aktif"]["Email"].tolist()
            with st.form("ap_reset_pw_form", clear_on_submit=True):
                rp_email    = st.selectbox("Pilih User *", ["— pilih —"] + active_users, key="rp_email")
                rp_pass_new = st.text_input("Password Baru *", type="password",
                                            placeholder="Minimal 8 karakter", key="rp_pass")
                rp_confirm  = st.text_input("Konfirmasi Password *", type="password",
                                            placeholder="Ulangi password baru", key="rp_confirm")
                rp_submit   = st.form_submit_button("🔑 Reset Password", use_container_width=True)

            if rp_submit:
                errors_rp = []
                if rp_email == "— pilih —":   errors_rp.append("Pilih user terlebih dahulu")
                if len(rp_pass_new) < 8:       errors_rp.append("Password minimal 8 karakter")
                if rp_pass_new != rp_confirm:  errors_rp.append("Konfirmasi password tidak cocok")

                if errors_rp:
                    for e in errors_rp: st.error(f"❌ {e}")
                else:
                    if reset_user_password(rp_email, rp_pass_new):
                        st.success(f"✅ Password **{rp_email}** berhasil direset. Informasikan ke user.")
                    else:
                        st.error("Gagal reset password. Pastikan koneksi ke Google Sheets aktif.")
    # ── Tab 4: Activity Log ────────────────────────────────────────
    with ap_tab4:
        st.markdown(f"""
        <div style="margin-bottom:16px;">
            <div style="font-size:14px;font-weight:600;color:{T['text']};">📋 Activity Log</div>
            <div style="font-size:12px;color:{T['text_variant']};margin-top:4px;">
                500 aktivitas terbaru · diurutkan dari terbaru
            </div>
        </div>
        """, unsafe_allow_html=True)

        log_df = get_activity_log(limit=500)

        if log_df.empty:
            st.info("Belum ada aktivitas tercatat. Log akan muncul setelah user mulai login.")
        else:
            # Summary metrics
            col_lg1, col_lg2, col_lg3, col_lg4 = st.columns(4)
            col_lg1.metric("Total Events",   len(log_df))
            col_lg2.metric("Login Events",   len(log_df[log_df.get("action_type","") == "login"]) if "action_type" in log_df.columns else "-")
            col_lg3.metric("Unique Users",   log_df["user_email"].nunique() if "user_email" in log_df.columns else "-")
            col_lg4.metric("Export Events",  len(log_df[log_df.get("action_type","") == "export"]) if "action_type" in log_df.columns else "-")

            st.markdown("---")

            # Filter log
            col_lf1, col_lf2, col_lf3 = st.columns(3)
            with col_lf1:
                log_users = ["Semua"] + sorted(log_df["user_email"].dropna().unique().tolist()) if "user_email" in log_df.columns else ["Semua"]
                f_log_user = st.selectbox("Filter User", log_users, key="f_log_user")
            with col_lf2:
                log_actions = ["Semua"] + sorted(log_df["action_type"].dropna().unique().tolist()) if "action_type" in log_df.columns else ["Semua"]
                f_log_action = st.selectbox("Filter Action", log_actions, key="f_log_action")
            with col_lf3:
                f_log_search = st.text_input("Cari detail", placeholder="Ketik...", key="f_log_search")

            view_log = log_df.copy()
            if f_log_user   != "Semua" and "user_email"   in view_log.columns: view_log = view_log[view_log["user_email"]   == f_log_user]
            if f_log_action != "Semua" and "action_type"  in view_log.columns: view_log = view_log[view_log["action_type"]  == f_log_action]
            if f_log_search.strip() and "detail" in view_log.columns:
                view_log = view_log[view_log["detail"].str.lower().str.contains(f_log_search.lower(), na=False)]

            st.caption(f"Menampilkan **{len(view_log)}** dari **{len(log_df)}** log entries")
            st.dataframe(view_log, use_container_width=True, height=450)

            # Export log
            if st.button("⬇️ Export Log ke Excel", key="btn_export_log"):
                buf = BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    view_log.to_excel(writer, index=False, sheet_name="Activity Log")
                st.download_button(
                    "📥 Download Activity Log",
                    data=buf.getvalue(),
                    file_name=f"activity_log_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_log"
                )
