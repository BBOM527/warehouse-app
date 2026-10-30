"""Warehouse Document Tracking & Bottleneck Analytics
Run: streamlit run app.py

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
DEFAULT_CUTOFF = time(16, 30)

STATUS_LABELS = {
    "received": "📥 รับเอกสาร",
    "in_progress": "🟡 กำลังจัด",
    "completed": "🔵 จัดเสร็จ / รอ PD รับ",
    "handed_over": "🟢 PD มารับแล้ว",
    "cancelled": "🔴 ยกเลิก",
}

TIMESTAMP_COLUMNS = {
    "in_progress": "in_progress_at",
    "completed": "completed_at",
    "handed_over": "handed_over_at",
    "cancelled": "cancelled_at",
}

# เลขที่เหล่านี้เป็นรายการตัวอย่างจากเวอร์ชันก่อน
# ลบข้อมูลจำลองชุดเดิมเพียงครั้งเดียว โดยไม่ลบใบเบิกจริงที่บันทึกภายหลัง
LEGACY_SAMPLE_NUMBERS = [f"WR-260{i:02d}" for i in range(1, 14)]
LEGACY_CLEANUP_KEY = "legacy_mock_rows_removed_v1"


def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """สร้างเฉพาะโครงสร้างตาราง และล้างข้อมูลจำลองเก่าที่เคยสร้างไว้"""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS requisitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requisition_no TEXT NOT NULL UNIQUE,
                department TEXT NOT NULL,
                requester TEXT NOT NULL,
                item_summary TEXT NOT NULL,
                received_at TEXT NOT NULL,
                in_progress_at TEXT,
                completed_at TEXT,
                handed_over_at TEXT,
                cancelled_at TEXT,
                cancellation_by TEXT,
                cancellation_reason TEXT,
                cancelled_labor_minutes REAL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'received',
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # รองรับฐานข้อมูลเดิมที่สร้างด้วยโค้ดรุ่นก่อน
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(requisitions)")
        }
        migrations = {
            "handed_over_at": "TEXT",
            "cancellation_by": "TEXT",
            "cancellation_reason": "TEXT",
            "cancelled_labor_minutes": "REAL DEFAULT 0",
        }

        for column, definition in migrations.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE requisitions ADD COLUMN {column} {definition}"
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
                f"""
                DELETE FROM requisitions
                WHERE requisition_no IN ({placeholders})
                """,
                LEGACY_SAMPLE_NUMBERS,
            )
            connection.execute(
                "INSERT INTO app_metadata (key, value) VALUES (?, ?)",
                (LEGACY_CLEANUP_KEY, "done"),
            )


def load_data():
    with get_connection() as connection:
        data = pd.read_sql_query(
            "SELECT * FROM requisitions ORDER BY received_at DESC, id DESC",
            connection,
        )

    for column in [
        "received_at",
        "in_progress_at",
        "completed_at",
        "handed_over_at",
        "cancelled_at",
    ]:
        data[column] = pd.to_datetime(data[column], errors="coerce")

    cutoff = st.session_state.cutoff
    data["late"] = data["received_at"].apply(
        lambda value: value.time() > cutoff if pd.notna(value) else False
    )
    data["processing_minutes"] = (
        data["completed_at"] - data["received_at"]
    ).dt.total_seconds() / 60
    data["waiting_minutes"] = (
        data["handed_over_at"] - data["completed_at"]
    ).dt.total_seconds() / 60
    data["status_label"] = data["status"].map(STATUS_LABELS)
    data["tag"] = data["late"].map(
        {
            True: "🔴 ใบเบิกเย็น/ส่งช้า",
            False: "🟢 ในเวลาตัดรอบ",
        }
    )

    return data


def add_requisition(number, department, requester, items, received_at, note):
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO requisitions (
                requisition_no, department, requester, item_summary,
                received_at, status, note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'received', ?, ?, ?)
            """,
            (
                number.strip(),
                department.strip(),
                requester.strip(),
                items.strip(),
                received_at.isoformat(timespec="minutes"),
                note.strip(),
                now,
                now,
            ),
        )


def update_status(
    record_id,
    status,
    event_at,
    note,
    cancellation_by="",
    cancellation_reason="",
    wasted_minutes=0,
):
    timestamp_column = TIMESTAMP_COLUMNS[status]
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection() as connection:
        connection.execute(
            f"""
            UPDATE requisitions
            SET status = ?,
                {timestamp_column} = ?,
                note = ?,
                cancellation_by = ?,
                cancellation_reason = ?,
                cancelled_labor_minutes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                event_at.isoformat(timespec="minutes"),
                note.strip(),
                cancellation_by.strip() or None,
                cancellation_reason.strip() or None,
                float(wasted_minutes or 0),
                now,
                record_id,
            ),
        )


# ---------------------------------------------------------------------
# Streamlit application
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="PK Warehouse | Document Flow",
    page_icon="📦",
    layout="wide",
)

if "cutoff" not in st.session_state:
    st.session_state.cutoff = DEFAULT_CUTOFF

initialize_database()

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Prompt', sans-serif;
    }

    .stApp {
        background:
            radial-gradient(ellipse at 8% 0%, rgba(78,153,165,.13), transparent 32%),
            radial-gradient(ellipse at 94% 7%, rgba(96,122,190,.12), transparent 30%),
            #f3f6fa;
    }

    .block-container {
        max-width: 1540px;
        padding-top: 1.3rem;
        padding-bottom: 2rem;
    }

    .hero {
        padding: 25px 30px;
        border: 1px solid rgba(255,255,255,.48);
        border-radius: 22px;
        color: #f9fbff;
        background: linear-gradient(115deg, #132b41, #1b6670);
        box-shadow: 0 18px 45px rgba(29,58,81,.17);
        margin-bottom: 20px;
    }

    .hero p {
        margin: 2px 0 0;
        color: #d6e6ef;
    }

    [data-testid="stMetric"] {
        background: rgba(255,255,255,.76);
        border: 1px solid rgba(255,255,255,.95);
        border-radius: 18px;
        padding: 16px 18px;
        box-shadow: 0 8px 24px rgba(26,48,71,.07);
        backdrop-filter: blur(12px);
    }

    [data-testid="stMetricValue"] {
        color: #172f46;
    }

    div.stButton > button,
    div.stFormSubmitButton > button,
    div.stDownloadButton > button {
        border-radius: 12px;
        transition: transform .12s ease, box-shadow .15s ease;
        box-shadow: 0 5px 14px rgba(28,73,103,.12);
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover,
    div.stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 9px 20px rgba(28,73,103,.2);
    }

    div.stButton > button:active,
    div.stFormSubmitButton > button:active,
    div.stDownloadButton > button:active {
        transform: scale(.98);
    }

    div[data-testid="stForm"] {
        background: rgba(255,255,255,.72);
        border: 1px solid rgba(255,255,255,.95);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 8px 26px rgba(26,48,71,.06);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #e5ebf1;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 8px 22px rgba(26,48,71,.06);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>📦 PK Warehouse · Document Flow</h1>
        <p>ติดตามทุกช่วงเวลา • จัดการคิวหน้างาน • บันทึกข้อมูลจากการทำงานจริง</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    st.session_state.cutoff = st.time_input(
        "Cut-off รับเอกสาร",
        value=st.session_state.cutoff,
        step=300,
        help="ใบเบิกที่เข้าหลังเวลานี้จะถูกติดแท็กใบเบิกเย็น",
    )
    st.caption(f"เวลาตัดรอบปัจจุบัน: **{st.session_state.cutoff:%H:%M} น.**")
    st.divider()
    st.markdown("**สีสถานะ**")
    st.markdown("🟡 กำลังจัด")
    st.markdown("🔵 จัดเสร็จ รอ PD")
    st.markdown("🟢 PD มารับแล้ว")
    st.markdown("🔴 ยกเลิก / ใบเบิกเย็น")

data = load_data()
has_data = not data.empty

if has_data:
    completed_data = data[data["completed_at"].notna()]
    handed_over_data = data[data["waiting_minutes"].notna()]
    cancelled_data = data[data["status"] == "cancelled"]

    late_percentage = data["late"].mean() * 100
    average_processing = (
        completed_data["processing_minutes"].mean()
        if not completed_data.empty
        else float("nan")
    )
    average_waiting = (
        handed_over_data["waiting_minutes"].mean()
        if not handed_over_data.empty
        else float("nan")
    )
    wasted_labor = data["cancelled_labor_minutes"].fillna(0).sum()
else:
    completed_data = data.copy()
    handed_over_data = data.copy()
    cancelled_data = data.copy()
    late_percentage = 0
    average_processing = float("nan")
    average_waiting = float("nan")
    wasted_labor = 0


# KPI cards
kpis = st.columns(5)
kpis[0].metric("📄 ยอดรวมใบเบิก", f"{len(data):,}")
kpis[1].metric("🔴 ใบเบิกเย็น", f"{late_percentage:.1f}%")
kpis[2].metric(
    "⏱️ เวลาจัดเฉลี่ย",
    f"{average_processing / 60:.1f} ชม."
    if pd.notna(average_processing)
    else "—",
)
kpis[3].metric(
    "🕒 เวลารอรับเฉลี่ย",
    f"{average_waiting:.0f} นาที"
    if pd.notna(average_waiting)
    else "—",
)
kpis[4].metric(
    "❌ ยกเลิก / แรงงานสูญเปล่า",
    f"{len(cancelled_data)} / {wasted_labor:.0f} นาที",
)

st.subheader("📊 Bottleneck Dashboard")

if not has_data:
    st.warning("ยังไม่มีข้อมูลใบเบิก")
else:
    chart_column, department_column = st.columns([1.25, 1])

    with chart_column:
        hourly = (
            data.assign(hour=data["received_at"].dt.hour)
            .groupby("hour")
            .size()
            .reindex(range(7, 22), fill_value=0)
            .rename("ใบเบิก")
            .reset_index()
        )
        hourly.columns = ["ชั่วโมง", "ใบเบิก"]
        hourly["ช่วง"] = hourly["ชั่วโมง"].apply(
            lambda hour: "🔴 หลัง Cut-off"
            if hour >= st.session_state.cutoff.hour
            else "🟢 ก่อน Cut-off"
        )

        chart = px.bar(
            hourly,
            x="ชั่วโมง",
            y="ใบเบิก",
            color="ช่วง",
            color_discrete_map={
                "🟢 ก่อน Cut-off": "#319783",
                "🔴 หลัง Cut-off": "#dc5962",
            },
            title="เวลาที่รับเอกสารรายชั่วโมง",
            text="ใบเบิก",
        )
        chart.update_layout(
            template="plotly_white",
            height=350,
            margin=dict(l=10, r=10, t=55, b=10),
            legend_title_text="",
            xaxis=dict(dtick=1, title="ชั่วโมงที่รับ"),
            yaxis_title="จำนวนใบเบิก",
            paper_bgcolor="rgba(255,255,255,0)",
            plot_bgcolor="rgba(255,255,255,0)",
        )
        chart.update_traces(textposition="outside")
        st.plotly_chart(chart, use_container_width=True)

    with department_column:
        summary = (
            data.groupby("department")
            .agg(total=("id", "count"), late_count=("late", "sum"))
            .reset_index()
        )
        summary["late_percentage"] = (
            summary["late_count"] / summary["total"] * 100
        )
        summary = summary.sort_values("late_percentage", ascending=True)

        department_chart = px.bar(
            summary,
            x="late_percentage",
            y="department",
            orientation="h",
            text=summary["late_percentage"].map(lambda value: f"{value:.0f}%"),
            title="สัดส่วนใบเบิกเย็นแยกตามแผนก/ไลน์",
            labels={
                "late_percentage": "ใบเบิกเย็น (%)",
                "department": "แผนก/ไลน์",
            },
            color="late_percentage",
            color_continuous_scale=["#66b99d", "#f0bd58", "#d9535d"],
        )
        department_chart.update_layout(
            template="plotly_white",
            height=350,
            margin=dict(l=10, r=10, t=55, b=10),
            coloraxis_showscale=False,
            paper_bgcolor="rgba(255,255,255,0)",
            plot_bgcolor="rgba(255,255,255,0)",
        )
        department_chart.update_xaxes(range=[0, 100])
        st.plotly_chart(department_chart, use_container_width=True)

    st.info(
        f"📌 มีใบเบิกหลัง Cut-off {st.session_state.cutoff:%H:%M} น. "
        f"**{int(data['late'].sum())} รายการ ({late_percentage:.1f}%)** "
        f"และมีเวลางานสูญเปล่าจากรายการยกเลิกรวม **{wasted_labor:.0f} นาที**"
    )


# ---------------------------------------------------------------------
# New requisition form
# ---------------------------------------------------------------------

new_column, update_column = st.columns([1, 1.3])

with new_column:
    st.subheader("➕ รับใบเบิกใหม่")

    with st.form("new_requisition", clear_on_submit=True):
        requisition_no = st.text_input(
            "เลขที่ใบเบิก *",
            placeholder="ระบุเลขที่ใบเบิก",
        )
        department = st.text_input(
            "แผนก / ไลน์ผลิต *",
            placeholder="ระบุแผนกหรือไลน์",
        )
        requester = st.text_input("ชื่อผู้เบิก PN/PD *")
        item_summary = st.text_area("รายการสินค้า *", height=75)

        date_column, time_column = st.columns(2)
        received_date = date_column.date_input("วันที่รับ", value=date.today())
        received_time = time_column.time_input(
            "เวลารับเอกสาร",
            value=datetime.now().time().replace(second=0, microsecond=0),
            step=300,
        )

        note = st.text_input("หมายเหตุ")
        submit_new = st.form_submit_button(
            "📥 รับใบเบิก",
            use_container_width=True,
            type="primary",
        )

        if submit_new:
            required = [
                requisition_no.strip(),
                department.strip(),
                requester.strip(),
                item_summary.strip(),
            ]

            if not all(required):
                st.error("กรุณากรอกข้อมูลที่มี * ให้ครบ")
            else:
                try:
                    add_requisition(
                        requisition_no,
                        department,
                        requester,
                        item_summary,
                        datetime.combine(received_date, received_time),
                        note,
                    )
                    st.success("รับใบเบิกเรียบร้อยแล้ว")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("เลขที่ใบเบิกนี้มีอยู่แล้ว")


# ---------------------------------------------------------------------
# Update status
# ---------------------------------------------------------------------

with update_column:
    st.subheader("🔄 อัปเดตสถานะงาน")

    open_data = data[
        ~data["status"].isin(["handed_over", "cancelled"])
    ]

    if open_data.empty:
        st.info(
            "ยังไม่มีรายการสำหรับอัปเดตสถานะ"
            if not has_data
            else "ไม่มีรายการที่รออัปเดต"
        )
    else:
        record_options = {
            f"{row.requisition_no} · {row.department} · {row.status_label}": int(row.id)
            for row in open_data.itertuples()
        }
        selected_label = st.selectbox("เลือกใบเบิก", list(record_options))
        selected_row = data[
            data["id"] == record_options[selected_label]
        ].iloc[0]

        # วางตัวเลือกสถานะนอก form เพื่อให้ฟอร์มยกเลิกแสดงทันทีเมื่อเลือก
        new_status = st.selectbox(
            "สถานะใหม่",
            ["in_progress", "completed", "handed_over", "cancelled"],
            format_func=lambda value: STATUS_LABELS[value],
        )

        with st.form("status_update"):
            date_column, time_column = st.columns(2)
            event_date = date_column.date_input(
                "วันที่เกิดสถานะ",
                value=date.today(),
                key="event_date",
            )
            event_time = time_column.time_input(
                "เวลาที่เกิดสถานะ",
                value=datetime.now().time().replace(second=0, microsecond=0),
                step=300,
                key="event_time",
            )

            cancellation_by = ""
            cancellation_reason = ""
            wasted_minutes = 0.0

            if new_status == "cancelled":
                st.warning("การยกเลิกต้องระบุผู้สั่งยกเลิกและสาเหตุ")
                cancellation_by = st.text_input(
                    "ผู้สั่งยกเลิก PN/PD *",
                    placeholder="ระบุ PN/PD หรือชื่อผู้แจ้ง",
                )
                cancellation_reason = st.text_area(
                    "สาเหตุการยกเลิก *",
                    placeholder="ระบุสาเหตุ",
                    height=70,
                )
                wasted_minutes = st.number_input(
                    "เวลางานคลังที่สูญเปล่า (นาที) *",
                    min_value=0.0,
                    step=5.0,
                    value=0.0,
                )

            update_note = st.text_input(
                "หมายเหตุเพิ่มเติม",
                value=str(selected_row["note"] or ""),
            )
            submit_update = st.form_submit_button(
                "บันทึกสถานะ",
                use_container_width=True,
                type="primary",
            )

            if submit_update:
                event_at = datetime.combine(event_date, event_time)
                received_at = selected_row["received_at"].to_pydatetime()

                if event_at < received_at:
                    st.error("เวลาสถานะต้องไม่ก่อนเวลารับเอกสาร")
                elif (
                    new_status == "handed_over"
                    and pd.notna(selected_row["completed_at"])
                    and event_at < selected_row["completed_at"].to_pydatetime()
                ):
                    st.error("เวลา PD มารับต้องไม่ก่อนเวลาจัดเสร็จ")
                elif new_status == "cancelled" and (
                    not cancellation_by.strip()
                    or not cancellation_reason.strip()
                    or wasted_minutes <= 0
                ):
                    st.error(
                        "กรุณาระบุผู้สั่งยกเลิก สาเหตุ "
                        "และเวลางานที่สูญเปล่าให้ครบ"
                    )
                else:
                    update_status(
                        int(selected_row["id"]),
                        new_status,
                        event_at,
                        update_note,
                        cancellation_by,
                        cancellation_reason,
                        wasted_minutes,
                    )
                    st.success("อัปเดตสถานะเรียบร้อยแล้ว")
                    st.rerun()


# ---------------------------------------------------------------------
# Web Audio API tick sound
# ---------------------------------------------------------------------

st.components.v1.html(
    """
    <script>
    (() => {
      const parentWindow = window.parent;

      if (parentWindow.__warehouseTickInstalled) return;
      parentWindow.__warehouseTickInstalled = true;

      parentWindow.playWarehouseTick = function () {
        try {
          const AudioContext =
            parentWindow.AudioContext ||
            parentWindow.webkitAudioContext;

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
          // ถ้าเบราว์เซอร์ปิดเสียงไว้ แอปยังทำงานได้ตามปกติ
        }
      };

      parentWindow.document.addEventListener(
        "click",
        (event) => {
          const button = event.target.closest("button");
          if (!button) return;

          const label = (button.innerText || "").trim();
          const isAction =
            label.includes("รับใบเบิก") ||
            label.includes("บันทึกสถานะ") ||
            label.includes("Export");

          if (isAction && parentWindow.playWarehouseTick) {
            parentWindow.playWarehouseTick();
          }
        },
        true
      );
    })();
    </script>
    """,
    height=0,
    width=0,
)


# ---------------------------------------------------------------------
# Filterable table and export
# ---------------------------------------------------------------------

st.divider()
st.subheader("📋 ทะเบียนใบเบิก")

filter1, filter2, filter3 = st.columns([1, 1, 1.4])

status_filter = filter1.multiselect(
    "กรองสถานะ",
    list(STATUS_LABELS),
    format_func=lambda value: STATUS_LABELS[value],
)
tag_filter = filter2.selectbox(
    "กรองใบเบิกเย็น",
    ["ทั้งหมด", "🔴 ใบเบิกเย็น", "🟢 ในเวลาตัดรอบ"],
)
search = filter3.text_input(
    "ค้นหาเลขที่ / แผนก / ผู้เบิก / รายการ",
    placeholder="พิมพ์คำค้นหา",
)

filtered = data.copy()

if status_filter:
    filtered = filtered[filtered["status"].isin(status_filter)]

if tag_filter == "🔴 ใบเบิกเย็น":
    filtered = filtered[filtered["late"]]
elif tag_filter == "🟢 ในเวลาตัดรอบ":
    filtered = filtered[~filtered["late"]]

if search.strip():
    search_columns = [
        "requisition_no",
        "department",
        "requester",
        "item_summary",
        "cancellation_by",
        "cancellation_reason",
    ]
    search_mask = (
        filtered[search_columns]
        .fillna("")
        .astype(str)
        .apply(
            lambda column: column.str.contains(
                search.strip(),
                case=False,
                regex=False,
            )
        )
        .any(axis=1)
    )
    filtered = filtered[search_mask]

display_columns = [
    "requisition_no",
    "department",
    "requester",
    "item_summary",
    "received_at",
    "in_progress_at",
    "completed_at",
    "handed_over_at",
    "cancelled_at",
    "status_label",
    "tag",
    "processing_minutes",
    "waiting_minutes",
    "cancellation_by",
    "cancellation_reason",
    "cancelled_labor_minutes",
    "note",
]

table = filtered[display_columns].copy()
table.columns = [
    "เลขที่ใบเบิก",
    "แผนก/ไลน์",
    "ผู้เบิก",
    "รายการ",
    "📥 รับเอกสาร",
    "🟡 เริ่มจัด",
    "🔵 จัดเสร็จ",
    "🟢 PD รับของ",
    "❌ ยกเลิกเมื่อ",
    "สถานะ",
    "แท็ก",
    "เวลาจัด (นาที)",
    "เวลารอ PD (นาที)",
    "ผู้สั่งยกเลิก",
    "สาเหตุยกเลิก",
    "แรงงานสูญเปล่า (นาที)",
    "หมายเหตุ",
]

for column in [
    "📥 รับเอกสาร",
    "🟡 เริ่มจัด",
    "🔵 จัดเสร็จ",
    "🟢 PD รับของ",
    "❌ ยกเลิกเมื่อ",
]:
    table[column] = (
        pd.to_datetime(table[column], errors="coerce")
        .dt.strftime("%d/%m/%Y %H:%M")
        .fillna("—")
    )

for column in [
    "เวลาจัด (นาที)",
    "เวลารอ PD (นาที)",
    "แรงงานสูญเปล่า (นาที)",
]:
    table[column] = table[column].round(0).astype("Int64")

if not has_data:
    st.warning("ยังไม่มีข้อมูลใบเบิก")

st.caption(f"แสดง {len(table):,} จาก {len(data):,} รายการ")
st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
    height=440,
)

csv_data = table.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "📥 Export Data to CSV",
    data=csv_data,
    file_name=f"warehouse_tracking_{date.today():%Y%m%d}.csv",
    mime="text/csv",
    use_container_width=True,
)

try:
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        table.to_excel(
            writer,
            index=False,
            sheet_name="Warehouse Tracking",
        )
    excel_buffer.seek(0)

    st.download_button(
        "📊 Export Data to Excel",
        data=excel_buffer,
        file_name=f"warehouse_tracking_{date.today():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
except ImportError:
    st.caption("ติดตั้ง openpyxl เพื่อเปิดใช้ Export Excel: pip install openpyxl")

st.caption(
    "Processing Lead Time = รับเอกสารถึงจัดเสร็จ • "
    "Waiting Time = จัดเสร็จถึง PD มารับ • "
    "Wasted Labor Time = เวลาที่คลังทำงานไปก่อนใบเบิกถูกยกเลิก"
)
