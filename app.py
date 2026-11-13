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
    "PD",
    "ธุรการPD",
    "จัดซื้อ",
    "วางแผน",
    "RD",
    "บัญชี",
    "ขนส่ง",
    "คลังสินค้าสำเร็จรูป",
    "CS",
    "คลังวัตถุดิบ&แพคเกจจิ้ง",
    "อื่นๆ",
]
PRODUCTION_LINES = [f"L{i}" for i in range(1, 11)]

# คอลัมน์ที่แอปใช้งาน ไม่มีเวลา PD มารับหรือเวลารอรับ PD
CANONICAL_COLUMNS = [
    "id",
    "job_number",
    "department",
    "line",
    "item_name",
    "quantity",
    "created_at",
    "start_pick_time",
    "finish_pick_time",
    "cancelled_at",
    "cancelled_by",
    "cancel_reason",
    "status",
    "created_by",
    "updated_at",
]


# ============================================================
# Clean Light Theme
# ============================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');

    :root {
        --bg: #f8fafc;
        --panel: #ffffff;
        --border: #e2e8f0;
        --text: #1e293b;
        --muted: #64748b;
        --blue: #2563eb;
        --green: #16a34a;
        --orange: #d97706;
        --red: #dc2626;
        --shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
    }

    html, body, [class*="css"], button, input, textarea, select {
        font-family: 'Prompt', sans-serif !important;
    }

    .stApp {
        color: var(--text);
        background:
            radial-gradient(circle at 10% 0%, rgba(37,99,235,.045), transparent 28%),
            linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    }

    [data-testid="stHeader"] { background: rgba(248,250,252,.82); }
    [data-testid="stSidebar"] {
        background: #fff;
        border-right: 1px solid var(--border);
    }

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 16px 20px;
        margin: 2px 0 20px;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: rgba(255,255,255,.94);
        box-shadow: var(--shadow);
    }
    .brand {
        color: #0f172a;
        font-size: 20px;
        font-weight: 700;
        letter-spacing: .035em;
    }
    .brand-subtitle { color: var(--muted); font-size: 12px; margin-top: 2px; }
    .profile-pill, .clock-pill {
        white-space: nowrap;
        border-radius: 999px;
        padding: 7px 12px;
        font-size: 13px;
        font-weight: 600;
    }
    .profile-pill {
        border: 1px solid #bbf7d0;
        background: #f0fdf4;
        color: #15803d;
    }
    .clock-pill {
        border: 1px solid #dbeafe;
        background: #eff6ff;
        color: #1d4ed8;
    }

    .page-heading { margin: 4px 0 18px; }
    .page-heading h1 {
        color: #0f172a;
        font-size: 27px;
        font-weight: 700;
        margin: 0;
    }
    .page-heading p { color: var(--muted); font-size: 14px; margin: 3px 0 0; }

    .kpi-card {
        height: 100%;
        min-height: 112px;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: var(--panel);
        box-shadow: var(--shadow);
        padding: 17px 18px;
    }
    .kpi-label { color: var(--muted); font-size: 13px; }
    .kpi-value { color: #0f172a; font-size: 25px; font-weight: 700; margin-top: 6px; }
    .kpi-hint { color: #94a3b8; font-size: 12px; margin-top: 1px; }

    .tag-badge {
        display: inline-block;
        white-space: nowrap;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 600;
    }
    .tag-late { color: #b91c1c; background: #fee2e2; }
    .tag-normal { color: #166534; background: #dcfce7; }

    .panel, .timeline-card {
        border: 1px solid var(--border);
        border-radius: 12px;
        background: #fff;
        box-shadow: var(--shadow);
        padding: 18px;
        margin: 8px 0 16px;
    }
    .timeline-card { padding: 14px; margin: 8px 0; }
    .timeline-time { color: #0f172a; font-size: 15px; font-weight: 600; }
    .timeline-label { color: var(--muted); font-size: 12px; }
    .footer {
        color: #94a3b8;
        font-size: 11px;
        text-align: center;
        padding: 22px 0 10px;
        letter-spacing: .04em;
    }
    .small-muted { color: var(--muted); font-size: 12px; }

    div.stButton > button, div.stDownloadButton > button {
        border-radius: 10px !important;
        border: 1px solid #cbd5e1 !important;
        transition: transform .16s ease, box-shadow .16s ease;
        font-weight: 500 !important;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 7px 16px rgba(15,23,42,.10);
    }
    div.stButton > button:active, div.stDownloadButton > button:active {
        transform: scale(.985);
    }
    button[kind="primary"] {
        color: white !important;
        border: 0 !important;
        background: linear-gradient(110deg, #16a34a, #2563eb) !important;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stDateInput"] input,
    div[data-testid="stTimeInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        border-radius: 10px !important;
    }

    div[data-testid="stDataFrame"], div[data-testid="stTable"] {
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
        background: #fff;
        box-shadow: var(--shadow);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Shared helper functions
# ============================================================

def heading(title, subtitle=""):
    """แสดงหัวข้อและคำอธิบายของแต่ละหน้า"""
    st.markdown(
        f"""
        <div class="page-heading">
            <h1>{html.escape(str(title))}</h1>
            <p>{html.escape(str(subtitle))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def now_bangkok():
    return datetime.now(BANGKOK).replace(microsecond=0)


def to_bangkok_datetime(value):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return None
        if dt.tzinfo is None:
            dt = dt.tz_localize(BANGKOK)
        else:
            dt = dt.tz_convert(BANGKOK)
        return dt.to_pydatetime()
    except (TypeError, ValueError, AttributeError):
        return None


def format_timestamp(value):
    dt = to_bangkok_datetime(value)
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "—"


def format_duration(minutes):
    if minutes is None or pd.isna(minutes):
        return "—"
    try:
        total = max(0, int(round(float(minutes))))
    except (TypeError, ValueError, OverflowError):
        return "—"

    hours, mins = divmod(total, 60)
    if hours:
        return f"{hours} ชม. {mins} นาที" if mins else f"{hours} ชม."
    return f"{mins} นาที"


def duration_minutes(start, end):
    start_dt = to_bangkok_datetime(start)
    end_dt = to_bangkok_datetime(end)
    if not start_dt or not end_dt:
        return None
    # แสดงผลตามเวลาจริง แม้ timestamp จะอยู่คนละวัน
    return (end_dt - start_dt).total_seconds() / 60.0


def is_late_requisition(value):
    dt = to_bangkok_datetime(value)
    return bool(dt and dt.time() > CUTOFF_TIME)


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
        <div style="font-family:Arial,sans-serif;color:#2563eb;font-size:13px;
                    font-weight:600;text-align:right;">
            <span id="thai-clock">กำลังโหลดเวลาไทย…</span>
        </div>
        <script>
        const clockEl = document.getElementById("thai-clock");
        function updateThaiClock() {
            const now = new Date();
            const dateText = new Intl.DateTimeFormat("th-TH", {
                timeZone: "Asia/Bangkok",
                weekday: "short", year: "numeric", month: "short", day: "numeric"
            }).format(now);
            const timeText = new Intl.DateTimeFormat("th-TH", {
                timeZone: "Asia/Bangkok",
                hour: "2-digit", minute: "2-digit", second: "2-digit",
                hour12: false
            }).format(now);
            clockEl.textContent = "🇹🇭 " + dateText + " · " + timeText;
        }
        updateThaiClock();
        setInterval(updateThaiClock, 1000);
        </script>
        """,
        height=38,
    )
    st.markdown(
        """
        <div class="topbar">
            <div>
                <div class="brand">📦 SMART WAREHOUSE</div>
                <div class="brand-subtitle">Warehouse Requisition &amp; Bottleneck Analytics</div>
            </div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end;">
                <span class="clock-pill">เวลาไทย · Asia/Bangkok</span>
                <span class="profile-pill">● Administrator</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def play_tick():
    components.html(
        """
        <script>
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(800, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(400, ctx.currentTime + 0.04);
            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.04);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.04);
            osc.onended = () => ctx.close();
        } catch (e) {}
        </script>
        """,
        height=0,
    )


# ============================================================
# SQLite database and automatic schema migration
# ============================================================

def db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def table_columns(conn, table_name):
    return [
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    ]


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

        for column, definition in definitions.items():
            if column not in existing:
                conn.execute(
                    f"ALTER TABLE requisitions ADD COLUMN {column} {definition}"
                )
        conn.commit()

        # ย้ายข้อมูลจากชื่อคอลัมน์เดิมที่อาจมีในฐานข้อมูล
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
                        f"""
                        UPDATE requisitions
                        SET {target} = COALESCE(NULLIF({target}, ''), {candidate}, '')
                        WHERE {candidate} IS NOT NULL
                        """
                    )

        conn.execute(
            """
            UPDATE requisitions
            SET status = CASE
                WHEN COALESCE(cancelled_at, '') <> '' THEN 'ยกเลิก'
                WHEN COALESCE(finish_pick_time, '') <> '' THEN 'จัดเสร็จเรียบร้อย'
                WHEN COALESCE(start_pick_time, '') <> '' THEN 'กำลังจัด'
                ELSE 'รอจัด'
            END
            """
        )
        conn.commit()

        # สร้างตารางมาตรฐานเพื่อเก็บเฉพาะคอลัมน์ที่แอปใช้งาน
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

            select_exprs = []
            for column in CANONICAL_COLUMNS:
                if column in existing:
                    select_exprs.append(column)
                elif column == "id":
                    select_exprs.append("rowid AS id")
                elif column == "status":
                    select_exprs.append("'รอจัด' AS status")
                else:
                    select_exprs.append(f"'' AS {column}")

            conn.execute(
                f"""
                INSERT OR IGNORE INTO requisitions_new ({", ".join(CANONICAL_COLUMNS)})
                SELECT {", ".join(select_exprs)}
                FROM requisitions
                """
            )
            conn.execute("DROP TABLE requisitions")
            conn.execute("ALTER TABLE requisitions_new RENAME TO requisitions")
            conn.commit()

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_requisitions_created_at "
            "ON requisitions(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_requisitions_department "
            "ON requisitions(department)"
        )
        conn.commit()
    finally:
        conn.close()


def load_data():
    conn = db_connect()
    try:
        df = pd.read_sql_query(
            f"SELECT {', '.join(CANONICAL_COLUMNS)} "
            "FROM requisitions ORDER BY created_at DESC, id DESC",
            conn,
        )
    finally:
        conn.close()

    if not df.empty:
        df["quantity"] = (
            pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
        )
        df["status"] = df.apply(lambda row: get_status(row.to_dict()), axis=1)
        df["late"] = df["created_at"].apply(is_late_requisition)
        df["wait_start_minutes"] = df.apply(
            lambda row: duration_minutes(
                row.get("created_at"), row.get("start_pick_time")
            ),
            axis=1,
        )
        df["picking_minutes"] = df.apply(
            lambda row: duration_minutes(
                row.get("start_pick_time"), row.get("finish_pick_time")
            ),
            axis=1,
        )
        df["warehouse_total_minutes"] = df.apply(
            lambda row: duration_minutes(
                row.get("created_at"), row.get("finish_pick_time")
            ),
            axis=1,
        )
    else:
        for column in [
            "late",
            "wait_start_minutes",
            "picking_minutes",
            "warehouse_total_minutes",
        ]:
            df[column] = pd.Series(dtype="object")

    return df


def insert_requisition(
    job_number,
    department,
    line,
    item_name,
    quantity,
    created_at,
    created_by,
):
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
                job_number, department, line, item_name, quantity,
                created_at, start_pick_time, finish_pick_time,
                cancelled_at, cancelled_by, cancel_reason, status,
                created_by, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, '', '', '', '', '', 'รอจัด', ?, ?)
            """,
            (
                job_number,
                department,
                line,
                str(item_name or "").strip(),
                max(0, int(quantity or 0)),
                created_at,
                created_by,
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
            UPDATE requisitions
            SET start_pick_time = ?,
                finish_pick_time = ?,
                status = CASE
                    WHEN COALESCE(cancelled_at, '') <> '' THEN 'ยกเลิก'
                    WHEN COALESCE(?, '') <> '' THEN 'จัดเสร็จเรียบร้อย'
                    WHEN COALESCE(?, '') <> '' THEN 'กำลังจัด'
                    ELSE 'รอจัด'
                END,
                updated_at = ?
            WHERE id = ?
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
        # ใช้ cursor.rowcount หลัง commit เพื่อเช็กว่ามีแถวถูกแก้ไขหรือไม่
        return cursor.rowcount > 0
    finally:
        conn.close()


def cancel_requisition(job_id, cancelled_by, cancel_reason):
    conn = db_connect()
    try:
        now_text = now_bangkok().isoformat(sep=" ", timespec="seconds")
        cursor = conn.execute(
            """
            UPDATE requisitions
            SET cancelled_at = ?,
                cancelled_by = ?,
                cancel_reason = ?,
                status = 'ยกเลิก',
                updated_at = ?
            WHERE id = ?
            """,
            (
                now_text,
                cancelled_by.strip(),
                cancel_reason.strip(),
                now_text,
                int(job_id),
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ============================================================
# Search and date filters
# ============================================================

def filter_data(df, page_type="all", search_text="", start_date=None, end_date=None):
    """กรองข้อมูลด้วยช่วงวันที่และคำค้นหา ใช้ใน Dashboard และประวัติ."""
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
        row_dates = parsed.dt.date

        if start_date is not None:
            result = result.loc[row_dates.loc[result.index] >= start_date]
        if end_date is not None:
            result = result.loc[row_dates.loc[result.index] <= end_date]

    query = str(search_text or "").strip().casefold()
    if query:
        search_columns = [
            column
            for column in ["job_number", "department", "line", "item_name", "status"]
            if column in result.columns
        ]
        if search_columns:
            mask = result[search_columns].fillna("").astype(str).apply(
                lambda col: col.str.casefold().str.contains(re.escape(query), regex=True)
            ).any(axis=1)
            result = result.loc[mask]

    if page_type == "active" and "status" in result.columns:
        result = result.loc[result["status"] != "🔴 ยกเลิก"]

    return result.copy()


def render_filters(df, key_prefix):
    today = now_bangkok().date()
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        preset = st.selectbox(
            "ช่วงวันที่",
            ["ทั้งหมด", "วันนี้", "7 วันล่าสุด", "เลือกช่วงวันที่"],
            key=f"{key_prefix}_date_preset",
        )

    start_date = None
    end_date = None

    if preset == "วันนี้":
        start_date = end_date = today
    elif preset == "7 วันล่าสุด":
        start_date = today - timedelta(days=6)
        end_date = today
    elif preset == "เลือกช่วงวันที่":
        with col2:
            start_date = st.date_input(
                "ตั้งแต่วันที่",
                value=today,
                key=f"{key_prefix}_start_date",
            )
        with col3:
            end_date = st.date_input(
                "ถึงวันที่",
                value=today,
                key=f"{key_prefix}_end_date",
            )

    search = st.text_input(
        "🔎 ค้นหา JOB / แผนก / ไลน์ / สินค้า",
        key=f"{key_prefix}_search",
        placeholder="พิมพ์คำค้นหา…",
    )
    return filter_data(df, key_prefix, search, start_date, end_date)


def prepare_display_data(df):
    if df is None or df.empty:
        return pd.DataFrame()

    result = df.copy()
    result["status"] = result.apply(lambda row: get_status(row.to_dict()), axis=1)
    result["late"] = result["created_at"].apply(is_late_requisition)
    result["wait_start_minutes"] = result.apply(
        lambda row: duration_minutes(
            row.get("created_at"), row.get("start_pick_time")
        ),
        axis=1,
    )
    result["picking_minutes"] = result.apply(
        lambda row: duration_minutes(
            row.get("start_pick_time"), row.get("finish_pick_time")
        ),
        axis=1,
    )
    result["warehouse_total_minutes"] = result.apply(
        lambda row: duration_minutes(
            row.get("created_at"), row.get("finish_pick_time")
        ),
        axis=1,
    )

    result["created_display"] = result["created_at"].apply(format_timestamp)
    result["start_display"] = result["start_pick_time"].apply(format_timestamp)
    result["finish_display"] = result["finish_pick_time"].apply(format_timestamp)
    result["wait_start_display"] = result["wait_start_minutes"].apply(format_duration)
    result["picking_display"] = result["picking_minutes"].apply(format_duration)
    result["warehouse_total_display"] = result[
        "warehouse_total_minutes"
    ].apply(format_duration)
    result["late_display"] = result["late"].map(
        {True: "🔴 ใบเบิกเย็น", False: "🟢 ปกติ"}
    )
    return result


def render_table(df, key):
    if df is None or df.empty:
        st.info("ยังไม่มีข้อมูลใบเบิกในเงื่อนไขที่เลือก")
        return

    view = prepare_display_data(df)
    display = pd.DataFrame(
        {
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
            "เวลารอเริ่มจัด": view["wait_start_display"],
            "ระยะเวลาจัดสินค้า": view["picking_display"],
            "เวลารวมฝั่งคลัง": view["warehouse_total_display"],
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True, key=key)


# ============================================================
# Excel / CSV and timeline
# ============================================================

def make_export_frame(df):
    view = prepare_display_data(df)
    columns = [
        "เลขที่ Job",
        "วันเวลาที่รับใบเบิก",
        "แผนกที่เบิก",
        "ไลน์ผลิต",
        "รายการสินค้า",
        "จำนวน",
        "สถานะปัจจุบัน",
        "เวลาเริ่มจัด",
        "เวลาจัดเสร็จ / วาง Staging",
        "เวลารอเริ่มจัด (นาที)",
        "เวลารอเริ่มจัด",
        "ระยะเวลาจัดสินค้า (นาที)",
        "ระยะเวลาจัดสินค้า",
        "เวลารวมฝั่งคลัง (นาที)",
        "เวลารวมฝั่งคลัง",
        "ใบเบิกเย็น",
        "ผู้สั่งยกเลิก",
        "สาเหตุการยกเลิก",
    ]

    if view.empty:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(
        {
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
            "เวลารอเริ่มจัด": view["wait_start_display"],
            "ระยะเวลาจัดสินค้า (นาที)": view["picking_minutes"],
            "ระยะเวลาจัดสินค้า": view["picking_display"],
            "เวลารวมฝั่งคลัง (นาที)": view["warehouse_total_minutes"],
            "เวลารวมฝั่งคลัง": view["warehouse_total_display"],
            "ใบเบิกเย็น": view["late_display"],
            "ผู้สั่งยกเลิก": view["cancelled_by"],
            "สาเหตุการยกเลิก": view["cancel_reason"],
        }
    )


def create_excel_bytes(export_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="รายงานคลังสินค้า")
        worksheet = writer.sheets["รายงานคลังสินค้า"]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for cells in worksheet.columns:
            max_length = max(
                (len(str(cell.value)) for cell in cells if cell.value is not None),
                default=10,
            )
            worksheet.column_dimensions[cells[0].column_letter].width = min(
                max(max_length + 2, 12), 50
            )

    output.seek(0)
    return output.getvalue()


def show_timeline_dialog(record):
    @st.dialog("📄 หลักฐาน / สรุป Timeline", width="large")
    def timeline():
        row = prepare_display_data(pd.DataFrame([record])).iloc[0]

        st.markdown(
            f"""
            <div class="panel">
                <div style="font-size:20px;font-weight:700;color:#0f172a;">
                    JOB {html.escape(str(row.get("job_number", "")))}
                </div>
                <div style="color:#64748b;margin-top:4px;">
                    แผนก: {html.escape(str(row.get("department") or "—"))}
                    · ไลน์: {html.escape(str(row.get("line") or "—"))}
                    · สินค้า: {html.escape(str(row.get("item_name") or "—"))}
                    · จำนวน: {html.escape(str(row.get("quantity") or 0))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        badge_class = "tag-late" if row["late"] else "tag-normal"
        badge_text = "🔴 ใบเบิกเย็น/ส่งช้า" if row["late"] else "🟢 ใบเบิกปกติ"
        st.markdown(
            f'<span class="tag-badge {badge_class}">{badge_text}</span>',
            unsafe_allow_html=True,
        )

        for icon, label, timestamp in [
            ("📥", "รับเรื่อง", row.get("created_at")),
            ("⏱️", "เริ่มจัดสินค้า", row.get("start_pick_time")),
            ("📦", "จัดเสร็จ / วาง Staging", row.get("finish_pick_time")),
        ]:
            st.markdown(
                f"""
                <div class="timeline-card">
                    <div style="font-size:20px">{icon}</div>
                    <div class="timeline-label">{html.escape(label)}</div>
                    <div class="timeline-time">{html.escape(format_timestamp(timestamp))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div class="panel">
                <b>เวลารอเริ่มจัด:</b> {html.escape(str(row["wait_start_display"]))}<br>
                <b>ระยะเวลาจัดสินค้า:</b> {html.escape(str(row["picking_display"]))}<br>
                <b>เวลารวมฝั่งคลัง:</b> {html.escape(str(row["warehouse_total_display"]))}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if row["status"] == "🔴 ยกเลิก":
            st.error(
                f"ยกเลิกโดย: {row.get('cancelled_by') or '—'}\n\n"
                f"สาเหตุ: {row.get('cancel_reason') or '—'}"
            )
        elif row.get("finish_pick_time"):
            st.success(
                "สินค้าจัดเสร็จวาง ณ จุด Staging เรียบร้อยแล้ว "
                "สิ้นสุดหน้าที่คลังสินค้า"
            )
        else:
            st.info("งานยังไม่เสร็จสิ้นฝั่งคลัง")

        if st.button("ปิด", key=f"timeline_close_{record.get('id')}"):
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
            """
            <div class="panel" style="padding:28px;">
                <div style="font-size:27px;font-weight:700;color:#0f172a;">
                    📦 SMART WAREHOUSE
                </div>
                <div style="color:#64748b;margin:4px 0 18px;">
                    เข้าสู่ระบบคลังสินค้า
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )
            submitted = st.form_submit_button(
                "เข้าสู่ระบบ",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if username == USERNAME and password == PASSWORD:
                st.session_state["authenticated"] = True
                st.session_state["display_name"] = DISPLAY_NAME
                st.rerun()
            st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")


# ============================================================
# Page 1: Requisition input
# ============================================================

def page_input():
    heading(
        "📝 บันทึกใบเบิก",
        "กรอกข้อมูล JOB หนึ่งรายการต่อครั้ง โดยระบุแผนก สินค้า และจำนวนให้ครบถ้วน",
    )
    st.info("เวลา Cut-off คือ 16:00 น. ระบบติดแท็กใบเบิกเย็นจากเวลารับเรื่องอัตโนมัติ")

    if "last_department" not in st.session_state:
        st.session_state["last_department"] = "PD"
    if "last_line" not in st.session_state:
        st.session_state["last_line"] = "L1"

    st.markdown('<div class="panel">', unsafe_allow_html=True)

    department_choice = st.selectbox(
        "แผนกที่เบิก",
        DEPARTMENTS,
        index=(
            DEPARTMENTS.index(st.session_state["last_department"])
            if st.session_state["last_department"] in DEPARTMENTS
            else 0
        ),
        key="input_department",
    )

    if department_choice == "อื่นๆ":
        department = st.text_input(
            "ระบุชื่อแผนก",
            key="input_custom_department",
            placeholder="พิมพ์ชื่อแผนก",
        ).strip()
        department = department or "อื่นๆ"
    else:
        department = department_choice

    line = ""
    if department == "PD":
        line = st.selectbox(
            "ไลน์ผลิต",
            PRODUCTION_LINES,
            index=(
                PRODUCTION_LINES.index(st.session_state["last_line"])
                if st.session_state["last_line"] in PRODUCTION_LINES
                else 0
            ),
            key="input_line",
        )

    col1, col2 = st.columns(2)
    with col1:
        job_number = st.text_input(
            "รหัส JOB *",
            key="input_job_number",
            placeholder="เช่น JOB-6901",
        )
        item_name = st.text_input(
            "รายการสินค้า",
            key="input_item_name",
            placeholder="ระบุรายการสินค้า",
        )
    with col2:
        quantity = st.number_input(
            "จำนวน",
            min_value=0,
            step=1,
            value=0,
            key="input_quantity",
        )
        st.caption(
            f"แผนก: {department} · ไลน์ผลิต: {line if department == 'PD' else '—'}"
        )

    if st.button(
        "📥 บันทึกรับเรื่อง",
        type="primary",
        use_container_width=True,
        key="input_save_requisition",
    ):
        if not job_number.strip():
            st.error("กรุณาระบุรหัส JOB")
        else:
            final_line = line if department == "PD" else ""
            created_at = now_bangkok().isoformat(sep=" ", timespec="seconds")
            ok, message = insert_requisition(
                job_number=job_number,
                department=department,
                line=final_line,
                item_name=item_name,
                quantity=int(quantity),
                created_at=created_at,
                created_by=DISPLAY_NAME,
            )

            if ok:
                st.session_state["last_department"] = (
                    department if department in DEPARTMENTS else "อื่นๆ"
                )
                if department == "PD":
                    st.session_state["last_line"] = final_line
                st.success(f"รับเรื่อง JOB {job_number.strip()} เรียบร้อย")
                play_tick()
                st.rerun()
            else:
                st.error(message)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Page 2: Status management
# ============================================================

def set_current_timestamp(date_key, time_key, enabled_key):
    """Callback ตั้งวันและเวลา ก่อนที่ Streamlit จะสร้าง widgets ในรอบใหม่."""
    current = now_bangkok()
    st.session_state[date_key] = current.date()
    st.session_state[time_key] = current.time().replace(microsecond=0)
    st.session_state[enabled_key] = True


def timestamp_input(label, job_id, field_name, existing_value):
    existing_dt = to_bangkok_datetime(existing_value)

    date_key = f"{field_name}_date_{job_id}"
    time_key = f"{field_name}_time_{job_id}"
    enabled_key = f"{field_name}_enabled_{job_id}"
    auto_key = f"{field_name}_auto_{job_id}"

    # State ถูกตั้งก่อนสร้าง widgets เท่านั้น
    if date_key not in st.session_state:
        st.session_state[date_key] = (
            existing_dt.date() if existing_dt else now_bangkok().date()
        )
    if time_key not in st.session_state:
        st.session_state[time_key] = (
            existing_dt.time().replace(microsecond=0)
            if existing_dt
            else time(0, 0)
        )
    if enabled_key not in st.session_state:
        st.session_state[enabled_key] = existing_dt is not None

    st.markdown(f"**{label}**")
    col_date, col_time, col_auto = st.columns([1, 1, 1])

    with col_date:
        st.date_input("วันที่", key=date_key)
    with col_time:
        st.time_input("เวลา", key=time_key, step=60)
    with col_auto:
        st.write("")
        st.write("")
        st.button(
            "⏱️ ลงเวลาปัจจุบัน",
            key=auto_key,
            on_click=set_current_timestamp,
            args=(date_key, time_key, enabled_key),
        )

    st.checkbox(
        f"บันทึกเวลา {label}",
        key=enabled_key,
    )

    if not st.session_state[enabled_key]:
        return ""

    chosen_datetime = datetime.combine(
        st.session_state[date_key],
        st.session_state[time_key],
    )
    return BANGKOK.localize(chosen_datetime).isoformat(
        sep=" ",
        timespec="seconds",
    )


def page_manage(df):
    heading(
        "⚙️ จัดการสถานะ",
        "บันทึกเวลาเริ่มจัด จัดเสร็จวาง Staging หรือยกเลิก JOB",
    )

    if df.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        return

    active_df = df.loc[df["status"] != "🔴 ยกเลิก"].copy()
    if active_df.empty:
        st.info("ไม่มี JOB ที่ยังดำเนินการอยู่")
        active_df = df.copy()

    choices = {
        f"{row['job_number']} · {row['department']} · {row['status']}": int(row["id"])
        for _, row in active_df.iterrows()
    }
    selected_label = st.selectbox(
        "เลือก JOB",
        list(choices.keys()),
        key="manage_job_select",
    )
    selected_id = choices[selected_label]
    record = df.loc[df["id"] == selected_id].iloc[0].to_dict()

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown(
        f"**JOB:** `{record.get('job_number')}` · "
        f"**แผนก:** {record.get('department') or '—'} · "
        f"**ไลน์:** {record.get('line') or '—'} · "
        f"**สถานะ:** {get_status(record)}"
    )
    st.caption(f"รับเรื่อง: {format_timestamp(record.get('created_at'))}")

    start_value = timestamp_input(
        "เริ่มจัดสินค้า",
        selected_id,
        "start_pick",
        record.get("start_pick_time"),
    )
    finish_value = timestamp_input(
        "จัดเสร็จ / วาง Staging",
        selected_id,
        "finish_pick",
        record.get("finish_pick_time"),
    )

    if st.button(
        "💾 บันทึกการอัปเดตสถานะ",
        type="primary",
        use_container_width=True,
        key=f"manage_save_status_{selected_id}",
    ):
        start_dt = to_bangkok_datetime(start_value)
        finish_dt = to_bangkok_datetime(finish_value)
        received_dt = to_bangkok_datetime(record.get("created_at"))

        if start_dt and received_dt and start_dt < received_dt:
            st.error("เวลาเริ่มจัดต้องไม่อยู่ก่อนเวลารับเรื่อง")
        elif start_dt and finish_dt and finish_dt < start_dt:
            st.error("เวลาจัดเสร็จต้องไม่อยู่ก่อนเวลาเริ่มจัด")
        elif finish_dt and not start_dt:
            st.error("กรุณาระบุเวลาเริ่มจัดก่อนบันทึกเวลาจัดเสร็จ")
        else:
            updated = update_requisition_times(
                selected_id,
                start_value,
                finish_value,
            )
            if updated:
                st.success("บันทึกเวลาสถานะเรียบร้อย")
                play_tick()
                st.rerun()
            else:
                st.error("ไม่พบ JOB ที่ต้องการอัปเดต")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("#### 🔴 ยกเลิก JOB")

    with st.form(f"cancel_form_{selected_id}"):
        cancelled_by = st.text_input(
            "ผู้สั่งยกเลิก (PN/PD) *",
            key=f"cancelled_by_{selected_id}",
        )
        cancel_reason = st.text_area(
            "สาเหตุการยกเลิก *",
            key=f"cancel_reason_{selected_id}",
        )
        confirm_cancel = st.checkbox(
            "ยืนยันการยกเลิกรายการนี้",
            key=f"confirm_cancel_{selected_id}",
        )
        cancel_submit = st.form_submit_button("🔴 บันทึกยกเลิก JOB")

    if cancel_submit:
        if not cancelled_by.strip() or not cancel_reason.strip():
            st.error("กรุณาระบุผู้สั่งยกเลิกและสาเหตุให้ครบ")
        elif not confirm_cancel:
            st.error("กรุณาติ๊กยืนยันก่อนบันทึกยกเลิก")
        elif cancel_requisition(selected_id, cancelled_by, cancel_reason):
            st.success("ยกเลิก JOB และบันทึกข้อมูลเรียบร้อย")
            play_tick()
            st.rerun()
        else:
            st.error("ไม่พบ JOB ที่ต้องการยกเลิก")

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Page 3: Dashboard
# ============================================================

def page_dashboard(df):
    heading(
        "📊 แดชบอร์ด",
        "ภาพรวมปริมาณงานและระยะเวลาการทำงานฝั่งคลังสินค้า",
    )
    filtered = render_filters(df, "dashboard")

    if filtered.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        return

    view = prepare_display_data(filtered)
    pending_count = int(
        view["status"].isin(["🟠 รอจัด", "🟡 กำลังจัด"]).sum()
    )
    completed = view.loc[view["status"] == "🟢 จัดเสร็จเรียบร้อย"]
    late_count = int(view["late"].fillna(False).sum())

    picking_values = (
        pd.to_numeric(completed["picking_minutes"], errors="coerce")
        .dropna()
        .tolist()
    )
    total_values = (
        pd.to_numeric(completed["warehouse_total_minutes"], errors="coerce")
        .dropna()
        .tolist()
    )
    avg_picking = (
        sum(picking_values) / len(picking_values)
        if picking_values
        else None
    )
    avg_total = (
        sum(total_values) / len(total_values)
        if total_values
        else None
    )
    late_percent = late_count / len(view) * 100 if len(view) else 0

    metrics = [
        ("ใบเบิกทั้งหมด", f"{len(view):,}", "ตามช่วงวันที่และคำค้น"),
        ("งานค้างฝั่งคลัง", f"{pending_count:,}", "รอจัด + กำลังจัด"),
        ("เวลาจัดเฉลี่ย", format_duration(avg_picking), "เริ่มจัด → จัดเสร็จ"),
        ("ใบเบิกเย็น", f"{late_count:,} ({late_percent:.1f}%)", "รับหลัง 16:00 น."),
    ]

    columns = st.columns(4)
    for column, (label, value, hint) in zip(columns, metrics):
        with column:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{html.escape(label)}</div>
                    <div class="kpi-value">{html.escape(value)}</div>
                    <div class="kpi-hint">{html.escape(hint)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if avg_total is not None:
        st.caption(
            "เวลารวมฝั่งคลังเฉลี่ย (รับเรื่อง → จัดเสร็จ): "
            f"{format_duration(avg_total)}"
        )

    left, right = st.columns([1, 1.3])

    with left:
        st.markdown("#### สัดส่วนใบเบิกปกติ / ใบเบิกเย็น")
        late_stats = pd.DataFrame(
            {
                "ประเภท": ["ใบเบิกปกติ", "ใบเบิกเย็น"],
                "จำนวน": [
                    int((~view["late"].fillna(False)).sum()),
                    late_count,
                ],
            }
        )

        if not late_stats.empty and len(late_stats) > 0:
            fig = px.pie(
                late_stats,
                names="ประเภท",
                values="จำนวน",
                hole=0.62,
                color="ประเภท",
                color_discrete_map={
                    "ใบเบิกปกติ": "#16a34a",
                    "ใบเบิกเย็น": "#dc2626",
                },
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(
                margin=dict(l=8, r=8, t=12, b=8),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend_title_text="",
                font=dict(family="Prompt", color="#334155"),
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                key="dashboard_late_donut",
            )
        else:
            st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")

    with right:
        st.markdown("#### เวลาที่รับใบเบิก")
        arrivals = view.copy()
        arrivals["_created"] = pd.to_datetime(
            arrivals["created_at"],
            errors="coerce",
        )
        arrivals = arrivals.dropna(subset=["_created"])

        if not arrivals.empty and len(arrivals) > 0:
            arrivals["ชั่วโมงที่รับ"] = (
                arrivals["_created"].dt.hour.astype(int).astype(str).str.zfill(2)
                + ":00"
            )
            hourly = (
                arrivals.groupby("ชั่วโมงที่รับ", as_index=False)
                .size()
                .rename(columns={"size": "จำนวนใบเบิก"})
                .sort_values("ชั่วโมงที่รับ")
            )

            if not hourly.empty and len(hourly) > 0:
                fig = px.bar(
                    hourly,
                    x="ชั่วโมงที่รับ",
                    y="จำนวนใบเบิก",
                    color_discrete_sequence=["#2563eb"],
                )
                fig.update_layout(
                    margin=dict(l=8, r=8, t=12, b=8),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Prompt", color="#334155"),
                    xaxis_title="",
                    yaxis_title="จำนวนใบเบิก",
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="dashboard_hourly_bar",
                )
            else:
                st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")
        else:
            st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")

    st.markdown("#### รายการใบเบิกล่าสุด")
    render_table(view.head(100), "dashboard_table")


# ============================================================
# Page 4: History and export
# ============================================================

def page_history(df):
    heading(
        "📄 ประวัติและส่งออกข้อมูล",
        "ค้นหา ดู Timeline และส่งออกรายงานการทำงานฝั่งคลัง",
    )
    filtered = render_filters(df, "history")

    if filtered.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        return

    render_table(filtered, "history_table")

    st.markdown("#### 📄 พิมพ์หลักฐาน / สรุป Timeline")
    eligible = filtered.loc[
        filtered.apply(
            lambda row: bool(row.get("late"))
            or row.get("status") == "🔴 ยกเลิก",
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
            list(records.keys()),
            key="history_timeline_select",
        )
        if st.button(
            "📄 พิมพ์หลักฐาน / สรุป Timeline",
            key="history_open_timeline",
        ):
            show_timeline_dialog(records[selected])

    st.markdown("#### 📥 ส่งออกรายงาน")
    export_df = make_export_frame(filtered)
    excel_bytes = create_excel_bytes(export_df)
    csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📥 ดาวน์โหลด Excel (.xlsx)",
            data=excel_bytes,
            file_name="รายงานสรุปการเบิกสินค้า_คลังสินค้า.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="history_download_excel",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "📥 ดาวน์โหลด CSV",
            data=csv_bytes,
            file_name="รายงานสรุปการเบิกสินค้า_คลังสินค้า.csv",
            mime="text/csv",
            key="history_download_csv",
            use_container_width=True,
        )

    st.markdown(
        """
        <div class="panel">
            <b>SMART WAREHOUSE VERSION 1.0</b><br>
            <span class="small-muted">
                รายงานประกอบด้วยข้อมูลรับเรื่อง เริ่มจัด จัดเสร็จ/วาง Staging
                และตัวชี้วัดระยะเวลาฝั่งคลัง
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Main
# ============================================================

def main():
    init_db()

    if not st.session_state.get("authenticated", False):
        login_screen()
        st.markdown(
            '<div class="footer">SMART WAREHOUSE © 2026 | BUSINESS MANAGEMENT SYSTEM</div>',
            unsafe_allow_html=True,
        )
        return

    render_topbar()

    with st.sidebar:
        st.markdown("### 📦 SMART WAREHOUSE")
        st.markdown(f"ผู้ใช้งาน: **{DISPLAY_NAME}**")
        st.caption("Warehouse Operations")
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

        if st.button(
            "ออกจากระบบ",
            use_container_width=True,
            key="logout_button",
        ):
            st.session_state["authenticated"] = False
            st.session_state.pop("display_name", None)
            st.rerun()

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
