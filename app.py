"""PK Warehouse | Modern JOB Tracking Dashboard

รันด้วย:
    streamlit run app.py

ติดตั้ง dependencies:
    pip install streamlit pandas plotly openpyxl pytz
"""

from datetime import date, datetime, time, timezone, timedelta
from io import BytesIO
from pathlib import Path
import os
import sqlite3

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BANGKOK_TZ = pytz.timezone("Asia/Bangkok")
UTC_PLUS_7 = timezone(timedelta(hours=7))
CUTOFF_TIME = time(16, 0)

LOGIN_USERNAME = "lNWBOOM"
LOGIN_PASSWORD = "Boomkub555"

STANDARD_DEPARTMENTS = [
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
PD_OPTIONS = [f"L{i}" for i in range(1, 11)]

STATUS_LABELS = {
    "received": "🟠 รอจัดของ",
    "in_progress": "🟠 กำลังจัด",
    "completed": "🔵 จัดเสร็จ / รอ PD",
    "handed_over": "🟢 เสร็จสิ้น",
    "cancelled": "🔴 ยกเลิก",
}
STATUS_OPTIONS = list(STATUS_LABELS)

DB_PATH = Path(
    os.getenv(
        "WAREHOUSE_DB",
        str(Path(__file__).resolve().with_name("warehouse_tracking.db")),
    )
)


# ---------------------------------------------------------------------
# Thailand time and duration helpers
# ---------------------------------------------------------------------

def bangkok_now():
    return datetime.now(BANGKOK_TZ)


def timestamp_now():
    return bangkok_now().isoformat(sep=" ", timespec="seconds")


def parse_timestamp(value):
    if value is None or pd.isna(value) or not str(value).strip():
        return None

    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        return BANGKOK_TZ.localize(parsed)

    return parsed.astimezone(BANGKOK_TZ)


def timestamp_text(value):
    parsed = parse_timestamp(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else ""


def format_timestamp(value):
    parsed = parse_timestamp(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else "—"


def duration_minutes(start, end):
    start_dt = parse_timestamp(start)
    end_dt = parse_timestamp(end)

    if start_dt is None or end_dt is None:
        return None

    return max(0, round((end_dt - start_dt).total_seconds() / 60))


def duration_label(minutes):
    if minutes is None:
        return "—"

    if minutes < 60:
        return f"{minutes} นาที"

    hours, remainder = divmod(minutes, 60)
    return f"{hours} ชม. {remainder} นาที" if remainder else f"{hours} ชม."


def safe_average(values):
    valid_values = [
        value for value in values
        if value is not None and pd.notna(value)
    ]

    if valid_values:
        return round(sum(valid_values) / len(valid_values))

    return 0


def is_late(received_at):
    received = parse_timestamp(received_at)
    return received is not None and received.time() > CUTOFF_TIME


def normalize_job_number(value):
    value = str(value or "").strip()

    if not value:
        return ""

    if value.upper().startswith("JOB-"):
        return value.upper()

    if value.isdigit() and len(value) == 4:
        return f"JOB-{value}"

    return value.upper()


# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------

def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS requisitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_number TEXT NOT NULL UNIQUE,
                department_option TEXT NOT NULL DEFAULT 'อื่นๆ',
                department TEXT NOT NULL DEFAULT '',
                pd_zone TEXT NOT NULL DEFAULT '',
                product_name TEXT NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL DEFAULT 1,
                received_at TEXT NOT NULL,
                in_progress_at TEXT,
                picked_at TEXT,
                handover_at TEXT,
                cancelled_at TEXT,
                cancelled_by TEXT,
                cancellation_reason TEXT,
                status TEXT NOT NULL DEFAULT 'received',
                processing_minutes INTEGER,
                waiting_minutes INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(requisitions)"
            )
        }

        migrations = {
            "job_number": "TEXT",
            "department_option": "TEXT NOT NULL DEFAULT 'อื่นๆ'",
            "department": "TEXT NOT NULL DEFAULT ''",
            "pd_zone": "TEXT NOT NULL DEFAULT ''",
            "product_name": "TEXT NOT NULL DEFAULT ''",
            "quantity": "INTEGER NOT NULL DEFAULT 1",
            "received_at": "TEXT",
            "in_progress_at": "TEXT",
            "picked_at": "TEXT",
            "handover_at": "TEXT",
            "cancelled_at": "TEXT",
            "cancelled_by": "TEXT",
            "cancellation_reason": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'received'",
            "processing_minutes": "INTEGER",
            "waiting_minutes": "INTEGER",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }

        for column, definition in migrations.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE requisitions ADD COLUMN {column} {definition}"
                )

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(requisitions)"
            )
        }

        # Map fields from older app schemas when present.
        legacy_mappings = {
            "requisition_no": "job_number",
            "item_summary": "product_name",
            "received_time": "received_at",
            "completed_at": "picked_at",
            "handed_over_at": "handover_at",
            "cancellation_by": "cancelled_by",
        }

        for old_column, new_column in legacy_mappings.items():
            if old_column in columns and new_column in columns:
                connection.execute(
                    f"""
                    UPDATE requisitions
                    SET {new_column} = {old_column}
                    WHERE ({new_column} IS NULL OR {new_column} = '')
                      AND {old_column} IS NOT NULL
                    """
                )

        # Backfill computed durations for older rows.
        rows = connection.execute(
            """
            SELECT id, received_at, picked_at, handover_at,
                   processing_minutes, waiting_minutes
            FROM requisitions
            """
        ).fetchall()

        for row in rows:
            processing = duration_minutes(row["received_at"], row["picked_at"])
            waiting = duration_minutes(row["picked_at"], row["handover_at"])

            if row["processing_minutes"] is None and processing is not None:
                connection.execute(
                    "UPDATE requisitions SET processing_minutes = ? WHERE id = ?",
                    (processing, row["id"]),
                )

            if row["waiting_minutes"] is None and waiting is not None:
                connection.execute(
                    "UPDATE requisitions SET waiting_minutes = ? WHERE id = ?",
                    (waiting, row["id"]),
                )


def load_records():
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT * FROM requisitions
            WHERE job_number IS NOT NULL
            ORDER BY received_at DESC, id DESC
            """,
            connection,
        )


def insert_records(entries):
    now = timestamp_now()

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO requisitions (
                job_number, department_option, department, pd_zone,
                product_name, quantity, received_at, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'received', ?, ?)
            """,
            [
                (
                    entry["job_number"],
                    entry["department_option"],
                    entry["department"],
                    entry["pd_zone"],
                    entry["product_name"],
                    entry["quantity"],
                    entry["received_at"],
                    now,
                    now,
                )
                for entry in entries
            ],
        )


def update_workflow_times(record_id, received_at, picked_at, handover_at, status):
    processing = duration_minutes(received_at, picked_at)
    waiting = duration_minutes(picked_at, handover_at)

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE requisitions
            SET picked_at = ?,
                handover_at = ?,
                processing_minutes = ?,
                waiting_minutes = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                picked_at,
                handover_at,
                processing,
                waiting,
                status,
                timestamp_now(),
                record_id,
            ),
        )


def update_record(record_id, values):
    processing = duration_minutes(
        values["received_at"],
        values["picked_at"],
    )
    waiting = duration_minutes(
        values["picked_at"],
        values["handover_at"],
    )

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE requisitions
            SET job_number = ?,
                department_option = ?,
                department = ?,
                pd_zone = ?,
                product_name = ?,
                quantity = ?,
                received_at = ?,
                in_progress_at = ?,
                picked_at = ?,
                handover_at = ?,
                cancelled_at = ?,
                cancelled_by = ?,
                cancellation_reason = ?,
                status = ?,
                processing_minutes = ?,
                waiting_minutes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                values["job_number"],
                values["department_option"],
                values["department"],
                values["pd_zone"],
                values["product_name"],
                values["quantity"],
                values["received_at"],
                values["in_progress_at"],
                values["picked_at"],
                values["handover_at"],
                values["cancelled_at"],
                values["cancelled_by"],
                values["cancellation_reason"],
                values["status"],
                processing,
                waiting,
                timestamp_now(),
                record_id,
            ),
        )


def delete_record(record_id):
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM requisitions WHERE id = ?",
            (record_id,),
        )


# ---------------------------------------------------------------------
# Live clock and tick sound
# ---------------------------------------------------------------------

def show_live_clock():
    st.components.v1.html(
        """
        <div id="th-clock"
             style="
               display:inline-block;padding:10px 15px;
               border:1px solid #E2E8F0;border-radius:12px;
               background:#FFFFFF;color:#1E293B;
               box-shadow:0 10px 30px rgba(0,0,0,.05);
               font-family:Kanit,Prompt,Segoe UI,sans-serif;
               font-size:14px;font-weight:600;">
        </div>
        <script>
        (() => {
          const clock = document.getElementById("th-clock");

          function updateClock() {
            clock.textContent = new Intl.DateTimeFormat("th-TH", {
              timeZone: "Asia/Bangkok",
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
              hour12: false
            }).format(new Date()) + " น. · Asia/Bangkok";
          }

          updateClock();
          window.setInterval(updateClock, 1000);
        })();
        </script>
        """,
        height=52,
    )


def play_tick():
    st.components.v1.html(
        """
        <script>
        (() => {
          try {
            const parent = window.parent;
            const AudioContext = parent.AudioContext || parent.webkitAudioContext;
            if (!AudioContext) return;

            const context = new AudioContext();
            const oscillator = context.createOscillator();
            const gain = context.createGain();
            const now = context.currentTime;

            oscillator.type = "sine";
            oscillator.frequency.setValueAtTime(800, now);
            oscillator.frequency.exponentialRampToValueAtTime(400, now + 0.04);
            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.04);

            oscillator.connect(gain);
            gain.connect(context.destination);
            oscillator.start(now);
            oscillator.stop(now + 0.04);
            oscillator.onended = () => context.close();
          } catch (error) {}
        })();
        </script>
        """,
        height=0,
    )


# ---------------------------------------------------------------------
# Streamlit setup and login
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="PK Warehouse | JOB Tracking",
    page_icon="📦",
    layout="wide",
)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "page" not in st.session_state:
    st.session_state.page = "📝 บันทึกใบเบิก"


def inject_global_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700&family=Prompt:wght@300;400;500;600;700&display=swap');

        :root {
            --page-bg: #F8FAFC;
            --surface: #FFFFFF;
            --ink: #1E293B;
            --muted: #64748B;
            --line: #E2E8F0;
            --soft-shadow: 0 10px 30px rgba(0,0,0,.05);
            --emerald: #0F9F82;
            --sky: #1689B9;
        }

        html, body, [class*="css"] {
            font-family: 'Kanit', 'Prompt', sans-serif;
        }

        .stApp {
            color: var(--ink);
            background:
                radial-gradient(ellipse at 7% 0%, rgba(20,184,166,.07), transparent 32%),
                radial-gradient(ellipse at 96% 5%, rgba(59,130,246,.05), transparent 30%),
                var(--page-bg);
        }

        .block-container {
            max-width: 1520px;
            padding-top: 1.1rem;
            padding-bottom: 2.5rem;
        }

        [data-testid="stHeader"] {
            background: rgba(248,250,252,.8);
        }

        [data-testid="stSidebar"] {
            background: #F1F5F9;
            border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
            color: var(--ink);
        }

        [data-testid="stSidebar"] hr {
            border-color: #DCE4ED;
        }

        .hero {
            padding: 23px 28px;
            border: 1px solid rgba(255,255,255,.65);
            border-radius: 16px;
            color: #FFFFFF;
            background: linear-gradient(115deg,#142A41,#176D70);
            box-shadow: 0 14px 34px rgba(25,54,78,.13);
            margin-bottom: 12px;
        }

        .hero p {
            margin: 5px 0 0;
            color: #D7E9EC;
            font-size: 13px;
        }

        [data-testid="stMetric"] {
            min-height: 122px;
            padding: 17px 18px;
            border: 1px solid var(--line);
            border-radius: 16px;
            background: var(--surface);
            box-shadow: var(--soft-shadow);
        }

        [data-testid="stMetricLabel"] {
            color: var(--muted);
            font-weight: 500;
        }

        [data-testid="stMetricValue"] {
            color: var(--ink);
            font-weight: 700;
        }

        div[data-testid="stForm"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid var(--line);
            border-radius: 16px;
            background: var(--surface);
            box-shadow: var(--soft-shadow);
        }

        div[data-testid="stForm"] {
            padding: 18px;
        }

        div[data-testid="stDataFrame"] {
            overflow: hidden;
            border: 1px solid var(--line);
            border-radius: 16px;
            background: var(--surface);
            box-shadow: var(--soft-shadow);
        }

        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stDateInput"] input,
        [data-testid="stTimeInput"] input,
        [data-testid="stTextArea"] textarea {
            border-radius: 11px;
            border-color: #DCE4ED;
        }

        div.stButton > button,
        div.stFormSubmitButton > button,
        div.stDownloadButton > button {
            min-height: 40px;
            border-radius: 12px;
            font-family: 'Kanit', 'Prompt', sans-serif;
            font-weight: 600;
            transition: transform .15s ease, box-shadow .15s ease, filter .15s ease;
        }

        div.stButton > button[kind="primary"],
        div.stFormSubmitButton > button[kind="primary"],
        div.stDownloadButton > button[kind="primary"] {
            color: #FFFFFF;
            border: 0;
            background: linear-gradient(110deg,var(--emerald),var(--sky));
            box-shadow: 0 7px 18px rgba(15,159,130,.18);
        }

        div.stButton > button:hover,
        div.stFormSubmitButton > button:hover,
        div.stDownloadButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 24px rgba(22,70,90,.15);
            filter: brightness(1.03);
        }

        div.stButton > button:active,
        div.stFormSubmitButton > button:active {
            transform: scale(.985);
        }

        @media (max-width: 700px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }
            .hero {
                padding: 19px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_login():
    inject_global_css()

    st.markdown(
        """
        <div class="hero">
          <h1>📦 PK Warehouse</h1>
          <p>เข้าสู่ระบบติดตามและวิเคราะห์ใบเบิกคลังสินค้า</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button(
                "เข้าสู่ระบบ",
                type="primary",
                use_container_width=True,
            )

            if submitted:
                if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Username หรือ Password ไม่ถูกต้อง")


if not st.session_state.authenticated:
    show_login()
    st.stop()


# ---------------------------------------------------------------------
# Navigation and app header
# ---------------------------------------------------------------------

inject_global_css()
initialize_database()

with st.sidebar:
    st.markdown("## 📦 PK Warehouse")
    st.caption(f"ผู้ใช้: {LOGIN_USERNAME}")
    st.divider()

    page = st.radio(
        "เมนูหลัก",
        [
            "📝 บันทึกใบเบิก",
            "📊 Dashboard สรุปผล",
            "✏️ จัดการ/อัปเดตสถานะ",
            "📋 ประวัติ & Export",
        ],
        key="page",
    )

    st.divider()

    if st.button("ออกจากระบบ (Logout)", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

st.markdown(
    """
    <div class="hero">
      <h1>📦 PK Warehouse · JOB Tracking</h1>
      <p>บันทึก JOB • ติดตามการจัดสินค้าและ PD มารับ • วิเคราะห์คอขวด</p>
    </div>
    """,
    unsafe_allow_html=True,
)

show_live_clock()
records = load_records()


# ---------------------------------------------------------------------
# Shared filters and table formatting
# ---------------------------------------------------------------------

def select_date_range(prefix):
    today = bangkok_now().date()

    selection = st.selectbox(
        "ช่วงวันที่",
        ["วันนี้", "สัปดาห์นี้", "เลือกช่วงวันที่"],
        key=f"{prefix}_date_selection",
    )

    if selection == "วันนี้":
        return today, today

    if selection == "สัปดาห์นี้":
        return today - timedelta(days=today.weekday()), today

    start_col, end_col = st.columns(2)
    start_date = start_col.date_input(
        "วันที่เริ่มต้น",
        value=today.replace(day=1),
        key=f"{prefix}_start_date",
    )
    end_date = end_col.date_input(
        "วันที่สิ้นสุด",
        value=today,
        key=f"{prefix}_end_date",
    )

    if start_date > end_date:
        st.error("วันที่เริ่มต้นต้องไม่อยู่หลังวันที่สิ้นสุด")
        return None, None

    return start_date, end_date


def filter_records(dataframe, start_date, end_date, search_text=""):
    if dataframe.empty or start_date is None or end_date is None:
        return dataframe.iloc[0:0].copy()

    received_dates = dataframe["received_at"].apply(
        lambda value: (
            parse_timestamp(value).date()
            if parse_timestamp(value)
            else None
        )
    )

    filtered = dataframe[
        received_dates.apply(
            lambda value: value is not None
            and start_date <= value <= end_date
        )
    ].copy()

    query = search_text.strip().casefold()
    if query:
        columns = [
            column
            for column in [
                "job_number",
                "product_name",
                "department",
                "pd_zone",
            ]
            if column in filtered.columns
        ]

        if columns:
            mask = (
                filtered[columns]
                .fillna("")
                .astype(str)
                .apply(
                    lambda column: column.str.casefold().str.contains(
                        query,
                        regex=False,
                    )
                )
                .any(axis=1)
            )
            filtered = filtered[mask]

    return filtered


def status_cell_style(value):
    value = str(value)

    if "เสร็จสิ้น" in value:
        return (
            "background-color:#D1FAE5;color:#065F46;"
            "font-weight:600;border-radius:999px"
        )
    if "ยกเลิก" in value:
        return (
            "background-color:#FEE2E2;color:#991B1B;"
            "font-weight:600;border-radius:999px"
        )
    if "จัดเสร็จ" in value:
        return (
            "background-color:#DBEAFE;color:#1E40AF;"
            "font-weight:600;border-radius:999px"
        )
    if "กำลังจัด" in value or "รอจัด" in value:
        return (
            "background-color:#FEF3C7;color:#92400E;"
            "font-weight:600;border-radius:999px"
        )

    return ""


def create_display_table(dataframe):
    rows = []

    for _, row in dataframe.iterrows():
        rows.append(
            {
                "Job ID": row["id"],
                "เลขที่ JOB": row["job_number"],
                "สินค้า": row["product_name"],
                "จำนวน": row["quantity"],
                "แผนก": row["department"],
                "PD / ไลน์": row["pd_zone"],
                "📥 รับใบเบิก": format_timestamp(row["received_at"]),
                "🟠 เริ่มจัด": format_timestamp(row["in_progress_at"]),
                "🔵 จัดเสร็จ": format_timestamp(row["picked_at"]),
                "🟢 PD มารับ": format_timestamp(row["handover_at"]),
                "❌ ยกเลิก": format_timestamp(row["cancelled_at"]),
                "สถานะ": STATUS_LABELS.get(row["status"], row["status"]),
                "ใบเบิกเย็น": (
                    "🔴 ใช่" if is_late(row["received_at"]) else "🟢 ไม่ใช่"
                ),
                "เวลาจัด": duration_label(
                    duration_minutes(row["received_at"], row["picked_at"])
                ),
                "เวลารอ PD": duration_label(
                    duration_minutes(row["picked_at"], row["handover_at"])
                ),
                "ผู้สั่งยกเลิก": row["cancelled_by"] or "—",
                "สาเหตุยกเลิก": row["cancellation_reason"] or "—",
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "Job ID",
            "เลขที่ JOB",
            "สินค้า",
            "จำนวน",
            "แผนก",
            "PD / ไลน์",
            "📥 รับใบเบิก",
            "🟠 เริ่มจัด",
            "🔵 จัดเสร็จ",
            "🟢 PD มารับ",
            "❌ ยกเลิก",
            "สถานะ",
            "ใบเบิกเย็น",
            "เวลาจัด",
            "เวลารอ PD",
            "ผู้สั่งยกเลิก",
            "สาเหตุยกเลิก",
        ],
    )


def show_styled_table(dataframe, height=450):
    styled = dataframe.style.map(
        status_cell_style,
        subset=["สถานะ"],
    )
    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=height,
    )


# ---------------------------------------------------------------------
# Page 1: Add multiple jobs
# ---------------------------------------------------------------------

if page == "📝 บันทึกใบเบิก":
    st.subheader("📝 บันทึกใบเบิก")
    st.caption(
        f"เวลาไทย: {bangkok_now():%Y-%m-%d %H:%M:%S} น. "
        "ระบบจะประทับเวลาตอนกดบันทึก"
    )

    st.info(
        "รายชื่อแผนกมาตรฐาน: "
        + " • ".join(STANDARD_DEPARTMENTS)
        + " | ในแต่ละแถวเลือกแผนกมาตรฐานหรือพิมพ์ชื่อใหม่ได้ในช่องเดียว"
    )

    row_count = st.selectbox(
        "จำนวนแถวสำหรับกรอก JOB",
        list(range(1, 11)),
        index=2,
        key="new_job_row_count",
    )

    with st.container(border=True):
        st.markdown("#### รายการ JOB")
        st.caption(
            "ช่องแผนกเป็น dropdown ที่รับข้อความใหม่ได้ "
            "• PD/ไลน์เลือกได้เฉพาะ L1–L10"
        )

        with st.form("new_records_form", clear_on_submit=True):
            entries = []

            for index in range(row_count):
                st.markdown(f"**รายการที่ {index + 1}**")
                job_col, dept_col, pd_col, product_col, qty_col = st.columns(
                    [1.05, 1.55, 0.8, 1.5, 0.6]
                )

                job_number = job_col.text_input(
                    "เลขที่ JOB",
                    key=f"new_job_{index}",
                    placeholder="JOB-6901",
                )

                department = dept_col.selectbox(
                    "แผนก",
                    STANDARD_DEPARTMENTS,
                    accept_new_options=True,
                    key=f"new_department_{index}",
                    help="เลือกจากรายการหรือพิมพ์ชื่อแผนกใหม่",
                )

                pd_zone = pd_col.selectbox(
                    "PD / ไลน์",
                    PD_OPTIONS,
                    key=f"new_pd_{index}",
                )

                product_name = product_col.text_input(
                    "ชื่อสินค้า",
                    key=f"new_product_{index}",
                    placeholder="ชื่อสินค้า",
                )

                quantity = qty_col.number_input(
                    "จำนวน",
                    min_value=1,
                    step=1,
                    value=1,
                    key=f"new_quantity_{index}",
                )

                entries.append(
                    {
                        "job_number": job_number,
                        "department": department,
                        "pd_zone": pd_zone,
                        "product_name": product_name,
                        "quantity": quantity,
                    }
                )

                if index < row_count - 1:
                    st.markdown(
                        "<hr style='margin:8px 0;border-color:#E2E8F0'>",
                        unsafe_allow_html=True,
                    )

            submit_entries = st.form_submit_button(
                "📥 บันทึกรับเรื่องทั้งหมด",
                type="primary",
                use_container_width=True,
            )

            if submit_entries:
                completed_entries = []
                errors = []

                for index, entry in enumerate(entries, start=1):
                    raw_job = str(entry["job_number"] or "").strip()
                    department = str(entry["department"] or "").strip()
                    pd_zone = str(entry["pd_zone"] or "").strip()
                    product_name = str(entry["product_name"] or "").strip()

                    if not any([raw_job, product_name]):
                        continue

                    job_number = normalize_job_number(raw_job)

                    if not job_number:
                        errors.append(f"แถว {index}: กรุณากรอกเลข JOB")
                        continue
                    if not department:
                        errors.append(f"{job_number}: กรุณาเลือกหรือพิมพ์แผนก")
                        continue
                    if pd_zone not in PD_OPTIONS:
                        errors.append(
                            f"{job_number}: กรุณาเลือก PD/ไลน์ L1–L10"
                        )
                        continue
                    if not product_name:
                        errors.append(f"{job_number}: กรุณากรอกชื่อสินค้า")
                        continue

                    completed_entries.append(
                        {
                            "job_number": job_number,
                            "department_option": (
                                department
                                if department in STANDARD_DEPARTMENTS
                                else "อื่นๆ"
                            ),
                            "department": department,
                            "pd_zone": pd_zone,
                            "product_name": product_name,
                            "quantity": int(entry["quantity"]),
                        }
                    )

                existing_numbers = (
                    {str(value).casefold() for value in records["job_number"]}
                    if not records.empty
                    else set()
                )
                batch_numbers = [
                    entry["job_number"].casefold()
                    for entry in completed_entries
                ]

                duplicates_in_batch = {
                    value
                    for value in batch_numbers
                    if batch_numbers.count(value) > 1
                }
                duplicates_existing = [
                    entry["job_number"]
                    for entry in completed_entries
                    if entry["job_number"].casefold() in existing_numbers
                ]

                if errors:
                    for error in errors:
                        st.error(error)
                elif not completed_entries:
                    st.warning("กรุณากรอก JOB อย่างน้อยหนึ่งรายการ")
                elif duplicates_in_batch:
                    st.error(
                        "พบเลข JOB ซ้ำในรายการที่กรอก: "
                        + ", ".join(sorted(duplicates_in_batch))
                    )
                elif duplicates_existing:
                    st.error(
                        "เลข JOB เหล่านี้มีในระบบแล้ว: "
                        + ", ".join(duplicates_existing)
                    )
                else:
                    received_at = timestamp_now()
                    for entry in completed_entries:
                        entry["received_at"] = received_at

                    try:
                        insert_records(completed_entries)
                        st.success(
                            f"บันทึกใบเบิกแล้ว {len(completed_entries)} JOB"
                        )
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(
                            "พบเลข JOB ซ้ำในฐานข้อมูล "
                            "กรุณาตรวจสอบแล้วลองอีกครั้ง"
                        )


# ---------------------------------------------------------------------
# Page 2: Dashboard
# ---------------------------------------------------------------------

elif page == "📊 Dashboard สรุปผล":
    st.subheader("📊 Dashboard สรุปผล")

    filter_col, search_col = st.columns([1, 1])

    with filter_col:
        start_date, end_date = select_date_range("dashboard")

    with search_col:
        dashboard_search = st.text_input(
            "🔎 ค้นหา JOB / สินค้า / แผนก / PD",
            key="dashboard_search",
        )

    selected = filter_records(
        records,
        start_date,
        end_date,
        dashboard_search,
    )

    if selected.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิกในช่วงเวลาที่เลือก")

    processing_values = [
        duration_minutes(row["received_at"], row["picked_at"])
        for _, row in selected.iterrows()
        if row["picked_at"]
    ]
    processing_values = [
        value for value in processing_values if value is not None
    ]

    waiting_values = [
        duration_minutes(row["picked_at"], row["handover_at"])
        for _, row in selected.iterrows()
        if row["picked_at"] and row["handover_at"]
    ]
    waiting_values = [
        value for value in waiting_values if value is not None
    ]

    avg_processing = safe_average(processing_values)
    avg_waiting = safe_average(waiting_values)

    today = bangkok_now().date()
    today_count = 0

    if not records.empty:
        for value in records["received_at"]:
            parsed = parse_timestamp(value)
            if parsed and parsed.date() == today:
                today_count += 1

    pending_count = (
        int(
            selected["status"]
            .isin(["received", "in_progress", "completed"])
            .sum()
        )
        if not selected.empty
        else 0
    )

    if not processing_values and not waiting_values:
        bottleneck = "รอข้อมูล"
    elif waiting_values and avg_waiting > avg_processing:
        bottleneck = "รอ PD มารับ"
    else:
        bottleneck = "ขั้นตอนจัดสินค้า"

    kpis = st.columns(4)
    kpis[0].metric("📥 ยอดเบิกวันนี้", f"{today_count:,}")
    kpis[1].metric("📦 JOB ค้างดำเนินการ", f"{pending_count:,}")
    kpis[2].metric(
        "⏱️ เวลาจัดเฉลี่ย",
        duration_label(avg_processing) if processing_values else "0 นาที",
    )
    kpis[3].metric("🚦 จุดคอขวด", bottleneck)

    if not selected.empty:
        chart_col, status_col = st.columns(2)

        with chart_col:
            hourly_data = selected.copy()
            hourly_data["received_dt"] = hourly_data["received_at"].apply(
                parse_timestamp
            )
            hourly_data["ชั่วโมง"] = hourly_data["received_dt"].apply(
                lambda value: value.hour if value else None
            )

            hourly = (
                hourly_data.dropna(subset=["ชั่วโมง"])
                .groupby("ชั่วโมง")
                .size()
                .reindex(range(7, 22), fill_value=0)
                .rename("จำนวน JOB")
                .reset_index()
            )

            figure = px.bar(
                hourly,
                x="ชั่วโมง",
                y="จำนวน JOB",
                title="จำนวนใบเบิกรายชั่วโมง",
                text="จำนวน JOB",
                color="จำนวน JOB",
                color_continuous_scale=["#99F6E4", "#0F9F82"],
            )
            figure.update_layout(
                template="plotly_white",
                height=340,
                coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=55, b=10),
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
            )
            st.plotly_chart(figure, use_container_width=True)

        with status_col:
            status_counts = (
                selected["status"]
                .map(STATUS_LABELS)
                .value_counts()
                .rename_axis("สถานะ")
                .reset_index(name="จำนวน JOB")
            )

            figure = px.pie(
                status_counts,
                names="สถานะ",
                values="จำนวน JOB",
                title="สัดส่วนสถานะใบเบิก",
                hole=0.52,
                color_discrete_sequence=[
                    "#F59E0B",
                    "#3B82F6",
                    "#10B981",
                    "#EF4444",
                    "#64748B",
                ],
            )
            figure.update_layout(
                template="plotly_white",
                height=340,
                margin=dict(l=10, r=10, t=55, b=10),
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
            )
            st.plotly_chart(figure, use_container_width=True)

        late_data = selected.copy()
        late_data["ช่วงเวลารับ"] = late_data["received_at"].apply(
            lambda value: "ใบเบิกเย็น" if is_late(value) else "ก่อน Cut-off"
        )
        department_summary = (
            late_data.groupby(["department", "ช่วงเวลารับ"])
            .size()
            .reset_index(name="จำนวน JOB")
        )

        st.markdown("#### 🔴 ใบเบิกเย็นแยกตามแผนก")

        figure = px.bar(
            department_summary,
            x="department",
            y="จำนวน JOB",
            color="ช่วงเวลารับ",
            barmode="group",
            color_discrete_map={
                "ใบเบิกเย็น": "#EF4444",
                "ก่อน Cut-off": "#10B981",
            },
        )
        figure.update_layout(
            template="plotly_white",
            height=320,
            margin=dict(l=10, r=10, t=25, b=10),
            xaxis_title="แผนก",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(figure, use_container_width=True)

        stage_rows = []

        for _, row in selected.iterrows():
            processing = duration_minutes(
                row["received_at"],
                row["picked_at"],
            )
            waiting = duration_minutes(
                row["picked_at"],
                row["handover_at"],
            )

            if processing is not None:
                stage_rows.append(
                    {
                        "ขั้นตอน": "รับเรื่องถึงจัดเสร็จ",
                        "นาที": processing,
                    }
                )
            if waiting is not None:
                stage_rows.append(
                    {
                        "ขั้นตอน": "จัดเสร็จถึง PD มารับ",
                        "นาที": waiting,
                    }
                )

        if stage_rows:
            stage_summary = (
                pd.DataFrame(stage_rows)
                .groupby("ขั้นตอน")["นาที"]
                .mean()
                .round(1)
                .reset_index()
            )

            figure = px.bar(
                stage_summary,
                x="ขั้นตอน",
                y="นาที",
                color="ขั้นตอน",
                text="นาที",
                title="เวลาเฉลี่ยในแต่ละขั้นตอน",
                color_discrete_sequence=["#0F9F82", "#3B82F6"],
            )
            figure.update_layout(
                template="plotly_white",
                height=300,
                showlegend=False,
                margin=dict(l=10, r=10, t=50, b=10),
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
            )
            st.plotly_chart(figure, use_container_width=True)


# ---------------------------------------------------------------------
# Page 3: Workflow, edit, cancel and delete
# ---------------------------------------------------------------------

elif page == "✏️ จัดการ/อัปเดตสถานะ":
    st.subheader("✏️ จัดการและอัปเดตสถานะ")

    if records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
    else:
        job_options = {
            f"ID {int(row['id'])} · {row['job_number']} · "
            f"{row['department']} · {row['pd_zone']} · {row['product_name']}": int(row["id"])
            for _, row in records.iterrows()
        }

        selected_label = st.selectbox("เลือก Job ID", list(job_options))
        selected_id = job_options[selected_label]
        selected = records[records["id"] == selected_id].iloc[0]

        st.markdown("#### ⏱️ Hybrid Timestamp")
        st.caption(
            f"เวลาไทยปัจจุบัน: {bangkok_now():%Y-%m-%d %H:%M:%S} "
            "• กด Auto Timestamp หรือแก้เวลาเองได้"
        )

        picked_key = f"picked_timestamp_{selected_id}"
        handover_key = f"handover_timestamp_{selected_id}"

        if picked_key not in st.session_state:
            st.session_state[picked_key] = timestamp_text(selected["picked_at"])
        if handover_key not in st.session_state:
            st.session_state[handover_key] = timestamp_text(
                selected["handover_at"]
            )

        auto_picked_col, auto_handover_col = st.columns(2)

        with auto_picked_col:
            if st.button(
                "⏱️ ลงเวลาปัจจุบัน · จัดเสร็จ",
                type="primary",
                use_container_width=True,
                key=f"auto_picked_{selected_id}",
            ):
                st.session_state[picked_key] = timestamp_now()

        with auto_handover_col:
            if st.button(
                "⏱️ ลงเวลาปัจจุบัน · PD มารับ",
                type="primary",
                use_container_width=True,
                key=f"auto_handover_{selected_id}",
            ):
                st.session_state[handover_key] = timestamp_now()

        picked_col, handover_col = st.columns(2)
        picked_input = picked_col.text_input(
            "เวลาจัดสินค้าเสร็จ",
            key=picked_key,
            help="รูปแบบ YYYY-MM-DD HH:MM:SS แก้เวลาเองได้",
        )
        handover_input = handover_col.text_input(
            "เวลา PD มารับสินค้า",
            key=handover_key,
            help="รูปแบบ YYYY-MM-DD HH:MM:SS แก้เวลาเองได้",
        )

        if st.button(
            "💾 บันทึกการอัปเดตสถานะ",
            type="primary",
            use_container_width=True,
            key=f"save_workflow_{selected_id}",
        ):
            picked_dt = parse_timestamp(picked_input)
            handover_dt = parse_timestamp(handover_input)
            received_dt = parse_timestamp(selected["received_at"])

            if picked_input.strip() and picked_dt is None:
                st.error("รูปแบบเวลาจัดเสร็จไม่ถูกต้อง")
            elif handover_input.strip() and handover_dt is None:
                st.error("รูปแบบเวลา PD มารับไม่ถูกต้อง")
            elif handover_dt and not picked_dt:
                st.error("กรุณาบันทึกเวลาจัดเสร็จก่อนเวลาที่ PD มารับ")
            elif picked_dt and received_dt and picked_dt < received_dt:
                st.error("เวลาจัดเสร็จต้องไม่ก่อนเวลารับใบเบิก")
            elif handover_dt and picked_dt and handover_dt < picked_dt:
                st.error("เวลา PD มารับต้องไม่ก่อนเวลาจัดเสร็จ")
            else:
                picked_value = (
                    picked_dt.isoformat(sep=" ", timespec="seconds")
                    if picked_dt
                    else None
                )
                handover_value = (
                    handover_dt.isoformat(sep=" ", timespec="seconds")
                    if handover_dt
                    else None
                )

                if handover_value:
                    new_status = "handed_over"
                elif picked_value:
                    new_status = "completed"
                elif selected["status"] in ("completed", "handed_over"):
                    new_status = "in_progress"
                else:
                    new_status = selected["status"]

                update_workflow_times(
                    selected_id,
                    selected["received_at"],
                    picked_value,
                    handover_value,
                    new_status,
                )
                play_tick()

                processing = duration_minutes(
                    selected["received_at"],
                    picked_value,
                )
                waiting = duration_minutes(
                    picked_value,
                    handover_value,
                )

                st.success(
                    "บันทึกแล้ว • เวลาจัด "
                    f"{duration_label(processing)} • เวลารอ PD "
                    f"{duration_label(waiting)}"
                )
                st.rerun()

        metric_col1, metric_col2 = st.columns(2)
        metric_col1.metric(
            "⏱️ Processing Time",
            duration_label(
                duration_minutes(selected["received_at"], selected["picked_at"])
            ),
        )
        metric_col2.metric(
            "🕒 Waiting Time",
            duration_label(
                duration_minutes(selected["picked_at"], selected["handover_at"])
            ),
        )

        st.divider()
        st.markdown("#### ✏️ แก้ไขรายละเอียดใบเบิก")

        current_department = str(selected["department"] or "")
        current_pd = str(selected["pd_zone"] or "")
        pd_index = PD_OPTIONS.index(current_pd) if current_pd in PD_OPTIONS else 0

        with st.container(border=True):
            with st.form("edit_record_form"):
                col1, col2 = st.columns(2)

                edited_job = col1.text_input(
                    "เลขที่ JOB",
                    value=str(selected["job_number"]),
                )
                edited_department = col2.selectbox(
                    "แผนก",
                    STANDARD_DEPARTMENTS,
                    index=(
                        STANDARD_DEPARTMENTS.index(current_department)
                        if current_department in STANDARD_DEPARTMENTS
                        else 0
                    ),
                    accept_new_options=True,
                    help="เลือกแผนกมาตรฐานหรือพิมพ์ชื่อใหม่",
                )
                edited_product = col1.text_input(
                    "ชื่อสินค้า",
                    value=str(selected["product_name"] or ""),
                )
                edited_pd = col2.selectbox(
                    "PD / ไลน์ผลิต",
                    PD_OPTIONS,
                    index=pd_index,
                )
                edited_quantity = col1.number_input(
                    "จำนวน",
                    min_value=1,
                    step=1,
                    value=max(1, int(selected["quantity"] or 1)),
                )
                edited_received = col2.text_input(
                    "เวลารับใบเบิก (YYYY-MM-DD HH:MM:SS)",
                    value=timestamp_text(selected["received_at"]),
                )
                edited_status = st.selectbox(
                    "สถานะ",
                    STATUS_OPTIONS,
                    index=(
                        STATUS_OPTIONS.index(selected["status"])
                        if selected["status"] in STATUS_OPTIONS
                        else 0
                    ),
                    format_func=lambda value: STATUS_LABELS[value],
                )
                edited_cancel_by = st.text_input(
                    "ผู้สั่งยกเลิก PN/PD",
                    value=str(selected["cancelled_by"] or ""),
                )
                edited_cancel_reason = st.text_area(
                    "สาเหตุการยกเลิก",
                    value=str(selected["cancellation_reason"] or ""),
                )

                save_edit = st.form_submit_button(
                    "💾 บันทึกการแก้ไข",
                    type="primary",
                    use_container_width=True,
                )

                if save_edit:
                    received_dt = parse_timestamp(edited_received)
                    normalized_job = normalize_job_number(edited_job)

                    if not normalized_job:
                        st.error("กรุณากรอกเลข JOB")
                    elif not str(edited_department).strip():
                        st.error("กรุณากรอกแผนก")
                    elif not edited_product.strip():
                        st.error("กรุณากรอกชื่อสินค้า")
                    elif received_dt is None:
                        st.error("รูปแบบเวลารับใบเบิกไม่ถูกต้อง")
                    elif edited_status == "cancelled" and (
                        not edited_cancel_by.strip()
                        or not edited_cancel_reason.strip()
                    ):
                        st.error("สถานะยกเลิกต้องระบุผู้สั่งและสาเหตุ")
                    else:
                        department_value = str(edited_department).strip()
                        values = {
                            "job_number": normalized_job,
                            "department_option": (
                                department_value
                                if department_value in STANDARD_DEPARTMENTS
                                else "อื่นๆ"
                            ),
                            "department": department_value,
                            "pd_zone": edited_pd,
                            "product_name": edited_product.strip(),
                            "quantity": int(edited_quantity),
                            "received_at": received_dt.isoformat(
                                sep=" ",
                                timespec="seconds",
                            ),
                            "in_progress_at": selected["in_progress_at"],
                            "picked_at": selected["picked_at"],
                            "handover_at": selected["handover_at"],
                            "cancelled_at": selected["cancelled_at"],
                            "cancelled_by": edited_cancel_by.strip(),
                            "cancellation_reason": edited_cancel_reason.strip(),
                            "status": edited_status,
                        }

                        try:
                            update_record(selected_id, values)
                            st.success("แก้ไขรายการแล้ว")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("เลข JOB นี้มีอยู่แล้ว")

        st.divider()
        st.markdown("#### 🔴 ยกเลิกหรือลบรายการ")

        cancel_col, delete_col = st.columns(2)

        with cancel_col:
            with st.container(border=True):
                cancel_by = st.text_input(
                    "ผู้สั่งยกเลิก PN/PD",
                    key=f"cancel_by_{selected_id}",
                )
                cancel_reason = st.text_area(
                    "สาเหตุการยกเลิก",
                    key=f"cancel_reason_{selected_id}",
                )
                confirm_cancel = st.checkbox(
                    "ยืนยันว่าต้องการยกเลิก JOB นี้",
                    key=f"confirm_cancel_{selected_id}",
                )

                if st.button(
                    "🔴 ยืนยันยกเลิก JOB",
                    disabled=not confirm_cancel,
                    key=f"cancel_button_{selected_id}",
                ):
                    if not cancel_by.strip() or not cancel_reason.strip():
                        st.error("กรุณาระบุผู้สั่งยกเลิกและสาเหตุ")
                    else:
                        department_value = str(selected["department"] or "")
                        cancel_values = {
                            "job_number": selected["job_number"],
                            "department_option": (
                                department_value
                                if department_value in STANDARD_DEPARTMENTS
                                else "อื่นๆ"
                            ),
                            "department": department_value,
                            "pd_zone": selected["pd_zone"],
                            "product_name": selected["product_name"],
                            "quantity": int(selected["quantity"]),
                            "received_at": selected["received_at"],
                            "in_progress_at": selected["in_progress_at"],
                            "picked_at": selected["picked_at"],
                            "handover_at": selected["handover_at"],
                            "cancelled_at": timestamp_now(),
                            "cancelled_by": cancel_by.strip(),
                            "cancellation_reason": cancel_reason.strip(),
                            "status": "cancelled",
                        }
                        update_record(selected_id, cancel_values)
                        st.success("ยกเลิก JOB และเก็บประวัติไว้แล้ว")
                        st.rerun()

        with delete_col:
            with st.container(border=True):
                st.caption("การลบจะนำรายการออกจากระบบถาวร")
                confirm_delete = st.checkbox(
                    "ยืนยันว่าต้องการลบ JOB นี้ถาวร",
                    key=f"confirm_delete_{selected_id}",
                )

                if st.button(
                    "🗑️ ลบรายการถาวร",
                    disabled=not confirm_delete,
                    key=f"delete_button_{selected_id}",
                ):
                    delete_record(selected_id)
                    st.success("ลบรายการแล้ว")
                    st.rerun()


# ---------------------------------------------------------------------
# Page 4: History and Excel export
# ---------------------------------------------------------------------

elif page == "📋 ประวัติ & Export":
    st.subheader("📋 ประวัติและส่งออกข้อมูล")

    filter_col, search_col = st.columns([1, 1])

    with filter_col:
        start_date, end_date = select_date_range("history")

    with search_col:
        history_search = st.text_input(
            "🔎 ค้นหา JOB / สินค้า / แผนก / PD",
            key="history_search",
        )

    historical_records = filter_records(
        records,
        start_date,
        end_date,
        history_search,
    )

    if historical_records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิกในช่วงเวลาที่เลือก")

    history_df = create_display_table(historical_records)
    show_styled_table(history_df, height=450)

    excel_buffer = BytesIO()

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        history_df.to_excel(
            writer,
            index=False,
            sheet_name="Requisition History",
        )

    excel_buffer.seek(0)

    st.download_button(
        "📥 ดาวน์โหลดข้อมูลที่กรองเป็น Excel",
        data=excel_buffer,
        file_name=f"warehouse_history_{bangkok_now():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
