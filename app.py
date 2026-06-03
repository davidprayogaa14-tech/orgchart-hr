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
        "data_source_local":"Lokal · CSV","auto_refresh":"Auto-refresh setiap 5 menit",
        "menu_label":"Menu","header_supra":"People","header_title":"Organization Dashboard",
        "header_subtitle":"Dashboard Visualisasi Data Organisasi","header_metric":"Total Karyawan",
        "mode_label":"MODE TAMPILAN","mode_division":"Per Divisi","mode_company":"Seluruh Perusahaan",
        "search_label":"Cari Karyawan","search_ph":"Ketik nama karyawan...",
        "filter_label":"Filter","filter_bu":"🏢 Business Unit","filter_div":"📁 Divisi",
        "filter_sbu":"🏷️ SBU/Tribe","filter_leader":"👤 Filter by Leader",
        "filter_all_sbu":"Semua SBU","filter_all_div":"Semua (divisi penuh)",
        "expand_level":"📶 Expand Level","download_data":"⬇️ Download Data",
        "showing_emp":"Menampilkan","employees":"karyawan",
        "emp_found":"Ditemukan","emp_not_found":"Tidak ada karyawan bernama",
        "company_warning":"⚠️ Mode seluruh perusahaan menampilkan semua karyawan.",
        "tab_data_title":"Data Karyawan","tab_data_sub":"Seluruh data karyawan dengan filter dan pencarian",
        "search_name":"🔍 Cari nama karyawan","filter_all":"Semua",
        "tab_cc_title":"Compliance Check","tab_cc_sub":"Deteksi inkonsistensi data antara Employee Data dan MPP Data",
        "cc_tab_summary":"📊  Ringkasan Isu","cc_tab_missing":"👤  Missing Manager ID",
        "cc_tab_mismatch":"🔀  Data Tidak Konsisten","cc_tab_ghost":"🔍  Tidak Terpetakan",
        "cc_tab_vacancy":"📋  Master MPP",
        "cc_no_mpp":"Data MPP tidak tersedia. Pastikan worksheet mpp_data sudah ada.",
        "cc_total_anomali":"Total Isu Data","cc_missing_mgr":"Missing Manager ID",
        "cc_mismatch":"Data Tidak Konsisten","cc_ghost":"Tidak Terpetakan","cc_vacancy":"Master MPP",
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
    },
    "en": {
        "nav_org":"Org Chart","nav_data":"Employee Data","nav_compliance":"Compliance Check",
        "nav_manager":"Manager List","nav_cr":"Change Request",
        "btn_refresh":"Refresh","btn_mode":"Mode","btn_logout":"Sign Out",
        "lang_toggle":"🇮🇩 Bahasa","data_source_live":"Live · Google Sheets",
        "data_source_local":"Local · CSV","auto_refresh":"Auto-refresh every 5 minutes",
        "menu_label":"Menu","header_supra":"People","header_title":"Organization Dashboard",
        "header_subtitle":"Organizational Data Visualization Dashboard","header_metric":"Total Employees",
        "mode_label":"VIEW MODE","mode_division":"By Division","mode_company":"Entire Company",
        "search_label":"Search Employee","search_ph":"Type employee name...",
        "filter_label":"Filter","filter_bu":"🏢 Business Unit","filter_div":"📁 Division",
        "filter_sbu":"🏷️ SBU/Tribe","filter_leader":"👤 Filter by Leader",
        "filter_all_sbu":"All SBUs","filter_all_div":"All (full division)",
        "expand_level":"📶 Expand Level","download_data":"⬇️ Download Data",
        "showing_emp":"Showing","employees":"employees",
        "emp_found":"Found","emp_not_found":"No employee named",
        "company_warning":"⚠️ Company-wide mode displays all employees.",
        "tab_data_title":"Employee Data","tab_data_sub":"All employee data with filters and search",
        "search_name":"🔍 Search employee name","filter_all":"All",
        "tab_cc_title":"Compliance Check","tab_cc_sub":"Detect data inconsistencies between Employee Data and MPP Data",
        "cc_tab_summary":"📊  Issue Summary","cc_tab_missing":"👤  Missing Manager ID",
        "cc_tab_mismatch":"🔀  Data Inconsistency","cc_tab_ghost":"🔍  Unmapped Employees",
        "cc_tab_vacancy":"📋  Master MPP",
        "cc_no_mpp":"MPP data not available. Please ensure the mpp_data worksheet exists.",
        "cc_total_anomali":"Total Data Issues","cc_missing_mgr":"Missing Manager ID",
        "cc_mismatch":"Data Inconsistency","cc_ghost":"Unmapped Employees","cc_vacancy":"Master MPP",
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

# Bootstrap fallback — digunakan HANYA ketika worksheet app_users belum ada.
# Hapus atau nonaktifkan setelah ACL di-seed via Admin Panel.
_ACL_FALLBACK = {
    "od_admin@mekari.com": {
        "name": "OD Admin", "role": "admin", "password": "mekari_od_2026",
        "allowed_bus": "*", "allowed_sbus": "*", "employee_id": "",
        "is_active": True, "scope_note": "Bootstrap admin",
    },
}

# Role → tab access mapping
# admin   : semua tab (0=OrgChart, 1=Data, 2=Compliance, 3=Manager, 4=CR, 99=AdminPanel)
# cxo     : hanya tab 0
# leader  : hanya tab 0
# employee: hanya tab 0
_ROLE_TAB_ACCESS = {
    "admin":    {0, 1, 2, 3, 4, 99},
    "cxo":      {0},
    "leader":   {0},
    "employee": {0},
}


def _can_access_tab(role: str, tab_idx: int) -> bool:
    """Return True jika role boleh mengakses tab_idx."""
    return tab_idx in _ROLE_TAB_ACCESS.get(role, {0})


@st.cache_data(ttl=120)
def load_acl_table() -> dict:
    """
    Load ACL dari worksheet 'app_users' di Google Sheets.
    Return dict keyed by email (lowercase).
    Fallback ke _ACL_FALLBACK jika sheet belum ada / kosong.
    """
    client = get_gspread_client()
    if not client:
        return _ACL_FALLBACK
    try:
        ws   = client.open_by_key(SHEET_ID).worksheet(SHEET_ACL_NAME)
        rows = ws.get_all_records()
        if not rows:
            return _ACL_FALLBACK
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
        return acl if acl else _ACL_FALLBACK
    except Exception:
        return _ACL_FALLBACK


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


def authenticate_user(email: str, password: str) -> dict | None:
    """
    Verifikasi email + password. Return user dict atau None.
    Urutan lookup:
    1. Streamlit Secrets [auth][users] (production)
    2. Google Sheets app_users (primary ACL)
    3. _ACL_FALLBACK (bootstrap only)
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
        if stored_pw and stored_pw == password:
            return user

    return None


def apply_rbac_filter(df: pd.DataFrame, user_info: dict) -> pd.DataFrame:
    """
    Row-Level Security — filter DataFrame berdasarkan role & scope user.

    Mapping:
    - admin / cxo   → full access, no filter
    - leader        → filter by allowed_bus + allowed_sbus
    - employee      → subtree C-1 (direct reports of their manager only)

    PENTING: fungsi ini hanya dipanggil SETELAH auth berhasil.
    df yang dikembalikan adalah satu-satunya data yang boleh dilihat user.
    """
    role = user_info.get("role", "employee")

    # ── Full access ───────────────────────────────────────────────
    if role in ("admin", "cxo"):
        return df

    # ── Leader: BU + SBU scope ────────────────────────────────────
    if role == "leader":
        raw_bus  = user_info.get("allowed_bus", "*").strip()
        raw_sbus = user_info.get("allowed_sbus", "*").strip()

        # Parse comma-separated, handle wildcard
        allowed_bus  = [] if raw_bus  == "*" else [b.strip() for b in raw_bus.split(",")  if b.strip()]
        allowed_sbus = [] if raw_sbus == "*" else [s.strip() for s in raw_sbus.split(",") if s.strip()]

        filtered = df.copy()

        if allowed_bus:  # non-empty = restricted
            if "Business Unit" in filtered.columns:
                filtered = filtered[filtered["Business Unit"].isin(allowed_bus)]

        if allowed_sbus:
            if "SBU/Tribe" in filtered.columns:
                # Tetap tampilkan node tanpa SBU (atasan lintas unit tetap visible)
                sbu_mask = (
                    filtered["SBU/Tribe"].isin(allowed_sbus) |
                    filtered["SBU/Tribe"].isin(["", "nan"]) |
                    filtered["SBU/Tribe"].isna()
                )
                filtered = filtered[sbu_mask]

        return filtered

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
            user_data.get("password", ""),
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
        ws.update_cell(cell.row, 4, new_password)   # Col 4 = password
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
_PEOPLE_DB_DROP_COLS = [
    "Webhook Timestamp", "Webhook ID", "user_id",
    # Employment Approval Line Name & Email TIDAK di-drop — di-rename ke Manager Name/Email
    "Employment Approval Line User ID",
    "Primary Budget Holder", "Secondary Budget Holder",
    "End Date", "Resign Date", "Original Placement",
    "Notice Period (TBC)", "Branch", "Tenure",
    "HRBP Email", "Join Date",
    "Employment Status", "Employment Type Status",  # di-drop setelah dipakai untuk filter
]

# Filter kriteria — dua kolom terpisah:
#   Employment Status      : Active, Resigned
#   Employment Type Status : Permanent, Intern, Probation, Contract
_EMPLOYMENT_STATUS_VALUES = {"active", "resigned"}
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
        print(f"[normalize_people_db] 'Employment Status' unique values: {unique_emp_status}")
        mask_status = df["Employment Status"].str.lower().isin(_EMPLOYMENT_STATUS_VALUES)
        df = df[mask_status].copy()
        print(f"[normalize_people_db] After Employment Status filter: {len(df)} records")
    else:
        print("[normalize_people_db] WARNING: 'Employment Status' column not found")

    # Filter kolom "Employment Type Status"
    if "Employment Type Status" in df.columns:
        df["Employment Type Status"] = df["Employment Type Status"].astype(str).str.strip()
        unique_type_status = df["Employment Type Status"].unique().tolist()
        print(f"[normalize_people_db] 'Employment Type Status' unique values: {unique_type_status}")
        mask_type = df["Employment Type Status"].str.lower().isin(_EMPLOYMENT_TYPE_VALUES)
        df = df[mask_type].copy()
        print(f"[normalize_people_db] After Employment Type Status filter: {len(df)} records")
    else:
        print("[normalize_people_db] WARNING: 'Employment Type Status' column not found")

    print(f"[normalize_people_db] Total filtered: {total_before} → {len(df)} records")

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
        print(f"[normalize_people_db] Manager ID sample (post-rename): {sample_mgr}")
    print(f"[normalize_people_db] Columns after rename: {df.columns.tolist()}")

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

    # Hapus baris tanpa Employee ID valid
    df = df[df["Employee ID"].str.len() > 0]
    df = df[df["Employee ID"] != "nan"]

    # Deduplicate Employee ID — People Database bisa mengandung
    # multiple rows per karyawan (misal: resign + rejoin).
    # Keep last row (data terbaru berdasarkan urutan di sheet).
    dupes = df["Employee ID"].duplicated(keep=False).sum()
    if dupes > 0:
        print(f"[normalize_people_db] Found {dupes} duplicate Employee ID rows — keeping last occurrence")
        df = df.drop_duplicates(subset=["Employee ID"], keep="last")

    print(f"[normalize_people_db] Final records loaded: {len(df)}")
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


@st.cache_data(ttl=60)
def load_change_requests():
    client = get_gspread_client()
    if not client:
        return pd.DataFrame()
    try:
        ws   = client.open_by_key(SHEET_ID).worksheet(SHEET_CR_NAME)
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
        return client.open_by_key(SHEET_ID).worksheet(SHEET_CR_NAME)
    except Exception:
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
        user_info  = st.session_state.get("user_info", {})
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
        df = pd.DataFrame(rows)
        # Tampilkan terbaru dulu, limit rows
        return df.iloc[::-1].head(limit).reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=_LOG_COLS)


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
    HEADER_H = 80

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
    c.drawRightString(page_w - 36, 18, "HR Organization Dashboard")


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


def generate_pdf(tree_nodes, title_text, div_name="", bu_name=""):
    """
    PDF Full — semua level, node lebih besar, nama+posisi+SBU lengkap,
    header profesional dengan metadata waktu & divisi.
    """
    if not REPORTLAB_OK:
        raise ImportError("ReportLab tidak tersedia")

    # Node dimensions — lebih besar untuk muat 4 baris teks
    NODE_W, NODE_H = 180, 76
    H_GAP, V_GAP   = 20, 52
    HEADER_H        = 90   # ruang header di atas
    FOOTER_H        = 44   # ruang footer di bawah

    downloaded_at = datetime.now().strftime("%d %B %Y, %H:%M")

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
                     subtitle=f"Organization Chart — Full Structure",
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

        # Employee ID kecil di pojok kanan bawah
        c.setFont("Helvetica", 5.5)
        c.setFillColor(PDF_TEXT_MUTED)
        c.drawRightString(x_left + NODE_W - 6, y_bottom + 5, emp_id)

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
    PDF Summary — tampilkan hingga Level 2, node lebih informatif,
    header profesional, nama + posisi + SBU lengkap.
    """
    if not REPORTLAB_OK:
        raise ImportError("ReportLab tidak tersedia")

    NODE_W_FULL, NODE_H_FULL = 190, 82
    NODE_W_L2,   NODE_H_L2   = 160, 72
    H_GAP, V_GAP = 18, 48
    HEADER_H     = 90
    FOOTER_H     = 44

    downloaded_at = datetime.now().strftime("%d %B %Y, %H:%M")

    def trim_tree(node, depth=0):
        if depth > 2:
            return None
        trimmed = dict(node)
        trimmed["_depth"]   = depth
        trimmed["children"] = [] if depth == 2 else [
            ch2 for ch2 in [trim_tree(ch, depth + 1) for ch in node.get("children", [])] if ch2
        ]
        return trimmed

    trimmed_roots = [t for t in [trim_tree(r) for r in tree_nodes] if t]

    def node_w(n): return NODE_W_FULL if n["_depth"] < 2 else NODE_W_L2
    def node_h(n): return NODE_H_FULL if n["_depth"] < 2 else NODE_H_L2

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
                     subtitle=f"Organization Chart — Summary (s/d Level 2)",
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
    for depth, lbl in {0: "Top Level", 1: "Level 1", 2: "Level 2"}.items():
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

        # Nama (bold, wrap)
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

        # Employee ID
        c.setFont("Helvetica", 5.5)
        c.setFillColor(PDF_TEXT_MUTED)
        c.drawRightString(x_left + nw - 5, y_bot + 4, emp_id)

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
def render_org_chart(tree_json_str, chart_height=700, initial_level="all", theme=None, highlight_id=None):
    # Convert highlight_id ke JS literal
    highlight_id_js = f'"{highlight_id}"' if highlight_id else 'null'
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
  <div class="legend-item"><div class="legend-dot" style="background:{node_in_bdr};border:1px solid {node_in_bdr}"></div><span>Divisi ini</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:{node_out_bdr};border:1px solid {node_out_bdr}"></div><span>Atasan luar divisi</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:#f59e0b;border-radius:999px"></div><span>Jml subordinate</span></div>
  <div class="legend-item" id="legend-highlight" style="display:none;">
    <div class="legend-dot" style="background:#f59e0b;border:2px solid #d97706;border-radius:3px;"></div>
    <span style="color:{hint_color}">Karyawan dicari</span>
  </div>
  <div class="legend-item" style="color:{hint_color}">💡 Klik node · Scroll zoom · Drag geser</div>
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
  const isHighlight = highlightId && node.id === highlightId;
  const wrapper = document.createElement('div'); wrapper.className = 'node-wrapper';
  const box     = document.createElement('div');
  const baseClass = node.company_mode ? 'company-mode' : node.in_div ? 'in-div' : 'out-div';
  box.className = `node-box ${{baseClass}}${{isHighlight ? ' highlighted' : ''}}`;
  if (isHighlight) {{ box.id = 'highlighted-node'; }}
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
function scrollToHighlighted() {{
  const el = document.getElementById('highlighted-node');
  if (!el) return;
  // Tunggu layout selesai
  setTimeout(() => {{
    const canvasRect = canvas.getBoundingClientRect();
    const elRect     = el.getBoundingClientRect();
    // Hitung posisi relatif terhadap tree-root
    const elCenterX  = elRect.left + elRect.width  / 2 - canvasRect.left;
    const elCenterY  = elRect.top  + elRect.height / 2 - canvasRect.top;
    const targetX    = canvasRect.width  / 2 - elCenterX;
    const targetY    = canvasRect.height / 2 - elCenterY;
    // Smooth transition
    treeRoot.style.transition = 'transform 0.6s cubic-bezier(0.4,0,0.2,1)';
    scale = 1.2;
    translateX = targetX;
    translateY = targetY - 60;
    applyTransform();
    setTimeout(() => {{ treeRoot.style.transition = ''; }}, 700);
    // Show legend item
    const legEl = document.getElementById('legend-highlight');
    if (legEl) legEl.style.display = 'flex';
  }}, 350);
}}
function rerenderTree() {{
  const r = document.getElementById('tree-root');
  r.innerHTML = '';
  treeData.forEach(n => r.appendChild(renderNode(n)));
  if (highlightId) {{ scrollToHighlighted(); }}
}}
treeData.forEach(n => applyInitialCollapse(n, 0));
rerenderTree();
if (!highlightId) {{ setTimeout(fitView, 300); }}
</script></body></html>"""


# ══════════════════════════════════════════════════════════════════
# STREAMLIT PAGE CONFIG
# ══════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Mekari", layout="wide", page_icon="⭐", initial_sidebar_state="expanded")

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
_auth_secrets = st.secrets.get("auth", {})
_google_creds = {
    "web": {
        "client_id":                  _auth_secrets.get("client_id", ""),
        "client_secret":              _auth_secrets.get("client_secret", ""),
        "auth_uri":                   "https://accounts.google.com/o/oauth2/auth",
        "token_uri":                  "https://oauth2.googleapis.com/token",
        "redirect_uris":              ["https://orgchart-hr-eajasa62ryaazvy8gu9enn.streamlit.app"],
        "javascript_origins":         ["https://orgchart-hr-eajasa62ryaazvy8gu9enn.streamlit.app"],
    }
}
_creds_tmp = _tempfile.NamedTemporaryFile(
    mode="w", suffix=".json", delete=False
)
_json.dump(_google_creds, _creds_tmp)
_creds_tmp.flush()

# Inisialisasi authenticator
_google_auth = _GoogleAuth(
    secret_credentials_path = _creds_tmp.name,
    cookie_name             = "mekari_od_auth",
    cookie_key              = _auth_secrets.get("cookie_secret", "mekari_od_2026_fallback"),
    redirect_uri            = "https://orgchart-hr-eajasa62ryaazvy8gu9enn.streamlit.app",
)

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
    # Render halaman login
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .stApp { background: #f5f5ff !important; }
    .block-container { max-width: 420px !important; padding-top: 14vh !important; margin: 0 auto !important; }
    header, #MainMenu, footer { visibility: hidden !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center; margin-bottom:40px;">
        <div style="width:52px;height:52px;border-radius:14px;background:#8E94F2;
            display:flex;align-items:center;justify-content:center;font-size:26px;
            margin:0 auto 20px;box-shadow:0 6px 24px rgba(142,148,242,0.4);">&#127962;</div>
        <div style="font-size:24px;font-weight:700;color:#1a1a2e;letter-spacing:-0.02em;">Mekari</div>
        <div style="font-size:12px;color:#7b7b9d;margin-top:6px;font-weight:500;
            letter-spacing:0.06em;text-transform:uppercase;">People Dashboard</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#fff;border:1.5px solid #e0e0f0;border-radius:12px;
        padding:28px 32px;text-align:center;box-shadow:0 4px 20px rgba(142,148,242,0.10);">
        <div style="font-size:14px;color:#3d3d5c;margin-bottom:20px;line-height:1.6;">
            Gunakan akun Google perusahaan Anda<br>
            <span style="color:#8E94F2;font-weight:600;">@mekari.com</span> untuk masuk
        </div>
    """, unsafe_allow_html=True)

    _auth_url = _google_auth.get_authorization_url()
    st.link_button("🔐  Login dengan Google", _auth_url, use_container_width=True)

    st.markdown("""
    </div>
    <div style="text-align:center;margin-top:20px;font-size:11px;color:#9e9ea0;">
        Akses dikelola oleh OD Team · Mekari People Analytics
    </div>
    """, unsafe_allow_html=True)
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
if st.session_state.get("user_email") != _google_email:
    st.session_state.user_email   = _google_email
    st.session_state.google_email = _google_email  # preserve agar tidak hilang
    st.session_state.user_info    = _user_info
    st.session_state.session_id   = str(_uuid.uuid4())[:8]
    log_activity(
        action_type="login",
        detail=f"Google OAuth login · role={_user_info.get('role','')}",
    )

_user_info = st.session_state.get("user_info", _user_info)
_user_role = _user_info.get("role", "employee")
_is_admin  = _user_role == "admin"
_is_cxo    = _user_role in ("admin", "cxo")

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "lang" not in st.session_state:
    st.session_state.lang = "id"
if "nav_filter" not in st.session_state:
    st.session_state.nav_filter = {}

L = LANG[st.session_state.lang]

df, data_source = load_data()

if df is None:
    st.error("Tidak ada data yang bisa dimuat. Pastikan credentials.json dan employee_data.csv tersedia.")
    st.stop()

# Apply Row-Level Security — filter df sesuai akses user
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
html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif !important;
    color: {T["text"]} !important;
    -webkit-font-smoothing: antialiased;
    letter-spacing: -0.01em;
}}
.stApp {{ background-color: {T["bg"]} !important; transition: background-color 0.3s ease, color 0.3s ease; }}
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
    box-shadow: 1px 0 0 0 {T["outline"]} !important;
    transition: background 0.3s ease !important;
}}
[data-testid="stSidebar"] .block-container {{ padding: 0 !important; background: transparent !important; }}
[data-testid="stSidebar"] * {{ color: {T["sidebar_text"]} !important; font-family: 'Inter', sans-serif !important; }}
[data-testid="stSidebar"] label {{
    font-size: 11px !important; font-weight: 600 !important;
    text-transform: uppercase !important; letter-spacing: 0.08em !important;
    color: {T["sidebar_text2"]} !important;
}}
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
[data-testid="stSidebar"] [data-testid="stButton"] button {{
    background: rgba(255,255,255,0.06) !important; color: {T["sidebar_text"]} !important;
    border: none !important; border-radius: 8px !important;
    font-size: 13px !important; font-weight: 500 !important; padding: 10px 16px !important;
    text-align: left !important; transform: none !important; box-shadow: none !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {{
    background: rgba(142,148,242,0.15) !important; color: {T["sidebar_active"]} !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {{
    background: {T["sidebar_pill"]} !important; color: {T["sidebar_active"]} !important;
    border: none !important; border-radius: 8px !important;
    font-size: 13px !important; font-weight: 600 !important; padding: 10px 16px !important;
    box-shadow: 0 1px 0 0 rgba(142,148,242,0.12) !important;
    transform: none !important; filter: none !important;
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
div[data-baseweb="popover"] ul, div[data-baseweb="menu"] {{
    background: {T["surface_lowest"]} !important; border: none !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 24px rgba(142,148,242,0.15), 0 0 0 1px {T["outline"]} !important;
}}
div[data-baseweb="popover"] li, [role="option"] {{
    background: transparent !important; color: {T["text"]} !important;
    font-family: 'Inter', sans-serif !important; font-size: 13.5px !important;
    border-radius: 6px !important; margin: 2px 4px !important;
}}
div[data-baseweb="popover"] li:hover, [role="option"]:hover {{
    background: {T["primary_fixed"]} !important; color: {T["primary"]} !important;
}}
div[data-baseweb="popover"] {{ background: transparent !important; }}
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
[data-testid="stDateInput"] > div > div {{
    background: {T["surface_lowest"]} !important; border: 1px solid {T["outline"]} !important; border-radius: 8px !important;
}}
[data-testid="stDateInput"] input {{ color: {T["text"]} !important; background: transparent !important; }}

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
[data-testid="stTooltipIcon"] {{ color: {T["text_variant"]} !important; }}

hr {{ border: none !important; border-top: 1px solid {T["outline"]} !important; }}
</style>
""", unsafe_allow_html=True)



# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    toggle_icon  = "☀️" if dm else "🌙"
    status_dot   = "🟢" if data_source == "google_sheets" else "🟡"
    status_txt   = L["data_source_live"] if data_source == "google_sheets" else L["data_source_local"]
    total_karyawan = len(df)
    total_bu       = df["Business Unit"].nunique()
    total_div      = df["Division"].nunique()
    total_mgr      = df[df["Employee ID"].isin(df["Manager ID"].unique())]["Employee ID"].nunique()

    st.markdown(f"""
    <div style="padding:24px 18px 18px 18px; border-bottom:1px solid {T['outline']}; margin-bottom:4px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:14px;">
            <div style="width:40px;height:40px;border-radius:8px;
                background:#ffffff;
                display:flex;align-items:center;justify-content:center;flex-shrink:0;
                box-shadow:0 2px 12px rgba(142,148,242,0.25);overflow:hidden;padding:4px;">
                <img src="data:image/png;base64,{_MEKARI_LOGO_B64}" style="width:100%;height:100%;object-fit:contain;" /></div>
            <div>
                <div style="font-size:15px;font-weight:700;color:{T['sidebar_active']};
                    font-family:'Inter',sans-serif;line-height:1.2;letter-spacing:-0.02em;">Mekari</div>
                <div style="font-size:10px;color:{T['sidebar_text2']};font-weight:500;
                    letter-spacing:0.06em;text-transform:uppercase;margin-top:2px;">People Dashboard</div>
            </div>
        </div>
        <div style="background:rgba(142,148,242,0.12);border-radius:6px;padding:6px 10px;
            display:flex;align-items:center;gap:6px;">
            <span style="font-size:8px;">{status_dot}</span>
            <span style="font-size:11px;color:{T['sidebar_text2']};font-weight:500;">{status_txt}</span>
        </div>
    </div>
    <div style="padding:12px 18px 8px 18px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
            <div style="background:rgba(142,148,242,0.10);border-radius:8px;padding:10px 12px;text-align:center;">
                <div style="font-size:19px;font-weight:700;color:{T['sidebar_active']};
                    font-family:'Inter',sans-serif;letter-spacing:-0.03em;">{total_karyawan:,}</div>
                <div style="font-size:10px;color:{T['sidebar_text2']};font-weight:500;
                    text-transform:uppercase;letter-spacing:0.05em;margin-top:2px;">{L["header_metric"]}</div>
            </div>
            <div style="background:rgba(142,148,242,0.10);border-radius:8px;padding:10px 12px;text-align:center;">
                <div style="font-size:19px;font-weight:700;color:{T['sidebar_active']};
                    font-family:'Inter',sans-serif;letter-spacing:-0.03em;">{total_mgr}</div>
                <div style="font-size:10px;color:{T['sidebar_text2']};font-weight:500;
                    text-transform:uppercase;letter-spacing:0.05em;margin-top:2px;">Manager</div>
            </div>
            <div style="background:rgba(142,148,242,0.10);border-radius:8px;padding:10px 12px;text-align:center;">
                <div style="font-size:19px;font-weight:700;color:{T['sidebar_active']};
                    font-family:'Inter',sans-serif;letter-spacing:-0.03em;">{total_bu}</div>
                <div style="font-size:10px;color:{T['sidebar_text2']};font-weight:500;
                    text-transform:uppercase;letter-spacing:0.05em;margin-top:2px;">Business Unit</div>
            </div>
            <div style="background:rgba(142,148,242,0.10);border-radius:8px;padding:10px 12px;text-align:center;">
                <div style="font-size:19px;font-weight:700;color:{T['sidebar_active']};
                    font-family:'Inter',sans-serif;letter-spacing:-0.03em;">{total_div}</div>
                <div style="font-size:10px;color:{T['sidebar_text2']};font-weight:500;
                    text-transform:uppercase;letter-spacing:0.05em;margin-top:2px;">Divisi</div>
            </div>
        </div>
    </div>
    <div style="padding:6px 18px;margin-bottom:2px;"><div style="height:1px;background:{T['outline']};"></div></div>
    <div style="padding:4px 18px 6px 18px;">
        <div style="font-size:10px;font-weight:600;text-transform:uppercase;
            letter-spacing:0.09em;color:{T['sidebar_text2']};">{L["menu_label"]}</div>
    </div>
    """, unsafe_allow_html=True)

    if "active_tab" not in st.session_state:
        st.session_state.active_tab = 0

    # User identity card
    _uname    = _user_info.get("name", "User")
    _uemail   = st.session_state.get("user_email", "")
    _urole    = _user_role.upper()
    _role_colors = {"ADMIN": "#8E94F2", "CXO": "#059669", "LEADER": "#d97706", "EMPLOYEE": "#64748b"}
    _role_color  = _role_colors.get(_urole, "#64748b")
    _initials    = "".join([w[0].upper() for w in _uname.split()[:2]])
    st.markdown(f"""
    <div style="padding:8px 18px 12px 18px;">
        <div style="display:flex;align-items:center;gap:10px;
            background:rgba(142,148,242,0.10);border-radius:8px;padding:10px 12px;">
            <div style="width:32px;height:32px;border-radius:50%;
                background:{T['primary']};
                display:flex;align-items:center;justify-content:center;
                font-size:12px;font-weight:600;color:white;flex-shrink:0;font-family:'Inter',sans-serif;">{_initials}</div>
            <div style="min-width:0;">
                <div style="font-size:13px;font-weight:600;color:{T['sidebar_active']};
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:'Inter',sans-serif;">{_uname}</div>
                <div style="display:flex;align-items:center;gap:5px;margin-top:3px;">
                    <span style="font-size:9px;font-weight:600;padding:2px 6px;border-radius:4px;
                        background:{_role_color};color:white;letter-spacing:0.05em;">{_urole}</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Tab visibility sementara ──────────────────────────────────
    # Hanya Org Chart yang ditampilkan.
    # Tab lain (Data Karyawan, Compliance, Manager, CR, Admin Panel)
    # akan dimunculkan kembali setelah integrasi SSO People Database selesai.
    # TODO: Kembalikan nav_items lengkap setelah SSO aktif.
    nav_items = [
        ("🌳", L["nav_org"], 0),
    ]

    active_idx = st.session_state.active_tab

    # Pastikan tab aktif masih boleh diakses role ini
    # (misal setelah role berubah via session lama)
    if not _can_access_tab(_user_role, active_idx):
        st.session_state.active_tab = 0
        active_idx = 0

    for icon_nav, label_nav, tab_idx in nav_items:
        # Render hanya tab yang boleh diakses role ini
        if not _can_access_tab(_user_role, tab_idx):
            continue
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
        if st.button(L["btn_refresh"], use_container_width=True, key="refresh_btn"):
            st.cache_data.clear(); st.rerun()
    with col_sb2:
        if st.button(f"{toggle_icon} {L['btn_mode']}", use_container_width=True, key="toggle_btn"):
            st.session_state.dark_mode = not st.session_state.dark_mode; st.rerun()

    # Language toggle
    if st.button(L["lang_toggle"], use_container_width=True, key="lang_btn"):
        st.session_state.lang = "en" if st.session_state.lang == "id" else "id"
        st.rerun()

    # Logout button
    st.markdown(f"""<div style="padding:4px 20px 0 20px;"><div style="height:1px;background:{T['outline']};"></div></div>""", unsafe_allow_html=True)
    if st.button(f"🚪  {L['btn_logout']}", use_container_width=True, key="logout_btn"):
        log_activity(action_type="logout", detail="User logout")
        for k in ["authenticated","user_email","user_info","active_tab","session_id","connected","oauth_state","token","google_email"]:
            st.session_state.pop(k, None)
        st.query_params.clear()
        try:
            _google_auth.logout()
        except Exception:
            pass
        st.rerun()

    st.markdown(f"""
    <div style="padding:12px 20px;font-size:10px;color:{T['sidebar_text2']};text-align:center;letter-spacing:0.03em;">
        {L["auto_refresh"]}
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# MAIN HEADER
# ══════════════════════════════════════════════════════════════════
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
    st.markdown(f"""
    <div style="font-size:10px;font-weight:700;text-transform:uppercase;
        letter-spacing:0.09em;color:{T['text3']};margin-bottom:10px;">MODE TAMPILAN</div>
    """, unsafe_allow_html=True)
    view_mode = st.radio("", ["Per Divisi", "Seluruh Perusahaan"], horizontal=True, label_visibility="collapsed")

    # ── Search Name ──────────────────────────────────────────────
    # [FIX] Search sekarang cari di seluruh df, auto-set filter BU/Divisi
    st.markdown(f"""
    <div style="font-size:12px;font-weight:600;color:{T['text3']};text-transform:uppercase;
        letter-spacing:0.06em;margin:16px 0 8px 0;">Cari Karyawan</div>
    """, unsafe_allow_html=True)

    col_search, col_search_info = st.columns([3, 5])
    with col_search:
        name_search = st.text_input(
            "🔍 Search Name", placeholder="Ketik nama karyawan...",
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
                    ❌ Tidak ada karyawan bernama "<b>{name_search}</b>"</div>""",
                    unsafe_allow_html=True)
            elif len(matched_global) == 1:
                emp = matched_global.iloc[0]
                st.markdown(f"""<div style="padding:8px 12px;background:#dcfce7;border-radius:8px;
                    font-size:12px;color:#166534;margin-top:4px;">
                    ✅ Ditemukan: <b>{emp['Employee Name']}</b> — {emp.get('Job Position','')},
                    <b>{emp.get('Division','')}</b> ({emp.get('Business Unit','')})</div>""",
                    unsafe_allow_html=True)
            else:
                names_list = ", ".join(matched_global["Employee Name"].tolist()[:4])
                suffix = f" +{len(matched_global)-4} lainnya" if len(matched_global) > 4 else ""
                st.markdown(f"""<div style="padding:8px 12px;background:#fef9c3;border-radius:8px;
                    font-size:12px;color:#854d0e;margin-top:4px;">
                    ⚠️ Ditemukan <b>{len(matched_global)}</b> karyawan: {names_list}{suffix}.
                    Pilih salah satu di bawah.</div>""", unsafe_allow_html=True)

    # Jika >1 hasil → selectbox pilih karyawan spesifik
    selected_emp_row = None
    if len(matched_global) > 1:
        emp_choices = ["— Pilih karyawan —"] + [
            f"{r['Employee Name']}  ·  {r.get('Division','')}  ·  {r.get('Business Unit','')}"
            for _, r in matched_global.iterrows()
        ]
        chosen_emp = st.selectbox("Pilih karyawan:", emp_choices,
                                  key="search_emp_choice", label_visibility="collapsed")
        if chosen_emp != "— Pilih karyawan —":
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
        st.session_state["sel_sbu"]    = "Semua SBU"
        st.session_state["sel_leader"] = "Semua (divisi penuh)"

    # ID karyawan target untuk highlight di tree
    search_highlight_id = str(selected_emp_row.get("Employee ID", "")) if selected_emp_row is not None else None
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
            if search_highlight_id and search_highlight_id in filtered["Employee ID"].values:
                _emp_name_hl = selected_emp_row["Employee Name"]
                st.caption(f"📊 Menampilkan **{len(filtered)}** karyawan — 🎯 **{_emp_name_hl}** ada di divisi ini")
            else:
                st.caption(f"📊 Menampilkan **{len(filtered)}** karyawan di divisi ini")

        selected_level  = {"All Level": "all", "Top Level": "top", "Level 1": "level1"}[level_opt]
        all_ids_needed  = get_all_managers(filtered["Employee ID"].tolist(), df)
        full_data       = df[df["Employee ID"].isin(all_ids_needed)].copy()
        all_ids_set     = set(full_data["Employee ID"].tolist())

        root_ids = full_data[
            ~full_data["Manager ID"].isin(all_ids_set) | full_data["Manager ID"].isin({"", "nan"})
        ]["Employee ID"].astype(str).tolist()

        tree_data  = build_tree_json(full_data, selected_div, root_ids, mode="division")
        chart_html = render_org_chart(json.dumps(tree_data), chart_height=680, initial_level=selected_level, theme=T, highlight_id=search_highlight_id)
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
                pdf_data = generate_pdf(tree_data, f"Org Chart — {selected_div} ({selected_bu})",
                                        div_name=selected_div, bu_name=selected_bu)
                st.download_button("📑 PDF (Full)", pdf_data, f"{selected_div}_full.pdf", "application/pdf", use_container_width=True)
            except Exception:
                st.button("📑 PDF (N/A)", disabled=True, use_container_width=True)
        with col_dl4:
            try:
                pdf_sum = generate_pdf_summary(tree_data, f"Org Chart Summary — {selected_div} ({selected_bu})",
                                              div_name=selected_div, bu_name=selected_bu)
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
        # Mode perusahaan: tampilkan seluruh tree (search sudah auto-switch ke Per Divisi)
        root_ids2  = df[(df["Manager ID"] == "") | (df["Manager ID"].isna())]["Employee ID"].tolist()
        tree_data2 = build_tree_json(df, "", root_ids2, mode="company")
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
                pdf2 = generate_pdf(tree_data2, "Org Chart — Seluruh Perusahaan",
                                    div_name="Semua Divisi", bu_name="Seluruh BU")
                st.download_button("📑 PDF (Full)", pdf2, "orgchart_perusahaan_full.pdf", "application/pdf", use_container_width=True)
            except Exception:
                st.button("📑 PDF (N/A)", disabled=True, use_container_width=True)
        with col_dl7:
            try:
                pdf_sum2 = generate_pdf_summary(tree_data2, "Org Chart Summary — Seluruh Perusahaan",
                                               div_name="Semua Divisi", bu_name="Seluruh BU")
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
# TAB 3 — COMPLIANCE CHECK
# ══════════════════════════════════════════════════════════════════
elif _active == 2:
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
        len(mis_df),
        help="Karyawan yang Job ID-nya cocok di Employee Data & MPP, namun ada field yang berbeda (contoh: nama divisi, career stage). Indikasi data tidak sinkron antar sistem."
    )
    k3.metric(
        L["cc_ghost"],
        len(ghost_df),
        help="Karyawan terdaftar di Employee Data namun Job ID-nya tidak ada di MPP. Kemungkinan posisi belum di-plot di MPP atau Job ID belum diinput."
    )
    k4.metric(
        L["cc_vacancy"],
        len(vac_df),
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
                h1c.markdown(f"<div style='font-size:11px;font-weight:700;color:{T['text_variant']};'>Employee ID</div>", unsafe_allow_html=True)
                h2c.markdown(f"<div style='font-size:11px;font-weight:700;color:{T['text_variant']};'>Nama Karyawan</div>", unsafe_allow_html=True)
                h3c.markdown(f"<div style='font-size:11px;font-weight:700;color:{T['text_variant']};'>{'Previous Manager' if change_type_shared=='Reporting Line' else 'Divisi Lama'}</div>", unsafe_allow_html=True)
                h4c.markdown(f"<div style='font-size:11px;font-weight:700;color:{T['text_variant']};'>{'New Manager' if change_type_shared=='Reporting Line' else 'Divisi Baru'}</div>", unsafe_allow_html=True)
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
                                rows_from_file = [(str(r.get("Employee ID","")).strip(), str(r.get("Employee Name","")).strip(),
                                                   str(r.get(old_col,"")).strip(), str(r.get(new_col,"")).strip())
                                                  for _, r in upload_df.iterrows()]
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
                            st.markdown(f"""
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
                                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                                        <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;letter-spacing:0.06em;">Sebelum</div>
                                            <div style="font-size:13px;color:#ef4444;font-weight:500;">❌ {row.get('data_lama','-')}</div></div>
                                        <div><div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;letter-spacing:0.06em;">Sesudah</div>
                                            <div style="font-size:13px;color:#22c55e;font-weight:500;">✅ {row.get('data_baru','-')}</div></div>
                                    </div>
                                </div>
                                <div style="margin-top:12px;padding-top:12px;border-top:1px solid {T['border']};">
                                    <div style="font-size:10px;color:{T['text_variant']};text-transform:uppercase;letter-spacing:0.06em;">Alasan</div>
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


# ══════════════════════════════════════════════════════════════════
# TAB 99 — ADMIN PANEL (role=admin only)
# Diakses via tab_idx=99, hanya muncul di navigasi untuk admin.
# ══════════════════════════════════════════════════════════════════
elif _active == 99:
    # Gate keamanan: double-check role di sini, bukan hanya di nav
    if not _is_admin:
        st.error("🚫 Akses ditolak — fitur ini hanya untuk Admin.")
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
        col_ap_m3.metric("Admin",  len(acl_display_df[acl_display_df["Role"] == "admin"])  if not acl_display_df.empty else 0)
        col_ap_m4.metric("Nonaktif", len(acl_display_df[acl_display_df["Status"] == "🔴 Nonaktif"]) if not acl_display_df.empty else 0)

        st.markdown("---")

        if not acl_display_df.empty:
            col_af1, col_af2, col_af3 = st.columns(3)
            with col_af1:
                f_role_ap = st.selectbox("Filter Role", ["Semua", "admin", "cxo", "leader", "employee"], key="ap_f_role")
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

        VALID_ROLES_AP = ["employee", "leader", "cxo", "admin"]

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
                    help="Pilih '*' untuk semua BU. Hanya relevan untuk role 'leader'."
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
            if f_role_ap_f in ("admin", "cxo") and "*" not in f_bus_ap:
                errors_ap.append("Role admin dan cxo harus memiliki BU scope '*' (full access)")

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
