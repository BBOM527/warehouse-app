from io import BytesIO
from datetime import datetime, timezone, timedelta, time
import html
import sqlite3

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st
import streamlit.components.v1 as components
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


# ── ตั้งค่าระบบ ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SMART WAREHOUSE",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

BANGKOK = pytz.timezone("Asia/Bangkok")
UTC_PLUS_7 = timezone(timedelta(hours=7))
DB_PATH = "warehouse_tracking.db"

LOGIN_USERNAME = "lNWBOOM"
LOGIN_PASSWORD = "Boomkub555"
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
CUTOFF_TIME = time(16, 0)


# ── Clean Light Enterprise Theme ──────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');

    :root {
        --bg:#f8fafc; --bg-soft:#f1f5f9; --card:#ffffff;
        --border:#e2e8f0; --ink:#1e293b; --ink-strong:#0f172a;
        --muted:#64748b; --blue:#2563eb; --green:#16a34a;
        --red:#dc2626; --orange:#d97706;
    }
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family:'Prompt',sans-serif; color:var(--ink);
    }
    [data-testid="stAppViewContainer"] {
        background:linear-gradient(180deg,var(--bg) 0%,var(--bg-soft) 100%);
    }
    [data-testid="stHeader"] { background:rgba(248,250,252,.88); }
    [data-testid="stSidebar"] {
        background:#fff; border-right:1px solid var(--border);
    }
    [data-testid="stSidebar"] * { color:var(--ink); }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { color:var(--ink); }

    h1,h2,h3,p,label { color:var(--ink); }
    h1 { color:var(--ink-strong); font-weight:600; letter-spacing:-.02em; }
    [data-testid="stCaptionContainer"], .stCaption { color:var(--muted); }

    [data-testid="stMetric"] {
        background:var(--card); border:1px solid var(--border);
        border-radius:12px; padding:18px 20px;
        box-shadow:0 10px 30px rgba(15,23,42,.05);
    }
    [data-testid="stMetricLabel"] { color:var(--muted); }
    [data-testid="stMetricValue"] { color:var(--ink-strong); font-weight:600; }

    [data-testid="stForm"],[data-testid="stExpander"],[data-testid="stDataFrame"],
    [data-testid="stTable"],[data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stDialog"] {
        background:var(--card); border:1px solid var(--border);
        border-radius:12px; box-shadow:0 10px 30px rgba(15,23,42,.05);
        overflow:hidden;
    }
    [data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input,[data-testid="stTimeInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] [data-baseweb="select"]>div {
        background:#fff; color:var(--ink); border:1px solid var(--border);
        border-radius:10px;
    }
    [data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button,
    [data-testid="stDownloadButton"] button {
        border-radius:10px; font-family:'Prompt',sans-serif; font-weight:500;
        transition:transform .18s ease,box-shadow .18s ease,filter .18s ease;
    }
    [data-testid="stButton"] button[kind="primary"],
    [data-testid="stFormSubmitButton"] button {
        background:linear-gradient(110deg,#16a34a,#2563eb);
        color:#fff; border:0; box-shadow:0 6px 16px rgba(37,99,235,.15);
    }
    [data-testid="stButton"] button:hover,
    [data-testid="stFormSubmitButton"] button:hover,
    [data-testid="stDownloadButton"] button:hover {
        transform:translateY(-2px); box-shadow:0 10px 20px rgba(15,23,42,.12);
        filter:brightness(1.03);
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] * { color:var(--ink); }

    .topbar {
        display:flex; justify-content:space-between; align-items:center;
        gap:1rem; padding:14px 20px; margin:0 0 18px;
        background:#fff; border:1px solid var(--border); border-radius:12px;
        box-shadow:0 6px 20px rgba(15,23,42,.04);
    }
    .brand { color:var(--ink-strong); font-size:1.12rem; font-weight:700; letter-spacing:.06em; }
    .profile {
        color:#166534; font-size:.88rem; padding:6px 12px;
        border:1px solid #bbf7d0; border-radius:999px; background:#f0fdf4;
    }
    .page-heading { margin:.2rem 0 1.15rem; }
    .page-heading h1 { margin:0; }
    .eyebrow { color:var(--blue); letter-spacing:.1em; font-size:.74rem; font-weight:600; }
    .subtle { color:var(--muted); }
    .clock-card {
        display:flex; justify-content:space-between; align-items:center; gap:1rem;
        background:#fff; border:1px solid var(--border); border-radius:12px;
        padding:12px 18px; margin-bottom:1rem;
        box-shadow:0 6px 20px rgba(15,23,42,.04);
    }
    .clock-time { font-size:1.1rem; font-weight:600; color:var(--green); }
    .clock-date { color:var(--muted); font-size:.9rem; }
    .section-card,.timeline-card {
        background:#fff; border:1px solid var(--border); border-radius:12px;
        padding:18px 20px; box-shadow:0 10px 25px rgba(15,23,42,.05);
        margin-bottom:1rem;
    }
    .timeline-step {
        border-left:3px solid var(--blue); padding:4px 0 12px 14px;
        margin:0 0 8px 4px; color:var(--ink);
    }
    .timeline-step.danger { border-left-color:var(--red); }
    .timeline-time { color:#166534; font-weight:600; }
    .login-card {
        max-width:480px; margin:8vh auto 0; padding:28px;
        background:#fff; border:1px solid var(--border); border-radius:16px;
        box-shadow:0 16px 40px rgba(15,23,42,.08);
    }
    .footer {
        text-align:center; color:var(--muted); font-size:.78rem;
        padding:28px 0 8px; letter-spacing:.06em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Helper functions: ประกาศก่อนเรียกใช้ในทุกหน้า ────────────────────────────
def heading(title, subtitle):
    st.markdown(
        f"""
        <div class="page-heading">
          <div class="eyebrow">SMART WAREHOUSE · CONTROL CENTER</div>
          <h1>{html.escape(str(title))}</h1>
          <div class="subtle">{html.escape(str(subtitle))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def now_bangkok():
    return datetime.now(BANGKOK).replace(microsecond=0)


def as_bangkok(value):
    if value is None or pd.isna(value):
        return None
    try:
        parsed = pd.Timestamp(value).to_pydatetime()
        return BANGKOK.localize(parsed) if parsed.tzinfo is None else parsed.astimezone(BANGKOK)
    except (TypeError, ValueError, OverflowError):
        return None


def stamp(value):
    parsed = as_bangkok(value)
    return parsed.isoformat() if parsed else None


def display_datetime(value):
    parsed = as_bangkok(value)
    return parsed.strftime("%d/%m/%Y %H:%M:%S") if parsed else "—"


def parse_local_datetime(date_value, time_value):
    if not date_value or not time_value:
        return None
    try:
        return BANGKOK.localize(datetime.combine(date_value, time_value))
    except (TypeError, ValueError):
        return None


def duration_minutes(start, end):
    start_dt, end_dt = as_bangkok(start), as_bangkok(end)
    if start_dt is None or end_dt is None:
        return None
    minutes = (end_dt - start_dt).total_seconds() / 60
    return round(minutes, 1) if minutes >= 0 else None


def format_duration(value):
    if value is None or pd.isna(value):
        return "—"
    minutes = int(round(float(value)))
    hours, remainder = divmod(minutes, 60)
    return f"{hours} ชม. {remainder} นาที" if hours else f"{remainder} นาที"


def job_status(row):
    if str(row.get("status", "")) == "ยกเลิก":
        return "🔴 ยกเลิก"
    if pd.notna(row.get("handover_at")):
        return "🟢 รับของแล้ว"
    if pd.notna(row.get("picked_at")):
        return "🔵 จัดเสร็จรอ PD"
    return "🟠 กำลังจัด"


# ── SQLite Auto Schema Update ─────────────────────────────────────────────────
def init_db():
    definitions = {
        "id": "INTEGER",
        "job_number": "TEXT NOT NULL DEFAULT ''",
        "department": "TEXT NOT NULL DEFAULT ''",
        "line": "TEXT NOT NULL DEFAULT ''",
        "production_line": "TEXT NOT NULL DEFAULT ''",
        "item_name": "TEXT NOT NULL DEFAULT ''",
        "quantity": "REAL",
        "received_at": "TEXT",
        "started_at": "TEXT",
        "picked_at": "TEXT",
        "completed_at": "TEXT",
        "handover_at": "TEXT",
        "cancelled_at": "TEXT",
        "cancelled_by": "TEXT",
        "cancel_reason": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'กำลังจัด'",
        "created_by": "TEXT NOT NULL DEFAULT 'Admin'",
        "updated_at": "TEXT",
    }

    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS requisitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_number TEXT NOT NULL DEFAULT '',
                department TEXT NOT NULL DEFAULT '',
                line TEXT NOT NULL DEFAULT '',
                production_line TEXT NOT NULL DEFAULT '',
                item_name TEXT NOT NULL DEFAULT '',
                quantity REAL,
                received_at TEXT,
                started_at TEXT,
                picked_at TEXT,
                completed_at TEXT,
                handover_at TEXT,
                cancelled_at TEXT,
                cancelled_by TEXT,
                cancel_reason TEXT,
                status TEXT NOT NULL DEFAULT 'กำลังจัด',
                created_by TEXT NOT NULL DEFAULT 'Admin',
                updated_at TEXT
            )
            """
        )

        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(requisitions)").fetchall()
        }
        for name, definition in definitions.items():
            if name not in columns:
                conn.execute(
                    f'ALTER TABLE requisitions ADD COLUMN "{name}" {definition}'
                )

        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(requisitions)").fetchall()
        }
        aliases = {
            "job_number": ("job_id", "job_no", "requisition_no"),
            "department": ("dept",),
            "line": ("production_line",),
            "received_at": ("received_time", "created_at"),
            "picked_at": ("completed_at", "completed_time", "picked_time"),
            "handover_at": ("handover_time",),
            "status": ("current_status",),
            "item_name": ("item", "product_name"),
        }
        for target, sources in aliases.items():
            for source in sources:
                if target in columns and source in columns and target != source:
                    conn.execute(
                        f"""
                        UPDATE requisitions SET "{target}"="{source}"
                        WHERE ("{target}" IS NULL OR "{target}"='')
                          AND "{source}" IS NOT NULL AND "{source}"!=''
                        """
                    )

        conn.execute(
            """
            UPDATE requisitions SET line=production_line
            WHERE (line IS NULL OR line='')
              AND production_line IS NOT NULL AND production_line!=''
            """
        )
        conn.execute(
            """
            UPDATE requisitions SET production_line=line
            WHERE (production_line IS NULL OR production_line='')
              AND line IS NOT NULL AND line!=''
            """
        )
        conn.execute(
            """
            UPDATE requisitions SET picked_at=completed_at
            WHERE (picked_at IS NULL OR picked_at='')
              AND completed_at IS NOT NULL AND completed_at!=''
            """
        )
        conn.execute(
            """
            UPDATE requisitions SET completed_at=picked_at
            WHERE (completed_at IS NULL OR completed_at='')
              AND picked_at IS NOT NULL AND picked_at!=''
            """
        )
        conn.execute("UPDATE requisitions SET id=rowid WHERE id IS NULL")
        conn.execute(
            """
            UPDATE requisitions SET job_number='LEGACY-' || rowid
            WHERE job_number IS NULL OR job_number=''
            """
        )
        conn.execute(
            """
            UPDATE requisitions SET received_at=?
            WHERE received_at IS NULL OR received_at=''
            """,
            (now_bangkok().isoformat(),),
        )
        conn.execute(
            """
            UPDATE requisitions SET status='กำลังจัด'
            WHERE status IS NULL OR status=''
            """
        )
        conn.commit()


def load_data():
    init_db()
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        data = pd.read_sql_query(
            """
            SELECT id, job_number, department, line, production_line, item_name,
                   quantity, received_at, started_at, picked_at, completed_at,
                   handover_at, cancelled_at, cancelled_by, cancel_reason,
                   status, created_by, updated_at
            FROM requisitions
            ORDER BY received_at DESC, id DESC
            """,
            conn,
        )

    if not data.empty:
        data["line"] = data["line"].fillna("")
        missing_line = data["line"].eq("")
        data.loc[missing_line, "line"] = data.loc[
            missing_line, "production_line"
        ].fillna("")
        data["picked_at"] = data["picked_at"].where(
            data["picked_at"].notna() & data["picked_at"].ne(""),
            data["completed_at"],
        )

        for column in (
            "received_at", "started_at", "picked_at",
            "handover_at", "cancelled_at", "updated_at",
        ):
            data[column] = pd.to_datetime(
                data[column], errors="coerce", utc=True
            ).dt.tz_convert("Asia/Bangkok")

        data["processing_minutes"] = data.apply(
            lambda row: duration_minutes(row["received_at"], row["picked_at"]),
            axis=1,
        )
        data["waiting_minutes"] = data.apply(
            lambda row: duration_minutes(row["picked_at"], row["handover_at"]),
            axis=1,
        )
        data["late"] = data["received_at"].apply(
            lambda value: bool(
                pd.notna(value)
                and value.time().replace(tzinfo=None) > CUTOFF_TIME
            )
        )
    return data


def insert_requisition(job_number, department, line, item_name, quantity, received_at):
    if department == "PD":
        if line not in PRODUCTION_LINES:
            return False, f"กรุณาเลือกไลน์ผลิต L1-L10 สำหรับ JOB {job_number}"
    else:
        line = ""

    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        duplicate = conn.execute(
            """
            SELECT 1 FROM requisitions
            WHERE job_number=? AND status!='ยกเลิก'
            LIMIT 1
            """,
            (job_number,),
        ).fetchone()
        if duplicate:
            return False, f"เลข JOB {job_number} มีอยู่ในระบบแล้ว"

        conn.execute(
            """
            INSERT INTO requisitions
            (job_number, department, line, production_line, item_name, quantity,
             received_at, status, created_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'กำลังจัด', ?, ?)
            """,
            (
                job_number, department, line, line, item_name, quantity,
                stamp(received_at), DISPLAY_NAME, stamp(now_bangkok()),
            ),
        )
        conn.commit()
    return True, f"บันทึก JOB {job_number} แล้ว"


def update_requisition(
    record_id, department, line, item_name, quantity,
    received_at, picked_at, handover_at,
):
    if department == "PD":
        if line not in PRODUCTION_LINES:
            raise ValueError("แผนก PD ต้องเลือกไลน์ผลิต L1-L10")
    else:
        line = ""

    status = (
        "รับของแล้ว" if handover_at
        else "จัดเสร็จ / รอ PD" if picked_at
        else "กำลังจัด"
    )
    picked_iso = stamp(picked_at)

    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute(
            """
            UPDATE requisitions
            SET department=?, line=?, production_line=?, item_name=?, quantity=?,
                received_at=?, picked_at=?, completed_at=?, handover_at=?,
                status=?, updated_at=?
            WHERE id=?
            """,
            (
                department, line, line, item_name, quantity,
                stamp(received_at), picked_iso, picked_iso, stamp(handover_at),
                status, stamp(now_bangkok()), record_id,
            ),
        )
        conn.commit()


def cancel_requisition(record_id, cancelled_by, reason):
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute(
            """
            UPDATE requisitions
            SET status='ยกเลิก', cancelled_at=?, cancelled_by=?,
                cancel_reason=?, updated_at=?
            WHERE id=?
            """,
            (
                stamp(now_bangkok()), cancelled_by.strip(), reason.strip(),
                stamp(now_bangkok()), record_id,
            ),
        )
        conn.commit()


# ── Export Excel และ CSV ──────────────────────────────────────────────────────
def export_dataframe(data):
    result = pd.DataFrame(index=data.index)
    result["เลขที่ Job"] = data["job_number"].fillna("").astype(str)
    result["วันเวลาที่เบิก"] = data["received_at"].apply(display_datetime)
    result["แผนกที่เบิก"] = data["department"].fillna("").astype(str)
    result["ไลน์ผลิต"] = data["line"].fillna("").astype(str)
    result["รายการสินค้า"] = data["item_name"].fillna("").astype(str)
    result["จำนวน"] = data["quantity"].apply(
        lambda value: "" if pd.isna(value) else value
    )
    result["สถานะปัจจุบัน"] = data.apply(job_status, axis=1)
    result["เวลาจัดเสร็จ"] = data["picked_at"].apply(display_datetime)
    result["เวลา PD มารับ"] = data["handover_at"].apply(display_datetime)
    result["ระยะเวลาจัดสินค้า (นาที)"] = data["processing_minutes"].apply(
        lambda value: "" if pd.isna(value) else round(float(value), 1)
    )
    result["ระยะเวลารอรับสินค้า (นาที)"] = data["waiting_minutes"].apply(
        lambda value: "" if pd.isna(value) else round(float(value), 1)
    )
    return result


def make_excel(data):
    export = export_dataframe(data)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="รายงานการเบิก")
        sheet = writer.sheets["รายงานการเบิก"]
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        sheet.row_dimensions[1].height = 30

        header_fill = PatternFill("solid", fgColor="2563EB")
        header_font = Font(name="Aptos", bold=True, color="FFFFFF", size=11)
        body_font = Font(name="Aptos", size=10)

        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="center", vertical="center", wrap_text=True
            )

        for cells in sheet.columns:
            letter = get_column_letter(cells[0].column)
            longest = 0
            for cell in cells:
                cell.font = header_font if cell.row == 1 else body_font
                if cell.row > 1:
                    cell.alignment = Alignment(vertical="center")
                longest = max(
                    longest,
                    len("" if cell.value is None else str(cell.value)),
                )
            sheet.column_dimensions[letter].width = min(max(longest + 3, 12), 42)

    buffer.seek(0)
    return buffer.getvalue()


def make_csv(data):
    return export_dataframe(data).to_csv(index=False).encode("utf-8-sig")


# ── กราฟ, Live Clock, Sound และ Timeline dialog ──────────────────────────────
def render_plotly_or_info(frame, required_columns, builder, key):
    if (
        not isinstance(frame, pd.DataFrame)
        or frame.empty
        or any(column not in frame.columns for column in required_columns)
    ):
        st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")
        return
    try:
        st.plotly_chart(builder(frame), use_container_width=True, key=key)
    except (ValueError, KeyError, TypeError, ZeroDivisionError):
        st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")


def set_timestamp(date_key, time_key, enabled_key):
    current = now_bangkok()
    st.session_state[date_key] = current.date()
    st.session_state[time_key] = current.time().replace(microsecond=0)
    st.session_state[enabled_key] = True


def play_success_sound():
    components.html(
        """
        <script>
        try {
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          const osc = ctx.createOscillator(), gain = ctx.createGain();
          osc.type = "sine";
          osc.frequency.setValueAtTime(880, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(520, ctx.currentTime + 0.045);
          gain.gain.setValueAtTime(0.12, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
          osc.connect(gain); gain.connect(ctx.destination);
          osc.start(); osc.stop(ctx.currentTime + 0.05);
        } catch (error) {}
        </script>
        """,
        height=0,
    )


def show_live_clock():
    components.html(
        """
        <div class="clock-card">
          <div>
            <div style="font-weight:600;color:#0f172a">🕒 เวลาประเทศไทย</div>
            <div id="thai-date" class="clock-date">กำลังโหลดวันที่…</div>
          </div>
          <div id="thai-clock" class="clock-time">--:--:--</div>
        </div>
        <script>
        function updateThaiClock() {
          const now = new Date();
          document.getElementById("thai-clock").textContent =
            new Intl.DateTimeFormat("th-TH", {
              timeZone:"Asia/Bangkok", hour:"2-digit", minute:"2-digit",
              second:"2-digit", hour12:false
            }).format(now);
          document.getElementById("thai-date").textContent =
            new Intl.DateTimeFormat("th-TH", {
              timeZone:"Asia/Bangkok", weekday:"long", year:"numeric",
              month:"long", day:"numeric"
            }).format(now);
        }
        updateThaiClock();
        setInterval(updateThaiClock, 1000);
        </script>
        """,
        height=76,
        scrolling=False,
    )


@st.dialog("📄 หลักฐานและ Timeline ใบเบิก")
def show_timeline_dialog(record):
    job = html.escape(str(record.get("job_number") or ""))
    department = html.escape(str(record.get("department") or "ไม่ระบุ"))
    line = html.escape(str(record.get("line") or "—"))
    item = html.escape(str(record.get("item_name") or "—"))
    status = html.escape(job_status(record))
    is_cancelled = str(record.get("status", "")) == "ยกเลิก"

    cancel_html = ""
    if is_cancelled:
        cancel_html = f"""
        <div class="timeline-step danger">
          🔴 ยกเลิก<br>
          <span class="timeline-time">{html.escape(display_datetime(record.get("cancelled_at")))}</span>
          <div>ผู้สั่งยกเลิก: {html.escape(str(record.get("cancelled_by") or "—"))}</div>
          <div>สาเหตุ: {html.escape(str(record.get("cancel_reason") or "—"))}</div>
        </div>
        """

    st.markdown(
        f"""
        <div class="timeline-card">
          <div class="eyebrow">SMART WAREHOUSE · EVIDENCE SLIP</div>
          <h2>JOB {job}</h2>
          <div>แผนก: <b>{department}</b>　ไลน์: <b>{line}</b></div>
          <div>รายการ: {item}</div>
          <div>สถานะ: <b>{status}</b></div>
          <hr>
          <div class="timeline-step">
            📥 รับเอกสาร<br>
            <span class="timeline-time">{html.escape(display_datetime(record.get("received_at")))}</span>
          </div>
          <div class="timeline-step">
            📦 จัดเสร็จ<br>
            <span class="timeline-time">{html.escape(display_datetime(record.get("picked_at")))}</span>
            <div>ระยะเวลาจัด: {html.escape(format_duration(record.get("processing_minutes")))}</div>
          </div>
          <div class="timeline-step">
            🟢 PD มารับสินค้า<br>
            <span class="timeline-time">{html.escape(display_datetime(record.get("handover_at")))}</span>
            <div>ระยะเวลารอรับ: {html.escape(format_duration(record.get("waiting_minutes")))}</div>
          </div>
          {cancel_html}
          <div class="subtle">เวลาอ้างอิง Asia/Bangkok · ผู้บันทึก: Admin</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("จับภาพหน้าจอหรือใช้คำสั่งพิมพ์ของเบราว์เซอร์เพื่อส่งเป็นหลักฐาน")


# ── Login ─────────────────────────────────────────────────────────────────────
try:
    init_db()
except sqlite3.OperationalError as error:
    st.error(f"เตรียมฐานข้อมูลไม่สำเร็จ: {error}")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown(
        """
        <div class="login-card">
          <div class="eyebrow">SMART WAREHOUSE</div>
          <h1>📦 เข้าสู่ระบบ</h1>
          <div class="subtle">ระบบติดตามใบเบิกและวิเคราะห์งานคลังสินค้า</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, center, _ = st.columns([1, 1.15, 1])
    with center:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button(
                "เข้าสู่ระบบ", type="primary", use_container_width=True
            )
        if submitted:
            if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
                st.session_state["authenticated"] = True
                st.session_state["display_name"] = DISPLAY_NAME
                st.rerun()
            st.error("Username หรือ Password ไม่ถูกต้อง")
    st.stop()


# ── Sidebar และ Topbar ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 SMART WAREHOUSE")
    st.caption("BUSINESS MANAGEMENT SYSTEM")
    st.markdown("---")
    st.markdown(f"👤 **{DISPLAY_NAME}**")
    st.caption("Administrator")
    page = st.radio(
        "เมนูหลัก",
        [
            "📊 Dashboard",
            "📝 บันทึกใบเบิก",
            "⚙️ จัดการสถานะ",
            "📄 ประวัติ / Reports",
        ],
        key="main_navigation",
        label_visibility="collapsed",
    )
    st.markdown("---")
    if st.button("ออกจากระบบ", key="logout_button", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state.pop("display_name", None)
        st.rerun()

st.markdown(
    """
    <div class="topbar">
      <div class="brand">SMART WAREHOUSE</div>
      <div class="profile">● Administrator</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.session_state.pop("play_success_tick", False):
    play_success_sound()

show_live_clock()

try:
    data = load_data()
except (sqlite3.OperationalError, pd.errors.DatabaseError) as error:
    st.error(f"อ่านฐานข้อมูลไม่สำเร็จ: {error}")
    st.stop()


# ── หน้า 1: Dashboard ─────────────────────────────────────────────────────────
if page == "📊 Dashboard":
    heading("ภาพรวมคลังสินค้า", "ติดตามปริมาณงาน ระยะเวลาจัด และใบเบิกเย็น")
    filtered = filter_data(data, "dashboard")

    if filtered.empty:
        st.info("ยังไม่มีข้อมูลใบเบิก")
    else:
        total = len(filtered)
        today = now_bangkok().date()
        today_count = int((filtered["received_at"].dt.date == today).sum())
        late_count = int(filtered["late"].sum())
        pending_count = int(filtered["status"].eq("กำลังจัด").sum())

        processing_values = filtered["processing_minutes"].dropna().tolist()
        average_processing = (
            sum(processing_values) / len(processing_values)
            if processing_values else 0
        )
        waiting_values = filtered["waiting_minutes"].dropna().tolist()
        average_waiting = (
            sum(waiting_values) / len(waiting_values)
            if waiting_values else 0
        )

        cards = st.columns(4)
        cards[0].metric("รวมใบเบิก", f"{total:,}", f"วันนี้ {today_count:,} JOB")
        cards[1].metric("จุดคอขวด · รอจัด", f"{pending_count:,}", "JOB")
        cards[2].metric("เวลาจัดเฉลี่ย", format_duration(average_processing))
        cards[3].metric(
            "ใบเบิกเย็น",
            f"{late_count / total * 100:.1f}%",
            f"{late_count:,} JOB",
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🍩 สัดส่วนใบเบิกปกติและใบเบิกเย็น")
            mix = pd.DataFrame(
                {
                    "ประเภทใบเบิก": ["ใบเบิกปกติ", "ใบเบิกเย็น"],
                    "จำนวน": [max(total - late_count, 0), late_count],
                }
            )

            def donut_chart(frame):
                fig = px.pie(
                    frame,
                    names="ประเภทใบเบิก",
                    values="จำนวน",
                    hole=.62,
                    color="ประเภทใบเบิก",
                    color_discrete_map={
                        "ใบเบิกปกติ": "#16a34a",
                        "ใบเบิกเย็น": "#dc2626",
                    },
                )
                fig.update_traces(
                    textinfo="label+percent",
                    textposition="inside",
                    hovertemplate="%{label}<br>%{value} JOB (%{percent})<extra></extra>",
                )
                fig.update_layout(
                    height=330, margin=dict(l=10, r=10, t=20, b=10),
                    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
                    font_color="#1e293b", legend_title_text="",
                )
                return fig

            render_plotly_or_info(
                mix, ["ประเภทใบเบิก", "จำนวน"], donut_chart, "dashboard_donut"
            )

        with col2:
            st.markdown("#### 🕒 จำนวนใบเบิกตามชั่วโมง")
            hourly = pd.DataFrame()
            if "received_at" in filtered.columns:
                source = filtered.dropna(subset=["received_at"])
                if not source.empty:
                    hourly = (
                        source.assign(ชั่วโมง=source["received_at"].dt.hour)
                        .groupby("ชั่วโมง", as_index=False)
                        .size()
                        .rename(columns={"size": "จำนวน JOB"})
                    )
                    if not hourly.empty:
                        hourly = (
                            hourly.set_index("ชั่วโมง")
                            .reindex(range(24), fill_value=0)
                            .rename_axis("ชั่วโมง")
                            .reset_index()
                        )

            def hourly_chart(frame):
                fig = px.bar(
                    frame, x="ชั่วโมง", y="จำนวน JOB", color="จำนวน JOB",
                    color_continuous_scale=["#bfdbfe", "#2563eb"],
                )
                fig.update_layout(
                    height=330, margin=dict(l=10, r=10, t=20, b=10),
                    plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                    font_color="#1e293b", coloraxis_showscale=False,
                )
                fig.update_xaxes(dtick=1, title="ชั่วโมงที่รับใบเบิก")
                fig.update_yaxes(title="จำนวน JOB", rangemode="tozero")
                return fig

            render_plotly_or_info(
                hourly, ["ชั่วโมง", "จำนวน JOB"], hourly_chart, "dashboard_hourly"
            )

        st.markdown("#### 📋 รายการใบเบิก")
        display_table(filtered, "dashboard_table")


# ── หน้า 2: บันทึกใบเบิก ─────────────────────────────────────────────────────
elif page == "📝 บันทึกใบเบิก":
    heading("บันทึกใบเบิก", "วางหรือกรอกเลข JOB พร้อมบันทึกเวลารับเอกสาร")
    st.caption(
        f"Cut-off {CUTOFF_TIME.strftime('%H:%M')} น. · "
        "ใบเบิกหลังเวลานี้จะติดแท็กใบเบิกเย็น"
    )

    current = now_bangkok()
    date_col, time_col = st.columns(2)
    received_date = date_col.date_input(
        "วันที่รับใบเบิก", value=current.date(), key="new_received_date"
    )
    received_time = time_col.time_input(
        "เวลารับใบเบิก",
        value=current.time().replace(microsecond=0),
        key="new_received_time",
    )
    received_at = parse_local_datetime(received_date, received_time)

    if "last_department" not in st.session_state:
        st.session_state["last_department"] = "PD"
    if "last_production_line" not in st.session_state:
        st.session_state["last_production_line"] = "L1"

    default_col, line_col = st.columns(2)
    with default_col:
        default_department = st.selectbox(
            "แผนกเริ่มต้นสำหรับรายการที่วาง",
            DEPARTMENTS,
            key="last_department",
            accept_new_options=True,
        )
    default_line = ""
    with line_col:
        if default_department == "PD":
            previous_line = st.session_state.get("last_production_line", "L1")
            line_index = (
                PRODUCTION_LINES.index(previous_line)
                if previous_line in PRODUCTION_LINES else 0
            )
            default_line = st.selectbox(
                "ไลน์ผลิตเริ่มต้น (PD)",
                PRODUCTION_LINES,
                index=line_index,
                key="last_production_line",
            )
        else:
            st.caption("แผนกอื่นไม่ต้องระบุไลน์ผลิต")

    st.markdown("#### 📋 Bulk Copy-Paste")
    st.caption(
        "วาง JOB ทีละบรรทัด หรือวางจาก Excel แบบ Tab-separated: "
        "เลข JOB / แผนก / รายการสินค้า / จำนวน / ไลน์ผลิต"
    )
    bulk_text = st.text_area(
        "รายการ JOB",
        height=150,
        placeholder="JOB-6901\nJOB-6902\n\nหรือวางหลายคอลัมน์จาก Excel",
        key="bulk_job_text",
    )

    st.markdown("#### ⌨️ เพิ่ม JOB ด้วยตนเอง")
    manual_count = st.number_input(
        "จำนวนแถวกรอกเอง",
        min_value=0,
        max_value=10,
        value=2,
        step=1,
        key="manual_job_count",
    )
    manual_rows = []

    for index in range(int(manual_count)):
        cols = st.columns([1.1, 1.2, .9, 1.2, .7])
        job = cols[0].text_input(
            "เลข JOB", key=f"manual_job_{index}", placeholder="เช่น JOB-6901"
        )
        dept = cols[1].selectbox(
            "แผนก",
            DEPARTMENTS,
            index=DEPARTMENTS.index(default_department)
            if default_department in DEPARTMENTS else 0,
            key=f"manual_department_{index}",
            accept_new_options=True,
        )
        if dept == "PD":
            previous_line = st.session_state.get("last_production_line", "L1")
            line_index = (
                PRODUCTION_LINES.index(previous_line)
                if previous_line in PRODUCTION_LINES else 0
            )
            line = cols[2].selectbox(
                "ไลน์ผลิต",
                PRODUCTION_LINES,
                index=line_index,
                key=f"manual_line_{index}",
            )
        else:
            line = ""
            cols[2].caption("ไม่ต้องระบุไลน์")

        item = cols[3].text_input("รายการสินค้า", key=f"manual_item_{index}")
        quantity = cols[4].number_input(
            "จำนวน", min_value=0, value=0, step=1,
            key=f"manual_quantity_{index}",
        )
        manual_rows.append((job, dept, line, item, quantity))

    if st.button(
        "✅ บันทึกรับเรื่องทั้งหมด",
        type="primary",
        use_container_width=True,
        key="save_all_requisitions",
    ):
        if received_at is None:
            st.error("กรุณาระบุวันที่และเวลารับใบเบิกให้ถูกต้อง")
        else:
            entries = []
            for raw_line in bulk_text.splitlines():
                raw_line = raw_line.strip()
                if not raw_line:
                    continue

                if "\t" in raw_line:
                    parts = [part.strip() for part in raw_line.split("\t")]
                elif "|" in raw_line:
                    parts = [part.strip() for part in raw_line.split("|")]
                elif "," in raw_line:
                    parts = [part.strip() for part in raw_line.split(",")]
                else:
                    parts = [raw_line]

                job = parts[0].strip()
                if job.lower() in {"job", "เลข job", "เลขที่ job", "job number"}:
                    continue

                department = (
                    parts[1] if len(parts) > 1 and parts[1] else default_department
                )
                item = parts[2] if len(parts) > 2 else ""
                quantity = 0
                if len(parts) > 3:
                    try:
                        quantity = int(float(parts[3].replace(",", "")))
                    except (ValueError, TypeError):
                        quantity = 0

                pasted_line = parts[4] if len(parts) > 4 else ""
                line = ""
                if department == "PD":
                    line = (
                        pasted_line
                        if pasted_line in PRODUCTION_LINES
                        else default_line
                    )
                entries.append((job, department, line, item, quantity))

            for job, department, line, item, quantity in manual_rows:
                if str(job).strip():
                    entries.append((str(job).strip(), department, line, item, quantity))

            if not entries:
                st.warning("กรุณาวางหรือกรอกเลข JOB อย่างน้อย 1 รายการ")
            else:
                saved, errors = 0, []
                for job, department, line, item, quantity in entries:
                    department = str(department).strip()
                    line_to_save = line if department == "PD" else ""

                    if department == "PD" and line_to_save not in PRODUCTION_LINES:
                        errors.append(f"JOB {job}: กรุณาเลือกไลน์ผลิต L1-L10")
                        continue

                    try:
                        ok, message = insert_requisition(
                            str(job).strip(),
                            department,
                            line_to_save,
                            str(item).strip(),
                            quantity if quantity > 0 else None,
                            received_at,
                        )
                    except sqlite3.OperationalError as error:
                        ok, message = False, f"JOB {job}: บันทึกไม่สำเร็จ ({error})"

                    if ok:
                        saved += 1
                    else:
                        errors.append(message)

                if saved:
                    st.success(f"บันทึกสำเร็จ {saved} JOB")
                for message in errors:
                    st.warning(message)
                if saved:
                    st.rerun()


# ── หน้า 3: จัดการสถานะ ──────────────────────────────────────────────────────
elif page == "⚙️ จัดการสถานะ":
    heading("จัดการสถานะ", "ลงเวลาจัดเสร็จ PD รับสินค้า หรือยกเลิก JOB")
    active = data[data["status"] != "ยกเลิก"] if not data.empty else data

    if active.empty:
        st.info("ยังไม่มีข้อมูลใบเบิกให้จัดการ")
    else:
        ids = active["id"].tolist()
        labels = {
            int(row["id"]): (
                f'{row["job_number"]} · {row["department"] or "ไม่ระบุ"} · '
                f'{job_status(row)}'
            )
            for _, row in active.iterrows()
        }
        selected_id = st.selectbox(
            "เลือก JOB",
            ids,
            format_func=lambda value: labels[int(value)],
            key="manage_selected_job",
        )
        record = active[active["id"] == selected_id].iloc[0]
        job_key = str(int(selected_id))

        st.markdown(
            f'<div class="section-card"><b>JOB {html.escape(str(record["job_number"]))}</b>'
            f'　·　{html.escape(str(record["department"] or "ไม่ระบุ"))}'
            f'　·　{job_status(record)}</div>',
            unsafe_allow_html=True,
        )

        def record_date(value):
            parsed = as_bangkok(value)
            return parsed.date() if parsed else now_bangkok().date()

        def record_time(value):
            parsed = as_bangkok(value)
            return parsed.time().replace(microsecond=0) if parsed else time(0, 0)

        picked_enabled_key = f"picked_enabled_{job_key}"
        handover_enabled_key = f"handover_enabled_{job_key}"
        picked_date_key = f"picked_date_{job_key}"
        picked_time_key = f"picked_time_{job_key}"
        handover_date_key = f"handover_date_{job_key}"
        handover_time_key = f"handover_time_{job_key}"

        if picked_enabled_key not in st.session_state:
            st.session_state[picked_enabled_key] = pd.notna(record["picked_at"])
        if handover_enabled_key not in st.session_state:
            st.session_state[handover_enabled_key] = pd.notna(record["handover_at"])
        if picked_date_key not in st.session_state:
            st.session_state[picked_date_key] = record_date(record["picked_at"])
        if picked_time_key not in st.session_state:
            st.session_state[picked_time_key] = record_time(record["picked_at"])
        if handover_date_key not in st.session_state:
            st.session_state[handover_date_key] = record_date(record["handover_at"])
        if handover_time_key not in st.session_state:
            st.session_state[handover_time_key] = record_time(record["handover_at"])

        left, right = st.columns(2)
        with left:
            st.markdown("#### 📦 เวลาจัดเสร็จ")
            st.checkbox(
                "บันทึกเวลาจัดเสร็จแล้ว",
                key=picked_enabled_key,
            )
            st.button(
                "⏱️ ลงเวลาปัจจุบัน",
                key=f"auto_picked_{job_key}",
                on_click=set_timestamp,
                args=(picked_date_key, picked_time_key, picked_enabled_key),
            )
            picked_date = st.date_input("วันที่จัดเสร็จ", key=picked_date_key)
            picked_time = st.time_input("เวลาจัดเสร็จ", key=picked_time_key)

        with right:
            st.markdown("#### 🟢 PD มารับสินค้า")
            st.checkbox(
                "บันทึกเวลาที่ PD รับแล้ว",
                key=handover_enabled_key,
            )
            st.button(
                "⏱️ ลงเวลาปัจจุบัน",
                key=f"auto_handover_{job_key}",
                on_click=set_timestamp,
                args=(handover_date_key, handover_time_key, handover_enabled_key),
            )
            handover_date = st.date_input(
                "วันที่ PD รับสินค้า", key=handover_date_key
            )
            handover_time = st.time_input(
                "เวลา PD รับสินค้า", key=handover_time_key
            )

        received_at = as_bangkok(record["received_at"])
        picked_at = (
            parse_local_datetime(picked_date, picked_time)
            if st.session_state[picked_enabled_key] else None
        )
        handover_at = (
            parse_local_datetime(handover_date, handover_time)
            if st.session_state[handover_enabled_key] else None
        )

        if picked_at:
            st.caption(
                "เวลาจัด: " + format_duration(duration_minutes(received_at, picked_at))
            )
        if picked_at and handover_at:
            st.caption(
                "เวลารอ PD: " + format_duration(duration_minutes(picked_at, handover_at))
            )

        if st.button(
            "💾 บันทึกการอัปเดตสถานะ",
            type="primary",
            use_container_width=True,
            key=f"save_status_{job_key}",
        ):
            if handover_at and not picked_at:
                st.error("กรุณาระบุเวลาจัดเสร็จก่อนเวลาที่ PD มารับ")
            elif picked_at and duration_minutes(received_at, picked_at) is None:
                st.error("เวลาจัดเสร็จต้องไม่อยู่ก่อนเวลารับใบเบิก")
            elif handover_at and duration_minutes(picked_at, handover_at) is None:
                st.error("เวลา PD รับสินค้าต้องไม่อยู่ก่อนเวลาจัดเสร็จ")
            else:
                try:
                    update_requisition(
                        int(selected_id),
                        record["department"],
                        record["line"],
                        record["item_name"],
                        record["quantity"],
                        received_at,
                        picked_at,
                        handover_at,
                    )
                    st.session_state["play_success_tick"] = True
                    st.success("บันทึกเวลาเรียบร้อย")
                    st.rerun()
                except (ValueError, sqlite3.OperationalError) as error:
                    st.error(f"บันทึกไม่สำเร็จ: {error}")

        with st.expander("✏️ แก้ไขรายละเอียด JOB"):
            old_department = str(record["department"] or DEPARTMENTS[0])
            department_options = DEPARTMENTS.copy()
            if old_department not in department_options:
                department_options.insert(0, old_department)

            edit_department = st.selectbox(
                "แผนก",
                department_options,
                index=department_options.index(old_department),
                key=f"edit_department_{job_key}",
                accept_new_options=True,
            )

            edit_line = ""
            if edit_department == "PD":
                old_line = str(record["line"] or "L1")
                line_index = (
                    PRODUCTION_LINES.index(old_line)
                    if old_line in PRODUCTION_LINES else 0
                )
                edit_line = st.selectbox(
                    "ไลน์ผลิต (จำเป็นสำหรับ PD)",
                    PRODUCTION_LINES,
                    index=line_index,
                    key=f"edit_line_{job_key}",
                )

            edit_item = st.text_input(
                "รายการสินค้า",
                value=str(record["item_name"] or ""),
                key=f"edit_item_{job_key}",
            )
            edit_quantity = st.number_input(
                "จำนวน",
                min_value=0,
                value=int(record["quantity"]) if pd.notna(record["quantity"]) else 0,
                step=1,
                key=f"edit_quantity_{job_key}",
            )

            if st.button("บันทึกการแก้ไข", key=f"save_edit_{job_key}"):
                line_to_save = edit_line if edit_department == "PD" else ""
                try:
                    update_requisition(
                        int(selected_id),
                        str(edit_department).strip(),
                        line_to_save,
                        edit_item,
                        edit_quantity if edit_quantity > 0 else None,
                        received_at,
                        picked_at,
                        handover_at,
                    )
                    st.success("อัปเดตรายละเอียดแล้ว")
                    st.rerun()
                except (ValueError, sqlite3.OperationalError) as error:
                    st.error(f"อัปเดตไม่สำเร็จ: {error}")

        with st.expander("🔴 ยกเลิก JOB"):
            cancel_by = st.text_input(
                "ผู้สั่งยกเลิก (PN/PD) *",
                key=f"cancel_by_{job_key}",
            )
            cancel_reason = st.text_area(
                "สาเหตุการยกเลิก *",
                key=f"cancel_reason_{job_key}",
            )
            confirm_cancel = st.checkbox(
                "ยืนยันการยกเลิก JOB นี้",
                key=f"confirm_cancel_{job_key}",
            )
            can_cancel = bool(
                cancel_by.strip() and cancel_reason.strip() and confirm_cancel
            )

            if st.button(
                "🔴 บันทึกยกเลิก JOB",
                disabled=not can_cancel,
                key=f"cancel_button_{job_key}",
            ):
                try:
                    cancel_requisition(int(selected_id), cancel_by, cancel_reason)
                    st.success("ยกเลิก JOB แล้ว")
                    st.rerun()
                except sqlite3.OperationalError as error:
                    st.error(f"ยกเลิกไม่สำเร็จ: {error}")


# ── หน้า 4: ประวัติ รายงาน และตั้งค่า ────────────────────────────────────────
elif page == "📄 ประวัติ / Reports":
    heading("ประวัติและรายงาน", "ค้นหา JOB ดาวน์โหลดไฟล์ และเปิด Timeline")
    history = filter_data(data, "history")

    if history.empty:
        st.info("ยังไม่มีข้อมูลใบเบิก")
    else:
        display_table(history, "history_table")

        excel_col, csv_col = st.columns(2)
        with excel_col:
            st.download_button(
                "📥 ดาวน์โหลด Excel (.xlsx)",
                data=make_excel(history),
                file_name="รายงานสรุปการเบิกสินค้า_คลังสินค้า.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="download_excel",
            )
        with csv_col:
            st.download_button(
                "📄 ดาวน์โหลด CSV",
                data=make_csv(history),
                file_name="รายงานสรุปการเบิกสินค้า_คลังสินค้า.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_csv",
            )

        eligible = history[
            history["late"].fillna(False) | history["status"].eq("ยกเลิก")
        ]
        if not eligible.empty:
            st.markdown("#### 📄 พิมพ์หลักฐาน / สรุป Timeline")
            st.caption("แสดงรายการใบเบิกเย็นและงานที่ถูกยกเลิก")
            for _, row in eligible.iterrows():
                record_id = int(row["id"])
                label = (
                    f'📄 เปิด Timeline · {row["job_number"]} · '
                    f'{row["department"] or "ไม่ระบุ"}'
                )
                if st.button(
                    label,
                    key=f"timeline_button_{record_id}",
                    use_container_width=True,
                ):
                    st.session_state["timeline_record_id"] = record_id

        timeline_id = st.session_state.get("timeline_record_id")
        if timeline_id is not None:
            selected = history[history["id"] == timeline_id]
            if not selected.empty:
                show_timeline_dialog(selected.iloc[0].to_dict())

        st.caption(f"แสดง {len(history):,} รายการ")

    with st.expander("⚙️ ตั้งค่าระบบ"):
        st.markdown("### SMART WAREHOUSE")
        st.write("เวอร์ชันระบบ: **1.0**")
        st.write(f"Cut-off ใบเบิก: **{CUTOFF_TIME.strftime('%H:%M')} น.**")
        st.write("เขตเวลา: **Asia/Bangkok (UTC+7)**")
        st.write(f"ผู้ใช้งานปัจจุบัน: **{DISPLAY_NAME}**")
        st.write("ฐานข้อมูล: **SQLite**")


st.markdown(
    '<div class="footer">SMART WAREHOUSE © 2026 | BUSINESS MANAGEMENT SYSTEM</div>',
    unsafe_allow_html=True,
)
