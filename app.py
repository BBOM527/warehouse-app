"""PK Warehouse | Historical Requisition Dashboard

รันด้วย:
    streamlit run app.py

ติดตั้ง dependencies:
    pip install streamlit pandas plotly openpyxl
"""

from datetime import date, datetime, time, timezone, timedelta
from io import BytesIO
from pathlib import Path
import os
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BANGKOK_TZ = timezone(timedelta(hours=7), name="Asia/Bangkok")
CUTOFF_TIME = time(16, 0)

LOGIN_USERNAME = "lNWBOOM"
LOGIN_PASSWORD = "Boomkub555"

DEPARTMENTS = [
    "",
    "PD-Line 1",
    "PD-Line 2",
    "PD-Line 3",
    "PN-Line 1",
    "PN-Line 2",
    "ซ่อมบำรุง",
    "คุณภาพ",
    "คลังสินค้า",
    "อื่น ๆ",
]

STATUS_LABELS = {
    "received": "🟡 รับใบเบิก / รอดำเนินการ",
    "in_progress": "🟡 กำลังจัด",
    "completed": "🔵 จัดเสร็จ / รอรับ",
    "handed_over": "🟢 จ่ายของแล้ว",
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
# Thailand time helpers
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
        return parsed.replace(tzinfo=BANGKOK_TZ)

    return parsed.astimezone(BANGKOK_TZ)


def timestamp_text(value):
    parsed = parse_timestamp(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else ""


def format_timestamp(value):
    parsed = parse_timestamp(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else "—"


def is_late(value):
    received = parse_timestamp(value)
    return received is not None and received.time() > CUTOFF_TIME


def duration_minutes(start, end):
    start_dt = parse_timestamp(start)
    end_dt = parse_timestamp(end)

    if start_dt is None or end_dt is None:
        return None

    return max(0, round((end_dt - start_dt).total_seconds() / 60))


def safe_average(values):
    valid_values = [
        value for value in values
        if value is not None and pd.notna(value)
    ]
    if valid_values:
        return round(sum(valid_values) / len(valid_values))
    return 0


def duration_label(minutes):
    if minutes is None:
        return "—"

    if minutes < 60:
        return f"{minutes} นาที"

    hours, remainder = divmod(minutes, 60)
    return (
        f"{hours} ชม. {remainder} นาที"
        if remainder
        else f"{hours} ชม."
    )


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
                department TEXT NOT NULL,
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
            "department": "TEXT NOT NULL DEFAULT ''",
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

        # เติมข้อมูลจากชื่อคอลัมน์ของ schema รุ่นก่อน ถ้ามี
        if "requisition_no" in columns:
            connection.execute(
                """
                UPDATE requisitions
                SET job_number = requisition_no
                WHERE (job_number IS NULL OR job_number = '')
                  AND requisition_no IS NOT NULL
                """
            )

        if "item_summary" in columns:
            connection.execute(
                """
                UPDATE requisitions
                SET product_name = item_summary
                WHERE (product_name IS NULL OR product_name = '')
                  AND item_summary IS NOT NULL
                """
            )

        if "received_time" in columns:
            connection.execute(
                """
                UPDATE requisitions
                SET received_at = received_time
                WHERE (received_at IS NULL OR received_at = '')
                  AND received_time IS NOT NULL
                """
            )

        if "completed_at" in columns:
            connection.execute(
                """
                UPDATE requisitions
                SET picked_at = completed_at
                WHERE (picked_at IS NULL OR picked_at = '')
                  AND completed_at IS NOT NULL
                """
            )

        if "handed_over_at" in columns:
            connection.execute(
                """
                UPDATE requisitions
                SET handover_at = handed_over_at
                WHERE (handover_at IS NULL OR handover_at = '')
                  AND handed_over_at IS NOT NULL
                """
            )

        if "cancellation_by" in columns:
            connection.execute(
                """
                UPDATE requisitions
                SET cancelled_by = cancellation_by
                WHERE (cancelled_by IS NULL OR cancelled_by = '')
                  AND cancellation_by IS NOT NULL
                """
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
                job_number, department, product_name, quantity,
                received_at, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'received', ?, ?)
            """,
            [
                (
                    entry["job_number"],
                    entry["department"],
                    entry["product_name"],
                    entry["quantity"],
                    entry["received_at"],
                    now,
                    now,
                )
                for entry in entries
            ],
        )


def update_record(record_id, values):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE requisitions
            SET job_number = ?,
                department = ?,
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
                updated_at = ?
            WHERE id = ?
            """,
            (
                values["job_number"],
                values["department"],
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
                timestamp_now(),
                record_id,
            ),
        )


def update_status_times(record_id, picked_at, handover_at, status):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE requisitions
            SET picked_at = ?,
                handover_at = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                picked_at,
                handover_at,
                status,
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
# Live clock
# ---------------------------------------------------------------------

def show_live_clock():
    st.components.v1.html(
        """
        <div id="th-clock"
             style="
               display:inline-block;
               padding:10px 15px;
               border:1px solid rgba(255,255,255,.7);
               border-radius:12px;
               background:rgba(255,255,255,.78);
               color:#17304a;
               box-shadow:0 7px 20px rgba(26,48,71,.08);
               font-family:Segoe UI,Tahoma,sans-serif;
               font-size:14px;
               font-weight:650;">
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


# ---------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="PK Warehouse | Requisition Dashboard",
    page_icon="📦",
    layout="wide",
)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "page" not in st.session_state:
    st.session_state.page = "📝 บันทึกใบเบิกใหม่"


def show_login():
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(ellipse at 15% 5%, rgba(68,145,153,.18), transparent 35%),
                radial-gradient(ellipse at 90% 10%, rgba(86,111,177,.15), transparent 32%),
                #f3f6fa;
        }
        .login-card {
            max-width: 440px;
            margin: 9vh auto 0;
            padding: 26px;
            border: 1px solid rgba(255,255,255,.9);
            border-radius: 12px;
            background: rgba(255,255,255,.88);
            box-shadow: 0 16px 45px rgba(24,46,72,.12);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="login-card">
            <h1>📦 PK Warehouse</h1>
            <p>เข้าสู่ระบบบันทึกและวิเคราะห์ใบเบิกคลังสินค้า</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
# Main app styling and navigation
# ---------------------------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --shadow: 0 10px 28px rgba(26,48,71,.08);
    }

    .stApp {
        background:
            radial-gradient(ellipse at 8% 0%, rgba(76,153,165,.12), transparent 34%),
            radial-gradient(ellipse at 96% 8%, rgba(91,117,185,.10), transparent 30%),
            #f3f6fa;
    }

    .block-container {
        max-width: 1500px;
        padding-top: 1.2rem;
        padding-bottom: 2.5rem;
    }

    .hero {
        padding: 22px 26px;
        border: 1px solid rgba(255,255,255,.45);
        border-radius: 12px;
        color: white;
        background: linear-gradient(115deg, #132940, #176d70);
        box-shadow: 0 17px 38px rgba(25,54,78,.17);
        margin-bottom: 14px;
    }

    .hero p {
        margin: 4px 0 0;
        color: #d5e7eb;
    }

    [data-testid="stMetric"] {
        background: rgba(255,255,255,.84);
        border: 1px solid rgba(255,255,255,.95);
        border-radius: 12px;
        padding: 15px 17px;
        box-shadow: var(--shadow);
        backdrop-filter: blur(10px);
    }

    div[data-testid="stForm"] {
        background: rgba(255,255,255,.82);
        border: 1px solid rgba(255,255,255,.95);
        border-radius: 12px;
        padding: 17px;
        box-shadow: var(--shadow);
    }

    div.stButton > button,
    div.stFormSubmitButton > button,
    div.stDownloadButton > button {
        border-radius: 10px;
        transition: transform .12s ease, box-shadow .15s ease;
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover,
    div.stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 7px 18px rgba(28,55,78,.16);
    }

    div.stButton > button:active,
    div.stFormSubmitButton > button:active {
        transform: scale(.98);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

initialize_database()

with st.sidebar:
    st.markdown("## 📦 PK Warehouse")
    st.caption(f"ผู้ใช้: {LOGIN_USERNAME}")
    st.divider()

    page = st.radio(
        "เมนู",
        [
            "📝 บันทึกใบเบิกใหม่",
            "📊 Dashboard สรุปผล",
            "✏️ จัดการและแก้ไขรายการ",
            "📋 ประวัติและส่งออกข้อมูล Excel",
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
        <h1>📦 PK Warehouse · Requisition Dashboard</h1>
        <p>ติดตาม JOB • ดูประวัติย้อนหลัง • วิเคราะห์เวลาและจุดคอขวด</p>
    </div>
    """,
    unsafe_allow_html=True,
)

show_live_clock()
records = load_records()


# ---------------------------------------------------------------------
# Historical date filter
# ---------------------------------------------------------------------

def historical_filter(prefix):
    today = bangkok_now().date()

    mode = st.selectbox(
        "ช่วงเวลาที่ต้องการดู",
        ["กำหนดช่วงวันที่", "รายเดือน", "รายปี"],
        key=f"{prefix}_period_mode",
    )

    if mode == "กำหนดช่วงวันที่":
        col1, col2 = st.columns(2)
        start_date = col1.date_input(
            "วันที่เริ่มต้น",
            value=today.replace(day=1),
            key=f"{prefix}_start_date",
        )
        end_date = col2.date_input(
            "วันที่สิ้นสุด",
            value=today,
            key=f"{prefix}_end_date",
        )

    elif mode == "รายเดือน":
        col1, col2 = st.columns(2)

        year_options = list(range(today.year - 10, today.year + 1))
        selected_year = col1.selectbox(
            "ปี",
            year_options,
            index=len(year_options) - 1,
            key=f"{prefix}_month_year",
        )
        selected_month = col2.selectbox(
            "เดือน",
            list(range(1, 13)),
            index=today.month - 1,
            format_func=lambda month: f"{month:02d}",
            key=f"{prefix}_month",
        )

        start_date = date(selected_year, selected_month, 1)
        if selected_month == 12:
            end_date = date(selected_year, 12, 31)
        else:
            end_date = date(
                selected_year,
                selected_month + 1,
                1,
            ) - timedelta(days=1)

    else:
        year_options = list(range(today.year - 10, today.year + 1))
        selected_year = st.selectbox(
            "ปี",
            year_options,
            index=len(year_options) - 1,
            key=f"{prefix}_year",
        )
        start_date = date(selected_year, 1, 1)
        end_date = date(selected_year, 12, 31)

    if start_date > end_date:
        st.error("วันที่เริ่มต้นต้องไม่อยู่หลังวันที่สิ้นสุด")
        return None, None

    st.caption(
        f"กำลังดูข้อมูลวันที่ {start_date:%Y-%m-%d} "
        f"ถึง {end_date:%Y-%m-%d}"
    )
    return start_date, end_date


def filter_by_received_date(dataframe, start_date, end_date):
    if dataframe.empty or start_date is None or end_date is None:
        return dataframe.iloc[0:0].copy()

    received_dates = dataframe["received_at"].apply(
        lambda value: (
            parse_timestamp(value).date()
            if parse_timestamp(value)
            else None
        )
    )

    return dataframe[
        received_dates.apply(
            lambda value: value is not None
            and start_date <= value <= end_date
        )
    ].copy()


# ---------------------------------------------------------------------
# Page 1: New records
# ---------------------------------------------------------------------

if page == "📝 บันทึกใบเบิกใหม่":
    st.subheader("📝 บันทึกใบเบิกใหม่")
    st.caption(
        f"เวลาประเทศไทยขณะนี้: "
        f"{bangkok_now():%Y-%m-%d %H:%M:%S} น."
    )

    with st.form("new_records_form", clear_on_submit=True):
        starting_rows = pd.DataFrame(
            [
                {
                    "เลขที่ JOB": "",
                    "แผนก/ไลน์ผลิต": "",
                    "ชื่อสินค้า": "",
                    "จำนวน": 1,
                }
            ]
        )

        entries_df = st.data_editor(
            starting_rows,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "เลขที่ JOB": st.column_config.TextColumn(
                    "เลขที่ JOB",
                    help="เช่น JOB-6901 หรือใส่เลข 4 หลัก",
                ),
                "แผนก/ไลน์ผลิต": st.column_config.SelectboxColumn(
                    "แผนก/ไลน์ผลิต",
                    options=DEPARTMENTS,
                ),
                "ชื่อสินค้า": st.column_config.TextColumn("ชื่อสินค้า"),
                "จำนวน": st.column_config.NumberColumn(
                    "จำนวน",
                    min_value=1,
                    step=1,
                    format="%d",
                ),
            },
        )

        save_button = st.form_submit_button(
            "📥 บันทึกรับเรื่องทั้งหมด",
            type="primary",
            use_container_width=True,
        )

        if save_button:
            entries = []
            errors = []

            for row_number, (_, row) in enumerate(
                entries_df.iterrows(),
                start=1,
            ):
                raw_job = str(row.get("เลขที่ JOB", "") or "").strip()
                department = str(
                    row.get("แผนก/ไลน์ผลิต", "") or ""
                ).strip()
                product = str(row.get("ชื่อสินค้า", "") or "").strip()
                quantity_raw = row.get("จำนวน", 1)

                if not any([raw_job, department, product]):
                    continue

                job_number = normalize_job_number(raw_job)

                if not job_number:
                    errors.append(f"แถว {row_number}: กรุณากรอกเลข JOB")
                    continue
                if department not in DEPARTMENTS:
                    errors.append(
                        f"{job_number}: กรุณาเลือกแผนก/ไลน์จากรายการ"
                    )
                    continue
                if not product:
                    errors.append(f"{job_number}: กรุณากรอกชื่อสินค้า")
                    continue

                try:
                    quantity = int(quantity_raw)
                    if quantity < 1:
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append(
                        f"{job_number}: จำนวนต้องเป็นจำนวนเต็มตั้งแต่ 1 ขึ้นไป"
                    )
                    continue

                entries.append(
                    {
                        "job_number": job_number,
                        "department": department,
                        "product_name": product,
                        "quantity": quantity,
                    }
                )

            existing_numbers = (
                {str(value).casefold() for value in records["job_number"]}
                if not records.empty
                else set()
            )
            batch_numbers = [
                entry["job_number"].casefold()
                for entry in entries
            ]

            duplicated_in_batch = {
                number
                for number in batch_numbers
                if batch_numbers.count(number) > 1
            }
            duplicated_existing = [
                entry["job_number"]
                for entry in entries
                if entry["job_number"].casefold() in existing_numbers
            ]

            if errors:
                for error in errors:
                    st.error(error)
            elif not entries:
                st.warning("กรุณากรอกข้อมูล JOB อย่างน้อยหนึ่งรายการ")
            elif duplicated_in_batch:
                st.error(
                    "พบเลข JOB ซ้ำในรายการที่กรอก: "
                    + ", ".join(sorted(duplicated_in_batch))
                )
            elif duplicated_existing:
                st.error(
                    "เลข JOB เหล่านี้มีในระบบแล้ว: "
                    + ", ".join(duplicated_existing)
                )
            else:
                # เวลารับถูกสร้างตอน submit ด้วย timezone ประเทศไทย
                received_at = timestamp_now()
                for entry in entries:
                    entry["received_at"] = received_at

                try:
                    insert_records(entries)
                    st.success(f"บันทึกรับเรื่องแล้ว {len(entries)} JOB")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error(
                        "บันทึกไม่สำเร็จเพราะมีเลข JOB ซ้ำ "
                        "กรุณาตรวจสอบรายการแล้วลองอีกครั้ง"
                    )


# ---------------------------------------------------------------------
# Page 2: Dashboard and historical analytics
# ---------------------------------------------------------------------

elif page == "📊 Dashboard สรุปผล":
    st.subheader("📊 Dashboard สรุปผล")

    start_date, end_date = historical_filter("dashboard")
    filtered_records = filter_by_received_date(
        records,
        start_date,
        end_date,
    )

    if filtered_records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิกในช่วงวันที่เลือก")

    processing_values = [
        duration_minutes(row["received_at"], row["picked_at"])
        for _, row in filtered_records.iterrows()
        if row["picked_at"]
    ]
    processing_values = [
        value for value in processing_values if value is not None
    ]

    waiting_values = [
        duration_minutes(row["picked_at"], row["handover_at"])
        for _, row in filtered_records.iterrows()
        if row["picked_at"] and row["handover_at"]
    ]
    waiting_values = [
        value for value in waiting_values if value is not None
    ]

    avg_processing = safe_average(processing_values)
    avg_waiting = safe_average(waiting_values)

    if not processing_values and not waiting_values:
        bottleneck = "รอข้อมูล"
    elif avg_waiting > avg_processing:
        bottleneck = "รอ PD มารับ"
    else:
        bottleneck = "ขั้นตอนจัดสินค้า"

    selected_period_dates = filtered_records["received_at"].apply(
        parse_timestamp
    )
    today_count = sum(
        value is not None and value.date() == bangkok_now().date()
        for value in selected_period_dates
    )

    kpis = st.columns(4)
    kpis[0].metric("📥 ยอดเบิกวันนี้ในช่วงที่เลือก", f"{today_count:,}")
    kpis[1].metric("📄 จำนวน JOB ในช่วงที่เลือก", f"{len(filtered_records):,}")
    kpis[2].metric(
        "⏱️ เวลาเฉลี่ยจัดเสร็จ",
        duration_label(avg_processing)
        if processing_values
        else "0 นาที",
    )
    kpis[3].metric("🚦 จุดคอขวด", bottleneck)

    if not filtered_records.empty:
        chart_col, status_col = st.columns(2)

        with chart_col:
            hourly_data = filtered_records.copy()
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
                color_continuous_scale=["#b9ddd8", "#187e79"],
            )
            figure.update_layout(
                template="plotly_white",
                height=340,
                coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=55, b=10),
            )
            st.plotly_chart(figure, use_container_width=True)

        with status_col:
            status_counts = (
                filtered_records["status"]
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
                hole=0.5,
            )
            figure.update_layout(
                template="plotly_white",
                height=340,
                margin=dict(l=10, r=10, t=55, b=10),
            )
            st.plotly_chart(figure, use_container_width=True)

        late_data = filtered_records.copy()
        late_data["เวลาเข้าระบบ"] = late_data["received_at"].apply(
            lambda value: "ใบเบิกเย็น" if is_late(value) else "รับก่อน Cut-off"
        )
        department_summary = (
            late_data.groupby(["department", "เวลาเข้าระบบ"])
            .size()
            .reset_index(name="จำนวน JOB")
        )

        st.markdown("#### 🔴 ใบเบิกเย็นแยกตามแผนก/ไลน์")
        figure = px.bar(
            department_summary,
            x="department",
            y="จำนวน JOB",
            color="เวลาเข้าระบบ",
            barmode="group",
            color_discrete_map={
                "ใบเบิกเย็น": "#c2414d",
                "รับก่อน Cut-off": "#19845f",
            },
        )
        figure.update_layout(
            template="plotly_white",
            height=320,
            margin=dict(l=10, r=10, t=25, b=10),
            xaxis_title="แผนก/ไลน์ผลิต",
        )
        st.plotly_chart(figure, use_container_width=True)

        st.markdown("#### 🧱 วิเคราะห์เวลารอและเวลาจัด")
        stage_rows = []

        for _, row in filtered_records.iterrows():
            process_time = duration_minutes(
                row["received_at"],
                row["picked_at"],
            )
            wait_time = duration_minutes(
                row["picked_at"],
                row["handover_at"],
            )

            if process_time is not None:
                stage_rows.append(
                    {
                        "JOB": row["job_number"],
                        "แผนก/ไลน์": row["department"],
                        "ช่วง": "รับเรื่องถึงจัดเสร็จ",
                        "นาที": process_time,
                    }
                )

            if wait_time is not None:
                stage_rows.append(
                    {
                        "JOB": row["job_number"],
                        "แผนก/ไลน์": row["department"],
                        "ช่วง": "จัดเสร็จถึง PD รับ",
                        "นาที": wait_time,
                    }
                )

        if stage_rows:
            stage_df = pd.DataFrame(stage_rows)
            stage_summary = (
                stage_df.groupby("ช่วง")["นาที"]
                .mean()
                .reset_index()
            )
            stage_summary["นาที"] = stage_summary["นาที"].round(1)

            figure = px.bar(
                stage_summary,
                x="ช่วง",
                y="นาที",
                color="ช่วง",
                title="เวลาเฉลี่ยในแต่ละขั้นตอน",
                text="นาที",
                color_discrete_sequence=["#3474c4", "#19845f"],
            )
            figure.update_layout(
                template="plotly_white",
                height=300,
                showlegend=False,
                margin=dict(l=10, r=10, t=50, b=10),
            )
            st.plotly_chart(figure, use_container_width=True)
        else:
            st.info("ช่วงวันที่เลือกยังไม่มีข้อมูลเวลาจัดเสร็จหรือเวลารับของ")


# ---------------------------------------------------------------------
# Page 3: Edit records and update picked/handover timestamps
# ---------------------------------------------------------------------

elif page == "✏️ จัดการและแก้ไขรายการ":
    st.subheader("✏️ จัดการและแก้ไขรายการ")

    if records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
    else:
        record_options = {
            f"ID {int(row['id'])} · {row['job_number']} · "
            f"{row['department']} · {row['product_name']}": int(row["id"])
            for _, row in records.iterrows()
        }

        selected_label = st.selectbox(
            "เลือก Job ID ที่ต้องการอัปเดต",
            list(record_options),
        )
        selected_id = record_options[selected_label]
        selected = records[records["id"] == selected_id].iloc[0]

        st.markdown("#### ⏱️ อัปเดตเวลาจัดเสร็จและเวลาที่ PD มารับ")

        current_now = bangkok_now()
        current_picked = parse_timestamp(selected["picked_at"])
        current_handover = parse_timestamp(selected["handover_at"])

        picked_default = current_picked or current_now
        handover_default = current_handover or current_now

        with st.form("status_time_update_form"):
            st.caption(
                f"เวลาปัจจุบันประเทศไทย: "
                f"{bangkok_now():%Y-%m-%d %H:%M:%S}"
            )

            picked_enabled = st.checkbox(
                "บันทึก/แก้ไขเวลาจัดสินค้าเสร็จ",
                value=current_picked is not None,
            )
            picked_date_col, picked_time_col = st.columns(2)
            picked_date = picked_date_col.date_input(
                "วันที่จัดเสร็จ",
                value=picked_default.date(),
                key=f"picked_date_{selected_id}",
            )
            picked_time = picked_time_col.time_input(
                "เวลาจัดเสร็จ",
                value=picked_default.time().replace(tzinfo=None),
                step=60,
                key=f"picked_time_{selected_id}",
            )

            handover_enabled = st.checkbox(
                "บันทึก/แก้ไขเวลาที่ PD มารับสินค้า",
                value=current_handover is not None,
            )
            handover_date_col, handover_time_col = st.columns(2)
            handover_date = handover_date_col.date_input(
                "วันที่ PD มารับ",
                value=handover_default.date(),
                key=f"handover_date_{selected_id}",
            )
            handover_time = handover_time_col.time_input(
                "เวลาที่ PD มารับ",
                value=handover_default.time().replace(tzinfo=None),
                step=60,
                key=f"handover_time_{selected_id}",
            )

            save_times = st.form_submit_button(
                "บันทึกการอัปเดตสถานะ",
                type="primary",
                use_container_width=True,
            )

            if save_times:
                picked_value = (
                    datetime.combine(
                        picked_date,
                        picked_time,
                        tzinfo=BANGKOK_TZ,
                    ).isoformat(sep=" ", timespec="seconds")
                    if picked_enabled
                    else None
                )
                handover_value = (
                    datetime.combine(
                        handover_date,
                        handover_time,
                        tzinfo=BANGKOK_TZ,
                    ).isoformat(sep=" ", timespec="seconds")
                    if handover_enabled
                    else None
                )

                received_dt = parse_timestamp(selected["received_at"])
                picked_dt = parse_timestamp(picked_value)
                handover_dt = parse_timestamp(handover_value)

                if picked_enabled and picked_dt is None:
                    st.error("กรุณาระบุเวลาจัดเสร็จ")
                elif handover_enabled and handover_dt is None:
                    st.error("กรุณาระบุเวลาที่ PD มารับ")
                elif (
                    picked_dt is not None
                    and received_dt is not None
                    and picked_dt < received_dt
                ):
                    st.error("เวลาจัดเสร็จต้องไม่ก่อนเวลารับใบเบิก")
                elif (
                    handover_dt is not None
                    and picked_dt is None
                ):
                    st.error("กรุณาบันทึกเวลาจัดเสร็จก่อนเวลาที่ PD มารับ")
                elif (
                    handover_dt is not None
                    and picked_dt is not None
                    and handover_dt < picked_dt
                ):
                    st.error("เวลา PD มารับต้องไม่ก่อนเวลาจัดเสร็จ")
                else:
                    if handover_value:
                        new_status = "handed_over"
                    elif picked_value:
                        new_status = "completed"
                    else:
                        new_status = (
                            selected["status"]
                            if selected["status"] in STATUS_OPTIONS
                            else "received"
                        )

                    update_status_times(
                        selected_id,
                        picked_value,
                        handover_value,
                        new_status,
                    )
                    st.success(
                        "อัปเดตเวลาสถานะแล้ว "
                        f"• เวลาจัด: {duration_label(duration_minutes(selected['received_at'], picked_value))} "
                        f"• เวลารอ PD: {duration_label(duration_minutes(picked_value, handover_value))}"
                    )
                    st.rerun()

        st.divider()
        st.markdown("#### ✏️ แก้ไขรายละเอียดรายการ")

        current_department = str(selected["department"] or "")
        department_options = list(DEPARTMENTS)
        if current_department not in department_options:
            department_options.append(current_department)

        with st.form("edit_record_form"):
            edit_col1, edit_col2 = st.columns(2)

            edited_job = edit_col1.text_input(
                "เลขที่ JOB",
                value=str(selected["job_number"]),
            )
            edited_department = edit_col2.selectbox(
                "แผนก/ไลน์ผลิต",
                department_options,
                index=department_options.index(current_department),
            )
            edited_product = edit_col1.text_input(
                "ชื่อสินค้า",
                value=str(selected["product_name"] or ""),
            )
            edited_quantity = edit_col2.number_input(
                "จำนวน",
                min_value=1,
                step=1,
                value=max(1, int(selected["quantity"] or 1)),
            )

            edited_received = st.text_input(
                "เวลารับใบเบิก (ISO หรือ YYYY-MM-DD HH:MM:SS)",
                value=timestamp_text(selected["received_at"]),
            )

            save_edit = st.form_submit_button(
                "💾 บันทึกการแก้ไขรายละเอียด",
                type="primary",
                use_container_width=True,
            )

            if save_edit:
                normalized_job = normalize_job_number(edited_job)
                received_dt = parse_timestamp(edited_received)

                if not normalized_job:
                    st.error("กรุณากรอกเลข JOB")
                elif not edited_department:
                    st.error("กรุณาเลือกแผนก/ไลน์ผลิต")
                elif not edited_product.strip():
                    st.error("กรุณากรอกชื่อสินค้า")
                elif received_dt is None:
                    st.error("รูปแบบเวลารับใบเบิกไม่ถูกต้อง")
                else:
                    edit_values = {
                        "job_number": normalized_job,
                        "department": edited_department,
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
                        "cancelled_by": selected["cancelled_by"],
                        "cancellation_reason": selected["cancellation_reason"],
                        "status": selected["status"],
                    }

                    try:
                        update_record(selected_id, edit_values)
                        st.success("บันทึกการแก้ไขแล้ว")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("เลข JOB นี้มีอยู่แล้ว")

        st.divider()
        st.markdown("#### 🔴 ยกเลิกหรือลบรายการ")

        cancel_col, delete_col = st.columns(2)

        with cancel_col:
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
                    cancel_values = {
                        "job_number": selected["job_number"],
                        "department": selected["department"],
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
            st.caption("การลบจะนำรายการออกจากระบบถาวร")
            confirm_delete = st.checkbox(
                "ยืนยันว่าต้องการลบรายการนี้ถาวร",
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
# Page 4: History, filters and Excel export
# ---------------------------------------------------------------------

elif page == "📋 ประวัติและส่งออกข้อมูล Excel":
    st.subheader("📋 ประวัติและส่งออกข้อมูล Excel")

    start_date, end_date = historical_filter("history")
    historical_records = filter_by_received_date(
        records,
        start_date,
        end_date,
    )

    if historical_records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิกในช่วงวันที่เลือก")

    history_rows = []

    for _, row in historical_records.iterrows():
        history_rows.append(
            {
                "Job ID": row["id"],
                "เลขที่ JOB": row["job_number"],
                "แผนก/ไลน์ผลิต": row["department"],
                "ชื่อสินค้า": row["product_name"],
                "จำนวน": row["quantity"],
                "สถานะ": STATUS_LABELS.get(row["status"], row["status"]),
                "เวลารับ": format_timestamp(row["received_at"]),
                "เวลาเริ่มจัด": format_timestamp(row["in_progress_at"]),
                "เวลาจัดเสร็จ": format_timestamp(row["picked_at"]),
                "เวลาจ่ายของ": format_timestamp(row["handover_at"]),
                "เวลายกเลิก": format_timestamp(row["cancelled_at"]),
                "ผู้สั่งยกเลิก": row["cancelled_by"] or "—",
                "สาเหตุยกเลิก": row["cancellation_reason"] or "—",
                "เวลาจัด (นาที)": duration_minutes(
                    row["received_at"],
                    row["picked_at"],
                ),
                "เวลารอ PD (นาที)": duration_minutes(
                    row["picked_at"],
                    row["handover_at"],
                ),
                "ใบเบิกเย็น": "ใช่" if is_late(row["received_at"]) else "ไม่ใช่",
            }
        )

    history_columns = [
        "Job ID",
        "เลขที่ JOB",
        "แผนก/ไลน์ผลิต",
        "ชื่อสินค้า",
        "จำนวน",
        "สถานะ",
        "เวลารับ",
        "เวลาเริ่มจัด",
        "เวลาจัดเสร็จ",
        "เวลาจ่ายของ",
        "เวลายกเลิก",
        "ผู้สั่งยกเลิก",
        "สาเหตุยกเลิก",
        "เวลาจัด (นาที)",
        "เวลารอ PD (นาที)",
        "ใบเบิกเย็น",
    ]

    history_df = pd.DataFrame(history_rows, columns=history_columns)

    st.dataframe(
        history_df,
        use_container_width=True,
        hide_index=True,
        height=450,
    )

    excel_buffer = BytesIO()

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        history_df.to_excel(
            writer,
            index=False,
            sheet_name="Requisition History",
        )

    excel_buffer.seek(0)

    st.download_button(
        "📥 ดาวน์โหลดข้อมูลช่วงวันที่เลือกเป็น Excel",
        data=excel_buffer,
        file_name=f"warehouse_history_{bangkok_now():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
