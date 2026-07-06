# 📊 LogiWhiz Automation Suite — README

> Complete documentation for the end-to-end automation pipeline covering **SharePoint Revenue Reconciliation**, **Payout Report Delivery**, and **LogiWhiz Flash Report** delivery via WhatsApp.

---

## 📁 Repository Structure

```
d:\Whatsapp automation\
├── master_pipeline.py          # 🎯 Main orchestrator — runs Steps 0–4
├── step1_process_hk.py         # Step 1a — Housekeeping payout processor
├── step1b_process_staff.py     # Step 1b — IC Staff payout processor
├── step1c_process_site_rental.py # Step 1c — Site Rental processor
├── step2_excel_to_image.py     # Step 2 — Convert Excel reports → PNG images
├── step3_send_whatsapp.js      # Step 3 — (Legacy) WhatsApp sender
├── step4_flash.py              # Step 4 — LogiWhiz Clearline Flash Report
├── step4_send_whatsapp.js      # Step 4 WhatsApp sender (standalone)
├── whatsapp_service.js         # 🔌 Persistent HTTP WhatsApp service (port 3000)
├── check_whatsapp_status.js    # Health check for WhatsApp session
├── send_alert_email.py         # Email alert when WhatsApp session expires
├── setup_whatsapp_session.js   # One-time QR scan setup
├── send_now.py                 # Manual WhatsApp send trigger
├── run_pipeline.bat            # ▶ Run master_pipeline.py (scheduled)
├── run_whatsapp_service.bat    # ▶ Start WhatsApp persistent service
├── check_session_daily.bat     # ▶ Daily health check (Task Scheduler)
├── output/                     # Generated Excel files & screenshot PNGs
└── .wwebjs_auth/               # WhatsApp session storage (do not delete)

Remote Ubuntu Server (129.159.235.105):
├── /home/ubuntu/revenue.py     # SharePoint downloader + MongoDB inserter
├── /home/ubuntu/auth.json      # SharePoint cookie auth (31 cookies)
├── /home/ubuntu/downloads/     # Downloaded Excel files per client
│   ├── MLL/
│   ├── WZ/
│   ├── MLL_LMD/
│   └── WZ_LMD/
└── /home/ubuntu/revenue_cron.log  # Cron execution log
```

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────┐
│  LOCAL WINDOWS PC (d:\Whatsapp automation\)         │
│                                                     │
│  Task Scheduler → run_pipeline.bat                  │
│         ↓                                           │
│  master_pipeline.py (Steps 0–4)                     │
│    Step 0: Selenium → Whizzard Admin Portal         │
│    Step 1: Process Excel files (HK, Staff, Sites)   │
│    Step 2: Excel → PNG images                       │
│    Step 3: POST → WhatsApp Service (localhost:3000) │
│    Step 4: Playwright → LogiWhiz Flash screenshots  │
│         ↓                                           │
│  whatsapp_service.js (Node.js, port 3000)           │
│    POST /send-report  → Payout images               │
│    POST /send-flash   → Flash report images         │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  REMOTE UBUNTU SERVER (Oracle Cloud, 129.159.235.105)│
│                                                     │
│  Cron Job (every 5 hrs) → revenue.py               │
│    ↓  SharePoint REST API (auth.json cookies)       │
│    ↓  Download 4 Excel reports                      │
│    ↓  Parse with openpyxl                           │
│    ↓  Insert to MongoDB (LogiWhiz_Trackking DB)     │
└─────────────────────────────────────────────────────┘
```

---

## 🔄 Pipeline A — Payout Report Pipeline (master_pipeline.py)

Runs automatically via Windows Task Scheduler on the **5th of every month** (or manually any time). Skips Steps 0–3 during the grace period (1st–4th) to allow data to be finalized.

### Step 0 — Download from Whizzard Admin Portal

**Script:** `master_pipeline.py → download_all()`  
**Tool:** Selenium + ChromeDriver (headless)  
**Portal:** `https://adminpanel.whizzard.in`

Downloads 5 Excel files for the previous month:

| File | Report | Whizzard Section |
|------|--------|-----------------|
| `Staff_*.xlsx` | IC Staff Monthly Payments | Payouts → Staff |
| `Fleet_*.xlsx` | IC Fleet Final Payout | Payouts → Fleet |
| `HK_*.xlsx` | House Keeping Payout | Payouts → Housekeeping |
| `ActiveSites_*.xlsx` | Active/Disabled Sites | Sites → Default Tab |
| `SiteRental_*.xlsx` | Site Rental Payout | Sites → Rentals Tab |

> Files are saved to `output/` directory. The `_temp/` subdirectory is used as Chrome's download target and cleaned before each run.

---

### Step 1 — Process Excel Reports

Three sub-scripts filter and style the downloaded Excel files:

**`step1_process_hk.py`** — Housekeeping  
- Sheet: `System Format`  
- Filter: `Status = Pay` AND `RM Status = Pending`  
- Output: `output/HK_Pending.xlsx` (merged OM Name cells, color-coded rows)

**`step1b_process_staff.py`** — IC Staff  
- Filter: `Payment Status = Pending`  
- Output: `output/Staff_Pending.xlsx`

**`step1c_process_site_rental.py`** — Site Rental  
- Joins `SiteRental` + `ActiveSites` data  
- Filter: pending rental records  
- Output: `output/SiteRental_Pending.xlsx`

> If a report has **0 pending records**, no image is generated and no WhatsApp message is sent for that category.

---

### Step 2 — Excel → PNG Image

**Script:** `step2_excel_to_image.py`  
Converts each styled `_Pending.xlsx` into a PNG image using `openpyxl` + `Pillow`. The image is saved to `output/` (e.g., `HK.png`, `Staff.png`, `SiteRental.png`).

---

### Step 3 — Send via WhatsApp

**Script:** `whatsapp_service.js` (endpoint: `POST /send-report`)  
**Group:** LogiWhiz - Central + FinTech + Ops  
**Tag Person:** `919014054696`

For each report with `pendingCount > 0`, sends a caption + PNG image to the WhatsApp group with a tagged mention.

Sample caption:
```
Hi @[contact] sir,
Kindly find the payout status of Housekeeping for the month of May 2026
```

---

### Step 4 — LogiWhiz Clearline Flash Report

**Script:** `step4_flash.py`  
**Tool:** Playwright (async, headless Chromium)  
**Portal:** `https://logiwhizdevelopment.com/actual-cost`

Captures **8 screenshots** (4 combined images) across 4 filter combinations:

| Run | Entity | Payment Category | Output File |
|-----|--------|-----------------|-------------|
| 1 | MLL | Vendor | `MLL_Vendor_combined.png` |
| 2 | WZ | Vendor | `WZ_Vendor_combined.png` |
| 3 | MLL | Expense | `MLL_Expense_combined.png` |
| 4 | WZ | Expense | `WZ_Expense_combined.png` |

Each combined image = Table 1 (Pending by Status) stacked on Table 2 (Pending by Category).

**Sends via:** `POST /send-flash` → `whatsapp_service.js`

**Tags per entity:**
- MLL: `@919899528526 @919833989902 @917763066066 @919820331505`
- WZ: `@919899528526 @918892107032 @919833989902`

---

## 🔄 Pipeline B — Revenue Reconciliation (Remote Ubuntu Server)

Runs automatically via **cron job every 5 hours** on the Oracle Cloud Ubuntu server.

### Cron Schedule

```bash
# Runs at: 00:00, 05:00, 10:00, 15:00, 20:00 UTC daily
0 */5 * * * cd /home/ubuntu && venv/bin/python -u revenue.py >> /home/ubuntu/revenue_cron.log 2>&1
```

### How It Works

**Script:** `/home/ubuntu/revenue.py`

**Step 1 — Download from SharePoint**

Uses SharePoint REST API with cookies from `auth.json` (31 session cookies) to download 4 Excel reports directly (no browser needed — pure HTTP):

| Report Key | SharePoint File GUID | Download Path |
|-----------|---------------------|---------------|
| MLL | `95713CE3-8442-4970-AC70-CACD3E18311F` | `downloads/MLL/MLL_Downloaded.xlsx` |
| WZ | `e778d689-0c93-48ce-b066-42bdd1cf4a37` | `downloads/WZ/WZ_Downloaded.xlsx` |
| MLL_LMD | `2BB846F7-A277-4B85-8256-8D2004A732FB` | `downloads/MLL_LMD/MLL_LMD_Downloaded.xlsx` |
| WZ_LMD | `60EDD568-0A39-41FD-AD08-879E420BD50A` | `downloads/WZ_LMD/WZ_LMD_Downloaded.xlsx` |

**Step 2 — Parse & Insert to MongoDB**

- Parses each downloaded Excel using `openpyxl`
- Matches month names to sheet tabs (e.g., `"july"` → `"July-25"`)
- Auto-adds **last month** to the process list on each run
- Inserts records into MongoDB `LogiWhiz_Trackking` database:

| Report | Collection | Mode |
|--------|-----------|------|
| MLL | `Mll_revenue_Main` | Clear & re-insert |
| WZ | `Wz_revenue_Main` | Clear & re-insert |
| MLL_LMD | `Mll_revenue_Main` | **Append only** |
| WZ_LMD | `Wz_revenue_Main` | **Append only** |

**Month Configuration:**

```python
# MLL / WZ — Full year (July 2025 → current month)
months = ["july", "August", "september", "October", "november",
          "december", "january", "Feburary", "March", "April", "May"]

# MLL_LMD / WZ_LMD — Last 2 months only
months = ["April", "May"]
```

---

## 🔌 WhatsApp Service

**Script:** `whatsapp_service.js`  
**Port:** `3000`  
**Session Storage:** `.wwebjs_auth/` (persists across restarts)

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/status` | Returns `{ status: "ready" }` when connected |
| `POST` | `/send-report` | Sends payout report images (Steps 1–3) |
| `POST` | `/send-flash` | Sends LogiWhiz flash screenshots (Step 4) |

### Starting the Service

```bat
:: Option 1 — Run manually (auto-restarts on crash)
run_whatsapp_service.bat

:: Option 2 — Run directly
node whatsapp_service.js
```

### Health Check

```bat
node check_whatsapp_status.js
```

Returns `ready` or `offline`. If offline, triggers an **email alert** to `satyasaibathina@gmail.com` automatically.

---

## 🚀 How to Run

### Run Full Pipeline (Steps 0–4)

```bat
cd "d:\Whatsapp automation"
run_pipeline.bat
```

Or directly:
```bat
"C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe" master_pipeline.py
```

### Run Step 4 Only (LogiWhiz Flash)

```bat
"C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe" master_pipeline.py --step4-only
```

### Dry Run (No WhatsApp send)

```bat
"C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe" master_pipeline.py --dry-run
```

### Run Up to Step 3 Only (Skip Step 4)

```bat
"C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe" master_pipeline.py --upto-step3
```

### Run Revenue Script on Remote Server

```bat
ssh -i C:\Users\Admin\Downloads\oracle-openssh.pem ubuntu@129.159.235.105 "cd /home/ubuntu && venv/bin/python -u revenue.py"
```

---

## 🖥️ Technology Stack

### Local PC (Windows)

| Component | Technology |
|-----------|-----------|
| Payout download | Python 3.14, Selenium, ChromeDriver, webdriver-manager |
| Excel processing | pandas, openpyxl |
| Image generation | openpyxl, Pillow |
| Flash screenshots | Python 3.14, Playwright (async, Chromium) |
| WhatsApp service | Node.js, whatsapp-web.js, LocalAuth |
| Session health check | Node.js, axios / http |
| Email alerts | Python smtplib (Gmail SMTP) |

### Remote Ubuntu Server (Oracle Cloud)

| Component | Technology |
|-----------|-----------|
| SharePoint download | Python 3, `requests` (REST API + cookie auth) |
| Excel parsing | openpyxl |
| Database | MongoDB (`pymongo`) |
| Python env | `venv` at `/home/ubuntu/venv/` |
| Scheduling | Linux `cron` |

---

## ⚙️ Configuration & Credentials

### Local PC (master_pipeline.py)

```python
CHROME_PATH       = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_PROFILE_PATH = r"C:\Users\Admin\AppData\Local\Google\Chrome\User Data"
LOGIN_URL         = "https://adminpanel.whizzard.in/#/login"
MOBILE_NUMBER     = "6281111894"
PASSWORD          = "Mahesh@2026"
WA_GROUP_ID       = "919014054696-1587130182@g.us"
```

### Remote Server (revenue.py — environment variables)

Set in `~/.bashrc` on the Ubuntu server:

```bash
export MONGODB_URL="mongodb+srv://..."
export SHAREPOINT_USER="..."
export SHAREPOINT_PASS="..."
```

> **auth.json** stores the SharePoint session cookies. It must be re-generated by logging in via Playwright whenever the session expires (typically every 30–90 days).

---

## 📅 Scheduled Tasks (Windows Task Scheduler)

| Task | Script | Schedule |
|------|--------|----------|
| Run Pipeline | `run_pipeline.bat` | Monthly — 5th of each month, 9:00 AM |
| Check WA Session | `check_session_daily.bat` | Daily — 9:00 AM |

### Cron Job (Ubuntu Server)

```
0 */5 * * * cd /home/ubuntu && venv/bin/python -u revenue.py >> revenue_cron.log 2>&1
```

---

## 🔧 Maintenance & Troubleshooting

### WhatsApp Session Expired

**Symptoms:** `check_whatsapp_status.js` returns `offline`; email alert received.

**Fix:**
```bash
# On local PC — stop and restart the service; scan QR code
node setup_whatsapp_session.js
# OR start whatsapp_service.js and watch the console for QR code
node whatsapp_service.js
```
A `qr.png` is saved in the folder for easy scanning.

---

### SharePoint auth.json Expired

**Symptoms:** `revenue.py` logs `403 Forbidden` or `401 Unauthorized`.

**Fix:**
1. Run the Playwright login script locally to generate a fresh `auth.json`
2. Copy it to the server:
```bat
scp -i C:\Users\Admin\Downloads\oracle-openssh.pem auth.json ubuntu@129.159.235.105:/home/ubuntu/auth.json
```

---

### LogiWhiz Flash Report Failing (XPath errors)

**Symptoms:** `step4_flash.py` times out clicking a tab or filter.

**Diagnosis:** The LogiWhiz UI may have changed. Check the stable selectors currently used:

| Element | Selector |
|---------|----------|
| Pending Cost tab | `button[role='tab'][id$='trigger-pending-cost']` |
| Date picker | `button[aria-label='Service month']` |
| Entity dropdown | `#actual-filter-entity` |
| Payment Category | `#actual-filter-paymentCategory` |

**Fix:** Open `step4_flash.py` and update selectors using browser DevTools inspection on `https://logiwhizdevelopment.com/actual-cost`.

---

### Check Remote Revenue Logs

```bat
:: Copy latest log locally
scp -i C:\Users\Admin\Downloads\oracle-openssh.pem ubuntu@129.159.235.105:/home/ubuntu/revenue_cron.log ./remote_revenue_cron.log
```

---

### MongoDB Not Connecting (revenue.py)

**Symptoms:** `ConnectionFailure` in cron log.

**Fix:** Ensure `MONGODB_URL` is correctly exported in `~/.bashrc`:
```bash
bash -ic 'echo $MONGODB_URL'  # should print the connection string
```

---

## 📊 MongoDB Database Schema

**Database:** `LogiWhiz_Trackking`

| Collection | Source | Months Covered |
|-----------|--------|---------------|
| `Mll_revenue_Main` | MLL (main) | Jul 2025 → current |
| `Mll_revenue_Main` | MLL_LMD (append) | Last 2 months |
| `Wz_revenue_Main` | WZ (main) | Jul 2025 → current |
| `Wz_revenue_Main` | WZ_LMD (append) | Last 2 months |

Each document corresponds to one row in the SharePoint Excel sheet, tagged with `year` and `month` fields.

---

## 📋 Log Files

| Log | Location | Purpose |
|-----|----------|---------|
| Pipeline log | `d:\Whatsapp automation\pipeline_log.txt` | Run timestamps from `run_pipeline.bat` |
| Session check log | `d:\Whatsapp automation\session_check_log.txt` | Daily WA health check results |
| Revenue cron log | `/home/ubuntu/revenue_cron.log` (remote) | Full SharePoint download + MongoDB insert output |

---

## 🔑 Server Access

| Resource | Details |
|----------|---------|
| Remote Server IP | `129.159.235.105` |
| SSH User | `ubuntu` |
| SSH Key | `C:\Users\Admin\Downloads\oracle-openssh.pem` |
| Python venv | `/home/ubuntu/venv/` |
| SSH Command | `ssh -i C:\Users\Admin\Downloads\oracle-openssh.pem ubuntu@129.159.235.105` |

---

## 👤 Author & Contact

**Maintained by:** Bathina Satya Sai  
**Alert email:** satyasaibathina@gmail.com  
**Automation email:** automationscentral@gmail.com

---

*Last updated: June 2026*
