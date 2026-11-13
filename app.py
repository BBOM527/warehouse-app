from io import BytesIO
from datetime import datetime, timedelta, time
import html
import re
import sqlite3

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# SMART WAREHOUSE
# ติดตั้ง: pip install streamlit pandas plotly pytz openpyxl
# รัน: streamlit run app.py
# ============================================================

st.set_page_config(
    page_title="SMART WAREHOUSE",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = "warehouse.db"
BANGKOK = pytz.timezone("Asia/Bangkok")
CUTOFF_TIME = time(16, 0)

USERNAME = "lNWBOOM"
PASSWORD = "Boomkub555"
DISPLAY_NAME = "Admin"

DEPARTMENTS = [
    "PD", "ธุรการPD", "จัดซื้อ", "วางแผน", "RD", "บัญชี", "ขนส่ง",
    "คลังสินค้าสำเร็จรูป", "CS", "คลังวัตถุดิบ&แพคเกจจิ้ง", "อื่นๆ",
]
PRODUCTION_LINES = [f"L{i}" for i in range(1, 11)]
CANONICAL_COLUMNS = [
    "id", "job_number", "department", "line", "item_name", "quantity",
    "created_at", "start_pick_time", "finish_pick_time", "cancelled_at",
    "cancelled_by", "cancel_reason", "status", "created_by", "updated_at",
]

THEMES = {
    "🟢 Enterprise Green & White": {
        "bg": "#f8fafc", "panel": "#ffffff", "text": "#1e293b",
        "muted": "#64748b", "border": "#e2e8f0", "accent": "#16a34a",
        "accent_hover": "#15803d", "soft": "#f0fdf4", "shadow": "rgba(15,23,42,.06)",
        "input_bg": "#ffffff", "sidebar": "#ffffff", "plot_text": "#334155",
    },
    "☀️ Clean Light": {
        "bg": "#f8fafc", "panel": "#ffffff", "text": "#1e293b",
        "muted": "#64748b", "border": "#e2e8f0", "accent": "#2563eb",
        "accent_hover": "#1d4ed8", "soft": "#eff6ff", "shadow": "rgba(15,23,42,.05)",
        "input_bg": "#ffffff", "sidebar": "#ffffff", "plot_text": "#334155",
    },
    "🌙 Smart Dark": {
        "bg": "#0b1120", "panel": "#151f32", "text": "#e5edf8",
        "muted": "#9aa9c0", "border": "#293750", "accent": "#579bff",
        "accent_hover": "#367fe8", "soft": "#1c2940", "shadow": "rgba(0,0,0,.2)",
        "input_bg": "#1c2940", "sidebar": "#101a2b", "plot_text": "#dbeafe",
    },
}


# ============================================================
# Shared functions (declared before pages)
# ============================================================

def heading(title, subtitle=""):
    st.markdown(
        f'<div class="page-heading"><h1>{html.escape(str(title))}</h1>'
        f'<p>{html.escape(str(subtitle))}</p></div>',
        unsafe_allow_html=True,
    )


def apply_theme(theme_name):
    theme = THEMES.get(theme_name, THEMES["🟢 Enterprise Green & White"])
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');
        :root {{
          --bg:{theme["bg"]}; --panel:{theme["panel"]}; --text:{theme["text"]};
          --muted:{theme["muted"]}; --border:{theme["border"]}; --accent:{theme["accent"]};
          --accent-hover:{theme["accent_hover"]}; --soft:{theme["soft"]};
          --shadow:{theme["shadow"]}; --input-bg:{theme["input_bg"]};
          --sidebar:{theme["sidebar"]}; --plot-text:{theme["plot_text"]};
        }}
        html,body,[class*="css"],button,input,textarea,select {{
          font-family:'Prompt',sans-serif !important;
        }}
        .stApp {{color:var(--text);background:var(--bg);}}
        [data-testid="stHeader"] {{background:var(--bg);}}
        [data-testid="stSidebar"] {{background:var(--sidebar);border-right:1px solid var(--border);}}
        [data-testid="stSidebar"] * {{color:var(--text);}}
        .topbar,.panel,.kpi-card,.entry-card,.timeline-card {{
          border:1px solid var(--border);border-radius:12px;background:var(--panel);
          box-shadow:0 10px 30px var(--shadow);
        }}
        .topbar {{
          display:flex;align-items:center;justify-content:space-between;gap:16px;
          padding:16px 20px;margin:2px 0 20px;
        }}
        .brand {{color:var(--text);font-size:20px;font-weight:700;letter-spacing:.035em;}}
        .brand-subtitle,.page-heading p {{color:var(--muted);font-size:13px;margin:3px 0 0;}}
        .profile-pill,.clock-pill {{white-space:nowrap;border-radius:999px;padding:7px 12px;font-size:13px;font-weight:600;}}
        .profile-pill {{border:1px solid #bbf7d0;background:#f0fdf4;color:#15803d;}}
        .clock-pill {{border:1px solid var(--border);background:var(--soft);color:var(--accent);}}
        .page-heading {{margin:4px 0 18px;}}
        .page-heading h1 {{color:var(--text);font-size:27px;font-weight:700;margin:0;}}
        .panel {{padding:18px;margin:8px 0 16px;}}
        .entry-card {{padding:14px 16px;margin:10px 0;}}
        .kpi-card {{height:100%;min-height:110px;padding:16px 18px;}}
        .kpi-label {{color:var(--muted);font-size:13px;}}
        .kpi-value {{color:var(--text);font-size:25px;font-weight:700;margin-top:6px;}}
        .kpi-hint,.small-muted {{color:var(--muted);font-size:12px;}}
        .timeline-card {{padding:14px;margin:8px 0;}}
        .timeline-time {{color:var(--text);font-size:15px;font-weight:600;}}
        .timeline-label {{color:var(--muted);font-size:12px;}}
        .tag-badge {{display:inline-block;border-radius:999px;padding:4px 10px;font-size:12px;font-weight:600;}}
        .tag-late {{color:#b91c1c;background:#fee2e2;}}
        .tag-normal {{color:#166534;background:#dcfce7;}}
        .footer {{color:var(--muted);font-size:11px;text-align:center;padding:22px 0 10px;}}
        div.stButton>button,div.stDownloadButton>button {{
          border-radius:10px !important;transition:transform .16s ease,box-shadow .16s ease;
          color:var(--text);border-color:var(--border);
        }}
        div.stButton>button:hover,div.stDownloadButton>button:hover {{
          transform:translateY(-1px);box-shadow:0 7px 16px var(--shadow);
        }}
        button[kind="primary"] {{
          color:white !important;border:0 !important;
          background:linear-gradient(110deg,var(--accent),var(--accent-hover)) !important;
        }}
        div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input,div[data-testid="stTimeInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stSelectbox"] div[data-baseweb="select"]>div {{
          border-radius:10px !important;background-color:var(--input-bg);color:var(--text);
        }}
        div[data-testid="stDataFrame"] {{border:1px solid var(--border);border-radius:12px;overflow:hidden;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def now_bangkok():
    return datetime.now(BANGKOK).replace(microsecond=0)


def to_bangkok_datetime(value):
    if value is None or pd.isna(value) or not str(value).strip():
        return None
    try:
        result = pd.to_datetime(value, errors="coerce")
        if pd.isna(result):
            return None
        if result.tzinfo is None:
            result = result.tz_localize(BANGKOK)
        else:
            result = result.tz_convert(BANGKOK)
        return result.to_pydatetime()
    except (TypeError, ValueError, AttributeError):
        return None


def format_timestamp(value):
    parsed = to_bangkok_datetime(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else "—"


def duration_minutes(start, end):
    start_dt, end_dt = to_bangkok_datetime(start), to_bangkok_datetime(end)
    if not start_dt or not end_dt:
        return None
    return (end_dt - start_dt).total_seconds() / 60


def format_duration(minutes):
    if minutes is None or pd.isna(minutes):
        return "—"
    try:
        total = max(0, int(round(float(minutes))))
    except (TypeError, ValueError, OverflowError):
        return "—"
    hours, mins = divmod(total, 60)
    if hours and mins:
        return f"{hours} ชม. {mins} นาที"
    return f"{hours} ชม." if hours else f"{mins} นาที"


def is_late(value):
    parsed = to_bangkok_datetime(value)
    return bool(parsed and parsed.time() > CUTOFF_TIME)


def get_status(row):
    if str(row.get("cancelled_at") or "").strip():
        return "🔴 ยกเลิก"
    if str(row.get("finish_pick_time") or "").strip():
        return "🟢 จัดเสร็จเรียบร้อย"
    if str(row.get("start_pick_time") or "").strip():
        return "🟡 กำลังจัด"
    return "🟠 รอจัด"


def render_topbar():
    components.html(
        """
        <div style="font:600 13px Arial;color:#2563eb;text-align:right">
          <span id="thai-clock">กำลังโหลดเวลาไทย…</span>
        </div>
        <script>
        const el=document.getElementById("thai-clock");
        function tick(){
          const d=new Intl.DateTimeFormat("th-TH",{timeZone:"Asia/Bangkok",
            weekday:"short",year:"numeric",month:"short",day:"numeric"}).format(new Date());
          const t=new Intl.DateTimeFormat("th-TH",{timeZone:"Asia/Bangkok",
            hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false}).format(new Date());
          el.textContent="🇹🇭 "+d+" · "+t;
        }
        tick();setInterval(tick,1000);
        </script>
        """,
        height=35,
    )
    st.markdown(
        """
        <div class="topbar">
          <div><div class="brand">📦 SMART WAREHOUSE</div>
          <div class="brand-subtitle">Warehouse Requisition & Bottleneck Analytics</div></div>
          <div style="display:flex;gap:10px;flex-wrap:wrap">
            <span class="clock-pill">เวลาไทย · Asia/Bangkok</span>
            <span class="profile-pill">● Administrator</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def play_tick():
    """เล่นเสียงติ๊กผ่าน Web Audio API เมื่อกดปุ่มหลัก"""
    components.html(
        """
        <script>
        try{
          const c=new(window.AudioContext||window.webkitAudioContext)();
          const o=c.createOscillator(),g=c.createGain();
          o.type="sine";o.frequency.setValueAtTime(800,c.currentTime);
          o.frequency.exponentialRampToValueAtTime(420,c.currentTime+.045);
          g.gain.setValueAtTime(.10,c.currentTime);
          g.gain.exponentialRampToValueAtTime(.008,c.currentTime+.045);
          o.connect(g);g.connect(c.destination);o.start();o.stop(c.currentTime+.045);
          o.onended=()=>c.close();
        }catch(e){}
        </script>
        """,
        height=0,
    )


# ============================================================
# SQLite and automatic schema update
# ============================================================

def db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn, table):
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]


def init_db():
    conn = db_connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS requisitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_number TEXT NOT NULL UNIQUE,
                department TEXT NOT NULL DEFAULT '',
                line TEXT NOT NULL DEFAULT '',
                item_name TEXT NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT '',
                start_pick_time TEXT NOT NULL DEFAULT '',
                finish_pick_time TEXT NOT NULL DEFAULT '',
                cancelled_at TEXT NOT NULL DEFAULT '',
                cancelled_by TEXT NOT NULL DEFAULT '',
                cancel_reason TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'รอจัด',
                created_by TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.commit()

        existing = table_columns(conn, "requisitions")
        definitions = {
            "job_number": "TEXT NOT NULL DEFAULT ''",
            "department": "TEXT NOT NULL DEFAULT ''",
            "line": "TEXT NOT NULL DEFAULT ''",
            "item_name": "TEXT NOT NULL DEFAULT ''",
            "quantity": "INTEGER NOT NULL DEFAULT 0",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "start_pick_time": "TEXT NOT NULL DEFAULT ''",
            "finish_pick_time": "TEXT NOT NULL DEFAULT ''",
            "cancelled_at": "TEXT NOT NULL DEFAULT ''",
            "cancelled_by": "TEXT NOT NULL DEFAULT ''",
            "cancel_reason": "TEXT NOT NULL DEFAULT ''",
            "status": "TEXT NOT NULL DEFAULT 'รอจัด'",
            "created_by": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
        }
        for col, definition in definitions.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE requisitions ADD COLUMN {col} {definition}")
        conn.commit()

        existing = table_columns(conn, "requisitions")
        aliases = {
            "job_number": ["job_id", "job"],
            "department": ["dept", "department_name"],
            "line": ["production_line", "line_name"],
            "item_name": ["product", "item"],
            "quantity": ["qty", "amount"],
            "created_at": ["received_at", "received_time", "created_time"],
            "start_pick_time": ["started_at", "start_time"],
            "finish_pick_time": ["picked_at", "completed_at", "finish_time"],
            "cancelled_at": ["canceled_at", "cancel_time"],
            "cancelled_by": ["cancel_by", "canceled_by"],
            "cancel_reason": ["cancellation_reason", "canceled_reason"],
        }
        for target, candidates in aliases.items():
            for candidate in candidates:
                if candidate in existing:
                    conn.execute(
                        f"""UPDATE requisitions
                            SET {target}=COALESCE(NULLIF({target},''),{candidate},'')
                            WHERE {candidate} IS NOT NULL"""
                    )

        conn.execute(
            """
            UPDATE requisitions SET status=CASE
              WHEN COALESCE(cancelled_at,'')<>'' THEN 'ยกเลิก'
              WHEN COALESCE(finish_pick_time,'')<>'' THEN 'จัดเสร็จเรียบร้อย'
              WHEN COALESCE(start_pick_time,'')<>'' THEN 'กำลังจัด'
              ELSE 'รอจัด' END
            """
        )
        conn.commit()

        existing = table_columns(conn, "requisitions")
        if existing != CANONICAL_COLUMNS:
            conn.execute("DROP TABLE IF EXISTS requisitions_new")
            conn.execute(
                """
                CREATE TABLE requisitions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_number TEXT NOT NULL UNIQUE,
                    department TEXT NOT NULL DEFAULT '',
                    line TEXT NOT NULL DEFAULT '',
                    item_name TEXT NOT NULL DEFAULT '',
                    quantity INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT '',
                    start_pick_time TEXT NOT NULL DEFAULT '',
                    finish_pick_time TEXT NOT NULL DEFAULT '',
                    cancelled_at TEXT NOT NULL DEFAULT '',
                    cancelled_by TEXT NOT NULL DEFAULT '',
                    cancel_reason TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'รอจัด',
                    created_by TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            selects = [
                col if col in existing else
                ("rowid AS id" if col == "id" else
                 "'รอจัด' AS status" if col == "status" else f"'' AS {col}")
                for col in CANONICAL_COLUMNS
            ]
            conn.execute(
                f"""INSERT OR IGNORE INTO requisitions_new ({", ".join(CANONICAL_COLUMNS)})
                    SELECT {", ".join(selects)} FROM requisitions"""
            )
            conn.execute("DROP TABLE requisitions")
            conn.execute("ALTER TABLE requisitions_new RENAME TO requisitions")
            conn.commit()

        conn.execute("CREATE INDEX IF NOT EXISTS idx_req_created ON requisitions(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_req_department ON requisitions(department)")
        conn.commit()
    finally:
        conn.close()


def load_data():
    conn = db_connect()
    try:
        df = pd.read_sql_query(
            f"SELECT {', '.join(CANONICAL_COLUMNS)} FROM requisitions "
            "ORDER BY created_at DESC,id DESC",
            conn,
        )
    finally:
        conn.close()

    if not df.empty:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
        df["status"] = df.apply(lambda row: get_status(row.to_dict()), axis=1)
        df["late"] = df["created_at"].apply(is_late)
        df["wait_start_minutes"] = df.apply(
            lambda r: duration_minutes(r.get("created_at"), r.get("start_pick_time")), axis=1
        )
        df["picking_minutes"] = df.apply(
            lambda r: duration_minutes(r.get("start_pick_time"), r.get("finish_pick_time")), axis=1
        )
        df["warehouse_total_minutes"] = df.apply(
            lambda r: duration_minutes(r.get("created_at"), r.get("finish_pick_time")), axis=1
        )
    else:
        for col in ["late", "wait_start_minutes", "picking_minutes", "warehouse_total_minutes"]:
            df[col] = pd.Series(dtype="object")
    return df


def insert_requisition(job_number, department, line, item_name, quantity, created_at):
    job_number = str(job_number or "").strip()
    department = str(department or "").strip()
    line = str(line or "").strip() if department == "PD" else ""
    if not job_number:
        return False, "กรุณาระบุรหัส JOB"

    conn = db_connect()
    try:
        conn.execute(
            """
            INSERT INTO requisitions (
                job_number,department,line,item_name,quantity,created_at,
                start_pick_time,finish_pick_time,cancelled_at,cancelled_by,
                cancel_reason,status,created_by,updated_at
            ) VALUES (?,?,?,?,?,?,'','','','','','รอจัด',?,?)
            """,
            (
                job_number, department, line, str(item_name or "").strip(),
                max(0, int(quantity or 0)), created_at, DISPLAY_NAME,
                now_bangkok().isoformat(sep=" ", timespec="seconds"),
            ),
        )
        conn.commit()
        return True, "บันทึกสำเร็จ"
    except sqlite3.IntegrityError:
        return False, f"รหัส JOB {job_number} มีอยู่ในระบบแล้ว"
    except sqlite3.Error as exc:
        return False, f"บันทึกไม่สำเร็จ: {exc}"
    finally:
        conn.close()


def update_requisition_times(job_id, start_pick_time, finish_pick_time):
    conn = db_connect()
    try:
        cursor = conn.execute(
            """
            UPDATE requisitions SET
              start_pick_time=?,
              finish_pick_time=?,
              status=CASE
                WHEN COALESCE(cancelled_at,'')<>'' THEN 'ยกเลิก'
                WHEN COALESCE(?,'')<>'' THEN 'จัดเสร็จเรียบร้อย'
                WHEN COALESCE(?,'')<>'' THEN 'กำลังจัด'
                ELSE 'รอจัด' END,
              updated_at=?
            WHERE id=?
            """,
            (
                start_pick_time or "",
                finish_pick_time or "",
                finish_pick_time or "",
                start_pick_time or "",
                now_bangkok().isoformat(sep=" ", timespec="seconds"),
                int(job_id),
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def cancel_requisition(job_id, cancelled_by, cancel_reason):
    conn = db_connect()
    try:
        now_text = now_bangkok().isoformat(sep=" ", timespec="seconds")
        cursor = conn.execute(
            """UPDATE requisitions SET cancelled_at=?,cancelled_by=?,cancel_reason=?,
               status='ยกเลิก',updated_at=? WHERE id=?""",
            (now_text, cancelled_by.strip(), cancel_reason.strip(), now_text, int(job_id)),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ============================================================
# Filters, tables and exports
# ============================================================

def filter_data(df, page_type="all", search_text="", start_date=None, end_date=None):
    if df is None or df.empty:
        return pd.DataFrame(columns=(df.columns if df is not None else []))

    result = df.copy()
    if start_date is not None or end_date is not None:
        parsed = pd.to_datetime(result["created_at"], errors="coerce")
        try:
            if parsed.dt.tz is not None:
                parsed = parsed.dt.tz_convert(BANGKOK).dt.tz_localize(None)
        except (AttributeError, TypeError):
            pass
        dates = parsed.dt.date
        if start_date is not None:
            result = result.loc[dates.loc[result.index] >= start_date]
        if end_date is not None:
            result = result.loc[dates.loc[result.index] <= end_date]

    query = str(search_text or "").strip().casefold()
    if query:
        cols = [c for c in ["job_number", "department", "line", "item_name", "status"] if c in result]
        if cols:
            mask = result[cols].fillna("").astype(str).apply(
                lambda col: col.str.casefold().str.contains(re.escape(query), regex=True)
            ).any(axis=1)
            result = result.loc[mask]
    if page_type == "active":
        result = result.loc[result["status"] != "🔴 ยกเลิก"]
    return result.copy()


def render_filters(df, prefix):
    today = now_bangkok().date()
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        period = st.selectbox(
            "ช่วงวันที่", ["ทั้งหมด", "วันนี้", "7 วันล่าสุด", "เลือกช่วงวันที่"],
            key=f"{prefix}_period",
        )
    start_date = end_date = None
    if period == "วันนี้":
        start_date = end_date = today
    elif period == "7 วันล่าสุด":
        start_date, end_date = today - timedelta(days=6), today
    elif period == "เลือกช่วงวันที่":
        with c2:
            start_date = st.date_input("ตั้งแต่วันที่", today, key=f"{prefix}_start_date")
        with c3:
            end_date = st.date_input("ถึงวันที่", today, key=f"{prefix}_end_date")
    search = st.text_input(
        "🔎 ค้นหา JOB / แผนก / ไลน์ / สินค้า",
        key=f"{prefix}_search",
        placeholder="พิมพ์คำค้นหา…",
    )
    return filter_data(df, prefix, search, start_date, end_date)


def prepare_display_data(df):
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy()
    result["status"] = result.apply(lambda row: get_status(row.to_dict()), axis=1)
    result["late"] = result["created_at"].apply(is_late)
    result["wait_start_minutes"] = result.apply(
        lambda r: duration_minutes(r.get("created_at"), r.get("start_pick_time")), axis=1
    )
    result["picking_minutes"] = result.apply(
        lambda r: duration_minutes(r.get("start_pick_time"), r.get("finish_pick_time")), axis=1
    )
    result["warehouse_total_minutes"] = result.apply(
        lambda r: duration_minutes(r.get("created_at"), r.get("finish_pick_time")), axis=1
    )
    result["created_display"] = result["created_at"].apply(format_timestamp)
    result["start_display"] = result["start_pick_time"].apply(format_timestamp)
    result["finish_display"] = result["finish_pick_time"].apply(format_timestamp)
    result["wait_display"] = result["wait_start_minutes"].apply(format_duration)
    result["picking_display"] = result["picking_minutes"].apply(format_duration)
    result["total_display"] = result["warehouse_total_minutes"].apply(format_duration)
    result["late_display"] = result["late"].map({True: "🔴 ใบเบิกเย็น", False: "🟢 ปกติ"})
    return result


def render_table(df, key):
    if df is None or df.empty:
        st.info("ยังไม่มีข้อมูลใบเบิกในเงื่อนไขที่เลือก")
        return
    view = prepare_display_data(df)
    table = pd.DataFrame({
        "เลขที่ Job": view["job_number"],
        "วันเวลาที่รับใบเบิก": view["created_display"],
        "แผนก": view["department"],
        "ไลน์ผลิต": view["line"].replace("", "—"),
        "รายการสินค้า": view["item_name"].replace("", "—"),
        "จำนวน": view["quantity"],
        "สถานะ": view["status"],
        "แท็ก": view["late_display"],
        "เวลาเริ่มจัด": view["start_display"],
        "เวลาจัดเสร็จ / วาง Staging": view["finish_display"],
        "เวลารอเริ่มจัด": view["wait_display"],
        "ระยะเวลาจัดสินค้า": view["picking_display"],
        "เวลารวมฝั่งคลัง": view["total_display"],
    })
    st.dataframe(table, use_container_width=True, hide_index=True, key=key)


def make_export_frame(df):
    view = prepare_display_data(df)
    columns = [
        "เลขที่ Job", "วันเวลาที่รับใบเบิก", "แผนกที่เบิก", "ไลน์ผลิต",
        "รายการสินค้า", "จำนวน", "สถานะปัจจุบัน", "เวลาเริ่มจัด",
        "เวลาจัดเสร็จ / วาง Staging", "เวลารอเริ่มจัด (นาที)", "เวลารอเริ่มจัด",
        "ระยะเวลาจัดสินค้า (นาที)", "ระยะเวลาจัดสินค้า",
        "เวลารวมฝั่งคลัง (นาที)", "เวลารวมฝั่งคลัง", "ใบเบิกเย็น",
        "ผู้สั่งยกเลิก", "สาเหตุการยกเลิก",
    ]
    if view.empty:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame({
        "เลขที่ Job": view["job_number"],
        "วันเวลาที่รับใบเบิก": view["created_display"],
        "แผนกที่เบิก": view["department"],
        "ไลน์ผลิต": view["line"],
        "รายการสินค้า": view["item_name"],
        "จำนวน": view["quantity"],
        "สถานะปัจจุบัน": view["status"],
        "เวลาเริ่มจัด": view["start_display"],
        "เวลาจัดเสร็จ / วาง Staging": view["finish_display"],
        "เวลารอเริ่มจัด (นาที)": view["wait_start_minutes"],
        "เวลารอเริ่มจัด": view["wait_display"],
        "ระยะเวลาจัดสินค้า (นาที)": view["picking_minutes"],
        "ระยะเวลาจัดสินค้า": view["picking_display"],
        "เวลารวมฝั่งคลัง (นาที)": view["warehouse_total_minutes"],
        "เวลารวมฝั่งคลัง": view["total_display"],
        "ใบเบิกเย็น": view["late_display"],
        "ผู้สั่งยกเลิก": view["cancelled_by"],
        "สาเหตุการยกเลิก": view["cancel_reason"],
    })


def create_excel_bytes(dataframe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="รายงานคลังสินค้า")
        sheet = writer.sheets["รายงานคลังสินค้า"]
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cells in sheet.columns:
            width = max(
                (len(str(cell.value)) for cell in cells if cell.value is not None),
                default=10,
            )
            sheet.column_dimensions[cells[0].column_letter].width = min(max(width + 2, 12), 50)
    output.seek(0)
    return output.getvalue()


def show_timeline_dialog(record):
    @st.dialog("📄 หลักฐาน / สรุป Timeline", width="large")
    def timeline():
        row = prepare_display_data(pd.DataFrame([record])).iloc[0]
        st.markdown(
            f"""<div class="panel"><b style="font-size:20px">JOB
            {html.escape(str(row['job_number']))}</b><br>
            แผนก: {html.escape(str(row['department'] or '—'))} ·
            ไลน์: {html.escape(str(row['line'] or '—'))} ·
            สินค้า: {html.escape(str(row['item_name'] or '—'))} ·
            จำนวน: {html.escape(str(row['quantity']))}</div>""",
            unsafe_allow_html=True,
        )
        badge = "tag-late" if row["late"] else "tag-normal"
        label = "🔴 ใบเบิกเย็น/ส่งช้า" if row["late"] else "🟢 ใบเบิกปกติ"
        st.markdown(f'<span class="tag-badge {badge}">{label}</span>', unsafe_allow_html=True)

        for icon, name, value in [
            ("📥", "รับเรื่อง", row.get("created_at")),
            ("⏱️", "เริ่มจัดสินค้า", row.get("start_pick_time")),
            ("📦", "จัดเสร็จ / วาง Staging", row.get("finish_pick_time")),
        ]:
            st.markdown(
                f"""<div class="timeline-card">{icon}<div class="timeline-label">
                {html.escape(name)}</div><div class="timeline-time">
                {html.escape(format_timestamp(value))}</div></div>""",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"""<div class="panel"><b>เวลารอเริ่มจัด:</b> {row['wait_display']}<br>
            <b>ระยะเวลาจัดสินค้า:</b> {row['picking_display']}<br>
            <b>เวลารวมฝั่งคลัง:</b> {row['total_display']}</div>""",
            unsafe_allow_html=True,
        )
        if row["status"] == "🔴 ยกเลิก":
            st.error(f"ยกเลิกโดย: {row.get('cancelled_by') or '—'}\n\nสาเหตุ: {row.get('cancel_reason') or '—'}")
        elif row.get("finish_pick_time"):
            st.success("สินค้าจัดเสร็จวาง ณ จุด Staging เรียบร้อยแล้ว สิ้นสุดหน้าที่คลังสินค้า")
        else:
            st.info("งานยังไม่เสร็จสิ้นฝั่งคลัง")
        if st.button("ปิด", key=f"timeline_close_{record['id']}"):
            st.rerun()
    timeline()


# ============================================================
# Login
# ============================================================

def login_screen():
    st.markdown("<div style='height:7vh'></div>", unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1.15, 1])
    with center:
        st.markdown(
            '<div class="panel"><b style="font-size:25px">📦 SMART WAREHOUSE</b>'
            '<div class="small-muted">เข้าสู่ระบบคลังสินค้า</div></div>',
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("เข้าสู่ระบบ", type="primary", use_container_width=True)
        if submitted:
            if username == USERNAME and password == PASSWORD:
                st.session_state["authenticated"] = True
                st.session_state["display_name"] = DISPLAY_NAME
                st.rerun()
            st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")


# ============================================================
# Page: Multi-row input
# ============================================================

def initialize_entry_rows():
    if "entry_rows" not in st.session_state:
        st.session_state["entry_rows"] = ["row_1"]
        st.session_state["entry_next_id"] = 2


def add_entry_row():
    next_id = st.session_state.get("entry_next_id", 1)
    st.session_state["entry_rows"].append(f"row_{next_id}")
    st.session_state["entry_next_id"] = next_id + 1


def remove_entry_row(row_id):
    rows = st.session_state.get("entry_rows", [])
    if len(rows) > 1 and row_id in rows:
        rows.remove(row_id)


def page_input():
    heading(
        "📝 บันทึกใบเบิก",
        "เพิ่ม JOB หลายรายการในหน้าเดียว พร้อมกำหนดแผนก ไลน์ สินค้า และจำนวนแยกกัน",
    )
    st.info("เวลา Cut-off คือ 16:00 น. ระบบติดแท็กใบเบิกเย็นจากเวลารับเรื่องอัตโนมัติ")
    initialize_entry_rows()

    # สัดส่วนคอลัมน์: JOB(2) | แผนก(2) | ไลน์(2) | สินค้า(4) | จำนวน(2) | ลบ(1)
    header_cols = st.columns([2, 2, 2, 4, 2, 1])
    for col, title in zip(
        header_cols,
        ["รหัส JOB", "แผนก", "ไลน์ผลิต", "รายการสินค้า / รหัสสินค้า", "จำนวน", "ลบ"],
    ):
        with col:
            st.markdown(f"**{title}**")

    for index, row_id in enumerate(st.session_state["entry_rows"], start=1):
        st.markdown('<div class="entry-card">', unsafe_allow_html=True)
        cols = st.columns([2, 2, 2, 4, 2, 1])

        with cols[0]:
            st.text_input(
                "รหัส JOB",
                key=f"entry_job_{row_id}",
                placeholder="JOB-6901",
                label_visibility="collapsed",
            )

        with cols[1]:
            dept_key = f"entry_department_{row_id}"
            if dept_key not in st.session_state:
                last_dept = st.session_state.get("last_department", "PD")
                st.session_state[dept_key] = last_dept if last_dept in DEPARTMENTS else "PD"
            dept_choice = st.selectbox(
                "แผนก",
                DEPARTMENTS,
                key=dept_key,
                label_visibility="collapsed",
            )
            if dept_choice == "อื่นๆ":
                st.text_input(
                    "ระบุแผนก",
                    key=f"entry_custom_department_{row_id}",
                    placeholder="ระบุแผนก",
                )

        with cols[2]:
            if dept_choice == "PD":
                line_key = f"entry_line_{row_id}"
                if line_key not in st.session_state:
                    last_line = st.session_state.get("last_line", "L1")
                    st.session_state[line_key] = last_line if last_line in PRODUCTION_LINES else "L1"
                st.selectbox(
                    "ไลน์ผลิต",
                    PRODUCTION_LINES,
                    key=line_key,
                    label_visibility="collapsed",
                )
            else:
                # แผนกอื่นไม่แสดงตัวเลือกและจะบันทึก line เป็นค่าว่าง
                st.markdown(
                    '<div style="padding:9px 4px;color:#94a3b8">—</div>',
                    unsafe_allow_html=True,
                )

        with cols[3]:
            st.text_input(
                "รายการสินค้า / รหัสสินค้า",
                key=f"entry_item_{row_id}",
                placeholder="ชื่อหรือรหัสสินค้า",
                label_visibility="collapsed",
            )

        with cols[4]:
            st.number_input(
                "จำนวนที่เบิก",
                min_value=0,
                step=1,
                value=0,
                key=f"entry_quantity_{row_id}",
                label_visibility="collapsed",
            )

        with cols[5]:
            st.button(
                "ลบ",
                key=f"entry_remove_{row_id}",
                disabled=len(st.session_state["entry_rows"]) <= 1,
                on_click=remove_entry_row,
                args=(row_id,),
                use_container_width=True,
            )

        dept_value = (
            st.session_state.get(f"entry_custom_department_{row_id}", "").strip() or "อื่นๆ"
            if dept_choice == "อื่นๆ"
            else dept_choice
        )
        line_value = (
            st.session_state.get(f"entry_line_{row_id}", "")
            if dept_value == "PD"
            else ""
        )
        st.caption(
            f"รายการ {index} · {dept_value} · "
            f"ไลน์ {line_value if dept_value == 'PD' else 'ไม่ระบุ'}"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    add_col, save_col = st.columns([1, 4])
    with add_col:
        if st.button("➕ เพิ่มรายการเบิก", key="entry_add_row", use_container_width=True):
            play_tick()
            add_entry_row()
            st.rerun()

    with save_col:
        if st.button(
            "📥 บันทึกรับเรื่องทั้งหมด",
            type="primary",
            use_container_width=True,
            key="entry_save_all",
        ):
            play_tick()
            rows_to_save = []

            for row_id in st.session_state["entry_rows"]:
                job = str(st.session_state.get(f"entry_job_{row_id}", "")).strip()
                if not job:
                    continue

                dept_choice = st.session_state.get(f"entry_department_{row_id}", "PD")
                if dept_choice == "อื่นๆ":
                    department = (
                        str(st.session_state.get(f"entry_custom_department_{row_id}", "")).strip()
                        or "อื่นๆ"
                    )
                else:
                    department = dept_choice

                line = (
                    st.session_state.get(f"entry_line_{row_id}", "")
                    if department == "PD"
                    else ""
                )
                rows_to_save.append({
                    "job_number": job,
                    "department": department,
                    "line": line,
                    "item_name": str(st.session_state.get(f"entry_item_{row_id}", "")).strip(),
                    "quantity": int(st.session_state.get(f"entry_quantity_{row_id}", 0)),
                })

            if not rows_to_save:
                st.error("กรุณากรอกรหัส JOB อย่างน้อย 1 รายการ")
                return

            normalized_jobs = [row["job_number"].casefold() for row in rows_to_save]
            duplicate_jobs = sorted({
                job for job in normalized_jobs if normalized_jobs.count(job) > 1
            })
            if duplicate_jobs:
                st.error("พบรหัส JOB ซ้ำในฟอร์ม: " + ", ".join(duplicate_jobs))
                return

            received_at = now_bangkok().isoformat(sep=" ", timespec="seconds")
            saved_count, errors = 0, []

            for row in rows_to_save:
                department = row["department"]
                line = row["line"] if department == "PD" else ""
                if department == "PD" and line not in PRODUCTION_LINES:
                    errors.append(f"{row['job_number']}: กรุณาเลือกไลน์ L1-L10")
                    continue

                ok, message = insert_requisition(
                    row["job_number"],
                    department,
                    line,
                    row["item_name"],
                    row["quantity"],
                    received_at,
                )
                if ok:
                    saved_count += 1
                else:
                    errors.append(message)

            if saved_count:
                st.session_state["last_department"] = rows_to_save[-1]["department"]
                st.session_state["last_line"] = rows_to_save[-1]["line"] or "L1"
                st.success(f"บันทึกรับเรื่องสำเร็จ {saved_count} รายการ")
            for message in errors:
                st.warning(message)
            if saved_count:
                st.rerun()


# ============================================================
# Page: Status management (active jobs only)
# ============================================================

def set_current_timestamp(date_key, time_key, enabled_key):
    current = now_bangkok()
    st.session_state[date_key] = current.date()
    st.session_state[time_key] = current.time().replace(microsecond=0)
    st.session_state[enabled_key] = True


def timestamp_input(label, job_id, field_name, existing_value):
    existing = to_bangkok_datetime(existing_value)
    date_key = f"{field_name}_date_{job_id}"
    time_key = f"{field_name}_time_{job_id}"
    enabled_key = f"{field_name}_enabled_{job_id}"

    if date_key not in st.session_state:
        st.session_state[date_key] = existing.date() if existing else now_bangkok().date()
    if time_key not in st.session_state:
        st.session_state[time_key] = existing.time().replace(microsecond=0) if existing else time(0, 0)
    if enabled_key not in st.session_state:
        st.session_state[enabled_key] = existing is not None

    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.date_input("วันที่", key=date_key)
    with c2:
        st.time_input("เวลา", key=time_key, step=60)
    with c3:
        st.write("")
        st.write("")
        st.button(
            "⏱️ ลงเวลาปัจจุบัน",
            key=f"{field_name}_auto_{job_id}",
            on_click=set_current_timestamp,
            args=(date_key, time_key, enabled_key),
        )

    st.checkbox(f"บันทึกเวลา {label}", key=enabled_key)
    if not st.session_state[enabled_key]:
        return ""
    selected = datetime.combine(st.session_state[date_key], st.session_state[time_key])
    return BANGKOK.localize(selected).isoformat(sep=" ", timespec="seconds")


def page_manage(df):
    heading(
        "⚙️ จัดการสถานะ",
        "แสดงเฉพาะงานรอจัดและกำลังจัด งานเสร็จแล้วตรวจสอบได้จากประวัติ",
    )

    active = df.loc[df["status"].isin(["🟠 รอจัด", "🟡 กำลังจัด"])].copy()
    if active.empty:
        st.success("ไม่มี JOB ค้างจัดในขณะนี้ 🎉")
        return

    choices = {
        f"{row['job_number']} · {row['department']} · {row['status']}": int(row["id"])
        for _, row in active.iterrows()
    }
    selected = st.selectbox(
        "เลือก JOB ที่กำลังดำเนินการ",
        list(choices),
        key="manage_job_select",
    )
    job_id = choices[selected]
    record = active.loc[active["id"] == job_id].iloc[0].to_dict()

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown(
        f"**JOB:** `{record['job_number']}` · **แผนก:** {record['department'] or '—'} · "
        f"**ไลน์:** {record['line'] or '—'} · **สถานะ:** {get_status(record)}"
    )
    st.caption(f"รับเรื่อง: {format_timestamp(record.get('created_at'))}")

    start_dt = to_bangkok_datetime(record.get("start_pick_time"))
    quick_start, quick_finish = st.columns(2)

    with quick_start:
        if st.button(
            "⏱️ เริ่มจัดสินค้า",
            type="primary",
            use_container_width=True,
            key=f"quick_start_{job_id}",
            disabled=bool(start_dt),
        ):
            play_tick()
            now_text = now_bangkok().isoformat(sep=" ", timespec="seconds")
            if update_requisition_times(job_id, now_text, ""):
                st.success("บันทึกเวลาเริ่มจัดแล้ว")
                st.rerun()

    with quick_finish:
        if st.button(
            "📦 จัดเสร็จ/วาง Staging",
            type="primary",
            use_container_width=True,
            key=f"quick_finish_{job_id}",
            disabled=not bool(start_dt),
        ):
            play_tick()
            now_text = now_bangkok().isoformat(sep=" ", timespec="seconds")
            if update_requisition_times(
                job_id,
                record.get("start_pick_time", ""),
                now_text,
            ):
                st.success("จัดเสร็จแล้ว รายการถูกนำออกจากหน้าจัดการ")
                st.rerun()

    st.divider()
    st.markdown("##### ปรับเวลาเอง / แก้ไขเวลาที่บันทึก")
    start_value = timestamp_input(
        "เวลาเริ่มจัดสินค้า",
        job_id,
        "start_pick",
        record.get("start_pick_time"),
    )
    finish_value = timestamp_input(
        "เวลาจัดเสร็จ / วาง Staging",
        job_id,
        "finish_pick",
        record.get("finish_pick_time"),
    )

    if st.button(
        "💾 บันทึกเวลาแก้ไข",
        use_container_width=True,
        key=f"manual_save_{job_id}",
    ):
        play_tick()
        start_parsed = to_bangkok_datetime(start_value)
        finish_parsed = to_bangkok_datetime(finish_value)
        received_parsed = to_bangkok_datetime(record.get("created_at"))

        if start_parsed and received_parsed and start_parsed < received_parsed:
            st.error("เวลาเริ่มจัดต้องไม่อยู่ก่อนเวลารับเรื่อง")
        elif finish_parsed and not start_parsed:
            st.error("กรุณาระบุเวลาเริ่มจัดก่อนบันทึกเวลาจัดเสร็จ")
        elif start_parsed and finish_parsed and finish_parsed < start_parsed:
            st.error("เวลาจัดเสร็จต้องไม่อยู่ก่อนเวลาเริ่มจัด")
        elif update_requisition_times(job_id, start_value, finish_value):
            st.success("บันทึกเวลาเรียบร้อย")
            st.rerun()
        else:
            st.error("ไม่พบ JOB ที่ต้องการอัปเดต")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("#### 🔴 ยกเลิก JOB")
    with st.form(f"cancel_form_{job_id}"):
        cancelled_by = st.text_input("ผู้สั่งยกเลิก (PN/PD) *", key=f"cancel_by_{job_id}")
        cancel_reason = st.text_area("สาเหตุการยกเลิก *", key=f"cancel_reason_{job_id}")
        confirm = st.checkbox("ยืนยันการยกเลิกรายการนี้", key=f"cancel_confirm_{job_id}")
        submit_cancel = st.form_submit_button("🔴 บันทึกยกเลิก JOB")

    if submit_cancel:
        play_tick()
        if not cancelled_by.strip() or not cancel_reason.strip():
            st.error("กรุณาระบุผู้สั่งยกเลิกและสาเหตุให้ครบ")
        elif not confirm:
            st.error("กรุณาติ๊กยืนยันก่อนบันทึกยกเลิก")
        elif cancel_requisition(job_id, cancelled_by, cancel_reason):
            st.success("ยกเลิก JOB และบันทึกข้อมูลเรียบร้อย")
            st.rerun()
        else:
            st.error("ไม่พบ JOB ที่ต้องการยกเลิก")
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Page: Dashboard
# ============================================================

def page_dashboard(df):
    heading("📊 แดชบอร์ด", "ภาพรวมปริมาณงานและเวลาการทำงานฝั่งคลัง")
    filtered = render_filters(df, "dashboard")
    if filtered.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        return

    view = prepare_display_data(filtered)
    pending = int(view["status"].isin(["🟠 รอจัด", "🟡 กำลังจัด"]).sum())
    completed = view.loc[view["status"] == "🟢 จัดเสร็จเรียบร้อย"]
    late_count = int(view["late"].fillna(False).sum())
    processing = pd.to_numeric(completed["picking_minutes"], errors="coerce").dropna().tolist()
    totals = pd.to_numeric(completed["warehouse_total_minutes"], errors="coerce").dropna().tolist()
    avg_processing = sum(processing) / len(processing) if processing else None
    avg_total = sum(totals) / len(totals) if totals else None
    late_pct = late_count / len(view) * 100 if len(view) else 0

    cards = [
        ("ใบเบิกทั้งหมด", f"{len(view):,}", "ตามช่วงวันที่และคำค้น"),
        ("งานค้างฝั่งคลัง", f"{pending:,}", "รอจัด + กำลังจัด"),
        ("เวลาจัดเฉลี่ย", format_duration(avg_processing), "เริ่มจัด → จัดเสร็จ"),
        ("ใบเบิกเย็น", f"{late_count:,} ({late_pct:.1f}%)", "รับหลัง 16:00 น."),
    ]
    cols = st.columns(4)
    for col, (label, value, hint) in zip(cols, cards):
        with col:
            st.markdown(
                f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value}</div><div class="kpi-hint">{hint}</div></div>',
                unsafe_allow_html=True,
            )
    if avg_total is not None:
        st.caption(f"เวลารวมฝั่งคลังเฉลี่ย: {format_duration(avg_total)}")

    left, right = st.columns([1, 1.3])
    with left:
        st.markdown("#### สัดส่วนใบเบิกปกติ / ใบเบิกเย็น")
        stats = pd.DataFrame({
            "ประเภท": ["ใบเบิกปกติ", "ใบเบิกเย็น"],
            "จำนวน": [int((~view["late"].fillna(False)).sum()), late_count],
        })
        if not stats.empty and len(stats) > 0:
            fig = px.pie(
                stats, names="ประเภท", values="จำนวน", hole=.62, color="ประเภท",
                color_discrete_map={"ใบเบิกปกติ": "#16a34a", "ใบเบิกเย็น": "#dc2626"},
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(
                margin=dict(l=8, r=8, t=12, b=8),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend_title_text="",
                font=dict(family="Prompt", color=THEMES[st.session_state.get("theme_name", "🟢 Enterprise Green & White")]["plot_text"]),
            )
            st.plotly_chart(fig, use_container_width=True, key="dashboard_donut")
        else:
            st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")

    with right:
        st.markdown("#### เวลาที่รับใบเบิก")
        arrivals = view.copy()
        arrivals["_created"] = pd.to_datetime(arrivals["created_at"], errors="coerce")
        arrivals = arrivals.dropna(subset=["_created"])
        if not arrivals.empty and len(arrivals) > 0:
            arrivals["ชั่วโมงที่รับ"] = arrivals["_created"].dt.hour.astype(str).str.zfill(2) + ":00"
            hourly = arrivals.groupby("ชั่วโมงที่รับ", as_index=False).size()
            hourly = hourly.rename(columns={"size": "จำนวนใบเบิก"}).sort_values("ชั่วโมงที่รับ")
            if not hourly.empty and len(hourly) > 0:
                fig = px.bar(hourly, x="ชั่วโมงที่รับ", y="จำนวนใบเบิก",
                             color_discrete_sequence=[THEMES[st.session_state.get("theme_name", "🟢 Enterprise Green & White")]["accent"]])
                fig.update_layout(
                    margin=dict(l=8, r=8, t=12, b=8),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Prompt", color=THEMES[st.session_state.get("theme_name", "🟢 Enterprise Green & White")]["plot_text"]),
                    xaxis_title="", yaxis_title="จำนวนใบเบิก",
                )
                st.plotly_chart(fig, use_container_width=True, key="dashboard_hourly")
            else:
                st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")
        else:
            st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")

    st.markdown("#### รายการใบเบิกล่าสุด")
    render_table(view.head(100), "dashboard_table")


# ============================================================
# Page: History and export
# ============================================================

def page_history(df):
    heading("📄 ประวัติและส่งออกข้อมูล", "ตรวจสอบทุกสถานะ ดู Timeline และส่งออกรายงาน")
    filtered = render_filters(df, "history")
    if filtered.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        return

    render_table(filtered, "history_table")

    st.markdown("#### 📄 พิมพ์หลักฐาน / สรุป Timeline")
    eligible = filtered.loc[
        filtered.apply(
            lambda row: bool(row.get("late")) or row.get("status") == "🔴 ยกเลิก",
            axis=1,
        )
    ]
    if eligible.empty:
        st.caption("ไม่มีใบเบิกเย็นหรือ JOB ที่ยกเลิกในผลการค้นหานี้")
    else:
        records = {
            f"{row['job_number']} · {row['department']} · {row['status']}": row.to_dict()
            for _, row in eligible.iterrows()
        }
        selected = st.selectbox(
            "เลือกรายการสำหรับดูหลักฐาน",
            list(records),
            key="history_timeline_select",
        )
        if st.button("📄 พิมพ์หลักฐาน / สรุป Timeline", key="history_open_timeline"):
            show_timeline_dialog(records[selected])

    st.markdown("#### 📥 ส่งออกรายงาน")
    export_df = make_export_frame(filtered)
    excel_bytes = create_excel_bytes(export_df)
    csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📥 ดาวน์โหลด Excel (.xlsx)",
            data=excel_bytes,
            file_name="รายงานสรุปการเบิกสินค้า_คลังสินค้า.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="history_excel",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "📥 ดาวน์โหลด CSV",
            data=csv_bytes,
            file_name="รายงานสรุปการเบิกสินค้า_คลังสินค้า.csv",
            mime="text/csv",
            key="history_csv",
            use_container_width=True,
        )


# ============================================================
# Main
# ============================================================

def main():
    init_db()

    if not st.session_state.get("authenticated", False):
        apply_theme("🟢 Enterprise Green & White")
        login_screen()
        st.markdown(
            '<div class="footer">SMART WAREHOUSE © 2026 | BUSINESS MANAGEMENT SYSTEM</div>',
            unsafe_allow_html=True,
        )
        return

    with st.sidebar:
        st.markdown("### 📦 SMART WAREHOUSE")
        st.markdown(f"ผู้ใช้งาน: **{DISPLAY_NAME}**")

        theme_names = list(THEMES.keys())
        if "theme_name" not in st.session_state:
            st.session_state["theme_name"] = theme_names[0]
        st.selectbox(
            "🎨 เลือกธีมสี",
            theme_names,
            key="theme_name",
        )

        st.divider()
        page = st.radio(
            "เมนูหลัก",
            [
                "📝 บันทึกใบเบิก",
                "⚙️ จัดการสถานะ",
                "📊 แดชบอร์ด",
                "📄 ประวัติและส่งออกข้อมูล",
            ],
            key="main_navigation",
        )
        st.divider()
        if st.button("ออกจากระบบ", use_container_width=True, key="logout_button"):
            st.session_state["authenticated"] = False
            st.session_state.pop("display_name", None)
            st.rerun()

    apply_theme(st.session_state.get("theme_name"))
    render_topbar()
    df = load_data()

    if page == "📝 บันทึกใบเบิก":
        page_input()
    elif page == "⚙️ จัดการสถานะ":
        page_manage(df)
    elif page == "📊 แดชบอร์ด":
        page_dashboard(df)
    elif page == "📄 ประวัติและส่งออกข้อมูล":
        page_history(df)

    st.markdown(
        '<div class="footer">SMART WAREHOUSE © 2026 | BUSINESS MANAGEMENT SYSTEM</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
