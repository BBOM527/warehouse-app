"""PK Warehouse | Requisition Tracking

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
    """เวลาปัจจุบันแบบ timezone-aware ของประเทศไทย"""
    return datetime.now(BANGKOK_TZ)


def timestamp_now():
    """เวลาปัจจุบันสำหรับบันทึกลงฐานข้อมูล"""
    return bangkok_now().isoformat(sep=" ", timespec="seconds")


def parse_timestamp(value):
    """อ่านเวลาเดิมและแปลงให้เป็นเวลาไทยเสมอ"""
    if value is None or pd.isna(value) or not str(value).strip():
        return None

    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BANGKOK_TZ)
    else:
        parsed = parsed.astimezone(BANGKOK_TZ)

    return parsed


def timestamp_text(value):
    parsed = parse_timestamp(value)
    if parsed is None:
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def format_timestamp(value):
    parsed = parse_timestamp(value)
    if parsed is None:
        return "—"
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


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
    if remainder:
        return f"{hours} ชม. {remainder} นาที"

    return f"{hours} ชม."


def normalize_job_number(value):
    value = str(value or "").strip()

    if not value:
        return ""

    if value.upper().startswith("JOB-"):
        return value.upper()

    if value.isdigit() and len(value) == 4:
        return f"JOB-{value}"

    return value.upper()


def is_late(received_at):
    received = parse_timestamp(received_at)
    return received is not None and received.time() > CUTOFF_TIME


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

        # ย้ายข้อมูลจาก schema requisitions รุ่นเก่าถ้ามี
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(requisitions)"
            )
        }

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

        if "canceled_at" in columns:
            connection.execute(
                """
                UPDATE requisitions
                SET cancelled_at = canceled_at
                WHERE cancelled_at IS NULL
                  AND canceled_at IS NOT NULL
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

        if "cancellation_reason" in columns:
            connection.execute(
                """
                UPDATE requisitions
                SET cancellation_reason = cancellation_reason
                WHERE (cancellation_reason IS NULL OR cancellation_reason = '')
                  AND cancellation_reason IS NOT NULL
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
                    item["job_number"],
                    item["department"],
                    item["product_name"],
                    item["quantity"],
                    item["received_at"],
                    now,
                    now,
                )
                for item in entries
            ],
        )


def update_record(record_id, values):
    now = timestamp_now()

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
                now,
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
# Streamlit setup and login
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="PK Warehouse | Requisition Tracking",
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
        --ink: #17283b;
        --muted: #758397;
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
        padding: 23px 27px;
        border: 1px solid rgba(255,255,255,.45);
        border-radius: 12px;
        color: white;
        background: linear-gradient(115deg, #132940, #176d70);
        box-shadow: 0 17px 38px rgba(25,54,78,.17);
        margin-bottom: 18px;
    }

    .hero p { margin: 4px 0 0; color: #d5e7eb; }

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

with st.sidebar:
    st.markdown("## 📦 PK Warehouse")
    st.caption(f"เวลาไทย: {bangkok_now():%Y-%m-%d %H:%M:%S}")
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
    f"""
    <div class="hero">
        <h1>📦 PK Warehouse · Requisition Tracking</h1>
        <p>เวลาไทย {bangkok_now():%Y-%m-%d %H:%M:%S}
        • Cut-off 16:00 น. • บันทึกและติดตาม JOB</p>
    </div>
    """,
    unsafe_allow_html=True,
)

initialize_database()
records = load_records()


# ---------------------------------------------------------------------
# Page 1: New records
# ---------------------------------------------------------------------

if page == "📝 บันทึกใบเบิกใหม่":
    st.subheader("📝 บันทึกใบเบิกใหม่")
    st.caption(
        f"ระบบจะใช้เวลารับจากนาฬิกาประเทศไทยขณะกดบันทึก "
        f"(ตอนนี้ {bangkok_now():%Y-%m-%d %H:%M:%S})"
    )

    with st.form("new_records_form", clear_on_submit=True):
        input_data = pd.DataFrame(
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
            input_data,
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

        submit_entries = st.form_submit_button(
            "📥 บันทึกรับเรื่องทั้งหมด",
            type="primary",
            use_container_width=True,
        )

        if submit_entries:
            entries = []
            errors = []

            for row_number, (_, row) in enumerate(entries_df.iterrows(), start=1):
                raw_job = str(row.get("เลขที่ JOB", "") or "").strip()
                department = str(row.get("แผนก/ไลน์ผลิต", "") or "").strip()
                product = str(row.get("ชื่อสินค้า", "") or "").strip()
                raw_quantity = row.get("จำนวน", 1)

                if not any([raw_job, department, product]):
                    continue

                job_number = normalize_job_number(raw_job)

                if not job_number:
                    errors.append(f"แถว {row_number}: กรุณากรอกเลข JOB")
                    continue
                if not department:
                    errors.append(f"{job_number}: กรุณาเลือกแผนก/ไลน์ผลิต")
                    continue
                if not product:
                    errors.append(f"{job_number}: กรุณากรอกชื่อสินค้า")
                    continue

                try:
                    quantity = int(raw_quantity)
                    if quantity < 1:
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append(f"{job_number}: จำนวนต้องเป็นจำนวนเต็มตั้งแต่ 1 ขึ้นไป")
                    continue

                entries.append(
                    {
                        "job_number": job_number,
                        "department": department,
                        "product_name": product,
                        "quantity": quantity,
                    }
                )

            current_numbers = (
                {str(value).casefold() for value in records["job_number"]}
                if not records.empty
                else set()
            )
            batch_numbers = [
                entry["job_number"].casefold()
                for entry in entries
            ]

            duplicate_batch = {
                number
                for number in batch_numbers
                if batch_numbers.count(number) > 1
            }
            duplicate_existing = [
                entry["job_number"]
                for entry in entries
                if entry["job_number"].casefold() in current_numbers
            ]

            if errors:
                for error in errors:
                    st.error(error)
            elif not entries:
                st.warning("กรุณากรอกข้อมูล JOB อย่างน้อยหนึ่งรายการ")
            elif duplicate_batch:
                st.error(
                    "พบเลข JOB ซ้ำในรายการที่กรอก: "
                    + ", ".join(sorted(duplicate_batch))
                )
            elif duplicate_existing:
                st.error(
                    "เลข JOB นี้มีในระบบแล้ว: "
                    + ", ".join(duplicate_existing)
                )
            else:
                received_at = timestamp_now()
                for entry in entries:
                    entry["received_at"] = received_at

                try:
                    insert_records(entries)
                    st.success(f"บันทึกใบเบิกแล้ว {len(entries)} JOB")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error(
                        "บันทึกไม่สำเร็จเพราะมีเลข JOB ซ้ำ "
                        "กรุณาตรวจสอบข้อมูลแล้วลองอีกครั้ง"
                    )


# ---------------------------------------------------------------------
# Page 2: Dashboard
# ---------------------------------------------------------------------

elif page == "📊 Dashboard สรุปผล":
    st.subheader("📊 Dashboard สรุปผล")

    if records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        today_count = 0
        avg_processing = 0
        bottleneck = "รอข้อมูล"
    else:
        thai_today = bangkok_now().date()

        record_dates = records["received_at"].apply(parse_timestamp)
        today_count = sum(
            value is not None and value.date() == thai_today
            for value in record_dates
        )

        processing_values = [
            duration_minutes(row["received_at"], row["picked_at"])
            for _, row in records.iterrows()
            if row["picked_at"]
        ]
        processing_values = [
            value for value in processing_values if value is not None
        ]

        waiting_values = [
            duration_minutes(row["picked_at"], row["handover_at"])
            for _, row in records.iterrows()
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

    kpis = st.columns(4)
    kpis[0].metric("📥 ยอดเบิกวันนี้", f"{today_count:,}")
    kpis[1].metric("📄 จำนวน JOB", f"{len(records):,}")
    kpis[2].metric(
        "⏱️ เวลาเฉลี่ยจัดเสร็จ",
        duration_label(avg_processing)
        if (records.shape[0] and avg_processing)
        else "0 นาที",
    )
    kpis[3].metric("🚦 จุดคอขวด", bottleneck)

    if not records.empty:
        chart_col, status_col = st.columns(2)

        with chart_col:
            chart_data = records.copy()
            chart_data["received_dt"] = chart_data["received_at"].apply(
                parse_timestamp
            )
            chart_data["ชั่วโมง"] = chart_data["received_dt"].apply(
                lambda value: value.hour if value else None
            )
            hourly = (
                chart_data.dropna(subset=["ชั่วโมง"])
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
                records["status"]
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

        st.markdown("#### 🔴 ใบเบิกเย็นแยกตามแผนก/ไลน์")

        late_data = records.copy()
        late_data["เวลาเข้าระบบ"] = late_data["received_at"].apply(
            lambda value: "ใบเบิกเย็น"
            if is_late(value)
            else "รับก่อน Cut-off"
        )

        department_summary = (
            late_data.groupby(["department", "เวลาเข้าระบบ"])
            .size()
            .reset_index(name="จำนวน JOB")
        )

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


# ---------------------------------------------------------------------
# Page 3: Edit, cancel and delete records
# ---------------------------------------------------------------------

elif page == "✏️ จัดการและแก้ไขรายการ":
    st.subheader("✏️ จัดการและแก้ไขรายการ")

    if records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
    else:
        record_options = {
            f"{row['job_number']} · {row['department']} · {row['product_name']}": int(row["id"])
            for _, row in records.iterrows()
        }

        selected_label = st.selectbox(
            "เลือกใบเบิกที่ต้องการจัดการ",
            list(record_options),
        )
        selected_id = record_options[selected_label]
        selected = records[records["id"] == selected_id].iloc[0]

        st.markdown("#### แก้ไขข้อมูลใบเบิก")

        with st.form("edit_record_form"):
            col1, col2 = st.columns(2)

            edited_job = col1.text_input(
                "เลขที่ JOB",
                value=str(selected["job_number"]),
            )
            department_options = list(DEPARTMENTS)
            current_department = str(selected["department"] or "")
            if current_department not in department_options:
                department_options.append(current_department)

            edited_department = col2.selectbox(
                "แผนก/ไลน์ผลิต",
                department_options,
                index=department_options.index(current_department),
            )
            edited_product = col1.text_input(
                "ชื่อสินค้า",
                value=str(selected["product_name"] or ""),
            )
            edited_quantity = col2.number_input(
                "จำนวน",
                min_value=1,
                step=1,
                value=max(1, int(selected["quantity"] or 1)),
            )

            current_status = (
                selected["status"]
                if selected["status"] in STATUS_OPTIONS
                else "received"
            )
            edited_status = st.selectbox(
                "สถานะ",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(current_status),
                format_func=lambda value: STATUS_LABELS[value],
            )

            st.caption(
                "แก้ไขเวลาโดยใช้รูปแบบ YYYY-MM-DD HH:MM:SS "
                "พร้อมเขตเวลา +07:00 ได้ หรือเว้นว่างหากยังไม่มีเวลา"
            )

            received_at = st.text_input(
                "เวลารับใบเบิก",
                value=timestamp_text(selected["received_at"]),
            )
            in_progress_at = st.text_input(
                "เวลาเริ่มจัด",
                value=timestamp_text(selected["in_progress_at"]),
            )
            picked_at = st.text_input(
                "เวลาจัดเสร็จ",
                value=timestamp_text(selected["picked_at"]),
            )
            handover_at = st.text_input(
                "เวลาจ่ายของ / PD มารับ",
                value=timestamp_text(selected["handover_at"]),
            )
            cancelled_at = st.text_input(
                "เวลายกเลิก",
                value=timestamp_text(selected["cancelled_at"]),
            )

            canceled_by = st.text_input(
                "ผู้สั่งยกเลิก PN/PD",
                value=str(selected["cancelled_by"] or ""),
            )
            cancellation_reason = st.text_area(
                "สาเหตุการยกเลิก",
                value=str(selected["cancellation_reason"] or ""),
            )

            save_edit = st.form_submit_button(
                "💾 บันทึกการแก้ไข",
                type="primary",
                use_container_width=True,
            )

            if save_edit:
                normalized_job = normalize_job_number(edited_job)
                parsed_received = parse_timestamp(received_at)

                timestamp_inputs = {
                    "เวลาเริ่มจัด": in_progress_at,
                    "เวลาจัดเสร็จ": picked_at,
                    "เวลาจ่ายของ": handover_at,
                    "เวลายกเลิก": cancelled_at,
                }

                invalid_fields = [
                    label
                    for label, value in timestamp_inputs.items()
                    if value.strip() and parse_timestamp(value) is None
                ]

                if not normalized_job:
                    st.error("กรุณากรอกเลข JOB")
                elif not edited_department:
                    st.error("กรุณาเลือกแผนก/ไลน์ผลิต")
                elif not edited_product.strip():
                    st.error("กรุณากรอกชื่อสินค้า")
                elif parsed_received is None:
                    st.error("เวลารับใบเบิกไม่ถูกต้อง")
                elif invalid_fields:
                    st.error(
                        "ตรวจสอบรูปแบบเวลาในช่อง: "
                        + ", ".join(invalid_fields)
                    )
                elif edited_status == "cancelled" and (
                    not canceled_by.strip()
                    or not cancellation_reason.strip()
                ):
                    st.error("สถานะยกเลิกต้องระบุผู้สั่งและสาเหตุ")
                else:
                    def normalized_timestamp(value):
                        parsed = parse_timestamp(value)
                        return (
                            parsed.isoformat(sep=" ", timespec="seconds")
                            if parsed
                            else None
                        )

                    values = {
                        "job_number": normalized_job,
                        "department": edited_department,
                        "product_name": edited_product.strip(),
                        "quantity": int(edited_quantity),
                        "received_at": parsed_received.isoformat(
                            sep=" ",
                            timespec="seconds",
                        ),
                        "in_progress_at": normalized_timestamp(in_progress_at),
                        "picked_at": normalized_timestamp(picked_at),
                        "handover_at": normalized_timestamp(handover_at),
                        "cancelled_at": normalized_timestamp(cancelled_at),
                        "cancelled_by": canceled_by.strip(),
                        "cancellation_reason": cancellation_reason.strip(),
                        "status": edited_status,
                    }

                    try:
                        update_record(selected_id, values)
                        st.success("บันทึกการแก้ไขแล้ว")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("เลข JOB นี้มีอยู่แล้ว")

        st.divider()
        st.markdown("#### ยกเลิกหรือลบรายการ")

        cancel_col, delete_col = st.columns(2)

        with cancel_col:
            st.caption("ยกเลิกจะเก็บรายการไว้ในประวัติ")
            confirm_cancel = st.checkbox(
                "ยืนยันว่าต้องการยกเลิก JOB นี้",
                key=f"confirm_cancel_{selected_id}",
            )
            cancel_by_action = st.text_input(
                "ผู้สั่งยกเลิก PN/PD",
                key=f"cancel_by_{selected_id}",
            )
            cancel_reason_action = st.text_area(
                "สาเหตุการยกเลิก",
                key=f"cancel_reason_{selected_id}",
            )

            if st.button(
                "🔴 ยืนยันยกเลิก JOB",
                disabled=not confirm_cancel,
                key=f"cancel_button_{selected_id}",
            ):
                if not cancel_by_action.strip() or not cancel_reason_action.strip():
                    st.error("กรุณากรอกผู้สั่งยกเลิกและสาเหตุ")
                else:
                    values = {
                        "job_number": selected["job_number"],
                        "department": selected["department"],
                        "product_name": selected["product_name"],
                        "quantity": int(selected["quantity"]),
                        "received_at": selected["received_at"],
                        "in_progress_at": selected["in_progress_at"],
                        "picked_at": selected["picked_at"],
                        "handover_at": selected["handover_at"],
                        "cancelled_at": timestamp_now(),
                        "cancelled_by": cancel_by_action.strip(),
                        "cancellation_reason": cancel_reason_action.strip(),
                        "status": "cancelled",
                    }
                    update_record(selected_id, values)
                    st.success("ยกเลิก JOB และบันทึกประวัติแล้ว")
                    st.rerun()

        with delete_col:
            st.caption("ลบจะนำรายการออกจากระบบถาวร")
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

elif page == "📋 ประวัติและส่งออกข้อมูล Excel":
    st.subheader("📋 ประวัติและส่งออกข้อมูล Excel")

    if records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        history_df = pd.DataFrame(
            columns=[
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
            ]
        )
    else:
        history_df = records.copy()
        history_df["สถานะ"] = history_df["status"].map(STATUS_LABELS)
        history_df = history_df.rename(
            columns={
                "job_number": "เลขที่ JOB",
                "department": "แผนก/ไลน์ผลิต",
                "product_name": "ชื่อสินค้า",
                "quantity": "จำนวน",
                "received_at": "เวลารับ",
                "in_progress_at": "เวลาเริ่มจัด",
                "picked_at": "เวลาจัดเสร็จ",
                "handover_at": "เวลาจ่ายของ",
                "cancelled_at": "เวลายกเลิก",
                "cancelled_by": "ผู้สั่งยกเลิก",
                "cancellation_reason": "สาเหตุยกเลิก",
            }
        )

        history_columns = [
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
        ]
        history_df = history_df[history_columns]

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
        "📥 ดาวน์โหลดประวัติเป็น Excel",
        data=excel_buffer,
        file_name=f"warehouse_requisitions_{bangkok_now():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
