from io import BytesIO
from datetime import datetime, timezone, timedelta, time
import sqlite3

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st
import streamlit.components.v1 as components


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

# แผนกที่แสดงในฟอร์ม เรียงตามลำดับการใช้งาน
DEPARTMENTS = [
    "PD",
    "แอดมินPD",
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

    :root {
        --ink: #172033;
        --muted: #64748b;
        --line: #e2e8f0;
        --surface: #ffffff;
        --canvas: #f8fafc;
    }

    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family: 'Kanit', sans-serif;
        color: var(--ink);
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(ellipse at 4% 0%, rgba(14,165,233,.07), transparent 32%),
            radial-gradient(ellipse at 96% 5%, rgba(16,185,129,.07), transparent 28%),
            var(--canvas);
    }

    [data-testid="stHeader"] { background: rgba(248,250,252,.78); }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #101827 0%, #172033 100%);
        border-right: 1px solid rgba(255,255,255,.08);
    }
    [data-testid="stSidebar"] * { color: #e2e8f0; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { padding: .32rem 0; }

    h1, h2, h3 { letter-spacing: -.02em; }
    h1 { font-weight: 600; }

    [data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,.05);
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--ink); font-weight: 600; }

    [data-testid="stForm"], [data-testid="stExpander"],
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border: 1px solid var(--line);
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,.05);
        overflow: hidden;
        background: var(--surface);
    }
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stTimeInput"] input,
    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stTextArea"] textarea {
        border-radius: 12px;
    }

    [data-testid="stButton"] button,
    [data-testid="stFormSubmitButton"] button,
    [data-testid="stDownloadButton"] button {
        border-radius: 12px;
        font-family: 'Kanit', sans-serif;
        font-weight: 500;
        transition: transform .18s ease, box-shadow .18s ease, filter .18s ease;
    }
    [data-testid="stFormSubmitButton"] button,
    [data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(115deg, #059669, #0284c7);
        color: white;
        border: 0;
        box-shadow: 0 7px 18px rgba(2,132,199,.2);
    }
    [data-testid="stButton"] button:hover,
    [data-testid="stFormSubmitButton"] button:hover,
    [data-testid="stDownloadButton"] button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 22px rgba(15,23,42,.12);
        filter: brightness(1.03);
    }
    [data-testid="stButton"] button:active,
    [data-testid="stFormSubmitButton"] button:active { transform: scale(.98); }

    .page-heading {
        display:flex; align-items:flex-end; justify-content:space-between;
        gap:1rem; margin:.25rem 0 1.2rem;
    }
    .page-heading h1 { margin:0; }
    .eyebrow {
        color:#0284c7; text-transform:uppercase; letter-spacing:.12em;
        font-size:.76rem; font-weight:600;
    }
    .subtle { color:var(--muted); }
    .clock-card {
        display:flex; justify-content:space-between; align-items:center;
        gap:1rem; background:rgba(255,255,255,.88);
        border:1px solid var(--line); border-radius:16px;
        padding:12px 18px; margin:0 0 1.2rem;
        box-shadow:0 10px 30px rgba(0,0,0,.05);
    }
    .clock-time { font-size:1.15rem; font-weight:600; color:#0f766e; }
    .clock-date { color:var(--muted); font-size:.9rem; }
    .section-card {
        background:var(--surface); border:1px solid var(--line);
        border-radius:16px; padding:18px 20px;
        box-shadow:0 10px 30px rgba(0,0,0,.05); margin-bottom:1rem;
    }
    .login-wrap {
        max-width:480px; margin:8vh auto 0; padding:2rem;
        background:#fff; border:1px solid var(--line); border-radius:20px;
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
        if parsed.tzinfo is None:
            return BANGKOK.localize(parsed)
        return parsed.astimezone(BANGKOK)
    except (TypeError, ValueError, OverflowError):
        return None


def stamp(value):
    local_value = as_bangkok(value)
    return local_value.isoformat() if local_value else None


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
    hours, remaining = divmod(minutes, 60)
    return f"{hours} ชม. {remaining} นาที" if hours else f"{remaining} นาที"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS requisitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_number TEXT NOT NULL,
                department TEXT NOT NULL DEFAULT '',
                production_line TEXT NOT NULL DEFAULT '',
                item_name TEXT NOT NULL DEFAULT '',
                quantity REAL,
                received_at TEXT NOT NULL,
                started_at TEXT,
                picked_at TEXT,
                handover_at TEXT,
                cancelled_at TEXT,
                cancelled_by TEXT,
                cancel_reason TEXT,
                status TEXT NOT NULL DEFAULT 'กำลังจัด',
                created_by TEXT NOT NULL DEFAULT 'Admin',
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def load_data():
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM requisitions ORDER BY received_at DESC, id DESC", conn
        )

    if not df.empty:
        datetime_columns = [
            "received_at", "started_at", "picked_at",
            "handover_at", "cancelled_at", "updated_at",
        ]
        for column in datetime_columns:
            if column in df.columns:
                df[column] = pd.to_datetime(
                    df[column], errors="coerce", utc=True
                ).dt.tz_convert("Asia/Bangkok")

        df["processing_minutes"] = df.apply(
            lambda row: duration_minutes(row.get("received_at"), row.get("picked_at")),
            axis=1,
        )
        df["waiting_minutes"] = df.apply(
            lambda row: duration_minutes(row.get("picked_at"), row.get("handover_at")),
            axis=1,
        )
        df["late"] = df["received_at"].apply(
            lambda value: bool(
                pd.notna(value)
                and (value.hour, value.minute, value.second)
                > (CUTOFF_TIME.hour, CUTOFF_TIME.minute, 0)
            )
        )
    return df


def insert_requisition(job_number, department, line, item_name, quantity, received_at):
    # บังคับมีไลน์เมื่อแผนกเป็น PD และไม่บันทึกไลน์ให้แผนกอื่น
    if department == "PD" and line not in PRODUCTION_LINES:
        return False, f"กรุณาเลือกไลน์ผลิต L1-L10 สำหรับ JOB {job_number}"
    if department != "PD":
        line = ""

    with sqlite3.connect(DB_PATH) as conn:
        exists = conn.execute(
            "SELECT 1 FROM requisitions WHERE job_number=? AND status!='ยกเลิก' LIMIT 1",
            (job_number,),
        ).fetchone()
        if exists:
            return False, f"เลข JOB {job_number} มีอยู่ในระบบแล้ว"

        conn.execute(
            """
            INSERT INTO requisitions
            (job_number, department, production_line, item_name, quantity,
             received_at, status, created_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'กำลังจัด', ?, ?)
            """,
            (
                job_number, department, line, item_name, quantity,
                stamp(received_at), DISPLAY_NAME, stamp(now_bangkok()),
            ),
        )
        conn.commit()
    return True, f"บันทึก JOB {job_number} แล้ว"


def update_requisition(
    record_id, department, line, item_name, quantity,
    received_at, picked_at, handover_at,
):
    if department == "PD" and line not in PRODUCTION_LINES:
        raise ValueError("แผนก PD ต้องเลือกไลน์ผลิต L1-L10")
    if department != "PD":
        line = ""

    status = "รับของแล้ว" if handover_at else (
        "จัดเสร็จ / รอ PD" if picked_at else "กำลังจัด"
    )
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE requisitions
            SET department=?, production_line=?, item_name=?, quantity=?,
                received_at=?, picked_at=?, handover_at=?, status=?, updated_at=?
            WHERE id=?
            """,
            (
                department, line, item_name, quantity, stamp(received_at),
                stamp(picked_at), stamp(handover_at), status,
                stamp(now_bangkok()), record_id,
            ),
        )
        conn.commit()


def cancel_requisition(record_id, cancelled_by, reason):
    with sqlite3.connect(DB_PATH) as conn:
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


# ── ส่วนประกอบ UI ─────────────────────────────────────────────────────────────
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
          <div>
            <div class="eyebrow">WAREHOUSE FLOW · CONTROL CENTER</div>
            <h1>{title}</h1>
            <div class="subtle">{subtitle}</div>
          </div>
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
            username = st.text_input("Username", autocomplete="username")
            password = st.text_input(
                "Password", type="password", autocomplete="current-password"
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
    col1, col2 = st.columns([1.4, 1])
    with col1:
        query = st.text_input(
            "🔎 ค้นหา JOB / สินค้า / แผนก / ไลน์",
            key=f"{key_prefix}_search",
            placeholder="พิมพ์คำค้นหา…",
        ).strip().lower()
    with col2:
        mode = st.selectbox(
            "ช่วงวันที่",
            ["ทั้งหมด", "วันนี้", "สัปดาห์นี้", "เลือกช่วงวันที่"],
            key=f"{key_prefix}_date_mode",
        )

    start_date, end_date = None, None
    today = now_bangkok().date()

    if mode == "วันนี้":
        start_date = end_date = today
    elif mode == "สัปดาห์นี้":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif mode == "เลือกช่วงวันที่":
        selected_range = st.date_input(
            "วันที่เริ่มต้นและสิ้นสุด",
            value=(today - timedelta(days=6), today),
            key=f"{key_prefix}_range",
        )
        if isinstance(selected_range, (tuple, list)) and len(selected_range) == 2:
            start_date, end_date = selected_range

    result = df.copy()
    if start_date and end_date and not result.empty:
        dates = result["received_at"].dt.date
        result = result[(dates >= start_date) & (dates <= end_date)]

    if query and not result.empty:
        search_text = (
            result["job_number"].fillna("").astype(str)
            + " " + result["department"].fillna("").astype(str)
            + " " + result["production_line"].fillna("").astype(str)
            + " " + result["item_name"].fillna("").astype(str)
        ).str.lower()
        result = result[search_text.str.contains(query, na=False)]

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
    view["เริ่มจัด"] = view["started_at"].dt.strftime("%d/%m/%Y %H:%M").fillna("—")
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
        "production_line": "ไลน์ผลิต",
        "item_name": "รายการ",
        "quantity": "จำนวน",
        "รับใบเบิก": "รับใบเบิก",
        "เริ่มจัด": "เริ่มจัด",
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


def excel_bytes(df):
    export = df.copy()
    if not export.empty:
        for column in (
            "received_at", "started_at", "picked_at",
            "handover_at", "cancelled_at", "updated_at",
        ):
            if column in export.columns:
                export[column] = export[column].astype(str).replace("NaT", "")

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="Warehouse Jobs")
    buffer.seek(0)
    return buffer.getvalue()


# ── Login gate และ Sidebar ─────────────────────────────────────────────────────
init_db()
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
        label_visibility="collapsed",
    )

    st.markdown("---")
    if st.button("ออกจากระบบ", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state.pop("display_name", None)
        st.rerun()

show_live_clock()
data = load_data()


# ── บันทึกหลาย JOB พร้อมกัน ──────────────────────────────────────────────────
if page == "📝 บันทึกใบเบิก":
    heading("บันทึกใบเบิก", "รับงานระดับ JOB พร้อมประทับเวลาจริงจากคลังสินค้า")
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
        key="new_job_count",
    )

    with st.form("bulk_requisition_form", clear_on_submit=True):
        st.markdown("#### รายละเอียดใบเบิก")
        current_time = now_bangkok()
        received_date = st.date_input(
            "วันที่รับใบเบิก",
            value=current_time.date(),
            key="bulk_received_date",
        )
        received_time = st.time_input(
            "เวลารับใบเบิก",
            value=current_time.time().replace(microsecond=0),
            key="bulk_received_time",
        )
        received_at = parse_local_datetime(received_date, received_time)

        rows = []
        for index in range(int(row_count)):
            st.markdown(f"**JOB #{index + 1}**")
            cols = st.columns([1.1, 1.2, .8, 1.3, .7])

            job = cols[0].text_input(
                "เลข JOB",
                key=f"bulk_job_{index}",
                placeholder="เช่น JOB-6901",
            )
            department = cols[1].selectbox(
                "แผนก",
                DEPARTMENTS,
                key=f"bulk_department_{index}",
                accept_new_options=True,
            )

            # เฉพาะแผนก PD ที่ต้องเลือกไลน์ผลิต
            if department == "PD":
                line = cols[2].selectbox(
                    "ไลน์ผลิต",
                    PRODUCTION_LINES,
                    key=f"bulk_line_{index}",
                )
            else:
                line = ""
                cols[2].markdown(
                    "<div style='padding-top:2rem;color:#94a3b8'>"
                    "ไม่ต้องระบุไลน์ผลิต</div>",
                    unsafe_allow_html=True,
                )

            item = cols[3].text_input("รายการ (ถ้ามี)", key=f"bulk_item_{index}")
            quantity = cols[4].number_input(
                "จำนวน",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key=f"bulk_quantity_{index}",
            )
            rows.append((job, department, line, item, quantity))

        submitted = st.form_submit_button(
            "✅ บันทึกรับเรื่องทั้งหมด",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if received_at is None:
            st.error("กรุณาระบุวันที่และเวลารับใบเบิกให้ถูกต้อง")
        else:
            valid_rows = [row for row in rows if str(row[0]).strip()]
            if not valid_rows:
                st.warning("กรุณากรอกเลข JOB อย่างน้อย 1 รายการ")
            else:
                saved, errors = 0, []
                for job, department, line, item, quantity in valid_rows:
                    success, message = insert_requisition(
                        str(job).strip(),
                        str(department).strip(),
                        line if department == "PD" else "",
                        str(item).strip(),
                        quantity if quantity > 0 else None,
                        received_at,
                    )
                    if success:
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
        avg_processing = (
            round(sum(processing_values) / len(processing_values), 1)
            if processing_values else 0
        )
        waiting_values = filtered["waiting_minutes"].dropna().tolist()
        avg_waiting = (
            round(sum(waiting_values) / len(waiting_values), 1)
            if waiting_values else 0
        )

        cards = st.columns(4)
        cards[0].metric(
            "ใบเบิกในช่วงที่เลือก", f"{total:,}", f"วันนี้ {today_count:,} JOB"
        )
        cards[1].metric(
            "ใบเบิกเย็น", f"{late_count / total * 100:.1f}%", f"{late_count:,} JOB"
        )
        cards[2].metric("เวลาจัดเฉลี่ย", format_duration(avg_processing))
        bottleneck = "รอจัด" if pending_count else (
            "รอ PD รับ" if avg_waiting else "ปกติ"
        )
        cards[3].metric("จุดคอขวด", bottleneck, f"ค้างจัด {pending_count:,} JOB")

        left, right = st.columns(2)
        with left:
            st.markdown("#### 🕒 ปริมาณใบเบิกตามชั่วโมง")
            hourly = (
                filtered.assign(ชั่วโมง=filtered["received_at"].dt.hour)
                .groupby("ชั่วโมง", as_index=False)
                .size()
                .rename(columns={"size": "จำนวน JOB"})
            )
            hourly = (
                hourly.set_index("ชั่วโมง")
                .reindex(range(24), fill_value=0)
                .rename_axis("ชั่วโมง")
                .reset_index()
            )
            chart = px.bar(
                hourly,
                x="ชั่วโมง",
                y="จำนวน JOB",
                color="จำนวน JOB",
                color_continuous_scale=["#bae6fd", "#0284c7"],
            )
            chart.update_layout(
                height=330,
                margin=dict(l=10, r=10, t=20, b=10),
                plot_bgcolor="white",
                paper_bgcolor="white",
                coloraxis_showscale=False,
            )
            chart.update_xaxes(dtick=1, title="ชั่วโมงที่รับใบเบิก")
            chart.update_yaxes(title="จำนวน JOB", rangemode="tozero")
            st.plotly_chart(chart, use_container_width=True)

        with right:
            st.markdown("#### 🏢 ใบเบิกเย็นแยกตามแผนก")
            department_stats = (
                filtered.groupby("department", dropna=False)
                .agg(จำนวน=("job_number", "count"), ใบเบิกเย็น=("late", "sum"))
                .reset_index()
            )
            department_stats["แผนก"] = department_stats["department"].fillna("ไม่ระบุ")
            chart_department = px.bar(
                department_stats,
                x="แผนก",
                y=["จำนวน", "ใบเบิกเย็น"],
                barmode="group",
                color_discrete_sequence=["#38bdf8", "#f87171"],
            )
            chart_department.update_layout(
                height=330,
                margin=dict(l=10, r=10, t=20, b=10),
                plot_bgcolor="white",
                paper_bgcolor="white",
                legend_title_text="ประเภท",
            )
            st.plotly_chart(chart_department, use_container_width=True)

        st.markdown("#### 📌 รายการในช่วงที่เลือก")
        show_table(filtered, "dashboard_table")


# ── จัดการสถานะและรายละเอียด ─────────────────────────────────────────────────
elif page == "✏️ จัดการ / อัปเดตสถานะ":
    heading("จัดการและอัปเดตสถานะ", "บันทึกเวลาจัดเสร็จและเวลาที่ PD รับสินค้า")
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
            "เลือก JOB ที่ต้องการจัดการ",
            ids,
            format_func=lambda record_id: labels[int(record_id)],
        )
        record = active[active["id"] == selected_id].iloc[0]

        st.markdown(
            f'<div class="section-card"><b>JOB {record["job_number"]}</b>'
            f'　·　แผนก {record["department"] or "ไม่ระบุ"}'
            f'　·　{job_status(record)}</div>',
            unsafe_allow_html=True,
        )

        def date_for(value, fallback):
            parsed = as_bangkok(value)
            return parsed.date() if parsed else fallback

        def time_for(value):
            parsed = as_bangkok(value)
            return parsed.time().replace(microsecond=0) if parsed else time(0, 0)

        picked_exists_key = f"picked_exists_{selected_id}"
        handover_exists_key = f"handover_exists_{selected_id}"
        st.session_state.setdefault(picked_exists_key, pd.notna(record["picked_at"]))
        st.session_state.setdefault(handover_exists_key, pd.notna(record["handover_at"]))

        picked_date_key = f"picked_date_{selected_id}"
        picked_time_key = f"picked_time_{selected_id}"
        handover_date_key = f"handover_date_{selected_id}"
        handover_time_key = f"handover_time_{selected_id}"

        st.session_state.setdefault(
            picked_date_key, date_for(record["picked_at"], now_bangkok().date())
        )
        st.session_state.setdefault(picked_time_key, time_for(record["picked_at"]))
        st.session_state.setdefault(
            handover_date_key, date_for(record["handover_at"], now_bangkok().date())
        )
        st.session_state.setdefault(handover_time_key, time_for(record["handover_at"]))

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 📦 เวลาจัดสินค้าเสร็จ")
            picked_exists = st.checkbox(
                "บันทึกเวลาจัดเสร็จแล้ว", key=picked_exists_key
            )
            if st.button("⏱️ ลงเวลาปัจจุบัน", key=f"auto_picked_{selected_id}"):
                current = now_bangkok()
                st.session_state[picked_date_key] = current.date()
                st.session_state[picked_time_key] = current.time().replace(microsecond=0)
                st.session_state[picked_exists_key] = True
                st.rerun()
            picked_date = st.date_input("วันที่จัดเสร็จ", key=picked_date_key)
            picked_time = st.time_input("เวลาจัดเสร็จ", key=picked_time_key)

        with col_b:
            st.markdown("#### 🟢 เวลาที่ PD มารับสินค้า")
            handover_exists = st.checkbox(
                "บันทึกเวลาที่ PD รับแล้ว", key=handover_exists_key
            )
            if st.button("⏱️ ลงเวลาปัจจุบัน", key=f"auto_handover_{selected_id}"):
                current = now_bangkok()
                st.session_state[handover_date_key] = current.date()
                st.session_state[handover_time_key] = current.time().replace(microsecond=0)
                st.session_state[handover_exists_key] = True
                st.rerun()
            handover_date = st.date_input(
                "วันที่ PD รับสินค้า", key=handover_date_key
            )
            handover_time = st.time_input(
                "เวลา PD รับสินค้า", key=handover_time_key
            )

        received_at = as_bangkok(record["received_at"])
        picked_at = (
            parse_local_datetime(picked_date, picked_time) if picked_exists else None
        )
        handover_at = (
            parse_local_datetime(handover_date, handover_time)
            if handover_exists else None
        )

        if picked_at:
            st.caption(
                "เวลาจัดจากค่าที่เลือก: "
                + format_duration(duration_minutes(received_at, picked_at))
            )
        if picked_at and handover_at:
            st.caption(
                "เวลารอ PD จากค่าที่เลือก: "
                + format_duration(duration_minutes(picked_at, handover_at))
            )

        if st.button(
            "💾 บันทึกการอัปเดตสถานะ",
            type="primary",
            use_container_width=True,
            key=f"save_workflow_{selected_id}",
        ):
            if handover_at and not picked_at:
                st.error("กรุณาระบุเวลาจัดเสร็จก่อนบันทึกเวลาที่ PD มารับ")
            elif picked_at and duration_minutes(received_at, picked_at) is None:
                st.error("เวลาจัดเสร็จต้องไม่อยู่ก่อนเวลารับใบเบิก")
            elif handover_at and duration_minutes(picked_at, handover_at) is None:
                st.error("เวลา PD รับสินค้าต้องไม่อยู่ก่อนเวลาจัดเสร็จ")
            else:
                update_requisition(
                    int(selected_id),
                    record["department"],
                    record["production_line"],
                    record["item_name"],
                    record["quantity"],
                    received_at,
                    picked_at,
                    handover_at,
                )
                st.success("บันทึกเวลาและคำนวณระยะเวลาเรียบร้อย")
                st.rerun()

        st.markdown("---")
        with st.expander("✏️ แก้ไขรายละเอียด JOB"):
            current_department = str(record["department"] or DEPARTMENTS[0])
            department_options = DEPARTMENTS.copy()
            if current_department not in department_options:
                department_options.insert(0, current_department)

            edit_department = st.selectbox(
                "แผนก",
                department_options,
                index=department_options.index(current_department),
                key=f"edit_department_{selected_id}",
                accept_new_options=True,
            )

            # เฉพาะ PD เท่านั้นที่แสดงและต้องเลือกไลน์ผลิต
            edit_line = ""
            if edit_department == "PD":
                current_line = str(record["production_line"] or "L1")
                line_index = (
                    PRODUCTION_LINES.index(current_line)
                    if current_line in PRODUCTION_LINES else 0
                )
                edit_line = st.selectbox(
                    "ไลน์ผลิต",
                    PRODUCTION_LINES,
                    index=line_index,
                    key=f"edit_line_{selected_id}",
                )

            edit_item = st.text_input(
                "รายการ",
                value=str(record["item_name"] or ""),
                key=f"edit_item_{selected_id}",
            )
            edit_quantity = st.number_input(
                "จำนวน",
                min_value=0.0,
                value=float(record["quantity"])
                if pd.notna(record["quantity"]) else 0.0,
                key=f"edit_quantity_{selected_id}",
            )

            if st.button("บันทึกการแก้ไขรายละเอียด", key=f"save_edit_{selected_id}"):
                try:
                    update_requisition(
                        int(selected_id),
                        str(edit_department).strip(),
                        edit_line if edit_department == "PD" else "",
                        edit_item,
                        edit_quantity if edit_quantity > 0 else None,
                        received_at,
                        picked_at,
                        handover_at,
                    )
                    st.success("อัปเดตรายละเอียดแล้ว")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

        with st.expander("🔴 ยกเลิก JOB"):
            cancel_by = st.text_input(
                "ผู้แจ้งยกเลิก (PN/PD)", key=f"cancel_by_{selected_id}"
            )
            cancel_reason = st.text_area(
                "สาเหตุการยกเลิก", key=f"cancel_reason_{selected_id}"
            )
            confirm = st.checkbox(
                "ยืนยันการยกเลิก JOB นี้", key=f"confirm_cancel_{selected_id}"
            )
            if st.button(
                "ยืนยันยกเลิก",
                disabled=not confirm,
                key=f"cancel_button_{selected_id}",
            ):
                if not cancel_by.strip() or not cancel_reason.strip():
                    st.error("กรุณาระบุผู้แจ้งและสาเหตุการยกเลิก")
                else:
                    cancel_requisition(int(selected_id), cancel_by, cancel_reason)
                    st.success("ยกเลิก JOB แล้ว")
                    st.rerun()


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
            data=excel_bytes(filtered),
            file_name=f"warehouse_jobs_{now_bangkok().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.caption(f"แสดง {len(filtered):,} รายการ")


st.markdown(
    "<div style='text-align:center;color:#94a3b8;padding:1.5rem 0 0'>"
    "Warehouse Flow · เวลาอ้างอิง Asia/Bangkok · ผู้ใช้งาน Admin</div>",
    unsafe_allow_html=True,
)
