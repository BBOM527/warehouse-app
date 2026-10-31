"""PK Warehouse | Requisition Tracking

รันด้วย:
    streamlit run app.py

ติดตั้ง dependencies:
    pip install streamlit pandas plotly openpyxl
"""

from datetime import date, datetime, time
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

DB_PATH = Path(
    os.getenv(
        "WAREHOUSE_DB",
        str(Path(__file__).resolve().with_name("warehouse_tracking.db")),
    )
)

LOGIN_USERNAME = "lNWBOOM"
LOGIN_PASSWORD = "Boomkub555"

STATUS_LABELS = {
    "received": "🟡 รับใบเบิก / รอดำเนินการ",
    "in_progress": "🟡 กำลังจัด",
    "completed": "🔵 จัดเสร็จ / รอรับ",
    "handed_over": "🟢 จ่ายของแล้ว",
    "cancelled": "🔴 ยกเลิก",
}

STATUS_OPTIONS = list(STATUS_LABELS.keys())
LEGACY_MIGRATION_KEY = "legacy_jobs_migrated_v1"


# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------

def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """สร้างตารางเปล่า พร้อมย้าย JOB เก่าจากตาราง jobs หากมี"""
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
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        # เพิ่มคอลัมน์ที่อาจไม่มีในฐานข้อมูลจากเวอร์ชันก่อน
        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(requisitions)"
            )
        }

        migrations = {
            "product_name": "TEXT NOT NULL DEFAULT ''",
            "quantity": "INTEGER NOT NULL DEFAULT 1",
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

        migrate_legacy_jobs(connection)


def migrate_legacy_jobs(connection):
    """ย้าย JOB จาก schema รุ่นก่อนโดยไม่สร้างข้อมูลตัวอย่าง"""
    migrated = connection.execute(
        "SELECT value FROM app_metadata WHERE key = ?",
        (LEGACY_MIGRATION_KEY,),
    ).fetchone()

    if migrated is not None:
        return

    table_exists = connection.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'jobs'
        """
    ).fetchone()

    if table_exists:
        legacy_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(jobs)")
        }

        required_columns = {
            "id",
            "job_number",
            "department",
            "received_time",
            "status",
        }

        if required_columns.issubset(legacy_columns):
            legacy_rows = connection.execute(
                "SELECT * FROM jobs"
            ).fetchall()

            now = datetime.now().isoformat(sep=" ", timespec="seconds")

            for row in legacy_rows:
                job_number = str(row["job_number"] or "").strip()
                if not job_number:
                    continue

                # ข้ามเฉพาะเลขที่ mock data ของเวอร์ชันเก่า
                if job_number.startswith("WR-260"):
                    continue

                legacy_status = row["status"]
                status_map = {
                    "received": "received",
                    "in_progress": "in_progress",
                    "completed": "completed",
                    "handed_over": "handed_over",
                    "cancelled": "cancelled",
                }
                status = status_map.get(legacy_status, "received")

                connection.execute(
                    """
                    INSERT OR IGNORE INTO requisitions (
                        job_number, department, product_name, quantity,
                        received_at, in_progress_at, picked_at, handover_at,
                        cancelled_at, cancelled_by, cancellation_reason,
                        status, created_at, updated_at
                    )
                    VALUES (?, ?, '', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_number,
                        row["department"] or "",
                        row["received_time"],
                        row["in_progress_time"]
                        if "in_progress_time" in legacy_columns
                        else None,
                        row["picked_time"]
                        if "picked_time" in legacy_columns
                        else None,
                        row["handover_time"]
                        if "handover_time" in legacy_columns
                        else None,
                        row["canceled_time"]
                        if "canceled_time" in legacy_columns
                        else None,
                        row["canceled_by"]
                        if "canceled_by" in legacy_columns
                        else None,
                        row["cancel_reason"]
                        if "cancel_reason" in legacy_columns
                        else None,
                        status,
                        now,
                        now,
                    ),
                )

    connection.execute(
        "INSERT INTO app_metadata (key, value) VALUES (?, ?)",
        (LEGACY_MIGRATION_KEY, "done"),
    )


def load_records():
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT * FROM requisitions
            ORDER BY received_at DESC, id DESC
            """,
            connection,
        )


def insert_records(records):
    now = datetime.now().isoformat(sep=" ", timespec="seconds")

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
                for item in records
            ],
        )


def update_record(record_id, values):
    now = datetime.now().isoformat(sep=" ", timespec="seconds")

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
# Utility functions
# ---------------------------------------------------------------------

def timestamp_now():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def parse_timestamp(value):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None

    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def timestamp_text(value):
    parsed = parse_timestamp(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else ""


def minutes_between(start, end):
    start_dt = parse_timestamp(start)
    end_dt = parse_timestamp(end)

    if start_dt is None or end_dt is None:
        return None

    return max(0, round((end_dt - start_dt).total_seconds() / 60))


def safe_average(values):
    values = [
        value for value in values
        if value is not None and pd.notna(value)
    ]

    if values:
        return round(sum(values) / len(values))

    return 0


def duration_text(minutes):
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


def record_is_late(received_at):
    received = parse_timestamp(received_at)
    return received is not None and received.time() > time(16, 0)


def render_tick_sound():
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
# Login
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


def login_page():
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(ellipse at 15% 5%, rgba(68,145,153,.18), transparent 35%),
                radial-gradient(ellipse at 90% 10%, rgba(86,111,177,.15), transparent 32%),
                #f3f6fa;
        }
        .login-wrap {
            max-width: 440px;
            margin: 9vh auto 0;
            padding: 30px;
            border: 1px solid rgba(255,255,255,.9);
            border-radius: 18px;
            background: rgba(255,255,255,.86);
            box-shadow: 0 16px 45px rgba(24,46,72,.12);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="login-wrap">
          <h1>📦 PK Warehouse</h1>
          <p>เข้าสู่ระบบติดตามใบเบิกและสถานะงานคลังสินค้า</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button(
            "เข้าสู่ระบบ",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.page = "📝 บันทึกใบเบิกใหม่"
            st.rerun()
        else:
            st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")


if not st.session_state.authenticated:
    login_page()
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
        border-radius: 18px;
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

initialize_database()
records = load_records()

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
            "📋 ประวัติและส่งออกข้อมูล",
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
        <h1>📦 PK Warehouse · Requisition Tracking</h1>
        <p>บันทึก JOB • วิเคราะห์เวลา • แก้ไขข้อมูลและจัดการประวัติใบเบิก</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# Page 1: New requisitions
# ---------------------------------------------------------------------

if page == "📝 บันทึกใบเบิกใหม่":
    st.subheader("📝 บันทึกใบเบิกใหม่")
    st.caption(
        "เพิ่มหลาย JOB ได้ในครั้งเดียว • กรอกเฉพาะ JOB, แผนก/ไลน์, "
        "ชื่อสินค้า และจำนวน"
    )

    current_time = datetime.now()

    with st.form("new_requisitions_form", clear_on_submit=True):
        date_col, time_col = st.columns(2)

        received_date = date_col.date_input(
            "วันที่รับใบเบิก",
            value=date.today(),
        )
        received_time = time_col.time_input(
            "เวลารับใบเบิก",
            value=current_time.time().replace(second=0, microsecond=0),
            step=300,
        )

        initial_rows = pd.DataFrame(
            [
                {
                    "เลขที่ JOB": "",
                    "แผนก/ไลน์": "",
                    "ชื่อสินค้า": "",
                    "จำนวน": 1,
                }
            ]
        )

        entry_table = st.data_editor(
            initial_rows,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "เลขที่ JOB": st.column_config.TextColumn(
                    "เลขที่ JOB",
                    required=False,
                ),
                "แผนก/ไลน์": st.column_config.TextColumn(
                    "แผนก/ไลน์ผลิต",
                    required=False,
                ),
                "ชื่อสินค้า": st.column_config.TextColumn(
                    "ชื่อสินค้า",
                    required=False,
                ),
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
            entered = []
            errors = []

            for row_index, row in entry_table.iterrows():
                number_raw = str(row.get("เลขที่ JOB", "") or "").strip()
                department = str(row.get("แผนก/ไลน์", "") or "").strip()
                product = str(row.get("ชื่อสินค้า", "") or "").strip()
                quantity_raw = row.get("จำนวน", 1)

                if not any([number_raw, department, product]):
                    continue

                number = normalize_job_number(number_raw)

                if not number:
                    errors.append(f"แถว {row_index + 1}: กรุณากรอกเลข JOB")
                    continue
                if not department:
                    errors.append(f"{number}: กรุณากรอกแผนก/ไลน์")
                    continue
                if not product:
                    errors.append(f"{number}: กรุณากรอกชื่อสินค้า")
                    continue

                try:
                    quantity = int(quantity_raw)
                    if quantity < 1:
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append(f"{number}: จำนวนต้องเป็นจำนวนเต็มตั้งแต่ 1 ขึ้นไป")
                    continue

                entered.append(
                    {
                        "job_number": number,
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
                item["job_number"].casefold()
                for item in entered
            ]

            duplicates_in_batch = {
                number
                for number in batch_numbers
                if batch_numbers.count(number) > 1
            }
            duplicates_in_db = [
                item["job_number"]
                for item in entered
                if item["job_number"].casefold() in existing_numbers
            ]

            if errors:
                for error in errors:
                    st.error(error)
            elif not entered:
                st.warning("กรุณากรอกข้อมูล JOB อย่างน้อยหนึ่งรายการ")
            elif duplicates_in_batch:
                st.error(
                    "พบเลข JOB ซ้ำในตาราง: "
                    + ", ".join(sorted(duplicates_in_batch))
                )
            elif duplicates_in_db:
                st.error(
                    "เลข JOB เหล่านี้มีในระบบแล้ว: "
                    + ", ".join(duplicates_in_db)
                )
            else:
                received_at = datetime.combine(
                    received_date,
                    received_time,
                ).isoformat(sep=" ", timespec="seconds")

                for item in entered:
                    item["received_at"] = received_at

                try:
                    insert_records(entered)
                    render_tick_sound()
                    st.success(f"บันทึกใบเบิกแล้ว {len(entered)} JOB")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error(
                        "บันทึกไม่สำเร็จเพราะมีเลข JOB ซ้ำ "
                        "กรุณาตรวจสอบรายการแล้วลองอีกครั้ง"
                    )


# ---------------------------------------------------------------------
# Page 2: Dashboard
# ---------------------------------------------------------------------

elif page == "📊 Dashboard สรุปผล":
    st.subheader("📊 Dashboard สรุปผล")

    if records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        total_today = 0
        avg_processing = 0
        bottleneck = "—"
    else:
        today_text = date.today().isoformat()
        received_dates = pd.to_datetime(
            records["received_at"],
            errors="coerce",
        )
        total_today = int(
            (received_dates.dt.date == date.today()).sum()
        )

        processing_values = [
            minutes_between(row["received_at"], row["picked_at"])
            for _, row in records.iterrows()
            if row["picked_at"]
        ]
        processing_values = [
            value for value in processing_values if value is not None
        ]

        waiting_values = [
            minutes_between(row["picked_at"], row["handover_at"])
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
            bottleneck = "รอ PD รับของ"
        else:
            bottleneck = "ขั้นตอนจัดสินค้า"

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("📥 ยอดเบิกวันนี้", f"{total_today:,}")
    kpi_cols[1].metric("📄 จำนวน JOB ทั้งหมด", f"{len(records):,}")
    kpi_cols[2].metric(
        "⏱️ เวลาเฉลี่ยจัดเสร็จ",
        duration_text(avg_processing) if avg_processing else "0 นาที",
    )
    kpi_cols[3].metric("🚦 จุดคอขวด", bottleneck)

    if not records.empty:
        chart_col, status_col = st.columns(2)

        with chart_col:
            chart_data = records.copy()
            chart_data["received_dt"] = pd.to_datetime(
                chart_data["received_at"],
                errors="coerce",
            )
            chart_data["ชั่วโมง"] = chart_data["received_dt"].dt.hour
            hourly = (
                chart_data.groupby("ชั่วโมง")
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
                height=350,
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
                hole=0.52,
                color_discrete_sequence=[
                    "#d59620",
                    "#3474c4",
                    "#19845f",
                    "#c2414d",
                    "#778397",
                ],
            )
            figure.update_layout(
                template="plotly_white",
                height=350,
                margin=dict(l=10, r=10, t=55, b=10),
            )
            st.plotly_chart(figure, use_container_width=True)

        late_data = records.copy()
        late_data["ใบเบิกเย็น"] = late_data["received_at"].apply(
            lambda value: "ใบเบิกเย็น"
            if pd.notna(value) and datetime.fromisoformat(str(value)).time() > time(16, 0)
            else "รับก่อน Cut-off"
        )

        department_summary = (
            late_data.groupby(["department", "ใบเบิกเย็น"])
            .size()
            .reset_index(name="จำนวน JOB")
        )

        st.markdown("#### 🔴 ใบเบิกเย็นแยกตามแผนก/ไลน์")
        figure = px.bar(
            department_summary,
            x="department",
            y="จำนวน JOB",
            color="ใบเบิกเย็น",
            barmode="group",
            color_discrete_map={
                "ใบเบิกเย็น": "#c2414d",
                "รับก่อน Cut-off": "#19845f",
            },
        )
        figure.update_layout(
            template="plotly_white",
            height=330,
            margin=dict(l=10, r=10, t=25, b=10),
            xaxis_title="แผนก/ไลน์",
        )
        st.plotly_chart(figure, use_container_width=True)


# ---------------------------------------------------------------------
# Page 3: Manage, edit, cancel or delete
# ---------------------------------------------------------------------

elif page == "✏️ จัดการและแก้ไขรายการ":
    st.subheader("✏️ จัดการและแก้ไขรายการ")

    if records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
    else:
        options = {
            f"{row['job_number']} · {row['department']} · "
            f"{row['product_name']}": int(row["id"])
            for _, row in records.iterrows()
        }

        selected_label = st.selectbox(
            "เลือกใบเบิกที่ต้องการจัดการ",
            list(options),
        )
        selected_id = options[selected_label]
        selected = records[records["id"] == selected_id].iloc[0]

        st.markdown("#### แก้ไขข้อมูล JOB")
        with st.form("edit_record_form"):
            col1, col2 = st.columns(2)

            edited_job = col1.text_input(
                "เลขที่ JOB",
                value=str(selected["job_number"]),
            )
            edited_department = col2.text_input(
                "แผนก/ไลน์",
                value=str(selected["department"]),
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

            edited_status = st.selectbox(
                "สถานะ",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(selected["status"])
                if selected["status"] in STATUS_OPTIONS
                else 0,
                format_func=lambda value: STATUS_LABELS[value],
            )

            st.caption(
                "แก้ไขเวลาได้โดยใช้รูปแบบ YYYY-MM-DD HH:MM:SS "
                "เว้นว่างได้หากยังไม่มีเวลาในขั้นตอนนั้น"
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
                "เวลาจ่ายของ / PD รับ",
                value=timestamp_text(selected["handover_at"]),
            )
            canceled_at = st.text_input(
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

                timestamp_values = {
                    "in_progress_at": in_progress_at,
                    "picked_at": picked_at,
                    "handover_at": handover_at,
                    "cancelled_at": canceled_at,
                }

                invalid_timestamps = [
                    label
                    for label, value in timestamp_values.items()
                    if value.strip() and parse_timestamp(value) is None
                ]

                if not normalized_job:
                    st.error("กรุณากรอกเลข JOB")
                elif not edited_department.strip():
                    st.error("กรุณากรอกแผนก/ไลน์")
                elif not edited_product.strip():
                    st.error("กรุณากรอกชื่อสินค้า")
                elif parsed_received is None:
                    st.error("เวลารับใบเบิกต้องอยู่ในรูปแบบ YYYY-MM-DD HH:MM:SS")
                elif invalid_timestamps:
                    st.error(
                        "ตรวจสอบรูปแบบเวลาในช่อง: "
                        + ", ".join(invalid_timestamps)
                    )
                elif edited_status == "cancelled" and (
                    not canceled_by.strip()
                    or not cancellation_reason.strip()
                ):
                    st.error("สถานะยกเลิกต้องระบุผู้สั่งและสาเหตุ")
                else:
                    values = {
                        "job_number": normalized_job,
                        "department": edited_department.strip(),
                        "product_name": edited_product.strip(),
                        "quantity": int(edited_quantity),
                        "received_at": parsed_received.isoformat(
                            sep=" ", timespec="seconds"
                        ),
                        "in_progress_at": (
                            parse_timestamp(in_progress_at).isoformat(
                                sep=" ", timespec="seconds"
                            )
                            if in_progress_at.strip()
                            else None
                        ),
                        "picked_at": (
                            parse_timestamp(picked_at).isoformat(
                                sep=" ", timespec="seconds"
                            )
                            if picked_at.strip()
                            else None
                        ),
                        "handover_at": (
                            parse_timestamp(handover_at).isoformat(
                                sep=" ", timespec="seconds"
                            )
                            if handover_at.strip()
                            else None
                        ),
                        "cancelled_at": (
                            parse_timestamp(canceled_at).isoformat(
                                sep=" ", timespec="seconds"
                            )
                            if canceled_at.strip()
                            else None
                        ),
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
            st.caption(
                "ยกเลิกจะเก็บรายการไว้ในประวัติ พร้อมให้ระบุผู้สั่งและสาเหตุ"
            )
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
                    st.success("JOB ถูกยกเลิกและบันทึกประวัติแล้ว")
                    st.rerun()

        with delete_col:
            st.caption("ลบจะนำรายการออกจากระบบและประวัติถาวร")
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

elif page == "📋 ประวัติและส่งออกข้อมูล":
    st.subheader("📋 ประวัติและส่งออกข้อมูล")

    if records.empty:
        st.warning("ยังไม่มีข้อมูลใบเบิก")
        history_df = pd.DataFrame(
            columns=[
                "เลขที่ JOB",
                "แผนก/ไลน์",
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
                "department": "แผนก/ไลน์",
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
            "แผนก/ไลน์",
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
        file_name=f"warehouse_requisitions_{date.today():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
