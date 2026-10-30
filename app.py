"""PK Warehouse JOB Tracking
รันด้วย: streamlit run app.py

ติดตั้งแพ็กเกจ:
    pip install streamlit pandas plotly
"""

from datetime import date, datetime, time
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
CUTOFF_DEFAULT = time(16, 0)

STATUS_LABELS = {
    "received": "🟡 รับ JOB / กำลังจัด",
    "in_progress": "🟡 กำลังจัด",
    "completed": "🔵 จัดเสร็จ / รอ PD",
    "handed_over": "🟢 PD มารับแล้ว",
    "cancelled": "🔴 ยกเลิก",
}

STATUS_COLORS = {
    "received": "#d59620",
    "in_progress": "#d59620",
    "completed": "#3474c4",
    "handed_over": "#19845f",
    "cancelled": "#c2414d",
}

# รายการตัวอย่างจากเวอร์ชันก่อน ลบออกจากฐานข้อมูลเดิมเพียงครั้งเดียว
# หลังจากนั้นข้อมูล JOB จริงที่เพิ่มใหม่จะไม่ถูกลบ
LEGACY_SAMPLE_NUMBERS = [f"WR-260{i:02d}" for i in range(1, 14)]
LEGACY_CLEANUP_KEY = "legacy_mock_rows_removed_v1"


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

        cleanup_done = connection.execute(
            "SELECT value FROM app_metadata WHERE key = ?",
            (LEGACY_CLEANUP_KEY,),
        ).fetchone()

        if cleanup_done is None:
            placeholders = ",".join("?" for _ in LEGACY_SAMPLE_NUMBERS)
            connection.execute(
                f"DELETE FROM jobs WHERE job_number IN ({placeholders})",
                LEGACY_SAMPLE_NUMBERS,
            )
            connection.execute(
                "INSERT INTO app_metadata (key, value) VALUES (?, ?)",
                (LEGACY_CLEANUP_KEY, "done"),
            )


def load_jobs():
    with get_connection() as connection:
        return pd.read_sql_query(
            "SELECT * FROM jobs ORDER BY received_time DESC, id DESC",
            connection,
        )


def add_job(job_number, department, received_time):
    now = datetime.now().isoformat(sep=" ", timespec="seconds")

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                job_number, department, received_time, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, 'received', ?, ?)
            """,
            (job_number, department, received_time, now, now),
        )


def update_job(job_id, status, timestamp, canceled_by="", cancel_reason=""):
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
    except ValueError:
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
    if not value:
        return "—"

    parsed = parse_datetime(value)
    if parsed is None:
        return str(value)

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


def tick_sound():
    """เล่นเสียงติ๊กสั้น ๆ ผ่าน Web Audio API โดยไม่ใช้ไฟล์เสียง"""
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
            // ปิดเสียงหรือไม่รองรับ Web Audio ก็ยังใช้แอปได้ตามปกติ
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
    st.session_state.cutoff = CUTOFF_DEFAULT

initialize_database()

# CSS ต้องอยู่ภายใน string ที่ส่งให้ st.markdown
# ห้ามวางบรรทัด CSS เช่น --shadow: ... ไว้ตรง ๆ ในไฟล์ Python
st.markdown(
    """
    <style>
    :root {
        --ink: #162538;
        --muted: #748195;
        --line: #e4eaf1;
        --shadow: 0 14px 38px rgba(24, 46, 72, .09);
    }

    html, body, [class*="css"] {
        font-family: "Segoe UI", Tahoma, sans-serif;
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
# Sidebar settings
# ---------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    st.session_state.cutoff = st.time_input(
        "Cut-off รับใบเบิก",
        value=st.session_state.cutoff,
        step=300,
        help="ใบเบิกที่รับหลังเวลานี้จะถูกติดแท็กใบเบิกเย็น",
    )
    st.caption(f"Cut-off ปัจจุบัน: {st.session_state.cutoff:%H:%M} น.")
    st.divider()
    st.markdown("🟡 รับ JOB / กำลังจัด")
    st.markdown("🔵 จัดเสร็จ / รอ PD")
    st.markdown("🟢 PD มารับแล้ว")
    st.markdown("🔴 ยกเลิก")
    st.divider()
    st.caption("ข้อมูลบันทึกใน SQLite ที่อยู่ข้างไฟล์ app.py")


jobs = load_jobs()
has_data = not jobs.empty


# ---------------------------------------------------------------------
# KPI dashboard
# ---------------------------------------------------------------------

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

    waiting_values = [
        duration_minutes(row["picked_time"], row["handover_time"])
        for _, row in jobs.iterrows()
        if row["picked_time"] and row["handover_time"]
    ]

    canceled_jobs = jobs[jobs["status"] == "cancelled"]

    wasted_values = []
    for _, row in canceled_jobs.iterrows():
        work_start = row["in_progress_time"] or row["received_time"]
        wasted_values.append(
            duration_minutes(work_start, row["canceled_time"]) or 0
        )

    avg_processing = (
        round(sum(processing_values) / len(processing_values))
        if processing_values
        else None
    )
    avg_waiting = (
        round(sum(waiting_values) / len(waiting_values))
        if waiting_values
        else None
    )
    wasted_total = sum(wasted_values)
else:
    late_count = 0
    late_percentage = 0
    avg_processing = None
    avg_waiting = None
    canceled_jobs = jobs.copy()
    wasted_total = 0

kpis = st.columns(5)
kpis[0].metric("📄 JOB ทั้งหมด", f"{len(jobs):,}")
kpis[1].metric("🔴 ใบเบิกเย็น", f"{late_percentage:.1f}%")
kpis[2].metric("⏱️ เวลาจัดเฉลี่ย", duration_label(avg_processing))
kpis[3].metric("🕒 เวลารอ PD เฉลี่ย", duration_label(avg_waiting))
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

        hourly["เวลา"] = hourly["ชั่วโมง"].apply(
            lambda hour: "🔴 หลัง Cut-off"
            if hour >= st.session_state.cutoff.hour
            else "🟢 ก่อน Cut-off"
        )

        figure = px.bar(
            hourly,
            x="ชั่วโมง",
            y="จำนวน JOB",
            color="เวลา",
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

        department_summary = (
            department_data.groupby("department")
            .agg(
                total=("job_number", "count"),
                late_count=("late", "sum"),
            )
            .reset_index()
        )
        department_summary["late_pct"] = (
            department_summary["late_count"]
            / department_summary["total"]
            * 100
        )
        department_summary = department_summary.sort_values("late_pct")

        figure = px.bar(
            department_summary,
            x="late_pct",
            y="department",
            orientation="h",
            text=department_summary["late_pct"].map(
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
# Input: bulk and quick manual
# ---------------------------------------------------------------------

st.subheader("📥 รับ JOB เข้า")

department_input = st.text_input(
    "แผนก / ไลน์ผลิต *",
    placeholder="เช่น PD-Line 1",
    key="department_input",
)

bulk_text = st.text_area(
    "📋 วางหลาย JOB ได้ โดยแยกบรรทัด",
    placeholder="JOB-6901\nJOB-6902\nJOB-6903, PD-Line 2",
    help="ใส่เฉพาะ JOB ต่อบรรทัดได้ โดยระบบจะใช้แผนก/ไลน์ด้านบน",
)

bulk_col, quick_col = st.columns(2)

with bulk_col:
    if st.button(
        "📋 บันทึกรับเรื่องทั้งหมด",
        type="primary",
        use_container_width=True,
    ):
        default_department = department_input.strip()
        entries = []
        invalid_lines = []

        for line in bulk_text.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = [part.strip() for part in line.replace("\t", ",").split(",")]
            job_number = normalize_job_number(parts[0])
            department = parts[1] if len(parts) > 1 and parts[1] else default_department

            if not job_number or not department:
                invalid_lines.append(line)
            else:
                entries.append((job_number, department))

        existing_numbers = {
            str(value).casefold()
            for value in jobs["job_number"].tolist()
        } if has_data else set()

        duplicates = [
            number
            for number, _ in entries
            if number.casefold() in existing_numbers
        ]

        if invalid_lines:
            st.error(
                "กรุณาระบุแผนก/ไลน์ด้านบน หรือใส่แผนกต่อท้าย JOB ในแต่ละบรรทัด"
            )
        elif not entries:
            st.error("กรุณาวางเลข JOB อย่างน้อยหนึ่งรายการ")
        elif duplicates:
            st.error(f"JOB เหล่านี้มีในระบบแล้ว: {', '.join(duplicates)}")
        else:
            received_at = now_string()
            with get_connection() as connection:
                for job_number, department in entries:
                    connection.execute(
                        """
                        INSERT INTO jobs (
                            job_number, department, received_time, status,
                            created_at, updated_at
                        )
                        VALUES (?, ?, ?, 'received', ?, ?)
                        """,
                        (
                            job_number,
                            department,
                            received_at,
                            received_at,
                            received_at,
                        ),
                    )

            tick_sound()
            st.success(f"บันทึกรับเรื่องแล้ว {len(entries)} JOB")
            st.rerun()

with quick_col:
    with st.form("quick_job_form", clear_on_submit=True):
        quick_number = st.text_input(
            "⌨️ พิมพ์ด่วน: เลข 4 หลัก หรือ JOB-xxxx",
            placeholder="เช่น 6901",
        )
        quick_submit = st.form_submit_button(
            "รับ JOB ด่วน",
            use_container_width=True,
        )

        if quick_submit:
            job_number = normalize_job_number(quick_number)
            department = department_input.strip()

            existing_numbers = {
                str(value).casefold()
                for value in jobs["job_number"].tolist()
            } if has_data else set()

            if not job_number:
                st.error("กรุณากรอกเลข JOB")
            elif not department:
                st.error("กรุณากรอกแผนก/ไลน์ผลิตก่อนรับ JOB")
            elif job_number.casefold() in existing_numbers:
                st.error("เลข JOB นี้มีในระบบแล้ว")
            else:
                timestamp = now_string()
                add_job(job_number, department, timestamp)
                tick_sound()
                st.success(f"รับ {job_number} แล้ว")
                st.rerun()


# ---------------------------------------------------------------------
# Status update and cancellation
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

        selected_label = st.selectbox(
            "เลือก JOB",
            list(job_options.keys()),
        )
        selected_id = job_options[selected_label]
        selected_job = jobs[jobs["id"] == selected_id].iloc[0]

        new_status = st.selectbox(
            "สถานะใหม่",
            ["in_progress", "completed", "handed_over", "cancelled"],
            format_func=lambda value: STATUS_LABELS[value],
        )

        cancellation_by = ""
        cancellation_reason = ""

        if new_status == "cancelled":
            st.warning("การยกเลิกต้องระบุผู้สั่งยกเลิก PN/PD และสาเหตุ")
            cancellation_by = st.text_input(
                "ผู้สั่งยกเลิก PN/PD *",
                placeholder="ชื่อหรือรหัส PN/PD",
            )
            cancellation_reason = st.text_area(
                "สาเหตุการยกเลิก *",
                placeholder="เช่น เปลี่ยนแผน หรือยกเลิก JOB",
            )

        if st.button(
            "บันทึกสถานะ",
            type="primary",
            use_container_width=True,
        ):
            if new_status == "cancelled" and (
                not cancellation_by.strip()
                or not cancellation_reason.strip()
            ):
                st.error("กรุณาระบุผู้สั่งยกเลิกและสาเหตุให้ครบ")
            else:
                timestamp = now_string()

                if new_status == "handed_over" and not selected_job["picked_time"]:
                    st.error("ต้องบันทึกสถานะจัดเสร็จก่อน จึงบันทึก PD มารับได้")
                else:
                    update_job(
                        selected_id,
                        new_status,
                        timestamp,
                        cancellation_by.strip(),
                        cancellation_reason.strip(),
                    )
                    tick_sound()
                    st.success("บันทึกสถานะและเวลาแล้ว")
                    st.rerun()


# ---------------------------------------------------------------------
# Active queue
# ---------------------------------------------------------------------

st.subheader("⚡ คิวงาน")

if not has_data:
    st.warning("ยังไม่มีข้อมูลใบเบิก")
else:
    active_jobs = jobs[
        ~jobs["status"].isin(["handed_over", "cancelled"])
    ]

    if active_jobs.empty:
        st.info("ไม่มีงานค้างในคิว")
    else:
        for _, row in active_jobs.iterrows():
            late_badge = (
                " 🔴 ใบเบิกเย็น/ส่งช้า"
                if is_late(row["received_time"], st.session_state.cutoff)
                else ""
            )
            st.markdown(
                f"**{row['job_number']}** · {row['department']}  \n"
                f"{STATUS_LABELS.get(row['status'], row['status'])}"
                f"{late_badge}  \n"
                f"รับเรื่อง: `{format_timestamp(row['received_time'])}`"
            )


# ---------------------------------------------------------------------
# Register, evidence, filters, exports
# ---------------------------------------------------------------------

st.subheader("📋 ทะเบียน JOB")

filter_col, late_col, search_col = st.columns([1, 1, 1.5])

status_filter = filter_col.multiselect(
    "กรองสถานะ",
    list(STATUS_LABELS.keys()),
    format_func=lambda value: STATUS_LABELS[value],
)

late_filter = late_col.selectbox(
    "กรองใบเบิกเย็น",
    ["ทั้งหมด", "ใบเบิกเย็น", "ในเวลา Cut-off"],
)

search_text = search_col.text_input(
    "ค้นหา JOB หรือแผนก/ไลน์",
)

filtered = jobs.copy()

if status_filter and not filtered.empty:
    filtered = filtered[filtered["status"].isin(status_filter)]

if late_filter == "ใบเบิกเย็น" and not filtered.empty:
    filtered = filtered[
        filtered["received_time"].apply(
            lambda value: is_late(value, st.session_state.cutoff)
        )
    ]
elif late_filter == "ในเวลา Cut-off" and not filtered.empty:
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

display_rows = []

for _, row in filtered.iterrows():
    processing = duration_minutes(row["received_time"], row["picked_time"])
    waiting = duration_minutes(row["picked_time"], row["handover_time"])

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
            "เวลาจัด": duration_label(processing),
            "เวลารอ PD": duration_label(waiting),
            "ผู้สั่งยกเลิก": row["canceled_by"] or "—",
            "สาเหตุยกเลิก": row["cancel_reason"] or "—",
        }
    )

display_df = pd.DataFrame(
    display_rows,
    columns=[
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
    ],
)

if not has_data:
    st.warning("ยังไม่มีข้อมูลใบเบิก")

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    height=420,
)

if has_data:
    canceled_records = jobs[jobs["status"] == "cancelled"]

    if not canceled_records.empty:
        st.markdown("#### 📄 หลักฐานโต้แย้งรายการยกเลิก")

        for _, row in canceled_records.iterrows():
            work_start = row["in_progress_time"] or row["received_time"]
            wasted = duration_minutes(work_start, row["canceled_time"])
            title = (
                f"{row['job_number']} · {row['department']} · "
                f"ยกเลิก {format_timestamp(row['canceled_time'])}"
            )

            with st.expander(title):
                st.write(f"**รับเรื่อง:** {format_timestamp(row['received_time'])}")
                st.write(f"**เริ่มจัด:** {format_timestamp(row['in_progress_time'])}")
                st.write(f"**จัดเสร็จ:** {format_timestamp(row['picked_time'])}")
                st.write(f"**ยกเลิก:** {format_timestamp(row['canceled_time'])}")
                st.write(f"**เวลางานที่เสียไป:** {duration_label(wasted)}")
                st.write(f"**ผู้สั่งยกเลิก:** {row['canceled_by'] or '—'}")
                st.write(f"**สาเหตุ:** {row['cancel_reason'] or '—'}")

                st.button(
                    "🖨️ พิมพ์ / บันทึก PDF",
                    key=f"print_{row['id']}",
                    on_click=lambda: st.components.v1.html(
                        "<script>window.parent.print();</script>",
                        height=0,
                    ),
                )


csv_data = display_df.to_csv(index=False).encode("utf-8-sig")

st.download_button(
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

    st.download_button(
        "📊 Export Data to Excel",
        data=excel_buffer,
        file_name=f"warehouse_jobs_{date.today():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
except ImportError:
    st.caption("ติดตั้ง openpyxl เพื่อ Export Excel: pip install openpyxl")

st.caption(
    "Cut-off 16:00 น. • เวลาใช้ System Clock ของเครื่องที่รันแอป • "
    "Wasted Labor Duration คำนวณจากเวลาเริ่มจัด หรือเวลารับเรื่อง "
    "จนถึงเวลายกเลิก"
)
