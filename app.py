"""Warehouse document tracking & bottleneck analytics.
Run: streamlit run warehouse_document_tracking.py
"""
from datetime import date, datetime, time, timedelta
from pathlib import Path
import os
import sqlite3

import pandas as pd
import streamlit as st


DB_PATH = Path(
    os.getenv(
        "WAREHOUSE_DB",
        str(Path(__file__).resolve().with_name("warehouse_tracking.db")),
    )
)
DEFAULT_CUTOFF = time(16, 30)

STATUSES = {
    "received": "📥 รับเอกสาร",
    "in_progress": "📦 กำลังจัด",
    "completed": "✅ จัดเสร็จแล้ว",
    "returned": "🔄 รับคืนเอกสาร",
    "cancelled": "❌ เอกสารถูกยกเลิก",
}


def get_connection():
    """เปิดการเชื่อมต่อ SQLite"""
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def seed_mock_data(connection):
    """เพิ่มข้อมูลจำลองตัวอย่างสำหรับแสดงผลครั้งแรก"""
    samples = [
        ("WR-26001", "ผลิต", "สมชาย", "น็อต M8, แหวนรอง", 8, 12, "completed", 9, 5, "ส่งตามรอบเช้า"),
        ("WR-26002", "ซ่อมบำรุง", "วิภา", "น้ำมันหล่อลื่น", 9, 35, "completed", 10, 42, ""),
        ("WR-26003", "ผลิต", "อนันต์", "กล่องบรรจุภัณฑ์", 10, 48, "completed", 12, 20, ""),
        ("WR-26004", "คุณภาพ", "มาลี", "ถุงมือไนไตร", 13, 10, "completed", 14, 2, ""),
        ("WR-26005", "ผลิต", "สมชาย", "อะไหล่สายพาน", 15, 55, "in_progress", None, None, "เร่งด่วน ต้องใช้พรุ่งนี้เช้า"),
        ("WR-26006", "ซ่อมบำรุง", "ปรีชา", "ลูกปืน 6204", 16, 42, "received", None, None, "รับหลัง cut-off"),
        ("WR-26007", "ผลิต", "วิภา", "เทปกาว, ฟิล์มยืด", 17, 18, "completed", 18, 16, "รับหลัง cut-off"),
        ("WR-26008", "คลังสินค้า", "กิตติ", "ป้ายฉลาก", 14, 25, "returned", None, None, "คืนเอกสารเพื่อแก้ไข"),
        ("WR-26009", "ผลิต", "มาลี", "ถังพลาสติก", 11, 20, "cancelled", None, None, "ยกเลิกรายการ"),
        ("WR-26010", "คุณภาพ", "อนันต์", "อุปกรณ์ตรวจวัด", 16, 55, "completed", 18, 5, "รับหลัง cut-off"),
        ("WR-26011", "ผลิต", "ปรีชา", "วัตถุดิบ A-12", 8, 50, "completed", 10, 10, ""),
        ("WR-26012", "ซ่อมบำรุง", "กิตติ", "ซีลยาง", 15, 5, "completed", 16, 25, ""),
    ]

    now = datetime.now().isoformat(timespec="seconds")
    today = date.today()

    for index, sample in enumerate(samples):
        (
            number,
            department,
            requester,
            items,
            hour,
            minute,
            status,
            completed_hour,
            completed_minute,
            note,
        ) = sample

        sample_date = today - timedelta(days=index % 6)
        received_at = datetime.combine(sample_date, time(hour, minute))

        started_at = None
        if status in ("in_progress", "completed"):
            started_at = received_at + timedelta(minutes=20 + index * 5)

        completed_at = None
        if completed_hour is not None:
            completed_at = datetime.combine(
                sample_date,
                time(completed_hour, completed_minute),
            )

        returned_at = None
        if status == "returned":
            returned_at = received_at + timedelta(minutes=75)

        cancelled_at = None
        if status == "cancelled":
            cancelled_at = received_at + timedelta(minutes=22)

        connection.execute(
            """
            INSERT INTO requisitions (
                requisition_no, department, requester, item_summary,
                received_at, in_progress_at, completed_at, returned_at,
                cancelled_at, status, note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                number,
                department,
                requester,
                items,
                received_at.isoformat(timespec="minutes"),
                started_at.isoformat(timespec="minutes") if started_at else None,
                completed_at.isoformat(timespec="minutes") if completed_at else None,
                returned_at.isoformat(timespec="minutes") if returned_at else None,
                cancelled_at.isoformat(timespec="minutes") if cancelled_at else None,
                status,
                note,
                now,
                now,
            ),
        )


def initialize_database():
    """สร้างตารางและ mock data เมื่อฐานข้อมูลยังว่าง"""
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
                returned_at TEXT,
                cancelled_at TEXT,
                status TEXT NOT NULL DEFAULT 'received',
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        count = connection.execute(
            "SELECT COUNT(*) FROM requisitions"
        ).fetchone()[0]

        if count == 0:
            seed_mock_data(connection)


def load_data():
    """โหลดข้อมูลและคำนวณแท็กกับ Lead Time"""
    with get_connection() as connection:
        data = pd.read_sql_query(
            "SELECT * FROM requisitions ORDER BY received_at DESC, id DESC",
            connection,
        )

    datetime_columns = [
        "received_at",
        "in_progress_at",
        "completed_at",
        "returned_at",
        "cancelled_at",
    ]

    for column in datetime_columns:
        data[column] = pd.to_datetime(data[column], errors="coerce")

    cutoff = st.session_state.cutoff

    data["late"] = data["received_at"].apply(
        lambda value: value.time() > cutoff if pd.notna(value) else False
    )
    data["lead_minutes"] = (
        data["completed_at"] - data["received_at"]
    ).dt.total_seconds() / 60
    data["status_label"] = data["status"].map(STATUSES)
    data["tag"] = data["late"].map(
        {
            True: "🔴 ใบเบิกเย็น/ส่งช้า",
            False: "🟢 ในเวลาตัดรอบ",
        }
    )

    return data


def add_requisition(number, department, requester, items, received_at, note):
    """บันทึกใบเบิกใหม่"""
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


def update_status(record_id, status, event_at, note):
    """อัปเดตสถานะและเวลาในขั้นตอนที่เลือก"""
    timestamp_columns = {
        "in_progress": "in_progress_at",
        "completed": "completed_at",
        "returned": "returned_at",
        "cancelled": "cancelled_at",
    }

    timestamp_column = timestamp_columns[status]
    now = datetime.now().isoformat(timespec="seconds")

    # ชื่อ column มาจาก dictionary ที่กำหนดไว้ในโค้ดเท่านั้น
    with get_connection() as connection:
        connection.execute(
            f"""
            UPDATE requisitions
            SET status = ?, {timestamp_column} = ?, note = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                event_at.isoformat(timespec="minutes"),
                note.strip(),
                now,
                record_id,
            ),
        )


# ---------------------------------------------------------------------
# Streamlit application
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="Warehouse Document Tracking",
    page_icon="📦",
    layout="wide",
)

if "cutoff" not in st.session_state:
    st.session_state.cutoff = DEFAULT_CUTOFF

initialize_database()

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.3rem;
        padding-bottom: 2.5rem;
        max-width: 1500px;
    }
    [data-testid="stMetric"] {
        background: #f1f7fb;
        border: 1px solid #dce8ef;
        padding: 15px;
        border-radius: 14px;
    }
    .hero {
        padding: 20px 25px;
        border-radius: 18px;
        color: white;
        background: linear-gradient(110deg, #12304a, #146c72);
        margin-bottom: 18px;
    }
    .hero p {
        margin: 0;
        opacity: .85;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>📦 Warehouse Document Tracking</h1>
        <p>บันทึกเวลาทุกขั้นตอน • มองเห็นใบเบิกหลัง Cut-off • วิเคราะห์คอขวดคลังสินค้า</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    st.session_state.cutoff = st.time_input(
        "เวลา Cut-off",
        value=st.session_state.cutoff,
        step=300,
        help="ใบเบิกที่รับหลังเวลานี้จะติดแท็กใบเบิกเย็น",
    )
    st.caption(f"ตัดรอบเวลา {st.session_state.cutoff:%H:%M} น.")
    st.divider()
    st.markdown("**5 สถานะเอกสาร**")

    for status_label in STATUSES.values():
        st.caption(status_label)

    st.divider()
    st.caption("บันทึกข้อมูลใน SQLite บนเครื่องที่รันแอป")


data = load_data()
completed_data = data[data["completed_at"].notna()]

late_percentage = data["late"].mean() * 100 if len(data) else 0
average_lead = (
    completed_data["lead_minutes"].mean()
    if not completed_data.empty
    else float("nan")
)

average_display = (
    f"{average_lead / 60:.1f} ชม."
    if pd.notna(average_lead)
    else "—"
)

metric1, metric2, metric3 = st.columns(3)
metric1.metric("📄 เอกสารทั้งหมด", f"{len(data):,}")
metric2.metric("🔴 ใบเบิกเย็น", f"{late_percentage:.1f}%")
metric3.metric(
    "⏱️ เวลาจัดเฉลี่ย",
    average_display,
    help="เวลาตั้งแต่รับเอกสารจนจัดเสร็จ เฉพาะรายการที่เสร็จแล้ว",
)

st.subheader("📊 ภาพรวมคอขวด")

chart_column, insight_column = st.columns([1.7, 1])

with chart_column:
    hourly_arrivals = (
        data.assign(hour=data["received_at"].dt.hour)
        .groupby("hour")
        .size()
        .reindex(range(7, 21), fill_value=0)
    )

    chart_data = pd.DataFrame(
        {
            "จำนวนใบเบิก": hourly_arrivals,
            "หลัง Cut-off": [
                count if hour >= st.session_state.cutoff.hour else 0
                for hour, count in hourly_arrivals.items()
            ],
        }
    )
    chart_data.index = [f"{hour:02d}:00" for hour in chart_data.index]

    st.bar_chart(
        chart_data,
        color=["#2e8b83", "#ed6a5a"],
        height=300,
    )
    st.caption(
        "จำนวนใบเบิกตามชั่วโมงรับเข้า • สีแดงคือเวลาตั้งแต่ Cut-off เป็นต้นไป"
    )

with insight_column:
    st.markdown("#### 🔎 ประเด็นจากข้อมูล")
    st.info(
        f"รับหลัง {st.session_state.cutoff:%H:%M} น. "
        f"**{int(data['late'].sum())} รายการ ({late_percentage:.1f}%)** "
        f"จากทั้งหมด {len(data)} รายการ"
    )

    late_completed = completed_data[completed_data["late"]]
    if not late_completed.empty:
        late_average = late_completed["lead_minutes"].mean()
        st.warning(
            f"ใบเบิกเย็นที่เสร็จแล้วใช้เวลาเฉลี่ย "
            f"**{late_average / 60:.1f} ชม.**"
        )

    st.caption("*ข้อมูลจำลองเริ่มต้น โปรดบันทึกข้อมูลจริงเมื่อเริ่มใช้งาน")


# ฟอร์มสร้างใบเบิก และฟอร์มอัปเดตสถานะ
new_column, update_column = st.columns([1, 1.35])

with new_column:
    st.subheader("➕ รับใบเบิกใหม่")

    with st.form("new_requisition", clear_on_submit=True):
        requisition_no = st.text_input(
            "เลขที่ใบเบิก *",
            placeholder="เช่น WR-26013",
        )
        department = st.text_input("แผนกผู้เบิก *")
        requester = st.text_input("ชื่อผู้เบิก *")
        item_summary = st.text_area("รายการสินค้า *", height=75)

        date_column, time_column = st.columns(2)
        received_date = date_column.date_input(
            "วันที่รับ",
            value=date.today(),
        )
        received_time = time_column.time_input(
            "เวลารับ",
            value=datetime.now().time().replace(second=0, microsecond=0),
            step=300,
        )

        note = st.text_input("หมายเหตุ")
        submitted = st.form_submit_button(
            "📥 บันทึกใบเบิก",
            use_container_width=True,
            type="primary",
        )

        if submitted:
            required_values = [
                requisition_no.strip(),
                department.strip(),
                requester.strip(),
                item_summary.strip(),
            ]

            if not all(required_values):
                st.error("กรุณากรอกช่องที่มี * ให้ครบ")
            else:
                received_at = datetime.combine(received_date, received_time)

                try:
                    add_requisition(
                        requisition_no,
                        department,
                        requester,
                        item_summary,
                        received_at,
                        note,
                    )
                    st.success("บันทึกใบเบิกแล้ว")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("เลขที่ใบเบิกนี้มีอยู่แล้ว กรุณาตรวจสอบเลขที่")


with update_column:
    st.subheader("🔄 อัปเดตสถานะและเวลา")

    active_data = data[
        ~data["status"].isin(["completed", "cancelled"])
    ].copy()

    if active_data.empty:
        st.info("ไม่มีรายการที่ต้องอัปเดต")
    else:
        options = {
            f"{row.requisition_no} · {row.department} · {row.status_label}": int(row.id)
            for row in active_data.itertuples()
        }

        selected_label = st.selectbox("เลือกใบเบิก", list(options))
        selected_row = data[data["id"] == options[selected_label]].iloc[0]

        with st.form("update_status"):
            new_status = st.selectbox(
                "สถานะใหม่",
                ["in_progress", "completed", "returned", "cancelled"],
                format_func=lambda value: STATUSES[value],
            )

            event_date_column, event_time_column = st.columns(2)
            event_date = event_date_column.date_input(
                "วันที่เกิดสถานะ",
                value=date.today(),
                key="event_date",
            )
            event_time = event_time_column.time_input(
                "เวลาที่เกิดสถานะ",
                value=datetime.now().time().replace(second=0, microsecond=0),
                step=300,
                key="event_time",
            )

            updated_note = st.text_input(
                "หมายเหตุ",
                value=str(selected_row["note"] or ""),
                key="updated_note",
            )

            save_status = st.form_submit_button(
                "บันทึกสถานะและเวลา",
                use_container_width=True,
                type="primary",
            )

            if save_status:
                event_at = datetime.combine(event_date, event_time)

                if event_at < selected_row["received_at"].to_pydatetime():
                    st.error("เวลาสถานะต้องไม่ก่อนเวลารับเอกสาร")
                else:
                    update_status(
                        int(selected_row["id"]),
                        new_status,
                        event_at,
                        updated_note,
                    )
                    st.success("อัปเดตสถานะแล้ว")
                    st.rerun()


# ตารางรายการและตัวกรอง
st.divider()
st.subheader("📋 รายการเอกสาร")

filter1, filter2, filter3 = st.columns([1, 1, 1.3])

status_filter = filter1.multiselect(
    "กรองสถานะ",
    list(STATUSES),
    format_func=lambda value: STATUSES[value],
)
late_filter = filter2.selectbox(
    "กรองแท็ก",
    ["ทั้งหมด", "🔴 ใบเบิกเย็น", "🟢 ในเวลาตัดรอบ"],
)
search_text = filter3.text_input(
    "ค้นหาเลขที่ / แผนก / ผู้เบิก / รายการ"
)

filtered_data = data.copy()

if status_filter:
    filtered_data = filtered_data[
        filtered_data["status"].isin(status_filter)
    ]

if late_filter == "🔴 ใบเบิกเย็น":
    filtered_data = filtered_data[filtered_data["late"]]
elif late_filter == "🟢 ในเวลาตัดรอบ":
    filtered_data = filtered_data[~filtered_data["late"]]

if search_text.strip():
    searchable_columns = [
        "requisition_no",
        "department",
        "requester",
        "item_summary",
    ]
    matches = (
        filtered_data[searchable_columns]
        .fillna("")
        .astype(str)
        .apply(
            lambda column: column.str.contains(
                search_text.strip(),
                case=False,
                regex=False,
            )
        )
        .any(axis=1)
    )
    filtered_data = filtered_data[matches]

display_columns = [
    "requisition_no",
    "department",
    "requester",
    "item_summary",
    "received_at",
    "in_progress_at",
    "completed_at",
    "returned_at",
    "cancelled_at",
    "status_label",
    "tag",
    "lead_minutes",
    "note",
]

table = filtered_data[display_columns].copy()
table.columns = [
    "เลขที่ใบเบิก",
    "แผนก",
    "ผู้เบิก",
    "รายการ",
    "📥 รับเอกสาร",
    "📦 กำลังจัด",
    "✅ จัดเสร็จ",
    "🔄 รับคืน",
    "❌ ยกเลิก",
    "สถานะ",
    "แท็ก",
    "Lead time (นาที)",
    "หมายเหตุ",
]

timestamp_columns = [
    "📥 รับเอกสาร",
    "📦 กำลังจัด",
    "✅ จัดเสร็จ",
    "🔄 รับคืน",
    "❌ ยกเลิก",
]

for column in timestamp_columns:
    table[column] = (
        pd.to_datetime(table[column], errors="coerce")
        .dt.strftime("%d/%m/%Y %H:%M")
        .fillna("—")
    )

table["Lead time (นาที)"] = table["Lead time (นาที)"].round().astype("Int64")

st.caption(f"แสดง {len(table)} จาก {len(data)} รายการ")

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
    height=410,
    column_config={
        "แท็ก": st.column_config.TextColumn(
            help="คำนวณจากเวลารับเอกสารเทียบกับ Cut-off"
        ),
        "Lead time (นาที)": st.column_config.NumberColumn(
            format="%d นาที"
        ),
    },
)

st.download_button(
    "⬇️ ดาวน์โหลดรายการเป็น CSV",
    data=table.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"warehouse_requisitions_{date.today():%Y%m%d}.csv",
    mime="text/csv",
)

st.caption(
    "เวลาจัดคำนวณจากรับเอกสารจนจัดเสร็จ • ใช้เวลาท้องถิ่นของเครื่องที่รันแอป "
    "• หากบันทึกสถานะเดิมซ้ำ ระบบใช้เวลาล่าสุด"
)

   
