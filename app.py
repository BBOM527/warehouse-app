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
    page_title="Warehouse Flow",
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


# ── Modern Enterprise UI ──────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700&display=swap');

    :root { --ink:#172033; --muted:#64748b; --line:#e2e8f0; --canvas:#f8fafc; }
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family:'Kanit',sans-serif; color:var(--ink);
    }
    [data-testid="stAppViewContainer"] {
        background:radial-gradient(ellipse at 4% 0%,rgba(14,165,233,.07),transparent 32%),
        radial-gradient(ellipse at 96% 5%,rgba(16,185,129,.07),transparent 28%),var(--canvas);
    }
    [data-testid="stHeader"] { background:rgba(248,250,252,.78); }
    [data-testid="stSidebar"] {
        background:linear-gradient(180deg,#101827 0%,#172033 100%);
        border-right:1px solid rgba(255,255,255,.08);
    }
    [data-testid="stSidebar"] * { color:#e2e8f0; }
    [data-testid="stMetric"] {
        background:#fff; border:1px solid var(--line); border-radius:16px;
        padding:18px 20px; box-shadow:0 10px 30px rgba(0,0,0,.05);
    }
    [data-testid="stMetricLabel"] { color:var(--muted); }
    [data-testid="stMetricValue"] { color:var(--ink); font-weight:600; }
    [data-testid="stForm"], [data-testid="stExpander"], [data-testid="stDataFrame"],
    [data-testid="stDialog"] {
        border:1px solid var(--line); border-radius:16px;
        box-shadow:0 10px 30px rgba(0,0,0,.05); overflow:hidden; background:#fff;
    }
    [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input, [data-testid="stTimeInput"] input,
    [data-testid="stSelectbox"] [data-baseweb="select"]>div,
    [data-testid="stTextArea"] textarea { border-radius:12px; }
    [data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button,
    [data-testid="stDownloadButton"] button {
        border-radius:12px; font-family:'Kanit',sans-serif; font-weight:500;
        transition:transform .18s ease,box-shadow .18s ease,filter .18s ease;
    }
    [data-testid="stButton"] button[kind="primary"],
    [data-testid="stFormSubmitButton"] button {
        background:linear-gradient(115deg,#059669,#0284c7); color:#fff;
        border:0; box-shadow:0 7px 18px rgba(2,132,199,.2);
    }
    [data-testid="stButton"] button:hover,
    [data-testid="stFormSubmitButton"] button:hover,
    [data-testid="stDownloadButton"] button:hover {
        transform:translateY(-2px); box-shadow:0 10px 22px rgba(15,23,42,.12);
        filter:brightness(1.03);
    }
    .page-heading { margin:.25rem 0 1.2rem; }
    .page-heading h1 { margin:0; font-weight:600; letter-spacing:-.02em; }
    .eyebrow { color:#0284c7; letter-spacing:.12em; font-size:.76rem; font-weight:600; }
    .subtle { color:var(--muted); }
    .clock-card {
        display:flex; justify-content:space-between; align-items:center; gap:1rem;
        background:rgba(255,255,255,.88); border:1px solid var(--line);
        border-radius:16px; padding:12px 18px; margin-bottom:1.2rem;
        box-shadow:0 10px 30px rgba(0,0,0,.05);
    }
    .clock-time { font-size:1.15rem; font-weight:600; color:#0f766e; }
    .clock-date { color:var(--muted); font-size:.9rem; }
    .section-card {
        background:#fff; border:1px solid var(--line); border-radius:16px;
        padding:18px 20px; box-shadow:0 10px 30px rgba(0,0,0,.05);
        margin-bottom:1rem;
    }
    .timeline-card {
        background:#fff; border:1px solid #e2e8f0; border-radius:16px;
        padding:18px 20px; margin:10px 0; box-shadow:0 8px 24px rgba(15,23,42,.06);
    }
    .timeline-step {
        border-left:3px solid #38bdf8; padding:4px 0 12px 14px; margin:0 0 8px 4px;
    }
    .timeline-step.danger { border-left-color:#ef4444; }
    .timeline-time { color:#0f766e; font-weight:600; }
    .login-wrap {
        max-width:480px; margin:8vh auto 0; padding:2rem; background:#fff;
        border:1px solid var(--line); border-radius:20px;
        box-shadow:0 20px 50px rgba(15,23,42,.09);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── วันที่ เวลา และฐานข้อมูล ─────────────────────────────────────────────────
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


def parse_local_datetime(date_value, time_value):
    if not date_value or not time_value:
        return None
    try:
        return BANGKOK.localize(datetime.combine(date_value, time_value))
    except (TypeError, ValueError):
        return None


def display_datetime(value):
    parsed = as_bangkok(value)
    return parsed.strftime("%d/%m/%Y %H:%M:%S") if parsed else "—"


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


def init_db():
    """สร้างตารางและเพิ่มคอลัมน์ที่ขาด พร้อมย้ายข้อมูลจาก schema เก่า."""
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

        # ย้ายข้อมูลเดิมก่อนเติมค่าเริ่มต้น
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
        for target, source_names in aliases.items():
            for source in source_names:
                if target in columns and source in columns and source != target:
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
        df = pd.read_sql_query(
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

    if not df.empty:
        df["line"] = df["line"].fillna("")
        no_line = df["line"].eq("")
        df.loc[no_line, "line"] = df.loc[no_line, "production_line"].fillna("")
        df["picked_at"] = df["picked_at"].where(
            df["picked_at"].notna() & df["picked_at"].ne(""),
            df["completed_at"],
        )

        for column in (
            "received_at", "started_at", "picked_at",
            "handover_at", "cancelled_at", "updated_at",
        ):
            df[column] = pd.to_datetime(
                df[column], errors="coerce", utc=True
            ).dt.tz_convert("Asia/Bangkok")

        df["processing_minutes"] = df.apply(
            lambda row: duration_minutes(row["received_at"], row["picked_at"]),
            axis=1,
        )
        df["waiting_minutes"] = df.apply(
            lambda row: duration_minutes(row["picked_at"], row["handover_at"]),
            axis=1,
        )
        df["late"] = df["received_at"].apply(
            lambda value: bool(
                pd.notna(value)
                and value.time().replace(tzinfo=None) > CUTOFF_TIME
            )
        )
    return df


def insert_requisition(job_number, department, line, item_name, quantity, received_at):
    # เฉพาะแผนก PD เท่านั้นที่เก็บค่าไลน์ L1-L10 ได้
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


# ── Excel export: เลือกเฉพาะคอลัมน์สำคัญ ภาษาไทย และ Auto-fit ──────────────────
def make_excel(df):
    export = pd.DataFrame(index=df.index)

    export["เลขที่ Job"] = df["job_number"].fillna("").astype(str)
    export["วันเวลาที่เบิก"] = df["received_at"].apply(display_datetime)
    export["แผนกที่เบิก"] = df["department"].fillna("").astype(str)
    export["ไลน์ผลิต"] = df["line"].fillna("").astype(str)
    export["รายการสินค้า"] = df["item_name"].fillna("").astype(str)
    export["จำนวน"] = df["quantity"].apply(
        lambda value: "" if pd.isna(value) else value
    )
    export["สถานะปัจจุบัน"] = df.apply(job_status, axis=1)
    export["เวลาจัดเสร็จ"] = df["picked_at"].apply(display_datetime)
    export["เวลา PD มารับ"] = df["handover_at"].apply(display_datetime)
    export["ระยะเวลาจัดสินค้า (นาที)"] = df["processing_minutes"].apply(
        lambda value: "" if pd.isna(value) else round(float(value), 1)
    )
    export["ระยะเวลารอรับสินค้า (นาที)"] = df["waiting_minutes"].apply(
        lambda value: "" if pd.isna(value) else round(float(value), 1)
    )

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="รายงานการเบิก")
        worksheet = writer.sheets["รายงานการเบิก"]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        worksheet.row_dimensions[1].height = 30

        header_fill = PatternFill("solid", fgColor="123047")
        header_font = Font(name="Aptos", bold=True, color="FFFFFF", size=11)
        body_font = Font(name="Aptos", size=10)

        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="center", vertical="center", wrap_text=True
            )

        for column_cells in worksheet.columns:
            letter = get_column_letter(column_cells[0].column)
            longest = 0
            for cell in column_cells:
                cell.font = header_font if cell.row == 1 else body_font
                if cell.row > 1:
                    cell.alignment = Alignment(vertical="center")
                text = "" if cell.value is None else str(cell.value)
                longest = max(longest, len(text))
            worksheet.column_dimensions[letter].width = min(max(longest + 3, 12), 42)

    buffer.seek(0)
    return buffer.getvalue()


# ── Timeline slip dialog ──────────────────────────────────────────────────────
@st.dialog("📄 หลักฐานและ Timeline ใบเบิก")
def show_timeline_dialog(record):
    job_number = html.escape(str(record.get("job_number", "")))
    department = html.escape(str(record.get("department") or "ไม่ระบุ"))
    line = html.escape(str(record.get("line") or "—"))
    item = html.escape(str(record.get("item_name") or "—"))
    status = html.escape(str(job_status(record)))
    is_cancelled = str(record.get("status", "")) == "ยกเลิก"

    received = display_datetime(record.get("received_at"))
    picked = display_datetime(record.get("picked_at"))
    handover = display_datetime(record.get("handover_at"))
    cancelled = display_datetime(record.get("cancelled_at"))
    processing = format_duration(record.get("processing_minutes"))
    waiting = format_duration(record.get("waiting_minutes"))

    cancelled_by = html.escape(str(record.get("cancelled_by") or "—"))
    cancel_reason = html.escape(str(record.get("cancel_reason") or "—"))

    timeline_html = f"""
    <div class="timeline-card">
      <div style="color:#0284c7;font-size:.78rem;letter-spacing:.1em">
        WAREHOUSE DOCUMENT EVIDENCE
      </div>
      <h2 style="margin:.25rem 0">JOB {job_number}</h2>
      <div>แผนก: <b>{department}</b>　ไลน์: <b>{line}</b></div>
      <div>รายการ: {item}</div>
      <div>สถานะ: <b>{status}</b></div>
      <hr style="border:0;border-top:1px solid #e2e8f0;margin:16px 0">
      <div class="timeline-step">
        📥 รับเอกสาร<br><span class="timeline-time">{received}</span>
      </div>
      <div class="timeline-step">
        📦 จัดเสร็จ<br><span class="timeline-time">{picked}</span>
        <div>ระยะเวลาจัด: {html.escape(processing)}</div>
      </div>
      <div class="timeline-step">
        🟢 PD มารับสินค้า<br><span class="timeline-time">{handover}</span>
        <div>ระยะเวลารอรับ: {html.escape(waiting)}</div>
      </div>
      {"<div class='timeline-step danger'>🔴 ยกเลิก<br><span class='timeline-time'>" + html.escape(cancelled) + "</span><div>ผู้สั่งยกเลิก: " + cancelled_by + "</div><div>สาเหตุ: " + cancel_reason + "</div></div>" if is_cancelled else ""}
      <div style="color:#64748b;font-size:.84rem;margin-top:12px">
        เวลาอ้างอิง Asia/Bangkok · ผู้บันทึก: Admin
      </div>
    </div>
    """
    st.markdown(timeline_html, unsafe_allow_html=True)
    st.caption("ใช้ปุ่มพิมพ์ของเบราว์เซอร์หรือจับภาพหน้าจอเพื่อส่งเป็นหลักฐาน")


# ── Dashboard helpers ─────────────────────────────────────────────────────────
def render_plotly_or_info(frame, required_columns, chart_builder, chart_key):
    if (
        frame is None
        or not isinstance(frame, pd.DataFrame)
        or frame.empty
        or len(frame) == 0
        or any(column not in frame.columns for column in required_columns)
    ):
        st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")
        return
    try:
        fig = chart_builder(frame)
        st.plotly_chart(fig, use_container_width=True, key=chart_key)
    except (ValueError, KeyError, TypeError, ZeroDivisionError):
        st.info("ℹ️ ยังไม่มีข้อมูลสำหรับแสดงกราฟ")


# ── Login และเมนู ─────────────────────────────────────────────────────────────
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
        <div class="login-wrap">
          <div class="eyebrow">WAREHOUSE FLOW</div>
          <h1 style="margin:.25rem 0">📦 เข้าสู่ระบบ</h1>
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

with st.sidebar:
    st.markdown("## 📦 Warehouse Flow")
    st.caption("DOCUMENT TRACKING")
    st.markdown("---")
    st.markdown(f"👤 **{DISPLAY_NAME}**")
    st.caption("ผู้ดูแลระบบ")
    page = st.radio(
        "เมนูหลัก",
        [
            "📝 บันทึกใบเบิก",
            "📊 Dashboard",
            "✏️ จัดการ / อัปเดตสถานะ",
            "📋 ประวัติ & Export",
        ],
        key="main_navigation",
        label_visibility="collapsed",
    )
    st.markdown("---")
    if st.button("ออกจากระบบ", key="logout_button", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state.pop("display_name", None)
        st.rerun()

# เล่นเสียงติ๊กหลังจากการบันทึกสถานะสำเร็จ
if st.session_state.pop("play_success_tick", False):
    components.html(
        """
        <script>
        try {
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "sine";
          osc.frequency.setValueAtTime(880, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(520, ctx.currentTime + 0.045);
          gain.gain.setValueAtTime(0.12, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start();
          osc.stop(ctx.currentTime + 0.05);
        } catch (e) {}
        </script>
        """,
        height=0,
    )

components.html(
    """
    <div class="clock-card">
      <div>
        <div style="font-weight:600;color:#172033">🕒 เวลาประเทศไทย</div>
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

try:
    data = load_data()
except (sqlite3.OperationalError, pd.errors.DatabaseError) as error:
    st.error(f"อ่านฐานข้อมูลไม่สำเร็จ: {error}")
    st.stop()


# ── หน้า 1: บันทึกใบเบิก ─────────────────────────────────────────────────────
if page == "📝 บันทึกใบเบิก":
    st.markdown(
        '<div class="eyebrow">WAREHOUSE FLOW · CONTROL CENTER</div>'
        "<h1>บันทึกใบเบิก</h1>"
        '<div class="subtle">รับงานระดับ JOB พร้อมเวลารับเอกสาร</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Cut-off เวลา {CUTOFF_TIME.strftime('%H:%M')} น. "
        "ระบบติดแท็กใบเบิกเย็นเมื่อรับเอกสารหลังเวลานี้"
    )

    current = now_bangkok()
    date_col, time_col = st.columns(2)
    received_date = date_col.date_input(
        "วันที่รับใบเบิก", value=current.date(), key="bulk_received_date"
    )
    received_time = time_col.time_input(
        "เวลารับใบเบิก",
        value=current.time().replace(microsecond=0),
        key="bulk_received_time",
    )
    received_at = parse_local_datetime(received_date, received_time)

    # จำแผนกและไลน์ล่าสุดเพื่อช่วยลดการเลือกซ้ำ
    if "last_department" not in st.session_state:
        st.session_state["last_department"] = "PD"
    if "last_production_line" not in st.session_state:
        st.session_state["last_production_line"] = "L1"

    default_col, line_col = st.columns([1, 1])
    with default_col:
        last_department = st.selectbox(
            "แผนกเริ่มต้นสำหรับรายการที่วาง",
            DEPARTMENTS,
            key="last_department",
            accept_new_options=True,
        )
    default_line = ""
    with line_col:
        if last_department == "PD":
            current_line = st.session_state.get("last_production_line", "L1")
            line_index = (
                PRODUCTION_LINES.index(current_line)
                if current_line in PRODUCTION_LINES else 0
            )
            default_line = st.selectbox(
                "ไลน์ผลิตเริ่มต้น (PD)",
                PRODUCTION_LINES,
                index=line_index,
                key="last_production_line",
            )
        else:
            st.caption("แผนกอื่นไม่ต้องระบุไลน์ผลิต")

    st.markdown("#### 📋 วางรายการ JOB")
    st.caption(
        "วาง JOB ทีละบรรทัดได้ หรือวางข้อมูลแบบ Tab-separated: "
        "เลข JOB / แผนก / รายการสินค้า / จำนวน / ไลน์ผลิต"
    )
    bulk_text = st.text_area(
        "รายการ JOB",
        height=180,
        placeholder="JOB-6901\nJOB-6902\n\nหรือวางแบบหลายคอลัมน์จาก Excel",
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
            "เลข JOB",
            key=f"manual_job_{index}",
            placeholder="เช่น JOB-6901",
        )
        dept = cols[1].selectbox(
            "แผนก",
            DEPARTMENTS,
            index=DEPARTMENTS.index(last_department)
            if last_department in DEPARTMENTS else 0,
            key=f"manual_department_{index}",
            accept_new_options=True,
        )
        if dept == "PD":
            selected_line = st.session_state.get("last_production_line", "L1")
            selected_index = (
                PRODUCTION_LINES.index(selected_line)
                if selected_line in PRODUCTION_LINES else 0
            )
            line = cols[2].selectbox(
                "ไลน์ผลิต",
                PRODUCTION_LINES,
                index=selected_index,
                key=f"manual_line_{index}",
            )
        else:
            line = ""
            cols[2].caption("ไม่ต้องระบุไลน์")

        item = cols[3].text_input("รายการสินค้า", key=f"manual_item_{index}")
        quantity = cols[4].number_input(
            "จำนวน",
            min_value=0,
            value=0,
            step=1,
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

            # รองรับข้อมูลวางทีละบรรทัด หรือข้อมูล Tab/Comma/Pipe-separated
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

                dept = parts[1] if len(parts) > 1 and parts[1] else last_department
                item = parts[2] if len(parts) > 2 else ""
                quantity = 0
                if len(parts) > 3:
                    try:
                        quantity = int(float(parts[3].replace(",", "")))
                    except (ValueError, TypeError):
                        quantity = 0
                pasted_line = parts[4] if len(parts) > 4 else ""
                line = ""
                if dept == "PD":
                    line = pasted_line if pasted_line in PRODUCTION_LINES else default_line

                entries.append((job, dept, line, item, quantity))

            for job, dept, line, item, quantity in manual_rows:
                if str(job).strip():
                    entries.append((str(job).strip(), dept, line, item, quantity))

            if not entries:
                st.warning("กรุณาวางหรือกรอกเลข JOB อย่างน้อย 1 รายการ")
            else:
                saved, errors = 0, []
                for job, dept, line, item, quantity in entries:
                    dept = str(dept).strip()
                    # Safeguard: บังคับ line ว่างทุกแผนกที่ไม่ใช่ PD
                    line_to_save = line if dept == "PD" else ""
                    if dept == "PD" and line_to_save not in PRODUCTION_LINES:
                        errors.append(f"JOB {job}: กรุณาเลือกไลน์ผลิต L1-L10")
                        continue

                    try:
                        ok, message = insert_requisition(
                            str(job).strip(),
                            dept,
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


# ── หน้า 2: Dashboard ─────────────────────────────────────────────────────────
elif page == "📊 Dashboard":
    heading("Dashboard", "ภาพรวมปริมาณงานและจุดคอขวดของคลังสินค้า")
    col_search, col_period = st.columns([1.4, 1])
    with col_search:
        query = st.text_input(
            "🔎 ค้นหา JOB / สินค้า / แผนก / ไลน์",
            key="dashboard_search",
            placeholder="พิมพ์คำค้นหา…",
        ).strip().lower()
    with col_period:
        period = st.selectbox(
            "ช่วงวันที่",
            ["ทั้งหมด", "วันนี้", "สัปดาห์นี้", "เลือกช่วงวันที่"],
            key="dashboard_period",
        )

    today = now_bangkok().date()
    start_date = end_date = None
    if period == "วันนี้":
        start_date = end_date = today
    elif period == "สัปดาห์นี้":
        start_date, end_date = today - timedelta(days=today.weekday()), today
    elif period == "เลือกช่วงวันที่":
        dates = st.date_input(
            "เลือกวันที่เริ่มต้นและสิ้นสุด",
            value=(today - timedelta(days=6), today),
            key="dashboard_date_range",
        )
        if isinstance(dates, (tuple, list)) and len(dates) == 2:
            start_date, end_date = dates

    filtered = data.copy()
    if start_date and end_date and not filtered.empty:
        received_dates = filtered["received_at"].dt.date
        filtered = filtered[
            (received_dates >= start_date) & (received_dates <= end_date)
        ]
    if query and not filtered.empty:
        searchable = (
            filtered["job_number"].fillna("").astype(str)
            + " " + filtered["department"].fillna("").astype(str)
            + " " + filtered["line"].fillna("").astype(str)
            + " " + filtered["item_name"].fillna("").astype(str)
        ).str.lower()
        filtered = filtered[searchable.str.contains(query, na=False)]

    if filtered.empty:
        st.info("ยังไม่มีข้อมูลใบเบิก")
    else:
        total = len(filtered)
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

        kpis = st.columns(4)
        kpis[0].metric("ใบเบิกวันนี้", f"{today_count:,}", f"ทั้งหมด {total:,} JOB")
        kpis[1].metric("งานค้างจัด", f"{pending_count:,}", "JOB")
        kpis[2].metric("เวลาจัดเฉลี่ย", format_duration(average_processing))
        kpis[3].metric("เวลารอรับเฉลี่ย", format_duration(average_waiting))

        chart_left, chart_right = st.columns(2)

        with chart_left:
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
                    frame,
                    x="ชั่วโมง",
                    y="จำนวน JOB",
                    color="จำนวน JOB",
                    color_continuous_scale=["#bae6fd", "#0284c7"],
                )
                fig.update_layout(
                    height=330,
                    margin=dict(l=10, r=10, t=20, b=10),
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    coloraxis_showscale=False,
                )
                fig.update_xaxes(dtick=1, title="ชั่วโมงที่รับใบเบิก")
                fig.update_yaxes(title="จำนวน JOB", rangemode="tozero")
                return fig

            render_plotly_or_info(
                hourly, ["ชั่วโมง", "จำนวน JOB"], hourly_chart, "arrival_hour_chart"
            )

        with chart_right:
            st.markdown("#### 🍩 สัดส่วนใบเบิกปกติและใบเบิกเย็น")
            late_count_chart = int(filtered["late"].sum())
            normal_count_chart = max(total - late_count_chart, 0)
            requisition_mix = pd.DataFrame(
                {
                    "ประเภทใบเบิก": ["ใบเบิกปกติ", "ใบเบิกเย็น"],
                    "จำนวน": [normal_count_chart, late_count_chart],
                }
            )

            def requisition_pie(frame):
                fig = px.pie(
                    frame,
                    names="ประเภทใบเบิก",
                    values="จำนวน",
                    hole=0.62,
                    color="ประเภทใบเบิก",
                    color_discrete_map={
                        "ใบเบิกปกติ": "#10b981",
                        "ใบเบิกเย็น": "#ef4444",
                    },
                )
                fig.update_traces(
                    textinfo="label+percent",
                    textposition="inside",
                    hovertemplate="%{label}<br>%{value} JOB (%{percent})<extra></extra>",
                )
                fig.update_layout(
                    height=330,
                    margin=dict(l=10, r=10, t=20, b=10),
                    paper_bgcolor="white",
                    legend_title_text="",
                )
                return fig

            render_plotly_or_info(
                requisition_mix,
                ["ประเภทใบเบิก", "จำนวน"],
                requisition_pie,
                "requisition_type_donut",
            )

        st.markdown("#### 📌 รายการในช่วงที่เลือก")
        display_table(filtered, "dashboard_table")


# ── สถานะสำหรับแสดงผล ─────────────────────────────────────────────────────────
def job_status(row):
    if str(row.get("status", "")) == "ยกเลิก":
        return "🔴 ยกเลิก"
    if pd.notna(row.get("handover_at")):
        return "🟢 รับของแล้ว"
    if pd.notna(row.get("picked_at")):
        return "🔵 จัดเสร็จรอ PD"
    return "🟠 กำลังจัด"


def display_table(df, key):
    if df.empty:
        st.info("ยังไม่มีข้อมูลใบเบิกในเงื่อนไขที่เลือก")
        return

    view = df.copy()
    view["สถานะงาน"] = view.apply(job_status, axis=1)
    view["แท็ก"] = view["late"].map({True: "🔴 ใบเบิกเย็น", False: "ปกติ"})
    view["วันเวลาที่เบิก"] = view["received_at"].apply(display_datetime)
    view["เวลาจัดเสร็จ"] = view["picked_at"].apply(display_datetime)
    view["เวลา PD มารับ"] = view["handover_at"].apply(display_datetime)
    view["ระยะเวลาจัดสินค้า"] = view["processing_minutes"].apply(format_duration)
    view["ระยะเวลารอรับสินค้า"] = view["waiting_minutes"].apply(format_duration)

    columns = {
        "job_number": "เลขที่ Job",
        "วันเวลาที่เบิก": "วันเวลาที่เบิก",
        "department": "แผนกที่เบิก",
        "line": "ไลน์ผลิต",
        "item_name": "รายการสินค้า",
        "quantity": "จำนวน",
        "สถานะงาน": "สถานะปัจจุบัน",
        "เวลาจัดเสร็จ": "เวลาจัดเสร็จ",
        "เวลา PD มารับ": "เวลา PD มารับ",
        "ระยะเวลาจัดสินค้า": "ระยะเวลาจัดสินค้า",
        "ระยะเวลารอรับสินค้า": "ระยะเวลารอรับสินค้า",
        "แท็ก": "แท็ก",
    }
    chosen = [column for column in columns if column in view.columns]
    st.dataframe(
        view[chosen].rename(columns=columns),
        use_container_width=True,
        hide_index=True,
        key=key,
    )


# ── หน้า 1: บันทึกใบเบิก ─────────────────────────────────────────────────────
if page == "📝 บันทึกใบเบิก":
    heading("บันทึกใบเบิก", "บันทึกงานระดับ JOB พร้อมเวลารับเอกสาร")
    st.caption(
        f"Cut-off เวลา {CUTOFF_TIME.strftime('%H:%M')} น. "
        "ระบบติดแท็กใบเบิกเย็นเมื่อรับเอกสารหลังเวลานี้"
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

    default_col, default_line_col = st.columns(2)
    with default_col:
        default_department = st.selectbox(
            "แผนกเริ่มต้นสำหรับรายการที่วาง",
            DEPARTMENTS,
            key="last_department",
            accept_new_options=True,
        )
    default_line = ""
    with default_line_col:
        if default_department == "PD":
            last_line = st.session_state.get("last_production_line", "L1")
            line_index = PRODUCTION_LINES.index(last_line) if last_line in PRODUCTION_LINES else 0
            default_line = st.selectbox(
                "ไลน์ผลิตเริ่มต้น (PD)",
                PRODUCTION_LINES,
                index=line_index,
                key="last_production_line",
            )
        else:
            st.caption("แผนกอื่นไม่ต้องระบุไลน์ผลิต")

    st.markdown("#### 📋 วางรายการ JOB")
    st.caption(
        "วาง JOB ทีละบรรทัด หรือวางจาก Excel แบบ Tab-separated: "
        "เลข JOB / แผนก / รายการสินค้า / จำนวน / ไลน์ผลิต"
    )
    bulk_text = st.text_area(
        "รายการ JOB",
        height=160,
        placeholder="JOB-6901\nJOB-6902\n\nหรือวางแบบหลายคอลัมน์จาก Excel",
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
            selected_line = st.session_state.get("last_production_line", "L1")
            selected_index = (
                PRODUCTION_LINES.index(selected_line)
                if selected_line in PRODUCTION_LINES else 0
            )
            line = cols[2].selectbox(
                "ไลน์ผลิต",
                PRODUCTION_LINES,
                index=selected_index,
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

                dept = parts[1] if len(parts) > 1 and parts[1] else default_department
                item = parts[2] if len(parts) > 2 else ""
                quantity = 0
                if len(parts) > 3:
                    try:
                        quantity = int(float(parts[3].replace(",", "")))
                    except (TypeError, ValueError):
                        quantity = 0
                pasted_line = parts[4] if len(parts) > 4 else ""
                line = ""
                if dept == "PD":
                    line = pasted_line if pasted_line in PRODUCTION_LINES else default_line
                entries.append((job, dept, line, item, quantity))

            for job, dept, line, item, quantity in manual_rows:
                if str(job).strip():
                    entries.append((str(job).strip(), dept, line, item, quantity))

            if not entries:
                st.warning("กรุณาวางหรือกรอกเลข JOB อย่างน้อย 1 รายการ")
            else:
                saved, errors = 0, []
                for job, dept, line, item, quantity in entries:
                    dept = str(dept).strip()
                    line_to_save = line if dept == "PD" else ""
                    if dept == "PD" and line_to_save not in PRODUCTION_LINES:
                        errors.append(f"JOB {job}: กรุณาเลือกไลน์ผลิต L1-L10")
                        continue
                    try:
                        ok, message = insert_requisition(
                            str(job).strip(),
                            dept,
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


# ── หน้า 2: Dashboard ─────────────────────────────────────────────────────────
elif page == "📊 Dashboard":
    heading("Dashboard", "ภาพรวมปริมาณงานและจุดคอขวดของคลังสินค้า")
    col_search, col_period = st.columns([1.4, 1])
    with col_search:
        query = st.text_input(
            "🔎 ค้นหา JOB / สินค้า / แผนก / ไลน์",
            key="dashboard_search",
            placeholder="พิมพ์คำค้นหา…",
        ).strip().lower()
    with col_period:
        period = st.selectbox(
            "ช่วงวันที่",
            ["ทั้งหมด", "วันนี้", "สัปดาห์นี้", "เลือกช่วงวันที่"],
            key="dashboard_period",
        )

    today = now_bangkok().date()
    start_date = end_date = None
    if period == "วันนี้":
        start_date = end_date = today
    elif period == "สัปดาห์นี้":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == "เลือกช่วงวันที่":
        selected_dates = st.date_input(
            "เลือกวันที่เริ่มต้นและสิ้นสุด",
            value=(today - timedelta(days=6), today),
            key="dashboard_date_range",
        )
        if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
            start_date, end_date = selected_dates

    filtered = data.copy()
    if start_date and end_date and not filtered.empty:
        received_dates = filtered["received_at"].dt.date
        filtered = filtered[
            (received_dates >= start_date) & (received_dates <= end_date)
        ]
    if query and not filtered.empty:
        searchable = (
            filtered["job_number"].fillna("").astype(str)
            + " " + filtered["department"].fillna("").astype(str)
            + " " + filtered["line"].fillna("").astype(str)
            + " " + filtered["item_name"].fillna("").astype(str)
        ).str.lower()
        filtered = filtered[searchable.str.contains(query, na=False)]

    if filtered.empty:
        st.info("ยังไม่มีข้อมูลใบเบิก")
    else:
        total = len(filtered)
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

        kpis = st.columns(4)
        kpis[0].metric("ใบเบิกวันนี้", f"{today_count:,}", f"ทั้งหมด {total:,} JOB")
        kpis[1].metric("งานค้างจัด", f"{pending_count:,}", "JOB")
        kpis[2].metric("เวลาจัดเฉลี่ย", format_duration(average_processing))
        kpis[3].metric("เวลารอรับเฉลี่ย", format_duration(average_waiting))

        chart_left, chart_right = st.columns(2)

        with chart_left:
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
                figure = px.bar(
                    frame, x="ชั่วโมง", y="จำนวน JOB", color="จำนวน JOB",
                    color_continuous_scale=["#bae6fd", "#0284c7"],
                )
                figure.update_layout(
                    height=330, margin=dict(l=10, r=10, t=20, b=10),
                    plot_bgcolor="white", paper_bgcolor="white",
                    coloraxis_showscale=False,
                )
                figure.update_xaxes(dtick=1, title="ชั่วโมงที่รับใบเบิก")
                figure.update_yaxes(title="จำนวน JOB", rangemode="tozero")
                return figure

            render_plotly_or_info(
                hourly, ["ชั่วโมง", "จำนวน JOB"], hourly_chart, "arrival_hour_chart"
            )

        with chart_right:
            st.markdown("#### 🍩 สัดส่วนใบเบิกปกติและใบเบิกเย็น")
            late_total = int(filtered["late"].sum())
            normal_total = max(total - late_total, 0)
            requisition_mix = pd.DataFrame(
                {
                    "ประเภทใบเบิก": ["ใบเบิกปกติ", "ใบเบิกเย็น"],
                    "จำนวน": [normal_total, late_total],
                }
            )

            def requisition_pie(frame):
                figure = px.pie(
                    frame,
                    names="ประเภทใบเบิก",
                    values="จำนวน",
                    hole=0.62,
                    color="ประเภทใบเบิก",
                    color_discrete_map={
                        "ใบเบิกปกติ": "#10b981",
                        "ใบเบิกเย็น": "#ef4444",
                    },
                )
                figure.update_traces(
                    textinfo="label+percent",
                    textposition="inside",
                    hovertemplate="%{label}<br>%{value} JOB (%{percent})<extra></extra>",
                )
                figure.update_layout(
                    height=330, margin=dict(l=10, r=10, t=20, b=10),
                    paper_bgcolor="white", legend_title_text="",
                )
                return figure

            render_plotly_or_info(
                requisition_mix,
                ["ประเภทใบเบิก", "จำนวน"],
                requisition_pie,
                "requisition_type_donut",
            )

        st.markdown("#### 📌 รายการในช่วงที่เลือก")
        display_table(filtered, "dashboard_table")


# ── หน้า 3: จัดการและอัปเดตสถานะ ────────────────────────────────────────────
elif page == "✏️ จัดการ / อัปเดตสถานะ":
    heading("จัดการและอัปเดตสถานะ", "อัปเดตเวลาจัดเสร็จ เวลารับสินค้า และการยกเลิก")
    active = data[data["status"] != "ยกเลิก"] if not data.empty else data

    if active.empty:
        st.info("ยังไม่มีข้อมูลใบเบิกให้จัดการ")
    else:
        job_ids = active["id"].tolist()
        job_labels = {
            int(row["id"]): (
                f'{row["job_number"]} · {row["department"] or "ไม่ระบุ"} · '
                f'{job_status(row)}'
            )
            for _, row in active.iterrows()
        }
        selected_id = st.selectbox(
            "เลือก JOB",
            job_ids,
            format_func=lambda value: job_labels[int(value)],
            key="manage_selected_job",
        )
        record = active[active["id"] == selected_id].iloc[0]
        job_key = str(int(selected_id))

        st.markdown(
            f'<div class="section-card"><b>JOB {html.escape(str(record["job_number"]))}</b>'
            f'　·　แผนก {html.escape(str(record["department"] or "ไม่ระบุ"))}'
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

        # ตั้งค่าเริ่มต้นก่อน widgets ถูกสร้าง และไม่แก้ทับค่าที่ผู้ใช้กำลังแก้
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

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📦 เวลาจัดเสร็จ")
            st.checkbox(
                "บันทึกเวลาจัดเสร็จแล้ว",
                key=picked_enabled_key,
            )
            st.button(
                "⏱️ ลงเวลาปัจจุบัน",
                key=f"auto_picked_button_{job_key}",
                on_click=set_timestamp,
                args=(picked_date_key, picked_time_key, picked_enabled_key),
            )
            picked_date = st.date_input(
                "วันที่จัดเสร็จ", key=picked_date_key
            )
            picked_time = st.time_input(
                "เวลาจัดเสร็จ", key=picked_time_key
            )

        with col2:
            st.markdown("#### 🟢 PD มารับสินค้า")
            st.checkbox(
                "บันทึกเวลาที่ PD รับแล้ว",
                key=handover_enabled_key,
            )
            st.button(
                "⏱️ ลงเวลาปัจจุบัน",
                key=f"auto_handover_button_{job_key}",
                on_click=set_timestamp,
                args=(handover_date_key, handover_time_key, handover_enabled_key),
            )
            handover_date = st.date_input(
                "วันที่ PD รับสินค้า", key=handover_date_key
            )
            handover_time = st.time_input(
                "เวลา PD รับสินค้า", key=handover_time_key
            )

        picked_at = (
            parse_local_datetime(picked_date, picked_time)
            if st.session_state[picked_enabled_key] else None
        )
        handover_at = (
            parse_local_datetime(handover_date, handover_time)
            if st.session_state[handover_enabled_key] else None
        )
        received_at = as_bangkok(record["received_at"])

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
            key=f"save_status_button_{job_key}",
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
                    key=f"edit_production_line_{job_key}",
                )

            edit_item = st.text_input(
                "รายการ",
                value=str(record["item_name"] or ""),
                key=f"edit_item_name_{job_key}",
            )
            edit_quantity = st.number_input(
                "จำนวน",
                min_value=0,
                value=int(record["quantity"]) if pd.notna(record["quantity"]) else 0,
                step=1,
                key=f"edit_quantity_{job_key}",
            )

            if st.button(
                "บันทึกการแก้ไขรายละเอียด",
                key=f"save_edit_button_{job_key}",
            ):
                # ค่าไลน์จะถูกล้างก่อน UPDATE หากแผนกไม่ใช่ PD
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
            cancel_confirmed = st.checkbox(
                "ยืนยันการยกเลิก JOB นี้",
                key=f"confirm_cancel_{job_key}",
            )
            cancel_ready = bool(
                cancel_by.strip() and cancel_reason.strip() and cancel_confirmed
            )
            if st.button(
                "🔴 บันทึกยกเลิก JOB",
                disabled=not cancel_ready,
                key=f"cancel_button_{job_key}",
            ):
                try:
                    cancel_requisition(int(selected_id), cancel_by, cancel_reason)
                    st.success("ยกเลิก JOB แล้ว")
                    st.rerun()
                except sqlite3.OperationalError as error:
                    st.error(f"ยกเลิกไม่สำเร็จ: {error}")


# ── หน้า 4: ประวัติ ส่งออก และ Timeline ──────────────────────────────────────
elif page == "📋 ประวัติ & Export":
    heading("ประวัติและส่งออกข้อมูล", "ค้นหา ตรวจสอบ และสร้างหลักฐาน Timeline")
    search_col, period_col = st.columns([1.4, 1])
    with search_col:
        query = st.text_input(
            "🔎 ค้นหา JOB / สินค้า / แผนก / ไลน์",
            key="history_search",
            placeholder="พิมพ์คำค้นหา…",
        ).strip().lower()
    with period_col:
        period = st.selectbox(
            "ช่วงวันที่",
            ["ทั้งหมด", "วันนี้", "สัปดาห์นี้", "เลือกช่วงวันที่"],
            key="history_period",
        )

    today = now_bangkok().date()
    start_date = end_date = None
    if period == "วันนี้":
        start_date = end_date = today
    elif period == "สัปดาห์นี้":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == "เลือกช่วงวันที่":
        selected_dates = st.date_input(
            "เลือกวันที่เริ่มต้นและสิ้นสุด",
            value=(today - timedelta(days=6), today),
            key="history_date_range",
        )
        if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
            start_date, end_date = selected_dates

    history = data.copy()
    if start_date and end_date and not history.empty:
        dates = history["received_at"].dt.date
        history = history[(dates >= start_date) & (dates <= end_date)]
    if query and not history.empty:
        searchable = (
            history["job_number"].fillna("").astype(str)
            + " " + history["department"].fillna("").astype(str)
            + " " + history["line"].fillna("").astype(str)
            + " " + history["item_name"].fillna("").astype(str)
        ).str.lower()
        history = history[searchable.str.contains(query, na=False)]

    if history.empty:
        st.info("ยังไม่มีข้อมูลใบเบิก")
    else:
        display_table(history, "history_table")
        st.download_button(
            "📥 ดาวน์โหลด Excel (.xlsx)",
            data=make_excel(history),
            file_name="รายงานสรุปการเบิกสินค้า_คลังสินค้า.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_excel_button",
        )

        # ปุ่ม Timeline แสดงเฉพาะใบเบิกเย็นหรือรายการที่ยกเลิก
        eligible = history[
            history["late"].fillna(False) | history["status"].eq("ยกเลิก")
        ]
        if not eligible.empty:
            st.markdown("#### 📄 พิมพ์หลักฐาน / สรุป Timeline")
            st.caption("แสดงปุ่มสำหรับใบเบิกเย็นและงานที่ถูกยกเลิก")
            for _, row in eligible.iterrows():
                row_id = int(row["id"])
                button_label = (
                    f'📄 เปิด Timeline · {row["job_number"]} · '
                    f'{row["department"] or "ไม่ระบุ"}'
                )
                if st.button(
                    button_label,
                    key=f"timeline_button_{row_id}",
                    use_container_width=True,
                ):
                    st.session_state["timeline_record_id"] = row_id

        selected_timeline_id = st.session_state.get("timeline_record_id")
        if selected_timeline_id is not None:
            selected_rows = history[history["id"] == selected_timeline_id]
            if not selected_rows.empty:
                show_timeline_dialog(selected_rows.iloc[0].to_dict())

        st.caption(f"แสดง {len(history):,} รายการ")


st.markdown(
    "<div style='text-align:center;color:#94a3b8;padding:1.5rem 0 0'>"
    "Warehouse Flow · เวลาอ้างอิง Asia/Bangkok · ผู้ใช้งาน Admin</div>",
    unsafe_allow_html=True,
)
