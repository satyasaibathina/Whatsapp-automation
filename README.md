# 🤖 WhatsApp Payout & Flash Reporting Automation

> Automated end-to-end pipeline for generating and delivering **Payout Reports** and **LogiWhiz Clearline Flash Reports** to WhatsApp groups daily via GitHub Actions + Oracle VPS.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  GITHUB ACTIONS (Cloud Runner — runs daily on schedule)     │
│                                                             │
│  payout_pipeline.yml → master_pipeline.py --upto-step3     │
│    Step 0: Selenium → Download Excel from Whizzard Portal   │
│    Step 1: Process Excel files (HK, Staff, Fleet, Sites)   │
│    Step 2: Excel → PNG images (openpyxl + Pillow)          │
│    Step 3: Encode PNGs to Base64 → POST /send-report       │
│                                                             │
│  flash_pipeline.yml → master_pipeline.py --step4-only      │
│    Step 4: Playwright → LogiWhiz screenshots               │
│            Encode PNGs to Base64 → POST /send-flash        │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP POST (Base64 image payload)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ORACLE VPS (Ubuntu 24.04 — 129.159.231.22:49301)          │
│                                                             │
│  whatsapp_service.js (PM2 — whatsapp-bot)                  │
│    POST /send-report → Decodes Base64 → Sends HD image     │
│    POST /send-flash  → Decodes Base64 → Sends HD image     │
│    GET  /status      → Returns { status: "ready" }         │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
repo root/
├── master_pipeline.py          # 🎯 Main orchestrator — runs Steps 0–4
├── step1_process_hk.py         # Step 1a — Housekeeping payout processor
├── step1b_process_staff.py     # Step 1b — IC Staff payout processor
├── step1c_process_site_rental.py # Step 1c — Site Rental processor
├── step1d_process_fleet.py     # Step 1d — IC Fleet payout processor
├── step2_excel_to_image.py     # Step 2 — Convert Excel reports → PNG images
├── step4_flash.py              # Step 4 — LogiWhiz Clearline Flash Report
├── env_loader.py               # Loads .env file into os.environ
├── requirements.txt            # Python dependencies for GitHub Actions runner
├── send_alert_email.py         # Email alert utility
└── .github/
    └── workflows/
        ├── payout_pipeline.yml # 📅 Runs Steps 1-3 daily at 7:00 AM IST
        └── flash_pipeline.yml  # 📅 Runs Step 4 daily at 8:00 AM IST
```

---

## 🔄 Pipeline 1 — Payout Report (Steps 1–3)

**Schedule:** Daily at **7:00 AM IST** (`30 1 * * *` UTC)  
**Workflow file:** `.github/workflows/payout_pipeline.yml`  
**Command:** `python master_pipeline.py --upto-step3`

### What it does:

| Step | Script | Action |
|------|--------|--------|
| Step 0 | `download_all()` in `master_pipeline.py` | Selenium logs into Whizzard Admin Portal and downloads Excel files for IC Staff, IC Fleet, Housekeeping, and Site Rental |
| Step 1 | `step1_process_hk.py`, `step1b_process_staff.py`, etc. | Filters and styles each Excel file, outputs a clean `_Pending.xlsx` |
| Step 2 | `step2_excel_to_image.py` | Converts each pending Excel to a PNG image |
| Step 3 | `POST /send-report` → VPS | Encodes images to Base64 and sends them to the Oracle VPS which dispatches them to the WhatsApp group |

### Reports Generated:
| Report | Pending Filter | Exclusions |
|--------|---------------|------------|
| Housekeeping | `Status=Pay` AND `RM Status=Pending` | None |
| IC Staff | `Payment Status=Pending` | Dipayan Chatterjee, Avik Debnath |
| IC Fleet | `Status=Pay` | Dipayan Chatterjee, Avik Debnath |
| Site Rental | Pending records | Skipped before 5th of month |

> ⚡ Only categories with `pendingCount > 0` generate an image and a WhatsApp message.

---

## 🔄 Pipeline 2 — Flash Report (Step 4)

**Schedule:** Daily at **8:00 AM IST** (`30 2 * * *` UTC)  
**Workflow file:** `.github/workflows/flash_pipeline.yml`  
**Command:** `python master_pipeline.py --step4-only`

### What it does:
1. Playwright logs into `https://logiwhizdevelopment.com/actual-cost`
2. Filters data to previous month, takes table screenshots for 4 combinations:

| Run | Entity | Category | Output File |
|-----|--------|----------|-------------|
| 1 | MLL | Vendor | `MLL_Vendor_combined.png` |
| 2 | WZ | Vendor | `WZ_Vendor_combined.png` |
| 3 | MLL | Expense | `MLL_Expense_combined.png` |
| 4 | WZ | Expense | `WZ_Expense_combined.png` |

3. Combines Table 1 (Pending by Status) + Table 2 (Pending by Category) into one stacked image
4. Encodes images to Base64 and sends to the Oracle VPS via `POST /send-flash`

---

## 🖥️ Oracle VPS — WhatsApp Service

**IP:** `129.159.231.22`  
**Port:** `49301`  
**Service:** `whatsapp_service.js` managed by PM2 as `whatsapp-bot`  
**Status URL:** `http://129.159.231.22:49301/status`

### Endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/status` | Returns `{ status: "ready" }` when WhatsApp connected |
| `POST` | `/send-report` | Receives Base64 payout images → sends to WhatsApp group |
| `POST` | `/send-flash` | Receives Base64 flash screenshots → sends to WhatsApp group |

### How to Push Code to VPS:
```powershell
# From local Windows PowerShell — upload updated whatsapp_service.js
scp -i "C:\Users\Admin\Downloads\you\oracle.pem" "d:\whatsapp-baileys\Whatsapp automation\vps_deploy\whatsapp_service.js" ubuntu@129.159.231.22:~/whatsapp-service/
```

### How to Restart the Service on VPS:
```bash
# SSH into VPS
ssh -i "C:\Users\Admin\Downloads\you\oracle.pem" ubuntu@129.159.231.22

# Clean restart (required to clear PM2 memory cache)
cd ~/whatsapp-service
pm2 delete whatsapp-bot
pm2 start whatsapp_service.js --name "whatsapp-bot"
pm2 logs whatsapp-bot --lines 20
```

> ⚠️ Always use `pm2 delete` + `pm2 start`. Never use `pm2 restart` — it keeps old environment variables cached in memory.

---

## 🔑 GitHub Secrets Configuration

Go to **GitHub → Settings → Secrets and Variables → Actions** and set:

| Secret | Description |
|--------|-------------|
| `WA_SERVICE_URL` | `http://129.159.231.22:49301` |
| `WA_API_KEY` | `WHIZZARD_SECRET_API_KEY_2026` |
| `WA_GROUP_ID` | WhatsApp group ID (e.g. `120363424704050063@g.us`) |
| `WA_TAG_PERSON` | Phone to tag in payout reports (e.g. `919014054696`) |
| `WA_TAG_PERSON_ALT` | Alternate tag phone (days 2–5 of month) |
| `WA_TAGS_MLL_VENDOR` | Comma-separated phones for MLL Vendor flash |
| `WA_TAGS_WZ_VENDOR` | Comma-separated phones for WZ Vendor flash |
| `WA_TAGS_MLL_EXPENSE` | Comma-separated phones for MLL Expense flash |
| `WA_TAGS_WZ_EXPENSE` | Comma-separated phones for WZ Expense flash |
| `WHIZZARD_MOBILE` | Whizzard admin portal login mobile |
| `WHIZZARD_PASSWORD` | Whizzard admin portal login password |
| `LOGIWHIZ_USERNAME` | LogiWhiz portal login username |
| `LOGIWHIZ_PASSWORD` | LogiWhiz portal login password |

---

## ▶️ How to Run Manually

### Run from GitHub Actions UI (Cloud):
1. Go to your repository → **Actions** tab
2. Select the workflow (**Payout Pipeline** or **Flash Report**)
3. Click **Run workflow** → **Run workflow** button

### Run Locally:
```bash
# Full pipeline (Steps 0–3 + Step 4)
python master_pipeline.py

# Payout only (Steps 0–3)
python master_pipeline.py --upto-step3

# Flash report only (Step 4)
python master_pipeline.py --step4-only

# Dry run (skips WhatsApp send — for testing)
python master_pipeline.py --dry-run
```

---

## 🔧 Troubleshooting

### ❌ HTTP Error 400: Bad Request on `/send-flash`
**Cause:** `WA_GROUP_ID` is missing in the GitHub Actions environment.  
**Fix:** Ensure `WA_GROUP_ID: ${{ secrets.WA_GROUP_ID }}` is in the `env:` block of `flash_pipeline.yml`.

### ❌ VPS returns old behavior after code upload
**Cause:** PM2 has the old code cached in memory.  
**Fix:** Run `pm2 delete whatsapp-bot` then `pm2 start whatsapp_service.js --name "whatsapp-bot"`.

### ❌ Images blurry in WhatsApp
**Cause:** Media sent without HD flag.  
**Fix:** Ensure `{ sendMediaAsHd: true }` is set in all `client.sendMessage()` calls in `whatsapp_service.js`.

### ❌ WhatsApp session expired on VPS
**Symptoms:** `/status` endpoint returns `{ status: "initializing" }` and never becomes ready.  
**Fix:** SSH into VPS, run `pm2 logs whatsapp-bot` and look for a QR code URL. Open it and scan with WhatsApp.

### ❌ GitHub Actions fails on Ubuntu 24.04 with `apt-get` errors
**Cause:** Old `apt-get` packages like `libgconf-2-4` no longer exist on Ubuntu 24.04.  
**Fix:** Remove manual `apt-get` installs from YAML. Use `playwright install-deps` instead.

---

## 🖥️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Report download | Python, Selenium, ChromeDriver |
| Excel processing | pandas, openpyxl |
| Image generation | Pillow (PIL) |
| Flash screenshots | Python, Playwright (async Chromium) |
| WhatsApp service | Node.js, whatsapp-web.js, PM2 |
| CI/CD | GitHub Actions |
| Hosting | Oracle Cloud Free Tier (Ubuntu 24.04) |

---

## 👤 Author

**Maintained by:** Bathina Satya Sai  
**Alert email:** satyasaibathina@gmail.com  
**Automation email:** automationscentral@gmail.com

---

*Last updated: July 2026*
