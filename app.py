<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="theme-color" content="#101d2d">
  <title>PK Warehouse | JOB Tracking</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #162538;
      --muted: #748195;
      --line: #e4eaf1;
      --surface: rgba(255, 255, 255, .83);
      --navy: #14253a;
      --teal: #187e79;
      --amber: #bc790a;
      --blue: #3474c4;
      --green: #19845f;
      --red: #c2414d;
      --shadow: 0 14px 38px rgba(24, 46, 72, .09);
      --radius: 20px;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Segoe UI", Tahoma, sans-serif;
      background:
        radial-gradient(ellipse at 8% 0%, rgba(76, 153, 165, .14), transparent 34%),
        radial-gradient(ellipse at 96% 8%, rgba(91, 117, 185, .12), transparent 30%),
        #f3f6fa;
    }

    button, input, textarea, select { font: inherit; }
    button { cursor: pointer; }

    .shell {
      width: min(1500px, calc(100% - 36px));
      margin: 0 auto;
      padding: 26px 0 48px;
    }

    .hero {
      position: relative;
      overflow: hidden;
      padding: 27px 30px;
      border: 1px solid rgba(255,255,255,.42);
      border-radius: 25px;
      color: white;
      background: linear-gradient(115deg, #132940, #176d70);
      box-shadow: 0 20px 48px rgba(25, 54, 78, .2);
    }

    .hero::after {
      content: "";
      position: absolute;
      width: 250px;
      height: 250px;
      right: -45px;
      top: -140px;
      border-radius: 50%;
      background: rgba(255,255,255,.08);
    }

    .hero h1 { margin: 0 0 7px; font-size: clamp(25px, 4vw, 36px); }
    .hero p { margin: 0; color: #d5e7eb; line-height: 1.6; }
    .hero-meta { margin-top: 17px; display: flex; gap: 9px; flex-wrap: wrap; }

    .hero-chip {
      padding: 7px 11px;
      border: 1px solid rgba(255,255,255,.2);
      border-radius: 999px;
      background: rgba(255,255,255,.1);
      color: #eef8fa;
      font-size: 12px;
    }

    .section-heading {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 12px;
      margin: 27px 2px 13px;
    }

    .section-heading h2 { margin: 0; font-size: 19px; }
    .section-heading p { margin: 4px 0 0; color: var(--muted); font-size: 13px; }

    .card, .kpi {
      border: 1px solid rgba(255,255,255,.92);
      border-radius: var(--radius);
      background: var(--surface);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }

    .kpis {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 13px;
      margin-top: 18px;
    }

    .kpi { padding: 17px 18px; }
    .kpi-label { color: var(--muted); font-size: 12px; font-weight: 600; }
    .kpi-value { margin-top: 8px; font-size: clamp(20px, 2.5vw, 29px); font-weight: 750; letter-spacing: -.5px; }
    .kpi-foot { margin-top: 4px; color: #8a96a6; font-size: 11px; }

    .layout {
      display: grid;
      grid-template-columns: minmax(300px, .88fr) minmax(0, 1.65fr);
      gap: 15px;
      align-items: start;
    }

    .card { padding: 19px; }
    .card h3 { margin: 0 0 5px; font-size: 16px; }
    .subtext { margin: 0 0 16px; color: var(--muted); font-size: 12px; line-height: 1.55; }

    .field { margin: 13px 0; }
    .field label { display: block; margin-bottom: 6px; font-size: 12px; font-weight: 650; }
    .field small { display: block; margin-top: 5px; color: var(--muted); font-size: 11px; }

    input, textarea, select {
      width: 100%;
      border: 1px solid #dce4ed;
      border-radius: 11px;
      padding: 10px 12px;
      color: var(--ink);
      background: rgba(255,255,255,.9);
      outline: none;
      transition: border-color .15s, box-shadow .15s;
    }

    input:focus, textarea:focus, select:focus {
      border-color: #5b9da0;
      box-shadow: 0 0 0 3px rgba(55, 140, 139, .12);
    }

    textarea { resize: vertical; min-height: 104px; line-height: 1.55; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .btn-row { display: flex; flex-wrap: wrap; gap: 8px; }
    .btn {
      display: inline-flex;
      justify-content: center;
      align-items: center;
      gap: 7px;
      min-height: 40px;
      padding: 9px 13px;
      border: 1px solid transparent;
      border-radius: 11px;
      color: white;
      background: var(--navy);
      font-weight: 650;
      font-size: 12px;
      box-shadow: 0 5px 14px rgba(28, 55, 78, .12);
      transition: transform .12s ease, box-shadow .15s ease, filter .15s ease;
    }

    .btn:hover { transform: translateY(-2px); box-shadow: 0 9px 20px rgba(28,55,78,.18); filter: brightness(1.04); }
    .btn:active { transform: scale(.98); }
    .btn.teal { background: var(--teal); }
    .btn.blue { background: var(--blue); }
    .btn.green { background: var(--green); }
    .btn.red { background: var(--red); }
    .btn.amber { background: var(--amber); }
    .btn.soft { color: #34475e; background: #f0f4f8; border-color: #e1e8ef; box-shadow: none; }
    .btn.small { min-height: 31px; padding: 6px 9px; font-size: 11px; border-radius: 9px; }
    .btn.block { width: 100%; }
    .btn:disabled { cursor: not-allowed; opacity: .48; transform: none; }

    .status-callout {
      padding: 11px 12px;
      border: 1px solid #e8edf2;
      border-radius: 12px;
      background: rgba(248,250,252,.8);
      color: #596a7d;
      font-size: 12px;
      line-height: 1.55;
    }

    .warning {
      padding: 11px 12px;
      border: 1px solid #f3d28a;
      border-radius: 12px;
      color: #795311;
      background: #fff8e8;
      font-size: 12px;
      line-height: 1.55;
    }

    .message {
      display: none;
      margin: 12px 0 0;
      padding: 10px 12px;
      border-radius: 11px;
      font-size: 12px;
      line-height: 1.5;
    }

    .message.show { display: block; }
    .message.success { color: #116447; background: #e8f6ef; border: 1px solid #c8ead9; }
    .message.error { color: #a22e3a; background: #fff0f1; border: 1px solid #f1c9cd; }

    .queue { display: grid; gap: 11px; }
    .job-card {
      padding: 14px;
      border: 1px solid #e5ebf1;
      border-radius: 15px;
      background: rgba(255,255,255,.8);
    }

    .job-top { display: flex; justify-content: space-between; gap: 10px; align-items: start; }
    .job-number { font-size: 16px; font-weight: 750; }
    .job-dept { margin-top: 3px; color: var(--muted); font-size: 12px; }
    .badge {
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 6px 9px;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 700;
      white-space: nowrap;
    }

    .badge.received { color: #73510e; background: #fff2ce; }
    .badge.in_progress { color: #73510e; background: #fff2ce; }
    .badge.completed { color: #245998; background: #e7f1ff; }
    .badge.handed_over { color: #176648; background: #e2f5eb; }
    .badge.cancelled { color: #9e303a; background: #fdebed; }

    .late-tag {
      display: inline-block;
      margin-top: 9px;
      padding: 5px 8px;
      border-radius: 8px;
      color: #a5323d;
      background: #fff0f1;
      font-size: 10px;
      font-weight: 700;
    }

    .timeline {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 7px;
      margin: 13px 0;
    }

    .time-cell { padding: 8px; border-radius: 10px; background: #f5f7fa; }
    .time-cell span { display: block; color: var(--muted); font-size: 9px; }
    .time-cell strong { display: block; margin-top: 4px; font-size: 10px; font-weight: 650; overflow-wrap: anywhere; }

    .job-actions { display: flex; flex-wrap: wrap; gap: 7px; }
    .table-tools { display: grid; grid-template-columns: 1fr 1fr 1.5fr; gap: 9px; margin-bottom: 12px; }
    .table-wrap { overflow: auto; border: 1px solid var(--line); border-radius: 14px; background: rgba(255,255,255,.8); }
    table { width: 100%; min-width: 1050px; border-collapse: collapse; font-size: 11px; }
    th, td { padding: 10px 11px; border-bottom: 1px solid #e9eef3; text-align: left; vertical-align: top; }
    th { position: sticky; top: 0; z-index: 1; color: #667589; background: #f7f9fb; font-weight: 700; white-space: nowrap; }
    tbody tr:hover { background: rgba(235,243,247,.55); }
    td.muted { color: #8b97a6; }
    .empty {
      padding: 32px 16px;
      border: 1px dashed #cad5df;
      border-radius: 15px;
      color: #728094;
      background: rgba(250,252,254,.7);
      text-align: center;
      font-size: 13px;
    }

    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 20;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 18px;
      background: rgba(13, 25, 39, .55);
      backdrop-filter: blur(5px);
    }

    .modal-backdrop.open { display: flex; }
    .modal {
      width: min(650px, 100%);
      max-height: min(90vh, 850px);
      overflow: auto;
      padding: 22px;
      border: 1px solid rgba(255,255,255,.7);
      border-radius: 20px;
      background: #fff;
      box-shadow: 0 25px 70px rgba(0,0,0,.25);
    }

    .modal h2 { margin: 0 0 5px; font-size: 20px; }
    .modal-sub { margin: 0 0 17px; color: var(--muted); font-size: 12px; }
    .evidence { border: 1px solid #e6ebf0; border-radius: 13px; overflow: hidden; }
    .evidence-row { display: grid; grid-template-columns: 185px 1fr; gap: 10px; padding: 11px 13px; border-bottom: 1px solid #edf0f3; font-size: 12px; }
    .evidence-row:last-child { border-bottom: 0; }
    .evidence-row span { color: var(--muted); }
    .evidence-row strong { overflow-wrap: anywhere; }
    .modal-actions { display: flex; justify-content: end; flex-wrap: wrap; gap: 8px; margin-top: 16px; }

    #scanner-box { display: none; margin-top: 12px; }
    #scanner-box.open { display: block; }
    #scanner-video { width: 100%; max-height: 270px; border-radius: 13px; background: #101820; object-fit: cover; }
    .scan-note { margin: 7px 0 0; color: var(--muted); font-size: 11px; }

    .footer-note { margin: 18px 2px 0; color: #8a96a6; font-size: 11px; line-height: 1.6; }

    @media (max-width: 1020px) {
      .kpis { grid-template-columns: repeat(3, 1fr); }
      .layout { grid-template-columns: 1fr; }
    }

    @media (max-width: 650px) {
      .shell { width: min(100% - 22px, 1500px); padding-top: 12px; }
      .hero { padding: 21px 18px; border-radius: 19px; }
      .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }
      .kpi { padding: 13px; }
      .table-tools { grid-template-columns: 1fr; }
      .timeline { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .row { grid-template-columns: 1fr; gap: 0; }
      .evidence-row { grid-template-columns: 1fr; gap: 3px; }
    }

    @media print {
      body * { visibility: hidden !important; }
      #print-slip, #print-slip * { visibility: visible !important; }
      #print-slip {
        position: absolute;
        inset: 0;
        width: 100%;
        padding: 24px;
        color: #111;
        background: #fff;
      }
      .modal-actions { display: none !important; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="hero">
      <h1>📦 PK Warehouse · JOB Tracking</h1>
      <p>บันทึกเวลารับงานและติดตามสถานะใบเบิก เพื่อให้มี Timeline อ้างอิงการทำงาน</p>
      <div class="hero-meta">
        <span class="hero-chip">🕓 Cut-off <strong id="cutoff-chip">16:00</strong></span>
        <span class="hero-chip">🗂️ บันทึกเฉพาะ JOB และแผนก/ไลน์</span>
        <span class="hero-chip">💾 เก็บข้อมูลไว้ในเบราว์เซอร์เครื่องนี้</span>
      </div>
    </header>

    <section class="kpis" aria-label="สรุปยอดงาน">
      <article class="kpi">
        <div class="kpi-label">📄 JOB ทั้งหมด</div>
        <div class="kpi-value" id="kpi-total">0</div>
        <div class="kpi-foot">รายการที่บันทึกไว้</div>
      </article>
      <article class="kpi">
        <div class="kpi-label">🔴 ใบเบิกเย็น</div>
        <div class="kpi-value" id="kpi-late">0%</div>
        <div class="kpi-foot">รับหลังเวลา Cut-off</div>
      </article>
      <article class="kpi">
        <div class="kpi-label">⏱️ เวลาจัดเฉลี่ย</div>
        <div class="kpi-value" id="kpi-pick">—</div>
        <div class="kpi-foot">รับเรื่องถึงจัดเสร็จ</div>
      </article>
      <article class="kpi">
        <div class="kpi-label">🕒 เวลารอ PD เฉลี่ย</div>
        <div class="kpi-value" id="kpi-wait">—</div>
        <div class="kpi-foot">จัดเสร็จถึงรับของ</div>
      </article>
      <article class="kpi">
        <div class="kpi-label">❌ ยกเลิก / เสียเวลา</div>
        <div class="kpi-value" id="kpi-cancel">0 / 0 นาที</div>
        <div class="kpi-foot">เวลาที่ใช้จัดก่อนถูกยกเลิก</div>
      </article>
    </section>

    <section class="layout" style="margin-top: 19px;">
      <div class="card">
        <h3>📥 รับ JOB เข้า</h3>
        <p class="subtext">เลือกรูปแบบการบันทึกที่สะดวก ระบบจะประทับเวลารับจากนาฬิกาเครื่อง</p>

        <div class="field">
          <label for="department">แผนก / ไลน์ผลิตที่เบิก *</label>
          <input id="department" type="text" placeholder="เช่น PD-Line 1" autocomplete="organization">
        </div>

        <div class="field">
          <label for="bulk-input">📋 วางหลาย JOB พร้อมกัน</label>
          <textarea id="bulk-input" placeholder="วางเลข JOB แยกบรรทัดได้&#10;JOB-6901&#10;JOB-6902&#10;หรือ: JOB-6903, PD-Line 2"></textarea>
          <small>ถ้าระบุแค่ JOB ระบบจะใช้แผนก/ไลน์ด้านบนกับทุกรายการ</small>
        </div>
        <button class="btn teal block" id="bulk-submit">📋 บันทึกรับเรื่องทั้งหมด</button>

        <div class="field" style="margin-top:20px">
          <label for="quick-job">⌨️ พิมพ์ด่วน</label>
          <input id="quick-job" type="text" inputmode="numeric" placeholder="พิมพ์เลข 4 หลัก หรือ JOB-6901" autocomplete="off">
          <small>กด Enter เพื่อบันทึกทันที และช่องจะพร้อมรับรายการถัดไป</small>
        </div>
        <button class="btn block" id="quick-submit">รับ JOB ด่วน</button>

        <div class="field" style="margin-top:20px">
          <label>📷 สแกนบาร์โค้ด / QR Code</label>
          <div class="btn-row">
            <button class="btn soft" id="camera-start">เปิดกล้องสแกน</button>
            <button class="btn soft" id="camera-stop" hidden>ปิดกล้อง</button>
          </div>
          <div id="scanner-box">
            <video id="scanner-video" playsinline muted></video>
            <p class="scan-note" id="scanner-note">หันกล้องไปที่บาร์โค้ดหรือ QR Code ของ JOB</p>
          </div>
        </div>

        <div id="input-message" class="message" role="status"></div>
      </div>

      <div class="card">
        <h3>⚡ คิวงานที่ต้องดำเนินการ</h3>
        <p class="subtext">กดปุ่มเมื่อเปลี่ยนขั้นตอน ระบบจะบันทึกเวลาปัจจุบันและเสียงตอบรับ</p>
        <div id="active-queue" class="queue"></div>
      </div>
    </section>

    <section class="section-heading">
      <div>
        <h2>📊 ภาพรวมงาน</h2>
        <p>กราฟจำนวน JOB ที่รับเข้ารายชั่วโมงและสัดส่วนใบเบิกเย็นแยกตามแผนก</p>
      </div>
    </section>

    <section class="layout">
      <div class="card">
        <h3>🕓 JOB ที่รับเข้ารายชั่วโมง</h3>
        <div id="hourly-chart"></div>
      </div>
      <div class="card">
        <h3>🏭 ใบเบิกเย็นแยกตามแผนก/ไลน์</h3>
        <div id="department-chart"></div>
      </div>
    </section>

    <section class="section-heading">
      <div>
        <h2>📋 ทะเบียน JOB</h2>
        <p>ค้นหา กรองสถานะ และเปิดหลักฐานสำหรับรายการที่ถูกยกเลิก</p>
      </div>
      <button class="btn soft" id="export-csv">⬇️ Export CSV</button>
    </section>

    <section class="card">
      <div class="table-tools">
        <select id="status-filter" aria-label="กรองตามสถานะ">
          <option value="">ทุกสถานะ</option>
          <option value="received">📥 รับ JOB / กำลังจัด</option>
          <option value="completed">🔵 จัดเสร็จ / รอ PD</option>
          <option value="handed_over">🟢 PD มารับแล้ว</option>
          <option value="cancelled">🔴 ยกเลิก</option>
        </select>
        <select id="late-filter" aria-label="กรองใบเบิกเย็น">
          <option value="">ใบเบิกทุกช่วงเวลา</option>
          <option value="late">🔴 ใบเบิกเย็น</option>
          <option value="ontime">🟢 ในเวลา Cut-off</option>
        </select>
        <input id="search" type="search" placeholder="ค้นหา JOB หรือแผนก/ไลน์">
      </div>

      <div id="empty-notice" class="empty" hidden>ยังไม่มีข้อมูลใบเบิก</div>
      <div class="table-wrap" id="table-wrap">
        <table>
          <thead>
            <tr>
              <th>เลขที่ JOB</th>
              <th>แผนก/ไลน์</th>
              <th>📥 รับเรื่อง</th>
              <th>🟡 เริ่มจัด</th>
              <th>🔵 จัดเสร็จ</th>
              <th>🟢 PD รับของ</th>
              <th>❌ ยกเลิก</th>
              <th>สถานะ</th>
              <th>แท็ก</th>
              <th>เวลาจัด</th>
              <th>เวลารอ PD</th>
              <th>หลักฐาน</th>
            </tr>
          </thead>
          <tbody id="job-table-body"></tbody>
        </table>
      </div>
    </section>

    <p class="footer-note">
      ข้อมูลเก็บใน Local Storage ของเบราว์เซอร์เครื่องนี้ ไม่ได้ส่งไปเซิร์ฟเวอร์
      • หากล้างข้อมูลเว็บไซต์/เบราว์เซอร์ ข้อมูลในเครื่องอาจถูกลบ ควร Export CSV สำรองเป็นระยะ
      • การสแกนกล้องต้องอนุญาตสิทธิ์กล้อง และทำงานบน HTTPS หรือ localhost
    </p>
  </main>

  <div class="modal-backdrop" id="evidence-modal" role="dialog" aria-modal="true" aria-labelledby="evidence-title">
    <div class="modal" id="print-slip">
      <h2 id="evidence-title">📄 หลักฐาน Timeline การยกเลิก JOB</h2>
      <p class="modal-sub">บันทึกจากระบบ PK Warehouse · JOB Tracking</p>
      <div id="evidence-content" class="evidence"></div>
      <div class="modal-actions">
        <button class="btn soft" id="evidence-close">ปิด</button>
        <button class="btn" id="evidence-print">🖨️ พิมพ์ / บันทึก PDF</button>
      </div>
    </div>
  </div>

  <div class="modal-backdrop" id="cancel-modal" role="dialog" aria-modal="true" aria-labelledby="cancel-title">
    <div class="modal">
      <h2 id="cancel-title">🔴 ยืนยันยกเลิก JOB</h2>
      <p class="modal-sub" id="cancel-job-label"></p>
      <div class="warning">การยกเลิกจะบันทึกเวลา ผู้สั่ง และสาเหตุไว้ใน Timeline</div>
      <div class="field">
        <label for="cancel-by">ผู้สั่งยกเลิก PN/PD *</label>
        <input id="cancel-by" type="text" placeholder="ชื่อผู้แจ้งหรือรหัส PN/PD">
      </div>
      <div class="field">
        <label for="cancel-reason">สาเหตุการยกเลิก *</label>
        <textarea id="cancel-reason" placeholder="ระบุสาเหตุหรือการเปลี่ยนแผน"></textarea>
      </div>
      <div class="modal-actions">
        <button class="btn soft" id="cancel-dismiss">กลับ</button>
        <button class="btn red" id="cancel-confirm">บันทึกยกเลิก</button>
      </div>
      <div id="cancel-message" class="message" role="status"></div>
    </div>
  </div>

  <script>
    "use strict";

    const STORAGE_KEY = "pk_warehouse_job_tracking_v1";
    const CUTOFF_HOUR = 16;
    const CUTOFF_MINUTE = 0;

    let jobs = loadJobs();
    let pendingCancelId = null;
    let cameraStream = null;
    let scanLoopActive = false;

    const $ = (selector) => document.querySelector(selector);

    function loadJobs() {
      try {
        const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        return Array.isArray(parsed) ? parsed : [];
      } catch (error) {
        return [];
      }
    }

    function persist() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs));
    }

    function localTimestamp(date = new Date()) {
      const pad = (value) => String(value).padStart(2, "0");
      return [
        date.getFullYear(),
        "-",
        pad(date.getMonth() + 1),
        "-",
        pad(date.getDate()),
        " ",
        pad(date.getHours()),
        ":",
        pad(date.getMinutes()),
        ":",
        pad(date.getSeconds())
      ].join("");
    }

    function parseTimestamp(value) {
      if (!value) return null;
      // Parse local "YYYY-MM-DD HH:MM:SS" without converting timezone.
      const match = String(value).match(
        /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/
      );
      if (!match) return null;
      return new Date(
        Number(match[1]), Number(match[2]) - 1, Number(match[3]),
        Number(match[4]), Number(match[5]), Number(match[6])
      );
    }

    function isLate(timestamp) {
      const value = parseTimestamp(timestamp);
      if (!value) return false;
      return value.getHours() > CUTOFF_HOUR ||
        (value.getHours() === CUTOFF_HOUR && value.getMinutes() > CUTOFF_MINUTE);
    }

    function elapsedMinutes(from, to) {
      const start = parseTimestamp(from);
      const end = parseTimestamp(to);
      if (!start || !end) return null;
      return Math.max(0, Math.round((end - start) / 60000));
    }

    function formatDuration(minutes) {
      if (minutes === null || !Number.isFinite(minutes)) return "—";
      if (minutes < 60) return `${minutes} นาที`;
      const hours = Math.floor(minutes / 60);
      const remainder = minutes % 60;
      return remainder ? `${hours} ชม. ${remainder} นาที` : `${hours} ชม.`;
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      })[character]);
    }

    function playTick() {
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
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
        // เสียงเป็นส่วนเสริม ไม่ขัดขวางการบันทึกข้อมูล
      }
    }

    function showMessage(element, text, type = "success") {
      element.textContent = text;
      element.className = `message show ${type}`;
      window.setTimeout(() => element.classList.remove("show"), 4200);
    }

    function makeJobNumber(raw) {
      const value = raw.trim();
      if (!value) return "";
      if (/^JOB-/i.test(value)) return value.toUpperCase();
      if (/^\d{4}$/.test(value)) return `JOB-${value}`;
      return value.toUpperCase();
    }

    function createJob(jobNumber, department) {
      const now = localTimestamp();
      const job = {
        id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
        jobNumber: makeJobNumber(jobNumber),
        department: department.trim(),
        receivedTime: now,
        inProgressTime: null,
        pickedTime: null,
        handoverTime: null,
        canceledTime: null,
        canceledBy: "",
        cancelReason: "",
        status: "received"
      };
      jobs.unshift(job);
      return job;
    }

    function addJobsFromBulk() {
      const text = $("#bulk-input").value.trim();
      const defaultDepartment = $("#department").value.trim();
      const message = $("#input-message");

      if (!text) {
        showMessage(message, "กรุณาวางเลข JOB อย่างน้อยหนึ่งรายการ", "error");
        return;
      }

      const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      const entries = [];
      const invalid = [];

      for (const line of lines) {
        const parts = line.split(/[,\t;|]/).map((part) => part.trim()).filter(Boolean);
        const number = makeJobNumber(parts[0] || "");
        const department = parts[1] || defaultDepartment;

        if (!number || !department) {
          invalid.push(line);
          continue;
        }

        entries.push({ number, department });
      }

      if (invalid.length) {
        showMessage(
          message,
          `กรอกแผนก/ไลน์ด้านบน หรือระบุแผนกหลังเลข JOB ในบรรทัดเดียวกัน: ${invalid.join(", ")}`,
          "error"
        );
        return;
      }

      const seen = new Set(jobs.map((job) => job.jobNumber.toLowerCase()));
      const duplicates = entries.filter((entry) => seen.has(entry.number.toLowerCase()));
      if (duplicates.length) {
        showMessage(
          message,
          `พบ JOB ที่มีในระบบแล้ว: ${duplicates.map((item) => item.number).join(", ")}`,
          "error"
        );
        return;
      }

      const receivedAt = localTimestamp();
      entries.forEach((entry) => {
        jobs.unshift({
          id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
          jobNumber: entry.number,
          department: entry.department,
          receivedTime: receivedAt,
          inProgressTime: null,
          pickedTime: null,
          handoverTime: null,
          canceledTime: null,
          canceledBy: "",
          cancelReason: "",
          status: "received"
        });
      });

      persist();
      playTick();
      $("#bulk-input").value = "";
      showMessage(message, `บันทึกรับเรื่องแล้ว ${entries.length} JOB`);
      render();
    }

    function addQuickJob() {
      const input = $("#quick-job");
      const message = $("#input-message");
      const number = makeJobNumber(input.value);
      const department = $("#department").value.trim();

      if (!number) {
        showMessage(message, "กรุณากรอกเลข JOB", "error");
        input.focus();
        return;
      }

      if (!department) {
        showMessage(message, "กรุณากรอกแผนก/ไลน์ผลิตก่อนรับ JOB", "error");
        $("#department").focus();
        return;
      }

      if (jobs.some((job) => job.jobNumber.toLowerCase() === number.toLowerCase())) {
        showMessage(message, `เลข ${number} มีในระบบแล้ว`, "error");
        input.select();
        return;
      }

      createJob(number, department);
      persist();
      playTick();
      input.value = "";
      showMessage(message, `รับ ${number} แล้ว`);
      render();
      input.focus();
    }

    function setStatus(id, status) {
      const job = jobs.find((item) => item.id === id);
      if (!job) return;

      const now = localTimestamp();

      if (status === "in_progress") {
        job.inProgressTime = job.inProgressTime || now;
        job.status = "in_progress";
      } else if (status === "completed") {
        job.inProgressTime = job.inProgressTime || now;
        job.pickedTime = now;
        job.status = "completed";
      } else if (status === "handed_over") {
        if (!job.pickedTime) {
          job.pickedTime = now;
        }
        job.handoverTime = now;
        job.status = "handed_over";
      }

      persist();
      playTick();
      render();
    }

    function openCancelModal(id) {
      const job = jobs.find((item) => item.id === id);
      if (!job) return;

      pendingCancelId = id;
      $("#cancel-job-label").textContent = `${job.jobNumber} · ${job.department}`;
      $("#cancel-by").value = "";
      $("#cancel-reason").value = "";
      $("#cancel-message").className = "message";
      $("#cancel-modal").classList.add("open");
      $("#cancel-by").focus();
    }

    function closeCancelModal() {
      $("#cancel-modal").classList.remove("open");
      pendingCancelId = null;
    }

    function confirmCancel() {
      const job = jobs.find((item) => item.id === pendingCancelId);
      const canceledBy = $("#cancel-by").value.trim();
      const reason = $("#cancel-reason").value.trim();

      if (!job) return;
      if (!canceledBy || !reason) {
        showMessage($("#cancel-message"), "กรุณาระบุผู้สั่งยกเลิกและสาเหตุให้ครบ", "error");
        return;
      }

      job.canceledTime = localTimestamp();
      job.canceledBy = canceledBy;
      job.cancelReason = reason;
      job.status = "cancelled";

      persist();
      playTick();
      closeCancelModal();
      render();
    }

    function statusLabel(status) {
      const labels = {
        received: "🟡 รับ JOB / กำลังจัด",
        in_progress: "🟡 กำลังจัด",
        completed: "🔵 จัดเสร็จ / รอ PD",
        handed_over: "🟢 PD มารับแล้ว",
        cancelled: "🔴 ยกเลิก"
      };
      return labels[status] || "—";
    }

    function shortTime(value) {
      if (!value) return "—";
      return escapeHtml(value);
    }

    function renderQueue() {
      const container = $("#active-queue");
      const active = jobs.filter((job) => !["handed_over", "cancelled"].includes(job.status));

      if (!active.length) {
        container.innerHTML = `<div class="empty">ยังไม่มีงานในคิวที่ต้องดำเนินการ</div>`;
        return;
      }

      container.innerHTML = active.map((job) => `
        <article class="job-card">
          <div class="job-top">
            <div>
              <div class="job-number">${escapeHtml(job.jobNumber)}</div>
              <div class="job-dept">${escapeHtml(job.department)}</div>
            </div>
            <span class="badge ${escapeHtml(job.status)}">${statusLabel(job.status)}</span>
          </div>
          ${isLate(job.receivedTime) ? `<div class="late-tag">🔴 ใบเบิกเย็น/ส่งช้า · รับหลัง 16:00 น.</div>` : ""}
          <div class="timeline">
            <div class="time-cell"><span>📥 รับเรื่อง</span><strong>${shortTime(job.receivedTime)}</strong></div>
            <div class="time-cell"><span>🟡 เริ่มจัด</span><strong>${shortTime(job.inProgressTime)}</strong></div>
            <div class="time-cell"><span>🔵 จัดเสร็จ</span><strong>${shortTime(job.pickedTime)}</strong></div>
            <div class="time-cell"><span>🟢 PD รับของ</span><strong>${shortTime(job.handoverTime)}</strong></div>
          </div>
          <div class="job-actions">
            ${job.status === "received" ? `<button class="btn amber small" data-action="start" data-id="${escapeHtml(job.id)}">🟡 เริ่มจัด</button>` : ""}
            ${["received", "in_progress"].includes(job.status) ? `<button class="btn blue small" data-action="picked" data-id="${escapeHtml(job.id)}">🔵 จัดเสร็จ / รอ PD</button>` : ""}
            ${job.status === "completed" ? `<button class="btn green small" data-action="handover" data-id="${escapeHtml(job.id)}">🟢 PD มารับแล้ว</button>` : ""}
            <button class="btn red small" data-action="cancel" data-id="${escapeHtml(job.id)}">🔴 ยกเลิก JOB</button>
          </div>
        </article>
      `).join("");
    }

    function renderKpis() {
      const total = jobs.length;
      const lateJobs = jobs.filter((job) => isLate(job.receivedTime));
      const pickedJobs = jobs.filter((job) => job.pickedTime);
      const handedJobs = jobs.filter((job) => job.handoverTime && job.pickedTime);
      const canceledJobs = jobs.filter((job) => job.status === "cancelled");

      const processing = pickedJobs
        .map((job) => elapsedMinutes(job.receivedTime, job.pickedTime))
        .filter((value) => value !== null);

      const waiting = handedJobs
        .map((job) => elapsedMinutes(job.pickedTime, job.handoverTime))
        .filter((value) => value !== null);

      const wasted = canceledJobs.reduce((totalMinutes, job) => {
        const start = job.inProgressTime || job.receivedTime;
        return totalMinutes + (elapsedMinutes(start, job.canceledTime) || 0);
      }, 0);

      const avg = (values) => values.length
        ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
        : null;

      $("#kpi-total").textContent = total.toLocaleString("th-TH");
      $("#kpi-late").textContent = total ? `${Math.round((lateJobs.length / total) * 100)}%` : "0%";
      $("#kpi-pick").textContent = avg(processing) === null ? "—" : formatDuration(avg(processing));
      $("#kpi-wait").textContent = avg(waiting) === null ? "—" : formatDuration(avg(waiting));
      $("#kpi-cancel").textContent = `${canceledJobs.length} / ${wasted} นาที`;
    }

    function renderHourlyChart() {
      const container = $("#hourly-chart");

      if (!jobs.length) {
        container.innerHTML = `<div class="empty">ยังไม่มีข้อมูลใบเบิก</div>`;
        return;
      }

      const startHour = 7;
      const endHour = 22;
      const counts = Array.from({ length: endHour - startHour }, (_, index) => ({
        hour: startHour + index,
        count: 0
      }));

      for (const job of jobs) {
        const timestamp = parseTimestamp(job.receivedTime);
        if (!timestamp) continue;
        const slot = counts.find((item) => item.hour === timestamp.getHours());
        if (slot) slot.count += 1;
      }

      const max = Math.max(1, ...counts.map((item) => item.count));
      const width = 720;
      const height = 210;
      const padLeft = 34;
      const padBottom = 33;
      const chartHeight = height - padBottom - 15;
      const barGap = 7;
      const barWidth = (width - padLeft - 12) / counts.length - barGap;

      const bars = counts.map((item, index) => {
        const x = padLeft + index * (barWidth + barGap);
        const barHeight = (item.count / max) * chartHeight;
        const y = chartHeight - barHeight + 12;
        const late = item.hour >= 16;
        return `
          <g>
            <rect x="${x}" y="${y}" width="${barWidth}" height="${Math.max(barHeight, 1)}"
              rx="5" fill="${late ? "#db5b63" : "#319783"}" opacity=".9">
              <title>${String(item.hour).padStart(2, "0")}:00 · ${item.count} JOB</title>
            </rect>
            <text x="${x + barWidth / 2}" y="${height - 9}" text-anchor="middle"
              font-size="9" fill="#778497">${String(item.hour).padStart(2, "0")}</text>
            ${item.count ? `<text x="${x + barWidth / 2}" y="${Math.max(y - 4, 11)}" text-anchor="middle" font-size="9" fill="#526176">${item.count}</text>` : ""}
          </g>`;
      }).join("");

      container.innerHTML = `
        <div style="overflow:auto">
          <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="กราฟจำนวน JOB ที่รับรายชั่วโมง" style="width:100%;min-width:480px;height:auto">
            <line x1="${padLeft}" y1="${chartHeight + 12}" x2="${width - 8}" y2="${chartHeight + 12}" stroke="#dfe6ed"/>
            ${bars}
          </svg>
        </div>
        <div style="display:flex;gap:14px;color:#778497;font-size:10px">
          <span><b style="color:#319783">●</b> ก่อน Cut-off</span>
          <span><b style="color:#db5b63">●</b> ตั้งแต่ 16:00 น. เป็นต้นไป</span>
        </div>`;
    }

    function renderDepartmentChart() {
      const container = $("#department-chart");

      if (!jobs.length) {
        container.innerHTML = `<div class="empty">ยังไม่มีข้อมูลใบเบิก</div>`;
        return;
      }

      const departments = new Map();
      for (const job of jobs) {
        const name = job.department || "ไม่ระบุแผนก";
        if (!departments.has(name)) departments.set(name, { total: 0, late: 0 });
        const item = departments.get(name);
        item.total += 1;
        if (isLate(job.receivedTime)) item.late += 1;
      }

      const rows = [...departments.entries()]
        .map(([name, values]) => ({
          name,
          total: values.total,
          percentage: values.total ? Math.round((values.late / values.total) * 100) : 0
        }))
        .sort((a, b) => b.percentage - a.percentage);

      container.innerHTML = rows.map((row) => `
        <div style="margin:13px 0">
          <div style="display:flex;justify-content:space-between;gap:10px;margin-bottom:5px;font-size:11px">
            <strong>${escapeHtml(row.name)}</strong>
            <span style="color:#748195">${row.percentage}% · ${row.total} JOB</span>
          </div>
          <div style="height:10px;border-radius:99px;background:#edf1f5;overflow:hidden">
            <div style="height:100%;width:${row.percentage}%;border-radius:99px;background:linear-gradient(90deg,#eeb954,#d9535d)"></div>
          </div>
        </div>
      `).join("");
    }

    function renderTable() {
      const body = $("#job-table-body");
      const statusFilter = $("#status-filter").value;
      const lateFilter = $("#late-filter").value;
      const query = $("#search").value.trim().toLowerCase();

      let filtered = jobs.filter((job) => {
        if (statusFilter && job.status !== statusFilter) return false;
        if (lateFilter === "late" && !isLate(job.receivedTime)) return false;
        if (lateFilter === "ontime" && isLate(job.receivedTime)) return false;
        if (query && !`${job.jobNumber} ${job.department}`.toLowerCase().includes(query)) return false;
        return true;
      });

      $("#empty-notice").hidden = jobs.length !== 0;
      $("#table-wrap").hidden = jobs.length === 0;

      if (!jobs.length) {
        body.innerHTML = "";
        return;
      }

      if (!filtered.length) {
        body.innerHTML = `<tr><td colspan="12" class="muted">ไม่พบรายการที่ตรงกับตัวกรอง</td></tr>`;
        return;
      }

      body.innerHTML = filtered.map((job) => {
        const processing = job.pickedTime
          ? formatDuration(elapsedMinutes(job.receivedTime, job.pickedTime))
          : "—";
        const waiting = job.handoverTime && job.pickedTime
          ? formatDuration(elapsedMinutes(job.pickedTime, job.handoverTime))
          : "—";

        return `
          <tr>
            <td><strong>${escapeHtml(job.jobNumber)}</strong></td>
            <td>${escapeHtml(job.department)}</td>
            <td>${shortTime(job.receivedTime)}</td>
            <td>${shortTime(job.inProgressTime)}</td>
            <td>${shortTime(job.pickedTime)}</td>
            <td>${shortTime(job.handoverTime)}</td>
            <td>${shortTime(job.canceledTime)}</td>
            <td><span class="badge ${escapeHtml(job.status)}">${statusLabel(job.status)}</span></td>
            <td>${isLate(job.receivedTime) ? `<span class="late-tag">🔴 ใบเบิกเย็น</span>` : `<span style="color:#19845f">🟢 ปกติ</span>`}</td>
            <td>${processing}</td>
            <td>${waiting}</td>
            <td>${job.status === "cancelled" ? `<button class="btn soft small" data-action="evidence" data-id="${escapeHtml(job.id)}">📄 ดูหลักฐาน</button>` : "—"}</td>
          </tr>`;
      }).join("");
    }

    function render() {
      $("#cutoff-chip").textContent = "16:00";
      renderKpis();
      renderQueue();
      renderHourlyChart();
      renderDepartmentChart();
      renderTable();
    }

    function openEvidence(id) {
      const job = jobs.find((item) => item.id === id);
      if (!job) return;

      const startWork = job.inProgressTime || job.receivedTime;
      const wasted = job.canceledTime
        ? elapsedMinutes(startWork, job.canceledTime)
        : null;

      const fields = [
        ["เลขที่ JOB", job.jobNumber],
        ["แผนก / ไลน์ผลิต", job.department],
        ["เวลารับใบเบิก", job.receivedTime || "—"],
        ["เวลาเริ่มจัด", job.inProgressTime || "ไม่มีการบันทึก"],
        ["เวลาจัดเสร็จ", job.pickedTime || "ยังจัดไม่เสร็จ"],
        ["เวลายกเลิก", job.canceledTime || "—"],
        ["เวลางานที่เสียไป", wasted === null ? "—" : `${wasted} นาที (${formatDuration(wasted)})`],
        ["ผู้สั่งยกเลิก PN/PD", job.canceledBy || "—"],
        ["สาเหตุการยกเลิก", job.cancelReason || "—"]
      ];

      $("#evidence-content").innerHTML = fields.map(([label, value]) => `
        <div class="evidence-row">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `).join("");

      $("#evidence-modal").classList.add("open");
    }

    function exportCsv() {
      if (!jobs.length) {
        window.alert("ยังไม่มีข้อมูลใบเบิกสำหรับ Export");
        return;
      }

      const headers = [
        "JOB", "Department", "Status",
        "Received Time", "In Progress Time", "Picked Time",
        "Handover Time", "Canceled Time", "Late Requisition",
        "Cancellation By", "Cancellation Reason", "Wasted Labor Minutes"
      ];

      const rows = jobs.map((job) => {
        const wasted = job.canceledTime
          ? elapsedMinutes(job.inProgressTime || job.receivedTime, job.canceledTime)
          : "";
        return [
          job.jobNumber,
          job.department,
          statusLabel(job.status),
          job.receivedTime || "",
          job.inProgressTime || "",
          job.pickedTime || "",
          job.handoverTime || "",
          job.canceledTime || "",
          isLate(job.receivedTime) ? "Yes" : "No",
          job.canceledBy || "",
          job.cancelReason || "",
          wasted
        ];
      });

      const csv = [headers, ...rows]
        .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
        .join("\r\n");

      const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `warehouse_jobs_${localTimestamp().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(url);
      playTick();
    }

    async function startCamera() {
      const note = $("#scanner-note");
      const video = $("#scanner-video");
      const scannerBox = $("#scanner-box");

      if (!("BarcodeDetector" in window)) {
        note.textContent = "เบราว์เซอร์นี้ยังไม่รองรับ BarcodeDetector กรุณาใช้ช่องพิมพ์ด่วนแทน";
        scannerBox.classList.add("open");
        return;
      }

      if (!navigator.mediaDevices?.getUserMedia) {
        note.textContent = "ไม่สามารถเปิดกล้องได้ กรุณาใช้ HTTPS หรือ localhost และอนุญาตสิทธิ์กล้อง";
        scannerBox.classList.add("open");
        return;
      }

      try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } },
          audio: false
        });
        video.srcObject = cameraStream;
        await video.play();
        scannerBox.classList.add("open");
        $("#camera-start").hidden = true;
        $("#camera-stop").hidden = false;

        const detector = new BarcodeDetector({
          formats: ["qr_code", "code_128", "code_39", "ean_13", "ean_8", "upc_a"]
        });
        scanLoopActive = true;
        note.textContent = "กำลังสแกน…";

        const scan = async () => {
          if (!scanLoopActive || !cameraStream) return;

          try {
            const results = await detector.detect(video);
            if (results.length) {
              const raw = results[0].rawValue || "";
              const jobMatch = raw.match(/JOB-\d+/i) || raw.match(/\b\d{4}\b/);
              if (jobMatch) {
                $("#quick-job").value = jobMatch[0];
                stopCamera();
                addQuickJob();
                return;
              }
            }
          } catch (error) {
            note.textContent = "อ่านบาร์โค้ดไม่สำเร็จ ลองปรับระยะกล้อง";
          }
          window.requestAnimationFrame(scan);
        };

        window.requestAnimationFrame(scan);
      } catch (error) {
        note.textContent = "เปิดกล้องไม่ได้ กรุณาตรวจสอบสิทธิ์กล้องของเบราว์เซอร์";
        scannerBox.classList.add("open");
      }
    }

    function stopCamera() {
      scanLoopActive = false;
      if (cameraStream) {
        cameraStream.getTracks().forEach((track) => track.stop());
        cameraStream = null;
      }
      $("#scanner-video").srcObject = null;
      $("#camera-start").hidden = false;
      $("#camera-stop").hidden = true;
      $("#scanner-note").textContent = "หันกล้องไปที่บาร์โค้ดหรือ QR Code ของ JOB";
    }

    $("#bulk-submit").addEventListener("click", addJobsFromBulk);
    $("#quick-submit").addEventListener("click", addQuickJob);
    $("#quick-job").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        addQuickJob();
      }
    });

    $("#active-queue").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button) return;

      const { action, id } = button.dataset;
      if (action === "start") setStatus(id, "in_progress");
      if (action === "picked") setStatus(id, "completed");
      if (action === "handover") setStatus(id, "handed_over");
      if (action === "cancel") openCancelModal(id);
    });

    $("#job-table-body").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action='evidence']");
      if (button) openEvidence(button.dataset.id);
    });

    $("#cancel-confirm").addEventListener("click", confirmCancel);
    $("#cancel-dismiss").addEventListener("click", closeCancelModal);
    $("#evidence-close").addEventListener("click", () => $("#evidence-modal").classList.remove("open"));
    $("#evidence-print").addEventListener("click", () => window.print());
    $("#export-csv").addEventListener("click", exportCsv);
    $("#camera-start").addEventListener("click", startCamera);
    $("#camera-stop").addEventListener("click", stopCamera);

    ["status-filter", "late-filter"].forEach((id) => {
      $(`#${id}`).addEventListener("change", renderTable);
    });
    $("#search").addEventListener("input", renderTable);

    $("#evidence-modal").addEventListener("click", (event) => {
      if (event.target.id === "evidence-modal") {
        $("#evidence-modal").classList.remove("open");
      }
    });
    $("#cancel-modal").addEventListener("click", (event) => {
      if (event.target.id === "cancel-modal") closeCancelModal();
    });

    render();
    $("#department").focus();
  </script>
</body>
</html>
