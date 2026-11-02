"""PK Warehouse | JOB Tracking Dashboard

รันด้วย:
    streamlit run app.py

ติดตั้ง dependencies:
    pip install streamlit pandas plotly openpyxl requests
"""

from datetime import date, datetime, time, timezone, timedelta
from io import BytesIO
from pathlib import Path
import os
import sqlite3

import pandas as pd
import plotly.express as px
import requests
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
    "completed": "🔵 จัดเสร็จ / รอ PD",
    "handed_over": "🟢 PD มารับแล้ว",
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


def format_timestamp(value):
    parsed = parse_timestamp(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else "—"


def timestamp_text(value):
    parsed = parse_timestamp(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else ""


def is_late(value):
    received = parse_timestamp(value)
    return received is not None and received.time() > CUTOFF_TIME


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
    return (
        f"{hours} ชม. {remainder} นาที"
        if remainder
        else f"{hours} ชม."
    )


def safe_average(values):
    values = [
        value for value in values
        if value is not None and pd.notna(value)
    ]

    if values:
        return round(sum(values) / len(values))

    return 0


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

        # Map fields from older versions of the app if those columns exist.
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


def save_workflow_times(record_id, picked_at, handover_at, status):
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
               background:rgba(255,255,255,.82);
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
            const formatted = new Intl.DateTimeFormat("th-TH", {
              timeZone: "Asia/Bangkok",
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
              hour12: false
            }).format(new Date());

            clock.textContent = formatted + " น. · Asia/Bangkok";
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
    page_title="PK Warehouse | JOB Tracking",
    page_icon="📦",
    layout="wide",
)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "page" not in st.session_state:
    st.session_state.page = "📝 บันทึกใบเบิก"

if not st.session_state.authenticated:
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
        login_submitted = st.form_submit_button(
            "เข้าสู่ระบบ",
            type="primary",
            use_container_width=True,
        )

    if login_submitted:
        if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Username หรือ Password ไม่ถูกต้อง")

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
        <p>บันทึกเวลา JOB • วิเคราะห์คอขวด • ค้นหาประวัติย้อนหลัง</p>
    </div>
    """,
    unsafe_allow_html=True,
)

show_live_clock()
records = load_records()


# ---------------------------------------------------------------------
# Date and search filters
# ---------------------------------------------------------------------

def get_date_range(prefix):
    today = bangkok_now().date()

    choice = st.selectbox(
        "ช่วงวันที่",
        ["วันนี้", "สัปดาห์นี้", "เลือกช่วงวันที่"],
        key=f"{prefix}_range_choice",
    )

    if choice == "วันนี้":
        return today, today

    if choice == "สัปดาห์นี้":
        week_start = today - timedelta(days=today.weekday())
        return week_start, today

    start_col, end_col = st.columns(2)
    start_date = start_col.date_input(
        "วันที่เริ่มต้น",
        value=today.replace(day=1),
        key=f"{prefix}_start",
    )
    end_date = end_col.date_input(
        "วันที่สิ้นสุด",
        value=today,
        key=f"{prefix}_end",
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

    result = dataframe[
        received_dates.apply(
            lambda value: value is not None
            and start_date <= value <= end_date
        )
    ].copy()

    search_text = search_text.strip().casefold()

    if search_text:
        columns_to_search = [
            column
            for column in ["job_number", "product_name", "department"]
            if column in result.columns
        ]

        if columns_to_search:
            mask = result[columns_to_search].fillna("").astype(str).apply(
                lambda column: column.str.casefold().str.contains(
                    search_text,
                    regex=False,
                )
            ).any(axis=1)
            result = result[mask]

    return result


def table_for_display(dataframe):
    rows = []

    for _, row in dataframe.iterrows():
        rows.append(
            {
                "Job ID": row["id"],
                "เลขที่ JOB": row["job_number"],
                "สินค้า": row["product_name"],
                "จำนวน": row["quantity"],
                "แผนก/ไลน์": row["department"],
                "📥 รับใบเบิก": format_timestamp(row["received_at"]),
                "🟡 เริ่มจัด": format_timestamp(row["in_progress_at"]),
                "🔵 จัดเสร็จ": format_timestamp(row["picked_at"]),
                "🟢 PD มารับ": format_timestamp(row["handover_at"]),
                "❌ ยกเลิก": format_timestamp(row["cancelled_at"]),
                "สถานะ": STATUS_LABELS.get(row["status"], row["status"]),
                "ใบเบิกเย็น": "🔴 ใช่" if is_late(row["received_at"]) else "🟢 ไม่ใช่",
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

    columns = [
        "Job ID",
        "เลขที่ JOB",
        "สินค้า",
        "จำนวน",
        "แผนก/ไลน์",
        "📥 รับใบเบิก",
        "🟡 เริ่มจัด",
        "🔵 จัดเสร็จ",
        "🟢 PD มารับ",
        "❌ ยกเลิก",
        "สถานะ",
        "ใบเบิกเย็น",
        "เวลาจัด",
        "เวลารอ PD",
        "ผู้สั่งยกเลิก",
        "สาเหตุยกเลิก",
    ]

    return pd.DataFrame(rows, columns=columns)


# ---------------------------------------------------------------------
# Page 1: New requisitions
# ---------------------------------------------------------------------

if page == "📝 บันทึกใบเบิก":
    st.subheader("📝 บันทึกใบเบิกใหม่")
    st.caption(
        f"เวลาปัจจุบันประเทศไทย: "
        f"{bangkok_now():%Y-%m-%d %H:%M:%S} น. "
        "เวลารับจะถูกประทับตอนกดบันทึก"
    )

    with st.form("new_records_form", clear_on_submit=True):
        initial_rows = pd.DataFrame(
            [
                {
                    "เลขที่ JOB": "",
                    "แผนก/ไลน์ผลิต": "",
                    "ชื่อสินค้า": "",
                    "จำนวน": 1,
                }
            ]
        )

        entry_df = st.data_editor(
            initial_rows,
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

        save_entries = st.form_submit_button(
            "📥 บันทึกรับเรื่องทั้งหมด",
            type="primary",
            use_container_width=True,
        )

        if save_entries:
            entries = []
            errors = []

            for row_number, (_, row) in enumerate(
                entry_df.iterrows(),
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
                    errors.append(f"{job_number}: กรุณาเลือกแผนก/ไลน์")
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

            duplicate_batch = {
                value
                for value in batch_numbers
                if batch_numbers.count(value) > 1
            }
            duplicate_existing = [
                entry["job_number"]
                for entry in entries
                if entry["job_number"].casefold() in existing_numbers
            ]

            if errors:
                for error in errors:
                    st.error(error)
            elif not entries:
                st.warning("กรุณากรอกข้อมูล JOB อย่างน้อยหนึ่งรายการ")
            elif duplicate_batch:
                st.error(
                    "พบเลข JOB ซ้ำในชุดข้อมูล: "
                    + ", ".join(sorted(duplicate_batch))
                )
            elif duplicate_existing:
                st.error(
                    "เลข JOB เหล่านี้มีในระบบแล้ว: "
                    + ", ".join(duplicate_existing)
                )
            else:
                received_at = timestamp_now()
                for entry in entries:
                    entry["received_at"] = received_at

                try:
                    insert_records(entries)
                    st.success(f"บันทึกแล้ว {len(entries)} JOB")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("พบ JOB ซ้ำในฐานข้อมูล กรุณาตรวจสอบแล้วลองใหม่")


# ---------------------------------------------------------------------
# Page 2: Dashboard and historical analytics
# ---------------------------------------------------------------------

elif page == "📊 Dashboard สรุปผล":
    st.subheader("📊 Dashboard สรุปผล")

    filter_col, search_col = st.columns([1, 1])
    with filter_col:
        start_date, end_date = get_date_range("dashboard")
    with search_col:
        dashboard_search = st.text_input(
            "ค้นหา JOB / สินค้า / แผนก",
            key="dashboard_search",
        )

    selected_records = filter_records(
        records,
        start_date,
        end_date,
        dashboard_search,
    )

    if selected_records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิกในช่วงเวลาที่เลือก")

    processing_values = [
        duration_minutes(row["received_at"], row["picked_at"])
        for _, row in selected_records.iterrows()
        if row["picked_at"]
    ]
    processing_values = [
        value for value in processing_values if value is not None
    ]

    waiting_values = [
        duration_minutes(row["picked_at"], row["handover_at"])
        for _, row in selected_records.iterrows()
        if row["picked_at"] and row["handover_at"]
    ]
    waiting_values = [
        value for value in waiting_values if value is not None
    ]

    avg_processing = safe_average(processing_values)
    avg_waiting = safe_average(waiting_values)

    today = bangkok_now().date()
    today_count = sum(
        (
            parsed := parse_timestamp(value)
        ) is not None and parsed.date() == today
        for value in records["received_at"]
    ) if not records.empty else 0

    pending_count = int(
        selected_records["status"].isin(
            ["received", "in_progress", "completed"]
        ).sum()
    ) if not selected_records.empty else 0

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

    if not selected_records.empty:
        chart_col, status_col = st.columns(2)

        with chart_col:
            hourly_data = selected_records.copy()
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
                selected_records["status"]
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

        late_data = selected_records.copy()
        late_data["เวลาเข้าระบบ"] = late_data["received_at"].apply(
            lambda value: "ใบเบิกเย็น" if is_late(value) else "ก่อน Cut-off"
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
                "ก่อน Cut-off": "#19845f",
            },
        )
        figure.update_layout(
            template="plotly_white",
            height=320,
            margin=dict(l=10, r=10, t=25, b=10),
            xaxis_title="แผนก/ไลน์ผลิต",
        )
        st.plotly_chart(figure, use_container_width=True)


# ---------------------------------------------------------------------
# Page 3: Workflow update, edit, cancel, delete
# ---------------------------------------------------------------------

elif page == "✏️ จัดการ/อัปเดตสถานะ":
    st.subheader("✏️ จัดการและอัปเดตสถานะ")

    if records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
    else:
        options = {
            f"ID {int(row['id'])} · {row['job_number']} · "
            f"{row['department']} · {row['product_name']}": int(row["id"])
            for _, row in records.iterrows()
        }

        selected_label = st.selectbox(
            "เลือก Job ID",
            list(options),
        )
        selected_id = options[selected_label]
        selected = records[records["id"] == selected_id].iloc[0]

        st.markdown("#### ⏱️ บันทึกเวลาจัดเสร็จและเวลาที่ PD มารับ")
        st.caption(
            f"เวลาประเทศไทยขณะนี้: {bangkok_now():%Y-%m-%d %H:%M:%S}"
        )

        picked_col, handover_col = st.columns(2)

        with picked_col:
            st.markdown("**🔵 เวลาจัดสินค้าเสร็จ**")
            st.write(format_timestamp(selected["picked_at"]))
            if st.button(
                "บันทึกเวลาจัดเสร็จเป็นเวลาปัจจุบัน",
                type="primary",
                use_container_width=True,
                key=f"picked_now_{selected_id}",
            ):
                picked_at = timestamp_now()
                received_dt = parse_timestamp(selected["received_at"])

                if (
                    received_dt
                    and parse_timestamp(picked_at) < received_dt
                ):
                    st.error("เวลาปัจจุบันก่อนเวลารับ JOB ตรวจสอบเวลาเครื่อง")
                else:
                    save_workflow_times(
                        selected_id,
                        picked_at,
                        selected["handover_at"],
                        "handed_over"
                        if selected["handover_at"]
                        else "completed",
                    )
                    st.success(
                        "บันทึกเวลาจัดเสร็จแล้ว "
                        f"(ใช้เวลา {duration_label(duration_minutes(selected['received_at'], picked_at))})"
                    )
                    st.rerun()

        with handover_col:
            st.markdown("**🟢 เวลาที่ PD มารับสินค้า**")
            st.write(format_timestamp(selected["handover_at"]))
            if st.button(
                "บันทึกเวลาที่ PD มารับเป็นเวลาปัจจุบัน",
                type="primary",
                use_container_width=True,
                key=f"handover_now_{selected_id}",
            ):
                if not selected["picked_at"]:
                    st.error("ต้องบันทึกเวลาจัดเสร็จก่อน จึงบันทึกเวลารับของได้")
                else:
                    handover_at = timestamp_now()
                    picked_dt = parse_timestamp(selected["picked_at"])

                    if (
                        picked_dt
                        and parse_timestamp(handover_at) < picked_dt
                    ):
                        st.error("เวลาปัจจุบันก่อนเวลาจัดเสร็จ ตรวจสอบเวลาเครื่อง")
                    else:
                        save_workflow_times(
                            selected_id,
                            selected["picked_at"],
                            handover_at,
                            "handed_over",
                        )
                        waiting = duration_minutes(
                            selected["picked_at"],
                            handover_at,
                        )
                        st.success(
                            f"บันทึก PD มารับแล้ว (รอ {duration_label(waiting)})"
                        )
                        st.rerun()

        st.markdown("#### 🛠️ แก้ไขเวลาที่บันทึกไว้")
        parsed_picked = parse_timestamp(selected["picked_at"]) or bangkok_now()
        parsed_handover = parse_timestamp(selected["handover_at"]) or bangkok_now()

        with st.form("manual_workflow_form"):
            picked_enabled = st.checkbox(
                "บันทึก/แก้ไขเวลาจัดเสร็จ",
                value=selected["picked_at"] is not None,
            )
            picked_date_col, picked_time_col = st.columns(2)

            picked_date = picked_date_col.date_input(
                "วันที่จัดเสร็จ",
                value=parsed_picked.date(),
                key=f"manual_picked_date_{selected_id}",
            )
            picked_time = picked_time_col.time_input(
                "เวลาจัดเสร็จ",
                value=parsed_picked.time().replace(tzinfo=None),
                key=f"manual_picked_time_{selected_id}",
            )

            handover_enabled = st.checkbox(
                "บันทึก/แก้ไขเวลาที่ PD มารับ",
                value=selected["handover_at"] is not None,
            )
            handover_date_col, handover_time_col = st.columns(2)

            handover_date = handover_date_col.date_input(
                "วันที่ PD มารับ",
                value=parsed_handover.date(),
                key=f"manual_handover_date_{selected_id}",
            )
            handover_time = handover_time_col.time_input(
                "เวลาที่ PD มารับ",
                value=parsed_handover.time().replace(tzinfo=None),
                key=f"manual_handover_time_{selected_id}",
            )

            save_manual_times = st.form_submit_button(
                "บันทึกการอัปเดตสถานะ",
                type="primary",
                use_container_width=True,
            )

            if save_manual_times:
                picked_at = (
                    datetime.combine(
                        picked_date,
                        picked_time,
                        tzinfo=BANGKOK_TZ,
                    ).isoformat(sep=" ", timespec="seconds")
                    if picked_enabled
                    else None
                )
                handover_at = (
                    datetime.combine(
                        handover_date,
                        handover_time,
                        tzinfo=BANGKOK_TZ,
                    ).isoformat(sep=" ", timespec="seconds")
                    if handover_enabled
                    else None
                )

                received_dt = parse_timestamp(selected["received_at"])
                picked_dt = parse_timestamp(picked_at)
                handover_dt = parse_timestamp(handover_at)

                if picked_enabled and picked_dt is None:
                    st.error("กรุณาระบุเวลาจัดเสร็จ")
                elif handover_enabled and handover_dt is None:
                    st.error("กรุณาระบุเวลาที่ PD มารับ")
                elif (
                    picked_dt
                    and received_dt
                    and picked_dt < received_dt
                ):
                    st.error("เวลาจัดเสร็จต้องไม่ก่อนเวลารับ JOB")
                elif handover_dt and not picked_dt:
                    st.error("กรุณาบันทึกเวลาจัดเสร็จก่อนเวลาที่ PD มารับ")
                elif (
                    handover_dt
                    and picked_dt
                    and handover_dt < picked_dt
                ):
                    st.error("เวลา PD มารับต้องไม่ก่อนเวลาจัดเสร็จ")
                else:
                    if handover_at:
                        new_status = "handed_over"
                    elif picked_at:
                        new_status = "completed"
                    elif selected["status"] in ("completed", "handed_over"):
                        new_status = "in_progress"
                    else:
                        new_status = selected["status"]

                    save_workflow_times(
                        selected_id,
                        picked_at,
                        handover_at,
                        new_status,
                    )
                    st.success("อัปเดตเวลาและคำนวณระยะเวลาแล้ว")
                    st.rerun()

        processing = duration_minutes(
            selected["received_at"],
            selected["picked_at"],
        )
        waiting = duration_minutes(
            selected["picked_at"],
            selected["handover_at"],
        )

        metric1, metric2 = st.columns(2)
        metric1.metric("⏱️ Processing Time", duration_label(processing))
        metric2.metric("🕒 Waiting Time", duration_label(waiting))

        st.divider()
        st.markdown("#### ✏️ แก้ไขรายละเอียด JOB")

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
                "เวลารับ (YYYY-MM-DD HH:MM:SS)",
                value=timestamp_text(selected["received_at"]),
            )
            edited_status = st.selectbox(
                "สถานะ",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(selected["status"])
                if selected["status"] in STATUS_OPTIONS
                else 0,
                format_func=lambda value: STATUS_LABELS[value],
            )

            edit_cancel_by = st.text_input(
                "ผู้สั่งยกเลิก PN/PD",
                value=str(selected["cancelled_by"] or ""),
            )
            edit_cancel_reason = st.text_area(
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
                elif not edited_department:
                    st.error("กรุณาเลือกแผนก/ไลน์ผลิต")
                elif not edited_product.strip():
                    st.error("กรุณากรอกชื่อสินค้า")
                elif received_dt is None:
                    st.error("รูปแบบเวลารับไม่ถูกต้อง")
                elif edited_status == "cancelled" and (
                    not edit_cancel_by.strip()
                    or not edit_cancel_reason.strip()
                ):
                    st.error("สถานะยกเลิกต้องระบุผู้สั่งและสาเหตุ")
                else:
                    values = {
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
                        "cancelled_by": edit_cancel_by.strip(),
                        "cancellation_reason": edit_cancel_reason.strip(),
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
# Page 4: History, search, date filters, Excel export
# ---------------------------------------------------------------------

elif page == "📋 ประวัติ & Export":
    st.subheader("📋 ประวัติและส่งออกข้อมูล")

    date_col, search_col = st.columns([1, 1])
    with date_col:
        start_date, end_date = get_date_range("history")
    with search_col:
        history_search = st.text_input(
            "ค้นหา JOB / สินค้า / แผนก",
            key="history_search",
        )

    history_records = filter_records(
        records,
        start_date,
        end_date,
        history_search,
    )

    if history_records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิกในช่วงเวลาที่เลือก")

    history_df = table_for_display(history_records)
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
        "📥 ดาวน์โหลดข้อมูลที่กรองเป็น Excel",
        data=excel_buffer,
        file_name=f"warehouse_history_{bangkok_now():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
