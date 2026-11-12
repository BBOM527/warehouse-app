from io import BytesIO
from datetime import datetime, timezone, timedelta, date, time
import html
import re
import sqlite3

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# SMART WAREHOUSE — Warehouse-side requisition tracking
# Install: streamlit pandas plotly pytz openpyxl
# Run:     streamlit run app.py
# ============================================================

st.set_page_config(
    page_title="SMART WAREHOUSE",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- App configuration ---
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

# Canonical database schema. PD handover/waiting fields are intentionally absent.
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
# CSS / Shared UI helpers
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
            radial-gradient(circle at 10% 0%, rgba(37, 99, 235, .045), transparent 28%),
            linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    }

    [data-testid="stHeader"] { background: rgba(248, 250, 252, .82); }
    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 1.2rem; }

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 16px 20px;
        margin: 2px 0 20px 0;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: rgba(255,255,255,.92);
        box-shadow: var(--shadow);
    }
    .brand {
        color: #0f172a;
        font-size: 20px;
        font-weight: 700;
        letter-spacing: .035em;
    }
    .brand-subtitle { color: var(--muted); font-size: 12px; margin-top: 2px; }
    .profile-pill {
        white-space: nowrap;
        border: 1px solid #bbf7d0;
        border-radius: 999px;
        background: #f0fdf4;
        color: #15803d;
        font-size: 13px;
        font-weight: 600;
        padding: 7px 12px;
    }
    .clock-pill {
        white-space: nowrap;
        border: 1px solid #dbeafe;
        border-radius: 999px;
        background: #eff6ff;
        color: #1d4ed8;
        font-size: 13px;
        font-weight: 500;
        padding: 7px 12px;
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

    .status-badge, .tag-badge {
        display: inline-block;
        white-space: nowrap;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 600;
    }
    .status-waiting { color: #92400e; background: #fef3c7; }
    .status-progress { color: #a16207; background: #fef9c3; }
    .status-finished { color: #166534; background: #dcfce7; }
    .status-cancelled { color: #991b1b; background: #fee2e2; }
    .tag-late { color: #b91c1c; background: #fee2e2; }
    .tag-advance { color: #5b21b6; background: #ede9fe; }
    .tag-normal { color: #166534; background: #dcfce7; }

    .panel {
        border: 1px solid var(--border);
        border-radius: 12px;
        background: #fff;
        box-shadow: var(--shadow);
        padding: 18px;
        margin: 8px 0 16px;
    }
    .timeline-card {
        border: 1px solid var(--border);
        border-radius: 12px;
        background: #fff;
        padding: 15px;
        margin: 8px 0;
    }
    .timeline-time { color: #0f172a; font-size: 15px; font-weight: 600; }
    .timeline-label { color: var(--muted); font-size: 12px; }
    .footer {
        color: #94a3b8;
        font-size: 11px;
        text-align: center;
        padding: 22px 0 10px;
        letter-spacing: .04em;
    }

    div.stButton > button, div.stDownloadButton > button {
        border-radius: 10px !important;
        border: 1px solid #cbd5e1 !important;
        transition: transform .16s ease, box-shadow .16s ease, filter .16s ease;
        font-weight: 500 !important;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 7px 16px rgba(15, 23, 42, .10);
        filter: brightness(1.02);
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
    .small-muted { color: var(--muted); font-size: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def heading(title, subtitle=""):
    """Render a consistent page heading."""
    safe_title = html.escape(str(title))
    safe_subtitle = html.escape(str(subtitle))
    st.markdown(
        f"""
        <div class="page-heading">
            <h1>{safe_title}</h1>
            <p>{safe_subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def now_bangkok():
    """Current timezone-aware Bangkok datetime."""
    return datetime.now(BANGKOK).replace(microsecond=0)


def to_bangkok_datetime(value):
    """Parse a stored timestamp into a Bangkok-aware datetime."""
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return None
        if getattr(dt, "tzinfo", None) is None:
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
    return max(0.0, (end_dt - start_dt).total_seconds() / 60.0)


def is_late_requisition(value):
    dt = to_bangkok_datetime(value)
    return bool(dt and dt.time() > CUTOFF_TIME)


def is_advance_order(created_at, start_pick_time):
    created = to_bangkok_datetime(created_at)
    started = to_bangkok_datetime(start_pick_time)
    return bool(created and started and created.date() != started.date())


def get_status(row):
    if str(row.get("cancelled_at") or "").strip():
        return "🔴 ยกเลิก"
    if str(row.get("finish_pick_time") or "").strip():
        return "🟢 จัดเสร็จเรียบร้อย"
    if str(row.get("start_pick_time") or "").strip():
        return "🟡 กำลังจัด"
    return "🟠 รอจัด"


def status_css_class(status):
    if "ยกเลิก" in status:
        return "status-cancelled"
    if "จัดเสร็จ" in status:
        return "status-finished"
    if "กำลังจัด" in status:
        return "status-progress"
    return "status-waiting"


def status_badge(status):
    return (
        f'<span class="status-badge {status_css_class(status)}">'
        f"{html.escape(status)}</span>"
    )


def render_topbar():
    components.html(
        """
        <div style="font-family:Arial,sans-serif; color:#2563eb; font-size:13px;
                    font-weight:600; text-align:right;">
            <span id="thai-clock">กำลังโหลดเวลาไทย…</span>
        </div>
        <script>
        const clockEl = document.getElementById("thai-clock");
        function updateThaiClock() {
            const now = new Date();
            const date = new Intl.DateTimeFormat("th-TH", {
                timeZone: "Asia/Bangkok",
                weekday: "short", year: "numeric", month: "short", day: "numeric"
            }).format(now);
            const time = new Intl.DateTimeFormat("th-TH", {
                timeZone: "Asia/Bangkok",
                hour: "2-digit", minute: "2-digit", second: "2-digit",
                hour12: false
            }).format(now);
            clockEl.textContent = "🇹🇭 " + date + " · " + time;
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
            <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end;">
                <span class="clock-pill">เวลาไทย · Asia/Bangkok</span>
                <span class="profile-pill">● Administrator</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def play_tick():
    """Play a short tick using the browser Web Audio API."""
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
# SQLite database / migration helpers
# ============================================================

def db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def table_columns(conn, table_name):
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]


def init_db():
    """Create/update the database and remove legacy PD handover columns."""
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

        # Re-read columns after schema updates.
        existing = table_columns(conn, "requisitions")

        # Carry values forward from common legacy column names when present.
        aliases = {
            "job_number": ["job_id", "job", "เลขที่_job"],
            "department": ["dept", "department_name"],
            "line": ["production_line", "line_name"],
            "item_name": ["product", "item", "รายการสินค้า"],
            "quantity": ["qty", "amount"],
            "created_at": ["received_at", "received_time", "created_time"],
            "start_pick_time": ["started_at", "start_time"],
            "finish_pick_time": ["picked_at", "completed_at", "finish_time"],
            "cancelled_at": ["canceled_at", "cancel_time"],
            "cancelled_by": ["cancel_by", "canceled_by"],
            "cancel_reason": ["cancellation_reason", "canceled_reason"],
        }
        for target, candidates in aliases.items():
            if target not in existing:
                continue
            for candidate in candidates:
                if candidate in existing:
                    conn.execute(
                        f"""
                        UPDATE requisitions
                        SET {target} = COALESCE(NULLIF({target}, ''), {candidate}, '')
                        WHERE {candidate} IS NOT NULL
                        """
                    )

        # Derive status from warehouse timestamps and cancellation fields.
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

        # Rebuild legacy tables to permanently remove PD handover/waiting columns.
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
            select_columns = []
            for col in CANONICAL_COLUMNS:
                if col in existing:
                    select_columns.append(col)
                elif col == "id":
                    select_columns.append("rowid AS id")
                elif col == "status":
                    select_columns.append("'รอจัด' AS status")
                else:
                    select_columns.append(f"'' AS {col}")
            conn.execute(
                f"""
                INSERT OR IGNORE INTO requisitions_new ({", ".join(CANONICAL_COLUMNS)})
                SELECT {", ".join(select_columns)}
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
            f"SELECT {', '.join(CANONICAL_COLUMNS)} FROM requisitions ORDER BY created_at DESC, id DESC",
            conn,
        )
    finally:
        conn.close()

    if df.empty:
        for col in CANONICAL_COLUMNS:
            if col not in df.columns:
                df[col] = pd.Series(dtype="object")
    else:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
        df["status"] = df.apply(lambda row: get_status(row.to_dict()), axis=1)
        df["late"] = df["created_at"].apply(is_late_requisition)
        df["advance_order"] = df.apply(
            lambda row: is_advance_order(row.get("created_at"), row.get("start_pick_time")),
            axis=1,
        )
        df["wait_start_minutes"] = df.apply(
            lambda row: (
                None
                if is_advance_order(row.get("created_at"), row.get("start_pick_time"))
                else duration_minutes(row.get("created_at"), row.get("start_pick_time"))
            ),
            axis=1,
        )
        df["picking_minutes"] = df.apply(
            lambda row: duration_minutes(row.get("start_pick_time"), row.get("finish_pick_time")),
            axis=1,
        )
        df["warehouse_total_minutes"] = df.apply(
            lambda row: duration_minutes(row.get("created_at"), row.get("finish_pick_time")),
            axis=1,
        )

    # Ensure derived columns exist for empty data frames.
    for col in [
        "late",
        "advance_order",
        "wait_start_minutes",
        "picking_minutes",
        "warehouse_total_minutes",
    ]:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")
    return df


def insert_requisition(job_number, department, line, item_name, quantity, created_at, created_by):
    job_number = str(job_number).strip()
    department = str(department).strip()
    line = str(line).strip() if department == "PD" else ""
    if not job_number:
        return False, "กรุณาระบุเลขที่ JOB"

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
        return False, f"เลข JOB {job_number} มีอยู่ในระบบแล้ว"
    except sqlite3.Error as exc:
        return False, f"บันทึกไม่สำเร็จ: {exc}"
    finally:
        conn.close()


def update_requisition_times(job_id, start_pick_time, finish_pick_time):
    conn = db_connect()
    try:
        conn.execute(
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
        return conn.rowcount > 0
    finally:
        conn.close()


def cancel_requisition(job_id, cancelled_by, cancel_reason):
    conn = db_connect()
    try:
        conn.execute(
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
                now_bangkok().isoformat(sep=" ", timespec="seconds"),
                cancelled_by.strip(),
                cancel_reason.strip(),
                now_bangkok().isoformat(sep=" ", timespec="seconds"),
                int(job_id),
            ),
        )
        conn.commit()
        return conn.rowcount > 0
    finally:
        conn.close()


# ============================================================
# Search / date filters
# ============================================================

def filter_data(df, page_type="all", search_text="", start_date=None, end_date=None):
    """Filter rows by search text and created date, shared by dashboard/history."""
    if df is None or df.empty:
        return pd.DataFrame(columns=(df.columns if df is not None else []))

    result = df.copy()

    if start_date is not None or end_date is not None:
        parsed = pd.to_datetime(result["created_at"], errors="coerce")
        if getattr(parsed.dt, "tz", None) is not None:
            parsed = parsed.dt.tz_convert(BANGKOK).dt.tz_localize(None)
        dates = parsed.dt.date
        if start_date is not None:
            result = result.loc[dates.loc[result.index] >= start_date]
        if end_date is not None:
            result = result.loc[dates.loc[result.index] <= end_date]

    query = str(search_text or "").strip().casefold()
    if query:
        searchable_cols = [
            col for col in ["job_number", "department", "line", "item_name", "status"]
            if col in result.columns
        ]
        if searchable_cols:
            mask = result[searchable_cols].fillna("").astype(str).apply(
                lambda col: col.str.casefold().str.contains(re.escape(query), regex=True)
            ).any(axis=1)
            result = result.loc[mask]

    if page_type == "active" and "status" in result.columns:
        result = result.loc[result["status"] != "🔴 ยกเลิก"]
    return result.copy()


def render_filters(df, key_prefix):
    today = now_bangkok().date()
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
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
        with c2:
            start_date = st.date_input("ตั้งแต่วันที่", value=today, key=f"{key_prefix}_start_date")
        with c3:
            end_date = st.date_input("ถึงวันที่", value=today, key=f"{key_prefix}_end_date")
        if isinstance(start_date, (tuple, list)):
            start_date = start_date[0] if start_date else None
        if isinstance(end_date, (tuple, list)):
            end_date = end_date[-1] if end_date else None

    search = st.text_input(
        "🔎 ค้นหา JOB / แผนก / ไลน์ / สินค้า",
        key=f"{key_prefix}_search",
        placeholder="พิมพ์คำค้นหา…",
    )
    return filter_data(df, key_prefix, search, start_date, end_date)


# ============================================================
# Table / export / timeline helpers
# ============================================================

THAI_EXPORT_COLUMNS = [
    ("job_number", "เลขที่ Job"),
    ("created_at", "วันเวลาที่รับใบเบิก"),
    ("department", "แผนกที่เบิก"),
    ("line", "ไลน์ผลิต"),
    ("item_name", "รายการสินค้า"),
    ("quantity", "จำนวน"),
    ("status", "สถานะปัจจุบัน"),
    ("start_pick_time", "เวลาเริ่มจัด"),
    ("finish_pick_time", "เวลาจัดเสร็จ / วาง Staging"),
    ("wait_start_display", "เวลารอเริ่มจัด"),
    ("picking_display", "ระยะเวลาจัดสินค้า"),
    ("warehouse_total_display", "เวลารวมฝั่งคลัง"),
    ("late_display", "ใบเบิกเย็น"),
    ("advance_display", "เบิกล่วงหน้า"),
    ("cancelled_by", "ผู้สั่งยกเลิก"),
    ("cancel_reason", "สาเหตุการยกเลิก"),
]


def prepare_display_data(df):
    if df is None or df.empty:
        return pd.DataFrame()

    result = df.copy()
    result["status"] = result.apply(lambda row: get_status(row.to_dict()), axis=1)
    result["late"] = result["created_at"].apply(is_late_requisition)
    result["advance_order"] = result.apply(
        lambda row: is_advance_order(row.get("created_at"), row.get("start_pick_time")),
        axis=1,
    )
    result["wait_start_minutes"] = result.apply(
        lambda row: (
            None
            if is_advance_order(row.get("created_at"), row.get("start_pick_time"))
            else duration_minutes(row.get("created_at"), row.get("start_pick_time"))
        ),
        axis=1,
    )
    result["picking_minutes"] = result.apply(
        lambda row: duration_minutes(row.get("start_pick_time"), row.get("finish_pick_time")),
        axis=1,
    )
    result["warehouse_total_minutes"] = result.apply(
        lambda row: duration_minutes(row.get("created_at"), row.get("finish_pick_time")),
        axis=1,
    )
    result["wait_start_display"] = result.apply(
        lambda row: (
            "🌙 เบิกล่วงหน้า (รับเรื่องเมื่อวาน)"
            if row["advance_order"]
            else format_duration(row["wait_start_minutes"])
        ),
        axis=1,
    )
    result["picking_display"] = result["picking_minutes"].apply(format_duration)
    result["warehouse_total_display"] = result["warehouse_total_minutes"].apply(format_duration)
    result["late_display"] = result["late"].map({True: "🔴 ใบเบิกเย็น", False: "🟢 ปกติ"})
    result["advance_display"] = result["advance_order"].map(
        {True: "🌙 เบิกล่วงหน้า", False: ""}
    )
    result["created_display"] = result["created_at"].apply(format_timestamp)
    result["start_display"] = result["start_pick_time"].apply(format_timestamp)
    result["finish_display"] = result["finish_pick_time"].apply(format_timestamp)
    result["tag_display"] = result.apply(
        lambda row: " · ".join(
            tag for tag in [
                "🔴 ใบเบิกเย็น" if row["late"] else "",
                "🌙 เบิกล่วงหน้า" if row["advance_order"] else "",
            ] if tag
        ) or "🟢 ปกติ",
        axis=1,
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
            "แท็ก": view["tag_display"],
            "เวลาเริ่มจัด": view["start_display"],
            "เวลาจัดเสร็จ / วาง Staging": view["finish_display"],
            "เวลารอเริ่มจัด": view["wait_start_display"],
            "ระยะเวลาจัดสินค้า": view["picking_display"],
            "เวลารวมฝั่งคลัง": view["warehouse_total_display"],
        }
    )
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        key=key,
    )


def make_export_frame(df):
    view = prepare_display_data(df)
    if view.empty:
        return pd.DataFrame(columns=[thai for _, thai in THAI_EXPORT_COLUMNS])

    export = pd.DataFrame()
    for source, target in THAI_EXPORT_COLUMNS:
        if source in view.columns:
            export[target] = view[source]
        else:
            export[target] = ""
    export["วันเวลาที่รับใบเบิก"] = view["created_at"].apply(format_timestamp)
    export["เวลาเริ่มจัด"] = view["start_pick_time"].apply(format_timestamp)
    export["เวลาจัดเสร็จ / วาง Staging"] = view["finish_pick_time"].apply(format_timestamp)
    return export


def create_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="รายงานคลังสินค้า")
        worksheet = writer.sheets["รายงานคลังสินค้า"]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for column_cells in worksheet.columns:
            values = [
                len(str(cell.value)) if cell.value is not None else 0
                for cell in column_cells
            ]
            width = min(max(max(values, default=10) + 2, 12), 50)
            worksheet.column_dimensions[column_cells[0].column_letter].width = width
    output.seek(0)
    return output.getvalue()


def show_timeline_dialog(record):
    @st.dialog("📄 หลักฐาน / สรุป Timeline", width="large")
    def _dialog():
        view = prepare_display_data(pd.DataFrame([record]))
        row = view.iloc[0]
        st.markdown(
            f"""
            <div class="panel">
                <div style="font-size:20px;font-weight:700;color:#0f172a;">
                    JOB {html.escape(str(row.get("job_number", "")))}
                </div>
                <div style="color:#64748b;margin-top:4px;">
                    แผนก: {html.escape(str(row.get("department", "—")))}
                    {(" · ไลน์ " + html.escape(str(row.get("line"))) ) if row.get("line") else ""}
                    · สินค้า: {html.escape(str(row.get("item_name") or "—"))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if bool(row.get("late")):
            st.markdown(
                '<span class="tag-badge tag-late">🔴 ใบเบิกเย็น/ส่งช้า</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="tag-badge tag-normal">🟢 ใบเบิกปกติ</span>',
                unsafe_allow_html=True,
            )

        if bool(row.get("advance_order")):
            st.markdown(
                '<span class="tag-badge tag-advance">🌙 เบิกล่วงหน้า (รับเรื่องเมื่อวาน)</span>',
                unsafe_allow_html=True,
            )

        events = [
            ("📥", "รับเรื่อง", row.get("created_at")),
            ("⏱️", "เริ่มจัด", row.get("start_pick_time")),
            ("📦", "จัดเสร็จ / วาง Staging", row.get("finish_pick_time")),
        ]
        for icon, label, timestamp in events:
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

        if row.get("status") == "🔴 ยกเลิก":
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

    _dialog()


def parse_bulk_text(text):
    """Parse one job per line; accepts tab, pipe, or comma separated columns."""
    rows = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "\t" in line:
            parts = [part.strip() for part in line.split("\t")]
        elif "|" in line:
            parts = [part.strip() for part in line.split("|")]
        elif "," in line:
            parts = [part.strip() for part in line.split(",")]
        else:
            parts = [line]

        # Skip common pasted header rows.
        if parts and any(token in parts[0].casefold() for token in ("job", "เลขที่")):
            continue

        rows.append(
            {
                "job_number": parts[0] if len(parts) > 0 else "",
                "item_name": parts[1] if len(parts) > 1 else "",
                "quantity": parts[2] if len(parts) > 2 else "0",
            }
        )
    return rows


# ============================================================
# Authentication
# ============================================================

def login_screen():
    st.markdown("<div style='height:7vh'></div>", unsafe_allow_html=True)
    left, center, right = st.columns([1, 1.15, 1])
    with center:
        st.markdown(
            """
            <div class="panel" style="padding:28px;">
                <div style="font-size:27px;font-weight:700;color:#0f172a;">📦 SMART WAREHOUSE</div>
                <div style="color:#64748b;margin:4px 0 18px;">เข้าสู่ระบบคลังสินค้า</div>
            </div>
            """,
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
# App pages
# ============================================================

def page_dashboard(df):
    heading("📊 Dashboard ภาพรวม", "ภาพรวมปริมาณงานและระยะเวลาการทำงานฝั่งคลังสินค้า")
    filtered = render_filters(df, "dashboard")
    if filtered.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        return

    view = prepare_display_data(filtered)
    active_pending = int(view["status"].isin(["🟠 รอจัด", "🟡 กำลังจัด"]).sum())
    completed = view.loc[view["status"] == "🟢 จัดเสร็จเรียบร้อย"]
    late_count = int(view["late"].fillna(False).sum())

    picking_values = pd.to_numeric(completed["picking_minutes"], errors="coerce").dropna().tolist()
    total_values = pd.to_numeric(completed["warehouse_total_minutes"], errors="coerce").dropna().tolist()
    avg_picking = sum(picking_values) / len(picking_values) if picking_values else None
    avg_total = sum(total_values) / len(total_values) if total_values else None
    late_percent = (late_count / len(view) * 100) if len(view) else 0

    cols = st.columns(4)
    kpis = [
        ("ใบเบิกทั้งหมด", f"{len(view):,}", "ตามช่วงวันที่และคำค้น"),
        ("งานค้างฝั่งคลัง", f"{active_pending:,}", "รอจัด + กำลังจัด"),
        ("เวลาจัดเฉลี่ย", format_duration(avg_picking), "เริ่มจัด → จัดเสร็จ"),
        ("ใบเบิกเย็น", f"{late_count:,} ({late_percent:.1f}%)", "รับหลัง 16:00 น."),
    ]
    for col, (label, value, hint) in zip(cols, kpis):
        with col:
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
        st.caption(f"เวลารวมฝั่งคลังเฉลี่ย (รับเรื่อง → จัดเสร็จ): {format_duration(avg_total)}")

    chart_left, chart_right = st.columns([1, 1.3])
    with chart_left:
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
                color_discrete_map={"ใบเบิกปกติ": "#16a34a", "ใบเบิกเย็น": "#dc2626"},
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(
                margin=dict(l=8, r=8, t=12, b=8),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend_title_text="",
                font=dict(family="Prompt", color="#334155"),
            )
            st.plotly_chart(fig, use_container_width=True, key="dashboard_late_donut")
        else:
            st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")

    with chart_right:
        st.markdown("#### เวลาที่รับใบเบิก")
        arrivals = view.copy()
        arrivals["_created"] = pd.to_datetime(arrivals["created_at"], errors="coerce")
        arrivals = arrivals.dropna(subset=["_created"])
        if not arrivals.empty and len(arrivals) > 0:
            arrivals["ชั่วโมงที่รับ"] = arrivals["_created"].dt.hour.astype(int).astype(str).str.zfill(2) + ":00"
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
                st.plotly_chart(fig, use_container_width=True, key="dashboard_hourly_bar")
            else:
                st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")
        else:
            st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")

    st.markdown("#### รายการใบเบิกล่าสุด")
    render_table(view.head(100), "dashboard_table")


def page_input(df):
    heading("📝 บันทึกใบเบิก", "รับเรื่องใบเบิกและบันทึกเวลาตามเวลาประเทศไทย")
    st.info("เวลา Cut-off คือ 16:00 น. ระบบติดแท็กใบเบิกเย็นจากเวลารับเรื่องโดยอัตโนมัติ")

    if "last_department" not in st.session_state:
        st.session_state["last_department"] = "PD"
    if "last_line" not in st.session_state:
        st.session_state["last_line"] = "L1"

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    department = st.selectbox(
        "แผนกที่เบิก",
        DEPARTMENTS,
        index=DEPARTMENTS.index(st.session_state["last_department"])
        if st.session_state["last_department"] in DEPARTMENTS else 0,
        key="input_department",
    )
    if department == "อื่นๆ":
        department = st.text_input("ระบุชื่อแผนก", key="input_custom_department").strip() or "อื่นๆ"

    line = ""
    if department == "PD":
        line = st.selectbox(
            "ไลน์ผลิต",
            PRODUCTION_LINES,
            index=PRODUCTION_LINES.index(st.session_state["last_line"])
            if st.session_state["last_line"] in PRODUCTION_LINES else 0,
            key="input_line",
        )
    else:
        line = ""

    item_name = st.text_input("รายการสินค้า (ถ้ามี)", key="input_item_name")
    quantity = st.number_input("จำนวน", min_value=0, step=1, value=0, key="input_quantity")

    st.markdown("##### วางข้อมูลหลาย JOB พร้อมกัน")
    st.caption("วางหนึ่ง JOB ต่อหนึ่งบรรทัด: เลข JOB หรือ เลข JOB | รายการสินค้า | จำนวน")
    bulk_text = st.text_area(
        "Bulk Copy-Paste",
        height=145,
        placeholder="JOB-6901 | วัตถุดิบ A | 2\nJOB-6902 | กล่องบรรจุ | 0",
        key="input_bulk_text",
        label_visibility="collapsed",
    )
    manual_job = st.text_input("หรือบันทึก JOB เดียว", key="input_single_job", placeholder="เช่น JOB-6901")

    if st.button("📥 บันทึกรับเรื่องทั้งหมด", type="primary", use_container_width=True, key="input_save_all"):
        now_text = now_bangkok().isoformat(sep=" ", timespec="seconds")
        jobs = parse_bulk_text(bulk_text)
        if manual_job.strip():
            jobs.append(
                {
                    "job_number": manual_job.strip(),
                    "item_name": item_name.strip(),
                    "quantity": str(int(quantity)),
                }
            )
        if not jobs:
            st.error("กรุณาวาง JOB หรือกรอกเลข JOB อย่างน้อย 1 รายการ")
        else:
            st.session_state["last_department"] = department
            st.session_state["last_line"] = line if department == "PD" else ""
            successes, errors = 0, []
            for job in jobs:
                try:
                    job_qty = int(float(str(job.get("quantity", "0")).strip() or "0"))
                    job_qty = max(0, job_qty)
                except (ValueError, TypeError):
                    job_qty = 0
                job_item = job.get("item_name") or item_name
                ok, message = insert_requisition(
                    job_number=job.get("job_number"),
                    department=department,
                    line=line if department == "PD" else "",
                    item_name=job_item,
                    quantity=job_qty,
                    created_at=now_text,
                    created_by=DISPLAY_NAME,
                )
                if ok:
                    successes += 1
                else:
                    errors.append(message)

            if successes:
                st.success(f"บันทึกรับเรื่องสำเร็จ {successes} JOB")
                play_tick()
            for error in errors:
                st.warning(error)
            if successes:
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def set_timestamp_state(widget_key):
    st.session_state[widget_key] = now_bangkok().time().replace(microsecond=0)


def timestamp_input(label, job_id, field_name, existing_value):
    """Manual date/time editor plus auto-current-time button."""
    existing_dt = to_bangkok_datetime(existing_value)
    default_date = existing_dt.date() if existing_dt else now_bangkok().date()
    default_time = existing_dt.time().replace(microsecond=0) if existing_dt else time(0, 0)

    date_key = f"{field_name}_date_{job_id}"
    time_key = f"{field_name}_time_{job_id}"
    auto_key = f"{field_name}_auto_{job_id}"

    # Initial widget state is set only before widget creation.
    if date_key not in st.session_state:
        st.session_state[date_key] = default_date
    if time_key not in st.session_state:
        st.session_state[time_key] = default_time

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
            key=auto_key,
            on_click=set_timestamp_state,
            args=(time_key,),
            help="ใส่เวลาปัจจุบันของไทย โดยวันที่ใช้วันที่ปัจจุบัน",
        )
    if st.session_state.get(auto_key):
        st.session_state[date_key] = now_bangkok().date()
        st.session_state[auto_key] = False

    chosen_date = st.session_state[date_key]
    chosen_time = st.session_state[time_key]
    dt = BANGKOK.localize(datetime.combine(chosen_date, chosen_time))
    return dt.isoformat(sep=" ", timespec="seconds")


def page_manage(df):
    heading("⚙️ จัดการและอัปเดตสถานะ", "บันทึกเวลาเริ่มจัด จัดเสร็จวาง Staging หรือยกเลิก JOB")
    if df.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        return

    active_df = df.loc[df["status"] != "🔴 ยกเลิก"].copy()
    if active_df.empty:
        st.info("ไม่มี JOB ที่ยังดำเนินการอยู่")
        active_df = df.copy()

    options = {
        f"{row['job_number']} · {row['department']} · {row['status']}": int(row["id"])
        for _, row in active_df.iterrows()
    }
    selected_label = st.selectbox("เลือก JOB", list(options.keys()), key="manage_job_select")
    selected_id = options[selected_label]
    record = df.loc[df["id"] == selected_id].iloc[0].to_dict()

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown(
        f"**JOB:** `{record.get('job_number')}`  ·  "
        f"**แผนก:** {record.get('department') or '—'}  ·  "
        f"**ไลน์:** {record.get('line') or '—'}  ·  "
        f"**สถานะ:** {get_status(record)}"
    )
    st.caption(f"รับเรื่อง: {format_timestamp(record.get('created_at'))}")

    start_time_value = timestamp_input(
        "⏱️ เวลาเริ่มจัดสินค้า",
        selected_id,
        "start_pick",
        record.get("start_pick_time"),
    )
    finish_time_value = timestamp_input(
        "📦 เวลาจัดเสร็จ / วาง Staging",
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
        start_dt = to_bangkok_datetime(start_time_value)
        finish_dt = to_bangkok_datetime(finish_time_value)
        if start_dt and finish_dt and finish_dt < start_dt:
            st.error("เวลาจัดเสร็จต้องไม่อยู่ก่อนเวลาเริ่มจัด")
        else:
            updated = update_requisition_times(selected_id, start_time_value, finish_time_value)
            if updated:
                st.success("บันทึกเวลาสถานะเรียบร้อย")
                play_tick()
                st.rerun()
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
        else:
            if cancel_requisition(selected_id, cancelled_by, cancel_reason):
                st.success("ยกเลิก JOB และบันทึกข้อมูลเรียบร้อย")
                play_tick()
                st.rerun()
            st.error("ไม่พบ JOB ที่ต้องการยกเลิก")
    st.markdown("</div>", unsafe_allow_html=True)


def page_history(df):
    heading("📄 ประวัติและส่งออกข้อมูล", "ค้นหา ดู Timeline และส่งออกรายงานฝั่งคลัง")
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
        st.caption("ไม่มีรายการใบเบิกเย็นหรือ JOB ที่ยกเลิกในผลการค้นหานี้")
    else:
        labels = {
            f"{row['job_number']} · {row['department']} · {row['status']}": row.to_dict()
            for _, row in eligible.iterrows()
        }
        chosen = st.selectbox(
            "เลือกรายการสำหรับดูหลักฐาน",
            list(labels.keys()),
            key="history_timeline_select",
        )
        if st.button(
            "📄 พิมพ์หลักฐาน / สรุป Timeline",
            key="history_open_timeline",
        ):
            show_timeline_dialog(labels[chosen])

    st.markdown("#### 📥 ส่งออกรายงาน")
    export_frame = make_export_frame(filtered)
    excel_bytes = create_excel_bytes(export_frame)
    csv_bytes = export_frame.to_csv(index=False).encode("utf-8-sig")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📥 ดาวน์โหลด Excel (.xlsx)",
            data=excel_bytes,
            file_name="รายงานสรุปการเบิกสินค้า_คลังสินค้า.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="history_download_excel",
            use_container_width=True,
        )
    with c2:
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
                รายงานนี้ประกอบด้วยข้อมูลการรับเรื่อง เริ่มจัด จัดเสร็จ/วาง Staging
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
                "📊 Dashboard ภาพรวม",
                "📝 บันทึกใบเบิก",
                "⚙️ จัดการสถานะ",
                "📄 ประวัติและส่งออก",
            ],
            key="main_navigation",
        )
        st.divider()
        if st.button("ออกจากระบบ", use_container_width=True, key="logout_button"):
            st.session_state["authenticated"] = False
            st.session_state.pop("display_name", None)
            st.rerun()

    df = load_data()

    if page == "📊 Dashboard ภาพรวม":
        page_dashboard(df)
    elif page == "📝 บันทึกใบเบิก":
        page_input(df)
    elif page == "⚙️ จัดการสถานะ":
        page_manage(df)
    elif page == "📄 ประวัติและส่งออก":
        page_history(df)

    st.markdown(
        '<div class="footer">SMART WAREHOUSE © 2026 | BUSINESS MANAGEMENT SYSTEM</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
