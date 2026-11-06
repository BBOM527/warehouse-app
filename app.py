from io import BytesIO
from datetime import datetime, timezone, timedelta, time
import sqlite3

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st
import streamlit.components.v1 as components
from openpyxl.styles import Font, PatternFill, Alignment
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


# ── Modern Enterprise CSS ─────────────────────────────────────────────────────
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
    [data-testid="stForm"], [data-testid="stExpander"], [data-testid="stDataFrame"] {
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
    .login-wrap {
        max-width:480px; margin:8vh auto 0; padding:2rem; background:#fff;
        border:1px solid var(--line); border-radius:20px;
        box-shadow:0 20px 50px rgba(15,23,42,.09);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── เวลาและฐานข้อมูล ──────────────────────────────────────────────────────────
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

        # โอนค่าจากชื่อคอลัมน์เดิมก่อนเติมค่าเริ่มต้น
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
    # เฉพาะแผนก PD เท่านั้นที่บันทึกไลน์ L1-L10 ได้
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


# ── Excel export: เลือกเฉพาะข้อมูลสำคัญและจัดความกว้างคอลัมน์ ────────────────
def make_excel(df):
    export = pd.DataFrame(index=df.index)

    export["เลขที่ Job"] = df["job_number"].fillna("").astype(str)
    export["วันเวลาที่เบิก"] = df["received_at"].apply(
        lambda value: as_bangkok(value).strftime("%d/%m/%Y %H:%M:%S")
        if as_bangkok(value) else ""
    )
    export["แผนกที่เบิก"] = df["department"].fillna("").astype(str)
    export["ไลน์ผลิต"] = df["line"].fillna("").astype(str)
    export["รายการสินค้า"] = df["item_name"].fillna("").astype(str)
    export["จำนวน"] = df["quantity"].where(df["quantity"].notna(), "")

    export["สถานะปัจจุบัน"] = df.apply(
        lambda row: job_status(row), axis=1
    )
    export["เวลาจัดเสร็จ"] = df["picked_at"].apply(
        lambda value: as_bangkok(value).strftime("%d/%m/%Y %H:%M:%S")
        if as_bangkok(value) else ""
    )
    export["เวลา PD มารับ"] = df["handover_at"].apply(
        lambda value: as_bangkok(value).strftime("%d/%m/%Y %H:%M:%S")
        if as_bangkok(value) else ""
    )
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
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )

        # ปรับความกว้างคอลัมน์ตามความยาวข้อมูล โดยจำกัดความกว้างสูงสุด
        for column_cells in worksheet.columns:
            column_letter = get_column_letter(column_cells[0].column)
            max_length = 0
            for cell in column_cells:
                cell.font = header_font if cell.row == 1 else body_font
                cell.alignment = Alignment(
                    vertical="center",
                    wrap_text=(cell.row == 1),
                )
                value = "" if cell.value is None else str(cell.value)
                max_length = max(max_length, len(value))
            worksheet.column_dimensions[column_letter].width = min(
                max(max_length + 3, 12), 42
            )

    buffer.seek(0)
    return buffer.getvalue()


# ── Callback สำหรับปุ่มลงเวลา ─────────────────────────────────────────────────
def set_timestamp(date_key, time_key, enabled_key):
    """Callback ทำงานก่อนวาด widgets รอบใหม่ จึงตั้งค่า widget state ได้ปลอดภัย."""
    current = now_bangkok()
    st.session_state[date_key] = current.date()
    st.session_state[time_key] = current.time().replace(microsecond=0)
    st.session_state[enabled_key] = True


# ── UI helpers ────────────────────────────────────────────────────────────────
def show_live_clock():
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


def heading(title, subtitle):
    st.markdown(
        f"""
        <div class="page-heading">
          <div class="eyebrow">WAREHOUSE FLOW · CONTROL CENTER</div>
          <h1>{title}</h1>
          <div class="subtle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login():
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
            username = st.text_input(
                "Username", key="login_username", autocomplete="username"
            )
            password = st.text_input(
                "Password",
                key="login_password",
                type="password",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button(
                "เข้าสู่ระบบ", type="primary", use_container_width=True
            )
        if submitted:
            if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
                st.session_state["authenticated"] = True
                st.session_state["display_name"] = DISPLAY_NAME
                st.rerun()
            st.error("Username หรือ Password ไม่ถูกต้อง")


def filter_data(df, key_prefix):
    left, right = st.columns([1.4, 1])
    with left:
        query = st.text_input(
            "🔎 ค้นหา JOB / สินค้า / แผนก / ไลน์",
            key=f"{key_prefix}_search",
            placeholder="พิมพ์คำค้นหา…",
        ).strip().lower()
    with right:
        mode = st.selectbox(
            "ช่วงวันที่",
            ["ทั้งหมด", "วันนี้", "สัปดาห์นี้", "เลือกช่วงวันที่"],
            key=f"{key_prefix}_date_mode",
        )

    start_date = end_date = None
    today = now_bangkok().date()
    if mode == "วันนี้":
        start_date = end_date = today
    elif mode == "สัปดาห์นี้":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif mode == "เลือกช่วงวันที่":
        selected = st.date_input(
            "วันที่เริ่มต้นและสิ้นสุด",
            value=(today - timedelta(days=6), today),
            key=f"{key_prefix}_range",
        )
        if isinstance(selected, (tuple, list)) and len(selected) == 2:
            start_date, end_date = selected

    result = df.copy()
    if start_date and end_date and not result.empty:
        dates = result["received_at"].dt.date
        result = result[(dates >= start_date) & (dates <= end_date)]

    if query and not result.empty:
        searchable = (
            result["job_number"].fillna("").astype(str)
            + " " + result["department"].fillna("").astype(str)
            + " " + result["line"].fillna("").astype(str)
            + " " + result["item_name"].fillna("").astype(str)
        ).str.lower()
        result = result[searchable.str.contains(query, na=False)]
    return result


def job_status(row):
    if row.get("status") == "ยกเลิก":
        return "🔴 ยกเลิก"
    if pd.notna(row.get("handover_at")):
        return "🟢 รับของแล้ว"
    if pd.notna(row.get("picked_at")):
        return "🔵 จัดเสร็จ / รอ PD"
    return "🟠 กำลังจัด"


def show_table(df, key):
    if df.empty:
        st.info("ยังไม่มีข้อมูลใบเบิกในเงื่อนไขที่เลือก")
        return

    view = df.copy()
    view["สถานะงาน"] = view.apply(job_status, axis=1)
    view["แท็ก"] = view["late"].map({True: "🔴 ใบเบิกเย็น", False: "ปกติ"})
    view["รับใบเบิก"] = view["received_at"].dt.strftime("%d/%m/%Y %H:%M")
    view["จัดเสร็จ"] = view["picked_at"].dt.strftime("%d/%m/%Y %H:%M").fillna("—")
    view["PD รับของ"] = view["handover_at"].dt.strftime("%d/%m/%Y %H:%M").fillna("—")
    view["เวลาจัด (นาที)"] = view["processing_minutes"].apply(
        lambda value: "—" if pd.isna(value) else round(value, 1)
    )
    view["เวลารอ PD (นาที)"] = view["waiting_minutes"].apply(
        lambda value: "—" if pd.isna(value) else round(value, 1)
    )

    labels = {
        "job_number": "เลข JOB",
        "department": "แผนก",
        "line": "ไลน์ผลิต",
        "item_name": "รายการ",
        "quantity": "จำนวน",
        "รับใบเบิก": "รับใบเบิก",
        "จัดเสร็จ": "จัดเสร็จ",
        "PD รับของ": "PD รับของ",
        "เวลาจัด (นาที)": "เวลาจัด (นาที)",
        "เวลารอ PD (นาที)": "เวลารอ PD (นาที)",
        "สถานะงาน": "สถานะงาน",
        "แท็ก": "แท็ก",
        "cancelled_by": "ผู้ยกเลิก",
        "cancel_reason": "สาเหตุยกเลิก",
    }
    columns = [column for column in labels if column in view.columns]
    st.dataframe(
        view[columns].rename(columns=labels),
        use_container_width=True,
        hide_index=True,
        key=key,
    )


def render_plotly_or_info(frame, required_columns, chart_builder, chart_key):
    """ตรวจ DataFrame/คอลัมน์ก่อนเรียก Plotly และจับข้อผิดพลาดจากกราฟ."""
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
        figure = chart_builder(frame)
        st.plotly_chart(figure, use_container_width=True, key=chart_key)
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
    render_login()
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

show_live_clock()

try:
    data = load_data()
except (sqlite3.OperationalError, pd.errors.DatabaseError) as error:
    st.error(f"อ่านฐานข้อมูลไม่สำเร็จ: {error}")
    st.stop()


# ── บันทึกหลาย JOB ───────────────────────────────────────────────────────────
if page == "📝 บันทึกใบเบิก":
    heading("บันทึกใบเบิก", "บันทึกงานระดับ JOB พร้อมเวลารับเอกสาร")
    st.caption(
        f"Cut-off เวลา {CUTOFF_TIME.strftime('%H:%M')} น. "
        "ระบบติดแท็กใบเบิกเย็นเมื่อรับเอกสารหลังเวลานี้"
    )

    row_count = st.number_input(
        "จำนวน JOB ที่บันทึกพร้อมกัน",
        min_value=1,
        max_value=20,
        value=3,
        step=1,
        key="bulk_job_count",
    )
    current = now_bangkok()
    received_date = st.date_input(
        "วันที่รับใบเบิก", value=current.date(), key="bulk_received_date"
    )
    received_time = st.time_input(
        "เวลารับใบเบิก",
        value=current.time().replace(microsecond=0),
        key="bulk_received_time",
    )
    received_at = parse_local_datetime(received_date, received_time)

    rows = []
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("#### รายละเอียดใบเบิก")

    for index in range(int(row_count)):
        st.markdown(f"**JOB #{index + 1}**")
        cols = st.columns([1.1, 1.2, .8, 1.3, .7])

        job = cols[0].text_input(
            "เลข JOB",
            key=f"bulk_job_number_{index}",
            placeholder="เช่น JOB-6901",
        )
        department = cols[1].selectbox(
            "แผนก",
            DEPARTMENTS,
            key=f"bulk_department_{index}",
            accept_new_options=True,
        )

        if department == "PD":
            line = cols[2].selectbox(
                "ไลน์ผลิต (จำเป็น)",
                PRODUCTION_LINES,
                key=f"bulk_production_line_{index}",
            )
        else:
            line = ""
            cols[2].markdown(
                "<div style='padding-top:2rem;color:#94a3b8'>ไม่ต้องระบุไลน์</div>",
                unsafe_allow_html=True,
            )

        item = cols[3].text_input(
            "รายการ (ถ้ามี)", key=f"bulk_item_name_{index}"
        )
        quantity = cols[4].number_input(
            "จำนวน",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f"bulk_quantity_{index}",
        )
        rows.append((job, department, line, item, quantity))

    st.markdown("</div>", unsafe_allow_html=True)

    if st.button(
        "✅ บันทึกรับเรื่องทั้งหมด",
        type="primary",
        use_container_width=True,
        key="bulk_save_button",
    ):
        if received_at is None:
            st.error("กรุณาระบุวันที่และเวลารับใบเบิกให้ถูกต้อง")
        else:
            filled_rows = [row for row in rows if str(row[0]).strip()]
            if not filled_rows:
                st.warning("กรุณากรอกเลข JOB อย่างน้อย 1 รายการ")
            else:
                saved, errors = 0, []
                for job, department, line, item, quantity in filled_rows:
                    # INSERT บังคับล้างไลน์สำหรับแผนกที่ไม่ใช่ PD
                    line_to_save = line if department == "PD" else ""
                    try:
                        ok, message = insert_requisition(
                            str(job).strip(),
                            str(department).strip(),
                            line_to_save,
                            str(item).strip(),
                            quantity if quantity > 0 else None,
                            received_at,
                        )
                    except sqlite3.OperationalError as error:
                        ok, message = False, f"บันทึก JOB {job} ไม่สำเร็จ: {error}"

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


# ── Dashboard ─────────────────────────────────────────────────────────────────
elif page == "📊 Dashboard":
    heading("Dashboard", "ภาพรวมปริมาณงานและจุดคอขวดของคลังสินค้า")
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
        cards[0].metric(
            "ใบเบิกในช่วงที่เลือก", f"{total:,}", f"วันนี้ {today_count:,} JOB"
        )
        cards[1].metric(
            "ใบเบิกเย็น",
            f"{late_count / total * 100:.1f}%",
            f"{late_count:,} JOB",
        )
        cards[2].metric("เวลาจัดเฉลี่ย", format_duration(average_processing))
        bottleneck = "รอจัด" if pending_count else (
            "รอ PD รับ" if average_waiting else "ปกติ"
        )
        cards[3].metric("จุดคอขวด", bottleneck, f"ค้างจัด {pending_count:,} JOB")

        left, right = st.columns(2)

        with left:
            st.markdown("#### 🕒 ใบเบิกตามชั่วโมง")
            hourly = pd.DataFrame()
            if "received_at" in filtered.columns:
                hourly_source = filtered.dropna(subset=["received_at"])
                if not hourly_source.empty:
                    hourly = (
                        hourly_source.assign(
                            ชั่วโมง=hourly_source["received_at"].dt.hour
                        )
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
                    frame,
                    x="ชั่วโมง",
                    y="จำนวน JOB",
                    color="จำนวน JOB",
                    color_continuous_scale=["#bae6fd", "#0284c7"],
                )
                figure.update_layout(
                    height=330,
                    margin=dict(l=10, r=10, t=20, b=10),
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    coloraxis_showscale=False,
                )
                figure.update_xaxes(dtick=1, title="ชั่วโมงที่รับใบเบิก")
                figure.update_yaxes(title="จำนวน JOB", rangemode="tozero")
                return figure

            render_plotly_or_info(
                hourly,
                ["ชั่วโมง", "จำนวน JOB"],
                hourly_chart,
                "hourly_arrival_chart",
            )

        with right:
            st.markdown("#### 🏢 ใบเบิกเย็นแยกตามแผนก")
            dept_stats = pd.DataFrame()
            required = {"department", "job_number", "late"}
            if required.issubset(filtered.columns):
                dept_stats = (
                    filtered.groupby("department", dropna=False)
                    .agg(จำนวน=("job_number", "count"), ใบเบิกเย็น=("late", "sum"))
                    .reset_index()
                )
                if not dept_stats.empty:
                    dept_stats["แผนก"] = dept_stats["department"].fillna("ไม่ระบุ")

            def department_chart(frame):
                figure = px.bar(
                    frame,
                    x="แผนก",
                    y=["จำนวน", "ใบเบิกเย็น"],
                    barmode="group",
                    color_discrete_sequence=["#38bdf8", "#f87171"],
                )
                figure.update_layout(
                    height=330,
                    margin=dict(l=10, r=10, t=20, b=10),
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    legend_title_text="ประเภท",
                )
                return figure

            render_plotly_or_info(
                dept_stats,
                ["แผนก", "จำนวน", "ใบเบิกเย็น"],
                department_chart,
                "department_late_chart",
            )

        st.markdown("#### 📌 รายการในช่วงที่เลือก")
        show_table(filtered, "dashboard_table")


# ── จัดการสถานะและแก้ไข JOB ──────────────────────────────────────────────────
elif page == "✏️ จัดการ / อัปเดตสถานะ":
    heading("จัดการและอัปเดตสถานะ", "อัปเดตเวลาจัดเสร็จและเวลาที่ PD รับสินค้า")
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
            f'<div class="section-card"><b>JOB {record["job_number"]}</b>'
            f'　·　แผนก {record["department"] or "ไม่ระบุ"}'
            f'　·　{job_status(record)}</div>',
            unsafe_allow_html=True,
        )

        def record_date(value):
            parsed = as_bangkok(value)
            return parsed.date() if parsed else now_bangkok().date()

        def record_time(value):
            parsed = as_bangkok(value)
            return parsed.time().replace(microsecond=0) if parsed else time(0, 0)

        # กำหนดค่าเริ่มต้นก่อนสร้าง widgets และไม่เขียนทับค่าที่ผู้ใช้แก้ไว้
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
                "วันที่จัดเสร็จ",
                key=picked_date_key,
            )
            picked_time = st.time_input(
                "เวลาจัดเสร็จ",
                key=picked_time_key,
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
                "วันที่ PD รับสินค้า",
                key=handover_date_key,
            )
            handover_time = st.time_input(
                "เวลา PD รับสินค้า",
                key=handover_time_key,
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
                min_value=0.0,
                value=float(record["quantity"])
                if pd.notna(record["quantity"]) else 0.0,
                key=f"edit_quantity_{job_key}",
            )

            if st.button(
                "บันทึกการแก้ไขรายละเอียด",
                key=f"save_edit_button_{job_key}",
            ):
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
                "ผู้แจ้งยกเลิก (PN/PD)",
                key=f"cancel_by_{job_key}",
            )
            cancel_reason = st.text_area(
                "สาเหตุการยกเลิก",
                key=f"cancel_reason_{job_key}",
            )
            confirm_cancel = st.checkbox(
                "ยืนยันการยกเลิก JOB นี้",
                key=f"confirm_cancel_{job_key}",
            )
            if st.button(
                "ยืนยันยกเลิก",
                disabled=not confirm_cancel,
                key=f"cancel_button_{job_key}",
            ):
                if not cancel_by.strip() or not cancel_reason.strip():
                    st.error("กรุณาระบุผู้แจ้งและสาเหตุการยกเลิก")
                else:
                    try:
                        cancel_requisition(
                            int(selected_id), cancel_by, cancel_reason
                        )
                        st.success("ยกเลิก JOB แล้ว")
                        st.rerun()
                    except sqlite3.OperationalError as error:
                        st.error(f"ยกเลิกไม่สำเร็จ: {error}")


# ── ประวัติและส่งออก Excel ───────────────────────────────────────────────────
elif page == "📋 ประวัติ & Export":
    heading("ประวัติและส่งออกข้อมูล", "ค้นหา ตรวจสอบ และดาวน์โหลดข้อมูลใบเบิก")
    filtered = filter_data(data, "history")

    if filtered.empty:
        st.info("ยังไม่มีข้อมูลใบเบิก")
    else:
        show_table(filtered, "history_table")
        st.download_button(
            "📥 ดาวน์โหลด Excel (.xlsx)",
            data=make_excel(filtered),
            file_name="รายงานสรุปการเบิกสินค้า_คลังสินค้า.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_excel_button",
        )
        st.caption(f"แสดง {len(filtered):,} รายการ")


st.markdown(
    "<div style='text-align:center;color:#94a3b8;padding:1.5rem 0 0'>"
    "Warehouse Flow · เวลาอ้างอิง Asia/Bangkok · ผู้ใช้งาน Admin</div>",
    unsafe_allow_html=True,
)
                    
