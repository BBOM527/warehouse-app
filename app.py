"""PK Warehouse JOB Tracking
รันด้วย: streamlit run app.py

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


DB_PATH = Path(
    os.getenv(
        "WAREHOUSE_DB",
        str(Path(__file__).resolve().with_name("warehouse_tracking.db")),
    )
)
DEFAULT_CUTOFF = time(16, 0)

STATUS_LABELS = {
    "received": "🟡 รับ JOB / กำลังจัด",
    "in_progress": "🟡 กำลังจัด",
    "completed": "🔵 จัดเสร็จ / รอ PD",
    "handed_over": "🟢 PD มารับแล้ว",
    "cancelled": "🔴 ยกเลิก",
}

LEGACY_SAMPLE_NUMBERS = [f"WR-260{i:02d}" for i in range(1, 14)]


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
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_number TEXT NOT NULL UNIQUE,
                department TEXT NOT NULL,
                received_time TEXT NOT NULL,
                in_progress_time TEXT,
                picked_time TEXT,
                handover_time TEXT,
                canceled_time TEXT,
                canceled_by TEXT,
                cancel_reason TEXT,
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

        # ล้างเฉพาะข้อมูลจำลองจากเวอร์ชันก่อนเพียงครั้งเดียว
        cleanup_key = "legacy_mock_rows_removed_v1"
        cleaned = connection.execute(
            "SELECT value FROM app_metadata WHERE key = ?",
            (cleanup_key,),
        ).fetchone()

        if cleaned is None:
            placeholders = ",".join("?" for _ in LEGACY_SAMPLE_NUMBERS)
            connection.execute(
                f"DELETE FROM jobs WHERE job_number IN ({placeholders})",
                LEGACY_SAMPLE_NUMBERS,
            )
            connection.execute(
                "INSERT INTO app_metadata (key, value) VALUES (?, ?)",
                (cleanup_key, "done"),
            )


def load_jobs():
    with get_connection() as connection:
        return pd.read_sql_query(
            "SELECT * FROM jobs ORDER BY received_time DESC, id DESC",
            connection,
        )


def add_jobs_bulk(entries, received_time):
    """บันทึกหลาย JOB ใน transaction เดียว"""
    now = datetime.now().isoformat(sep=" ", timespec="seconds")

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO jobs (
                job_number,
                department,
                received_time,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'received', ?, ?)
            """,
            [
                (job_number, department, received_time, now, now)
                for job_number, department in entries
            ],
        )


def update_job(
    job_id,
    status,
    timestamp,
    canceled_by="",
    cancel_reason="",
):
    timestamp_column = {
        "in_progress": "in_progress_time",
        "completed": "picked_time",
        "handed_over": "handover_time",
        "cancelled": "canceled_time",
    }[status]

    now = datetime.now().isoformat(sep=" ", timespec="seconds")

    with get_connection() as connection:
        connection.execute(
            f"""
            UPDATE jobs
            SET status = ?,
                {timestamp_column} = ?,
                canceled_by = ?,
                cancel_reason = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                timestamp,
                canceled_by or None,
                cancel_reason or None,
                now,
                job_id,
            ),
        )


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def now_string():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def is_late(value, cutoff):
    received = parse_datetime(value)
    return received is not None and received.time() > cutoff


def duration_minutes(start, end):
    start_dt = parse_datetime(start)
    end_dt = parse_datetime(end)

    if start_dt is None or end_dt is None:
        return None

    return max(0, round((end_dt - start_dt).total_seconds() / 60))


def safe_average(values):
    """คำนวณค่าเฉลี่ยเมื่อมีข้อมูล มิฉะนั้นคืนค่า 0"""
    if values:
        return round(sum(values) / len(values))
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


def format_timestamp(value):
    parsed = parse_datetime(value)
    if parsed is None:
        return "—"
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def normalize_job_number(value):
    value = value.strip()

    if not value:
        return ""

    if value.upper().startswith("JOB-"):
        return value.upper()

    if value.isdigit() and len(value) == 4:
        return f"JOB-{value}"

    return value.upper()


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
          } catch (error) {
            // หากเบราว์เซอร์ปิดเสียงไว้ แอปยังทำงานได้ตามปกติ
          }
        })();
        </script>
        """,
        height=0,
    )


# ---------------------------------------------------------------------
# Streamlit setup and CSS
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="PK Warehouse | JOB Tracking",
    page_icon="📦",
    layout="wide",
)

if "cutoff" not in st.session_state:
    st.session_state.cutoff = DEFAULT_CUTOFF

initialize_database()

# CSS อยู่ภายใน string ของ st.markdown เพื่อป้องกัน SyntaxError
st.markdown(
    """
    <style>
    :root {
        --ink: #162538;
        --muted: #748195;
        --line: #e4eaf1;
        --shadow: 0 14px 38px rgba(24, 46, 72, .09);
    }

    .stApp {
        background:
            radial-gradient(ellipse at 8% 0%, rgba(76,153,165,.14), transparent 34%),
            radial-gradient(ellipse at 96% 8%, rgba(91,117,185,.12), transparent 30%),
            #f3f6fa;
    }

    .block-container {
        max-width: 1500px;
        padding-top: 1.25rem;
        padding-bottom: 2.5rem;
    }

    .hero {
        padding: 25px 30px;
        border: 1px solid rgba(255,255,255,.45);
        border-radius: 22px;
        color: white;
        background: linear-gradient(115deg, #132940, #176d70);
        box-shadow: 0 20px 48px rgba(25,54,78,.2);
        margin-bottom: 18px;
    }

    .hero p {
        margin: 5px 0 0;
        color: #d5e7eb;
    }

    [data-testid="stMetric"] {
        background: rgba(255,255,255,.83);
        border: 1px solid rgba(255,255,255,.95);
        border-radius: 17px;
        padding: 15px 17px;
        box-shadow: var(--shadow);
        backdrop-filter: blur(12px);
    }

    div[data-testid="stForm"] {
        background: rgba(255,255,255,.82);
        border: 1px solid rgba(255,255,255,.95);
        border-radius: 17px;
        padding: 17px;
        box-shadow: var(--shadow);
    }

    div.stButton > button,
    div.stFormSubmitButton > button,
    div.stDownloadButton > button {
        border-radius: 11px;
        transition: transform .12s ease, box-shadow .15s ease;
        box-shadow: 0 5px 14px rgba(28,55,78,.12);
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover,
    div.stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 9px 20px rgba(28,55,78,.18);
    }

    div.stButton > button:active,
    div.stFormSubmitButton > button:active,
    div.stDownloadButton > button:active {
        transform: scale(.98);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #e5ebf1;
        border-radius: 15px;
        overflow: hidden;
        box-shadow: var(--shadow);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>📦 PK Warehouse · JOB Tracking</h1>
        <p>บันทึกเวลา JOB • แสดงหลักฐาน Timeline • ติดตามงานจริงของคลังสินค้า</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    st.session_state.cutoff = st.time_input(
        "Cut-off รับใบเบิก",
        value=st.session_state.cutoff,
        step=300,
    )
    st.caption(f"Cut-off ปัจจุบัน: {st.session_state.cutoff:%H:%M} น.")
    st.divider()
    st.markdown("🟡 รับ JOB / กำลังจัด")
    st.markdown("🔵 จัดเสร็จ / รอ PD")
    st.markdown("🟢 PD มารับแล้ว")
    st.markdown("🔴 ยกเลิก")


jobs = load_jobs()
has_data = not jobs.empty

# กำหนดค่าเริ่มต้นไว้ก่อน เพื่อให้ใช้ได้แม้ฐานข้อมูลยังว่าง
processing_values = []
waiting_values = []

if has_data:
    late_count = sum(
        is_late(value, st.session_state.cutoff)
        for value in jobs["received_time"]
    )
    late_percentage = late_count / len(jobs) * 100

    processing_values = [
        duration_minutes(row["received_time"], row["picked_time"])
        for _, row in jobs.iterrows()
        if row["picked_time"]
    ]
    processing_values = [
        value for value in processing_values if value is not None
    ]

    waiting_values = [
        duration_minutes(row["picked_time"], row["handover_time"])
        for _, row in jobs.iterrows()
        if row["picked_time"] and row["handover_time"]
    ]
    waiting_values = [
        value for value in waiting_values if value is not None
    ]

    avg_processing = safe_average(processing_values)
    avg_waiting = safe_average(waiting_values)

    canceled_jobs = jobs[jobs["status"] == "cancelled"]
    wasted_values = []

    for _, row in canceled_jobs.iterrows():
        work_start = row["in_progress_time"] or row["received_time"]
        wasted = duration_minutes(work_start, row["canceled_time"])
        wasted_values.append(wasted if wasted is not None else 0)

    wasted_total = sum(wasted_values)
else:
    late_count = 0
    late_percentage = 0
    avg_processing = 0
    avg_waiting = 0
    canceled_jobs = jobs.copy()
    wasted_total = 0


# ---------------------------------------------------------------------
# KPI dashboard
# ---------------------------------------------------------------------

kpis = st.columns(5)

kpis[0].metric("📄 JOB ทั้งหมด", f"{len(jobs):,}")
kpis[1].metric("🔴 ใบเบิกเย็น", f"{late_percentage:.1f}%")

# เงื่อนไขนี้แก้ SyntaxError และป้องกันการหารด้วยศูนย์
kpis[2].metric(
    "⏱️ เวลาจัดเฉลี่ย",
    duration_label(avg_processing)
    if (processing_values and has_data)
    else "0 นาที",
)

kpis[3].metric(
    "🕒 เวลารอ PD เฉลี่ย",
    duration_label(avg_waiting)
    if (waiting_values and has_data)
    else "0 นาที",
)

kpis[4].metric(
    "❌ ยกเลิก / เสียเวลา",
    f"{len(canceled_jobs)} / {wasted_total} นาที",
)

st.subheader("📊 ภาพรวมการทำงาน")

if not has_data:
    st.warning("ยังไม่มีข้อมูลใบเบิก")
else:
    chart_col, department_col = st.columns(2)

    with chart_col:
        chart_data = jobs.copy()
        chart_data["received_at_dt"] = pd.to_datetime(
            chart_data["received_time"],
            errors="coerce",
        )
        chart_data["hour"] = chart_data["received_at_dt"].dt.hour

        hourly = (
            chart_data.groupby("hour")
            .size()
            .reindex(range(7, 22), fill_value=0)
            .rename("จำนวน JOB")
            .reset_index()
        )
        hourly.columns = ["ชั่วโมง", "จำนวน JOB"]
        hourly["ช่วงเวลา"] = hourly["ชั่วโมง"].apply(
            lambda hour: "🔴 หลัง Cut-off"
            if hour >= st.session_state.cutoff.hour
            else "🟢 ก่อน Cut-off"
        )

        figure = px.bar(
            hourly,
            x="ชั่วโมง",
            y="จำนวน JOB",
            color="ช่วงเวลา",
            color_discrete_map={
                "🟢 ก่อน Cut-off": "#319783",
                "🔴 หลัง Cut-off": "#db5b63",
            },
            title="จำนวน JOB ที่รับเข้ารายชั่วโมง",
            text="จำนวน JOB",
        )
        figure.update_layout(
            template="plotly_white",
            height=320,
            margin=dict(l=8, r=8, t=50, b=8),
            legend_title_text="",
            paper_bgcolor="rgba(255,255,255,0)",
            plot_bgcolor="rgba(255,255,255,0)",
            xaxis_title="ชั่วโมงที่รับ",
            yaxis_title="จำนวน JOB",
        )
        figure.update_xaxes(dtick=1)
        st.plotly_chart(figure, use_container_width=True)

    with department_col:
        department_data = jobs.copy()
        department_data["late"] = department_data["received_time"].apply(
            lambda value: is_late(value, st.session_state.cutoff)
        )

        summary = (
            department_data.groupby("department")
            .agg(
                total=("job_number", "count"),
                late_count=("late", "sum"),
            )
            .reset_index()
        )
        summary["late_pct"] = summary["late_count"] / summary["total"] * 100
        summary = summary.sort_values("late_pct")

        figure = px.bar(
            summary,
            x="late_pct",
            y="department",
            orientation="h",
            text=summary["late_pct"].map(
                lambda value: f"{value:.0f}%"
            ),
            title="สัดส่วนใบเบิกเย็นแยกตามแผนก/ไลน์",
            labels={
                "late_pct": "ใบเบิกเย็น (%)",
                "department": "แผนก/ไลน์",
            },
            color="late_pct",
            color_continuous_scale=["#66b99d", "#f0bd58", "#d9535d"],
        )
        figure.update_layout(
            template="plotly_white",
            height=320,
            margin=dict(l=8, r=8, t=50, b=8),
            coloraxis_showscale=False,
            paper_bgcolor="rgba(255,255,255,0)",
            plot_bgcolor="rgba(255,255,255,0)",
        )
        figure.update_xaxes(range=[0, 100])
        st.plotly_chart(figure, use_container_width=True)


# ---------------------------------------------------------------------
# Bulk and quick JOB input
# ---------------------------------------------------------------------

st.subheader("📥 รับ JOB เข้า")

department = st.text_input(
    "แผนก / ไลน์ผลิต *",
    placeholder="เช่น PD-Line 1",
    key="department_input",
)

bulk_text = st.text_area(
    "📋 วางหลาย JOB โดยแยกบรรทัด",
    placeholder="JOB-6901\nJOB-6902\nJOB-6903, PD-Line 2",
    help="ถ้าใส่เฉพาะ JOB ระบบจะใช้แผนก/ไลน์ด้านบน",
)

bulk_col, quick_col = st.columns(2)

with bulk_col:
    if st.button(
        "📋 บันทึกรับเรื่องทั้งหมด",
        type="primary",
        use_container_width=True,
    ):
        entries = []
        invalid_lines = []

        for line in bulk_text.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = [
                part.strip()
                for part in line.replace("\t", ",").split(",")
            ]
            number = normalize_job_number(parts[0])
            department_for_job = (
                parts[1]
                if len(parts) > 1 and parts[1]
                else department.strip()
            )

            if not number or not department_for_job:
                invalid_lines.append(line)
            else:
                entries.append((number, department_for_job))

        existing = (
            {str(number).casefold() for number in jobs["job_number"]}
            if has_data
            else set()
        )

        batch_numbers = [number.casefold() for number, _ in entries]
        duplicate_in_batch = {
            number for number in batch_numbers if batch_numbers.count(number) > 1
        }
        duplicate_in_database = [
            number
            for number, _ in entries
            if number.casefold() in existing
        ]

        if invalid_lines:
            st.error(
                "กรุณากรอกแผนก/ไลน์ด้านบน หรือระบุแผนกหลังเลข JOB "
                "เช่น JOB-6901, PD-Line 1"
            )
        elif not entries:
            st.error("กรุณาวางเลข JOB อย่างน้อยหนึ่งรายการ")
        elif duplicate_in_batch:
            st.error(
                "พบเลข JOB ซ้ำในข้อความที่วาง: "
                + ", ".join(sorted(duplicate_in_batch))
            )
        elif duplicate_in_database:
            st.error(
                "JOB เหล่านี้มีในระบบแล้ว: "
                + ", ".join(duplicate_in_database)
            )
        else:
            try:
                add_jobs_bulk(entries, now_string())
                play_tick()
                st.success(f"บันทึกรับเรื่องแล้ว {len(entries)} JOB")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error(
                    "บันทึกไม่สำเร็จเนื่องจากมีเลข JOB ซ้ำ "
                    "กรุณาตรวจสอบข้อมูลแล้วลองอีกครั้ง"
                )

with quick_col:
    with st.form("quick_input", clear_on_submit=True):
        quick_number = st.text_input(
            "⌨️ พิมพ์เลข 4 หลัก หรือ JOB-xxxx",
            placeholder="เช่น 6901",
        )
        quick_submit = st.form_submit_button(
            "รับ JOB ด่วน",
            use_container_width=True,
        )

        if quick_submit:
            number = normalize_job_number(quick_number)
            department_for_job = department.strip()

            existing = (
                {str(value).casefold() for value in jobs["job_number"]}
                if has_data
                else set()
            )

            if not number:
                st.error("กรุณากรอกเลข JOB")
            elif not department_for_job:
                st.error("กรุณากรอกแผนก/ไลน์ผลิต")
            elif number.casefold() in existing:
                st.error("เลข JOB นี้มีในระบบแล้ว")
            else:
                try:
                    add_jobs_bulk(
                        [(number, department_for_job)],
                        now_string(),
                    )
                    play_tick()
                    st.success(f"รับ {number} แล้ว")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("บันทึกไม่สำเร็จ เลข JOB นี้อาจมีในระบบแล้ว")


# ---------------------------------------------------------------------
# Update JOB status
# ---------------------------------------------------------------------

st.subheader("🔄 อัปเดตสถานะ JOB")

if not has_data:
    st.info("เพิ่ม JOB ก่อน แล้วจึงอัปเดตสถานะได้")
else:
    active_jobs = jobs[
        ~jobs["status"].isin(["handed_over", "cancelled"])
    ]

    if active_jobs.empty:
        st.info("ไม่มี JOB ที่รออัปเดตสถานะ")
    else:
        job_options = {
            f"{row['job_number']} · {row['department']} · "
            f"{STATUS_LABELS.get(row['status'], row['status'])}": int(row["id"])
            for _, row in active_jobs.iterrows()
        }
        selected_label = st.selectbox("เลือก JOB", list(job_options))
        selected_id = job_options[selected_label]
        selected_job = jobs[jobs["id"] == selected_id].iloc[0]

        new_status = st.selectbox(
            "สถานะใหม่",
            ["in_progress", "completed", "handed_over", "cancelled"],
            format_func=lambda value: STATUS_LABELS[value],
        )

        canceled_by = ""
        cancel_reason = ""

        if new_status == "cancelled":
            st.warning("การยกเลิกต้องระบุผู้สั่ง PN/PD และสาเหตุ")
            canceled_by = st.text_input("ผู้สั่งยกเลิก PN/PD *")
            cancel_reason = st.text_area("สาเหตุการยกเลิก *")

        if st.button(
            "บันทึกสถานะ",
            type="primary",
            use_container_width=True,
        ):
            if new_status == "cancelled" and (
                not canceled_by.strip() or not cancel_reason.strip()
            ):
                st.error("กรุณาระบุผู้สั่งยกเลิกและสาเหตุให้ครบ")
            elif (
                new_status == "handed_over"
                and not selected_job["picked_time"]
            ):
                st.error("ต้องบันทึกจัดเสร็จก่อน จึงบันทึก PD มารับได้")
            else:
                update_job(
                    selected_id,
                    new_status,
                    now_string(),
                    canceled_by.strip(),
                    cancel_reason.strip(),
                )
                play_tick()
                st.success("อัปเดตสถานะแล้ว")
                st.rerun()


# ---------------------------------------------------------------------
# JOB register and filters
# ---------------------------------------------------------------------

st.subheader("📋 ทะเบียน JOB")

filter_col, late_col, search_col = st.columns([1, 1, 1.5])

status_filter = filter_col.multiselect(
    "กรองสถานะ",
    list(STATUS_LABELS),
    format_func=lambda value: STATUS_LABELS[value],
)
late_filter = late_col.selectbox(
    "กรองเวลา Cut-off",
    ["ทั้งหมด", "ใบเบิกเย็น", "ในเวลา"],
)
search_text = search_col.text_input("ค้นหา JOB / แผนก")

filtered = jobs.copy()

if status_filter and not filtered.empty:
    filtered = filtered[filtered["status"].isin(status_filter)]

if late_filter == "ใบเบิกเย็น" and not filtered.empty:
    filtered = filtered[
        filtered["received_time"].apply(
            lambda value: is_late(value, st.session_state.cutoff)
        )
    ]
elif late_filter == "ในเวลา" and not filtered.empty:
    filtered = filtered[
        ~filtered["received_time"].apply(
            lambda value: is_late(value, st.session_state.cutoff)
        )
    ]

if search_text.strip() and not filtered.empty:
    query = search_text.strip().casefold()
    filtered = filtered[
        filtered.apply(
            lambda row: query in str(row["job_number"]).casefold()
            or query in str(row["department"]).casefold(),
            axis=1,
        )
    ]

display_columns = [
    "เลขที่ JOB",
    "แผนก/ไลน์",
    "📥 รับเรื่อง",
    "🟡 เริ่มจัด",
    "🔵 จัดเสร็จ",
    "🟢 PD รับของ",
    "❌ ยกเลิก",
    "สถานะ",
    "แท็ก",
    "เวลาจัด",
    "เวลารอ PD",
    "ผู้สั่งยกเลิก",
    "สาเหตุยกเลิก",
]

display_rows = []

for _, row in filtered.iterrows():
    display_rows.append(
        {
            "เลขที่ JOB": row["job_number"],
            "แผนก/ไลน์": row["department"],
            "📥 รับเรื่อง": format_timestamp(row["received_time"]),
            "🟡 เริ่มจัด": format_timestamp(row["in_progress_time"]),
            "🔵 จัดเสร็จ": format_timestamp(row["picked_time"]),
            "🟢 PD รับของ": format_timestamp(row["handover_time"]),
            "❌ ยกเลิก": format_timestamp(row["canceled_time"]),
            "สถานะ": STATUS_LABELS.get(row["status"], row["status"]),
            "แท็ก": (
                "🔴 ใบเบิกเย็น/ส่งช้า"
                if is_late(row["received_time"], st.session_state.cutoff)
                else "🟢 ในเวลา Cut-off"
            ),
            "เวลาจัด": duration_label(
                duration_minutes(row["received_time"], row["picked_time"])
            ),
            "เวลารอ PD": duration_label(
                duration_minutes(row["picked_time"], row["handover_time"])
            ),
            "ผู้สั่งยกเลิก": row["canceled_by"] or "—",
            "สาเหตุยกเลิก": row["cancel_reason"] or "—",
        }
    )

display_df = pd.DataFrame(display_rows, columns=display_columns)

if not has_data:
    st.warning("ยังไม่มีข้อมูลใบเบิก")

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    height=420,
)


# ---------------------------------------------------------------------
# Cancellation evidence
# ---------------------------------------------------------------------

if has_data:
    canceled_jobs = jobs[jobs["status"] == "cancelled"]

    if not canceled_jobs.empty:
        st.markdown("#### 📄 หลักฐาน Timeline รายการยกเลิก")

        for _, row in canceled_jobs.iterrows():
            work_start = row["in_progress_time"] or row["received_time"]
            wasted = duration_minutes(work_start, row["canceled_time"])

            with st.expander(
                f"{row['job_number']} · {row['department']} · "
                f"ยกเลิก {format_timestamp(row['canceled_time'])}"
            ):
                st.write(f"**รับเรื่อง:** {format_timestamp(row['received_time'])}")
                st.write(f"**เริ่มจัด:** {format_timestamp(row['in_progress_time'])}")
                st.write(f"**จัดเสร็จ:** {format_timestamp(row['picked_time'])}")
                st.write(f"**ยกเลิก:** {format_timestamp(row['canceled_time'])}")
                st.write(f"**เวลางานที่เสียไป:** {duration_label(wasted)}")
                st.write(f"**ผู้สั่งยกเลิก:** {row['canceled_by'] or '—'}")
                st.write(f"**สาเหตุ:** {row['cancel_reason'] or '—'}")

                if st.button(
                    "🖨️ พิมพ์ / บันทึก PDF",
                    key=f"print_{row['id']}",
                ):
                    st.components.v1.html(
                        "<script>window.parent.print();</script>",
                        height=0,
                    )


# ---------------------------------------------------------------------
# CSV and Excel export
# ---------------------------------------------------------------------

csv_data = display_df.to_csv(index=False).encode("utf-8-sig")
csv_col, excel_col = st.columns(2)

csv_col.download_button(
    "📥 Export Data to CSV",
    data=csv_data,
    file_name=f"warehouse_jobs_{date.today():%Y%m%d}.csv",
    mime="text/csv",
    use_container_width=True,
)

try:
    excel_buffer = BytesIO()

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        display_df.to_excel(
            writer,
            index=False,
            sheet_name="JOB Tracking",
        )

    excel_buffer.seek(0)

    excel_col.download_button(
        "📊 Export Data to Excel",
        data=excel_buffer,
        file_name=f"warehouse_jobs_{date.today():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
except ImportError:
    excel_col.caption(
        "ติดตั้ง openpyxl เพื่อ Export Excel: pip install openpyxl"
    )

st.caption(
    "Cut-off 16:00 น. • เวลาจาก System Clock ของเครื่องที่รันแอป • "
    "เวลาเฉลี่ยแสดง 0 นาทีเมื่อยังไม่มีรายการที่คำนวณได้"
)
