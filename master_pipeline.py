"""
MASTER PIPELINE — Local PC (gtyrt folder)
==========================================
Full end-to-end for ALL 3 reports:
  1. 🏠 Housekeeping Payout
  2. 👷 IC Staff Monthly
  3. 🏢 Site Rental Payout

Run:
  python master_pipeline.py
"""

import env_loader
import os, sys, time, json, subprocess, shutil, urllib.request, urllib.error
from datetime import datetime

# Fix for Windows console character encoding issues
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from step1_process_hk           import process_hk_file
from step1b_process_staff        import process_staff_file
from step1c_process_site_rental  import process_site_rental_file
from step1d_process_fleet        import process_fleet_file
from step2_excel_to_image        import excel_to_image

def send_to_whatsapp_service(endpoint, data):
    if "--dry-run" in sys.argv:
        print("   [DRY RUN] Would send to WhatsApp:", json.dumps(data, indent=2))
        return True
    service_url = os.environ.get("WA_SERVICE_URL")
    if not service_url or not service_url.strip():
        if "GITHUB_ACTIONS" in os.environ:
            print("   ⚠️  WA_SERVICE_URL is not set in GitHub Actions. Skipping WhatsApp transmission.")
            return True
        service_url = "http://localhost:3000"
    service_url = service_url.rstrip("/")
    api_key = os.environ.get("WA_API_KEY")
    url = f"{service_url}{endpoint}"
    
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': api_key
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data.get('success', False)
    except urllib.error.URLError as e:
        print(f"❌ Could not connect to WhatsApp Service: {e.reason}")
        print(f"   Target URL: {url}")
        print("   Please ensure that the WhatsApp Service is running and reachable.")
        return False
    except Exception as e:
        print(f"❌ Error sending to WhatsApp service: {e}")
        return False

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
PIPELINE_DIR      = SCRIPT_DIR  # use folder where this script lives
# CHROME_PATH and BASE_PROFILE_PATH can be overridden via environment variables
CHROME_PATH = os.environ.get("CHROME_PATH")
if not CHROME_PATH:
    if sys.platform == "win32":
        CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    else:
        CHROME_PATH = "/usr/bin/google-chrome"

BASE_PROFILE_PATH = os.environ.get("CHROME_PROFILE_PATH")
if not BASE_PROFILE_PATH:
    if sys.platform == "win32":
        BASE_PROFILE_PATH = r"C:\Users\Admin\AppData\Local\Google\Chrome\User Data"
    else:
        # Save profile inside project directory to avoid permission issues on VPS
        BASE_PROFILE_PATH = os.path.join(PIPELINE_DIR, ".chrome_profile")
OUTPUT_DIR        = os.path.join(PIPELINE_DIR, "output")

LOGIN_URL     = "https://adminpanel.whizzard.in/#/login?returnUrl=%2F"
MOBILE_NUMBER = os.environ.get("WHIZZARD_MOBILE")
PASSWORD      = os.environ.get("WHIZZARD_PASSWORD")

# WhatsApp Config
WA_GROUP_ID   = os.environ.get("WA_GROUP_ID")
WA_TAG_PERSON = os.environ.get("WA_TAG_PERSON")
# ══════════════════════════════════════════════════════════


def get_previous_month():
    now = datetime.now()
    if now.month == 1: year, idx = now.year - 1, 12
    else:              year, idx = now.year, now.month - 1
    months = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    return year, months[idx - 1]


def get_driver(temp_dir):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    opts = Options()
    opts.binary_location = CHROME_PATH
    opts.add_argument(f"--user-data-dir={os.path.join(BASE_PROFILE_PATH, 'SeleniumGtyrtPipeline')}")
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_experimental_option("prefs", {
        "download.default_directory": os.path.abspath(temp_dir),
        "download.prompt_for_download": False,
        "directory_upgrade": True,
        "safebrowsing.enabled": True
    })
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def wait_loader(driver, t=60):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    try:
        WebDriverWait(driver, t).until(
            EC.invisibility_of_element_located((By.ID, "loader-wrapper")))
    except: pass


def do_click(driver, xpath, label, t=20):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    try:
        el = WebDriverWait(driver, t).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView({behavior:'instant',block:'center'});", el)
        time.sleep(0.5)
        try: el.click()
        except: driver.execute_script("arguments[0].click();", el)
        print(f"   ✓ {label}")
    except Exception as e:
        print(f"   ⚠ {label}: {e}")


def click_hamburger(driver):
    from selenium.webdriver.common.by import By
    try:
        btn = driver.find_element(By.XPATH, "/html/body/app-root/div/app-layout/header/a[2]/i")
        driver.execute_script("arguments[0].click();", btn)
    except:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "i.fa-bars")
            driver.execute_script("arguments[0].click();", btn)
        except: pass


def ensure_menu_expanded(driver, parent_xpath):
    from selenium.webdriver.common.by import By
    try:
        submenu = driver.find_element(By.XPATH, parent_xpath + '/ul')
        if not submenu.is_displayed():
            driver.find_element(By.XPATH, parent_xpath).click()
            time.sleep(1)
    except: pass


def pick_month(driver, year, month):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    try:
        # Click the header button to switch to years view (e.g. "2026" or "May 2026")
        nav_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//bs-datepicker-navigation-view/button[@class='current']"))
        )
        nav_btn.click()
        time.sleep(0.5)
    except Exception as e:
        pass

    try:
        # Click the year (e.g. 2026)
        year_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, f"//bs-years-calendar-view//span[text()='{year}']"))
        )
        year_btn.click()
        time.sleep(0.5)
    except Exception as e:
        pass

    try:
        # Click the month (e.g. May)
        month_abbr = month[:3] if len(month) > 3 else month
        try:
            month_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, f"//bs-month-calendar-view//span[text()='{month}']"))
            )
        except:
            month_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, f"//bs-month-calendar-view//span[text()='{month_abbr}']"))
            )
        month_btn.click()
        time.sleep(0.5)
    except Exception as e:
        pass


def wait_file_released(filepath, timeout=30):
    """Wait until Windows releases the file lock after Chrome finishes writing."""
    for _ in range(timeout):
        try:
            with open(filepath, 'ab'):
                return True
        except PermissionError:
            time.sleep(1)
    return False


def move_file_safe(src, dest):
    """Move file with retry in case Chrome still holds a lock."""
    wait_file_released(src)
    for attempt in range(10):
        try:
            shutil.move(src, dest)
            return True
        except PermissionError:
            time.sleep(2)
    print(f"   ⚠ Could not move file after retries: {src}")
    return False


def download_file(driver, btn_xpath, label, temp_dir):
    wait_loader(driver)
    initial = set(f for f in os.listdir(temp_dir) if not f.endswith(('.tmp', '.crdownload')))
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        btn = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, btn_xpath)))
        driver.execute_script("arguments[0].scrollIntoView({behavior:'instant',block:'center'});", btn)
        time.sleep(0.5)
        try: btn.click()
        except: driver.execute_script("arguments[0].click();", btn)
        print(f"   ⬇ Downloading: {label}")
    except Exception as e:
        print(f"   ⚠ Button not found [{label}]: {e}")
        return None
    for _ in range(120):
        current = set(f for f in os.listdir(temp_dir) if not f.endswith(('.tmp', '.crdownload')))
        new = current - initial
        if new:
            fname = list(new)[0]
            fpath = os.path.join(temp_dir, fname)
            print(f"   ✅ Got: {fname}")
            # Wait for Chrome to fully release the file
            wait_file_released(fpath)
            return fpath
        time.sleep(1)
    print(f"   ⚠ Timeout: {label}")
    return None


def download_all(year, month):
    print("\n" + "="*60)
    print("  STEP 0 — Download from Whizzard")
    print("="*60)
    print(f"📅 {month} {year}")

    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for f in os.listdir(OUTPUT_DIR):
        fp = os.path.join(OUTPUT_DIR, f)
        if os.path.isfile(fp):
            try: os.remove(fp)
            except: pass

    temp = os.path.join(OUTPUT_DIR, "_temp")
    os.makedirs(temp, exist_ok=True)
    for f in os.listdir(temp):
        fp = os.path.join(temp, f)
        if os.path.isfile(fp):
            try: os.remove(fp)
            except: pass


    driver = get_driver(temp)
    files  = {}

    try:
        # LOGIN
        print("🌐 Logging in...")
        driver.get(LOGIN_URL)
        time.sleep(2)
        wait = WebDriverWait(driver, 30)
        if "login" in driver.current_url:
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[placeholder*='Mobile']"))).send_keys(MOBILE_NUMBER)
            driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(PASSWORD)
            time.sleep(1)
            driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(Keys.ENTER)
            time.sleep(5)
            print("✅ Logged in")

        # 1. IC STAFF
        print("\n👷 IC Staff...")
        click_hamburger(driver)
        do_click(driver, '/html/body/app-root/div/app-layout/aside/ul/li[3]/a/span', "Payouts", 10)
        do_click(driver, '/html/body/app-root/div/app-layout/aside/ul/li[3]/ul/li[6]/a', "Staff Menu", 10)
        click_hamburger(driver)
        do_click(driver, '/html/body/app-root/div/app-layout/app-icstaff-monthly-payout/div[1]/div[2]/div/div/div/div/div[1]/div[1]/div/div/button/i', "Calendar", 10)
        pick_month(driver, year, month)
        f = download_file(driver, '/html/body/app-root/div/app-layout/app-icstaff-monthly-payout/div[1]/div[2]/div/div/div/div/div[2]/div/button', "Staff Main", temp)
        if f:
            dest = os.path.join(OUTPUT_DIR, "Staff_" + os.path.basename(f))
            move_file_safe(f, dest); files['staff'] = dest

        # 1.5 FLEET
        print("\n🚛 Fleet...")
        click_hamburger(driver)
        ensure_menu_expanded(driver, '/html/body/app-root/div/app-layout/aside/ul/li[3]')
        do_click(driver, '/html/body/app-root/div/app-layout/aside/ul/li[3]/ul/li[4]/a', "Fleet Menu", 10)
        click_hamburger(driver)
        do_click(driver, '/html/body/app-root/div/app-layout/app-icfleet-final-payout/div[1]/div[2]/div[1]/div[3]/div[1]/div/div/button/i', "Calendar", 10)
        pick_month(driver, year, month)
        f = download_file(driver, '/html/body/app-root/div/app-layout/app-icfleet-final-payout/div[1]/div[2]/div[1]/div[2]/button', "Fleet Main", temp)
        if f:
            dest = os.path.join(OUTPUT_DIR, "Fleet_" + os.path.basename(f))
            move_file_safe(f, dest); files['fleet'] = dest

        # 2. HOUSEKEEPING
        print("\n🏠 Housekeeping...")
        click_hamburger(driver)
        ensure_menu_expanded(driver, '/html/body/app-root/div/app-layout/aside/ul/li[3]')
        do_click(driver, '/html/body/app-root/div/app-layout/aside/ul/li[3]/ul/li[7]/a', "HK Menu", 10)
        do_click(driver, '/html/body/app-root/div/app-layout/app-house-keeping-staff/div/ul/li[3]/a', "HK Tab", 10)
        click_hamburger(driver)
        do_click(driver, '/html/body/app-root/div/app-layout/app-house-keeping-staff/div/div[2]/div[2]/div/div/div/div[1]/div[3]/div/div/button/i', "Calendar", 10)
        pick_month(driver, year, month)
        f = download_file(driver, '/html/body/app-root/div/app-layout/app-house-keeping-staff/div/div[2]/div[2]/div/div/div/div[1]/div[4]/button[1]', "HK", temp)
        if f:
            dest = os.path.join(OUTPUT_DIR, "HK_" + os.path.basename(f))
            move_file_safe(f, dest); files['hk'] = dest

        # 3. SITES
        if datetime.now().day >= 5:
            print("\n🏢 Sites...")
            click_hamburger(driver)
            ensure_menu_expanded(driver, '/html/body/app-root/div/app-layout/aside/ul/li[5]')
            do_click(driver, '/html/body/app-root/div/app-layout/aside/ul/li[5]/ul/li[3]/a', "Sites Menu", 10)
            click_hamburger(driver)

            # 3a. Active/Disabled Sites — default tab li[1], no calendar
            print("   📋 Active/Disabled Sites...")
            do_click(driver, '/html/body/app-root/div/app-layout/app-sites/div/ul/li[1]/a', "Default Tab", 10)
            time.sleep(1)
            f = download_file(driver, '/html/body/app-root/div/app-layout/app-sites/div/div[2]/div/div/div[1]/button[1]', "Active Sites", temp)
            if f:
                dest = os.path.join(OUTPUT_DIR, "ActiveSites_" + os.path.basename(f))
                move_file_safe(f, dest); files['active_sites'] = dest

            # 3b. Site Rentals — tab li[4], pick month
            print("   🏢 Site Rentals...")
            do_click(driver, '/html/body/app-root/div/app-layout/app-sites/div/ul/li[4]/a', "Rentals Tab", 10)
            time.sleep(1)
            do_click(driver, '/html/body/app-root/div/app-layout/app-sites/div/div[2]/div/div/div[1]/div[2]/div/div/div/button/i', "Calendar", 10)
            pick_month(driver, year, month)
            f = download_file(driver, '/html/body/app-root/div/app-layout/app-sites/div/div[2]/div/div/div[2]/div/div/div[2]/button', "Site Rentals", temp)
            if f:
                dest = os.path.join(OUTPUT_DIR, "SiteRental_" + os.path.basename(f))
                move_file_safe(f, dest); files['rental'] = dest
        else:
            print("\n🏢 Sites (Skipped for 1st-4th grace period)")

        time.sleep(5)

    except Exception as e:
        print(f"❌ Download error: {e}")
        import traceback; traceback.print_exc()
    finally:
        driver.quit()

    return files


def run_logiwhiz_flash():
    print("\n" + "="*60)
    print("  STEP 4 — Logiwhiz Clearline Flash Report")
    print("="*60)
    try:
        subprocess.run(["python", "step4_flash.py"], cwd=PIPELINE_DIR)
    except Exception as e:
        print(f"❌ Logiwhiz script failed: {e}")

def run_pipeline():
    print("\n" + "█"*60)
    print("  🏠👷🏢 FULL PAYOUT REPORT PIPELINE")
    print("█"*60)
    start = datetime.now()

    # Grace period: 1st to 4th of the month
    if start.day < 5:
        print(f"⏳ Today is the {start.day}th. Grace period is active (1st-4th) for Site Rental.")
        print("   Staff and Housekeeping payouts will still be processed and shared.")

    year, month = get_previous_month()
    month_name  = f"{month} {year}"
    print(f"📅 Reporting month: {month_name}")

    if "--skip-download" in sys.argv or "--step3-only" in sys.argv:
        print("⏭️ Skipping Whizzard download. Using existing files from output directory...")
        files = {}
        for f in os.listdir(OUTPUT_DIR):
            fp = os.path.join(OUTPUT_DIR, f)
            if os.path.isfile(fp):
                if f.startswith("HK_") and f.endswith(".xlsx") and "Pending" not in f:
                    files['hk'] = fp
                elif f.startswith("Staff_") and f.endswith(".xlsx") and "Pending" not in f:
                    files['staff'] = fp
                elif f.startswith("Fleet_") and f.endswith(".xlsx") and "Pending" not in f:
                    files['fleet'] = fp
    else:
        files = download_all(year, month)
    reports = []

    print("\n" + "="*60)
    print("  STEP 1+2 — Process & Convert to Images")
    print("="*60)

    # Housekeeping
    print("\n🏠 Processing Housekeeping...")
    if files.get('hk'):
        excel, count = process_hk_file(files['hk'], OUTPUT_DIR)
        img = excel_to_image(excel, os.path.join(OUTPUT_DIR, "HK.png")) if excel else None
    else:
        count, img = 0, None
        print("   ⚠️  File not downloaded")
    reports.append({"type": "Housekeeping", "pendingCount": count, "imagePath": img or ""})

    # IC Staff
    print("\n👷 Processing IC Staff...")
    if files.get('staff'):
        excel, count = process_staff_file(files['staff'], OUTPUT_DIR)
        img = excel_to_image(excel, os.path.join(OUTPUT_DIR, "Staff.png")) if excel else None
    else:
        count, img = 0, None
        print("   ⚠️  File not downloaded")
    reports.append({"type": "IC Staff", "pendingCount": count, "imagePath": img or ""})

    # Fleet
    print("\n🚛 Processing Fleet...")
    if files.get('fleet'):
        excel, count = process_fleet_file(files['fleet'], OUTPUT_DIR)
        img = excel_to_image(excel, os.path.join(OUTPUT_DIR, "Fleet.png")) if excel else None
    else:
        count, img = 0, None
        print("   ⚠️  File not downloaded")
    reports.append({"type": "IC Fleet", "pendingCount": count, "imagePath": img or ""})

    # Site Rental
    print("\n🏢 Processing Site Rental...")
    if start.day < 5:
        print("   ⏳ Skipped during grace period (1st-4th)")
        count, img = 0, None
    elif files.get('rental') and files.get('active_sites'):
        excel, count = process_site_rental_file(files['rental'], files['active_sites'], OUTPUT_DIR)
        img = excel_to_image(excel, os.path.join(OUTPUT_DIR, "SiteRental.png")) if excel else None
    else:
        count, img = 0, None
        print("   ⚠️  Files not downloaded (need both rental + active sites)")
    reports.append({"type": "Site Rental", "pendingCount": count, "imagePath": img or ""})

    # Summary
    print("\n📊 Summary:")
    for r in reports:
        status = f"⚠️  {r['pendingCount']} pending" if r['pendingCount'] > 0 else "✅ All clear"
        print(f"   {r['type']}: {status}")

    # Step 3 — WhatsApp
    print("\n" + "="*60)
    print("  STEP 3 — Send WhatsApp")
    print("="*60)

    # Determine tag person and noSir based on day of month (days 2 to 5)
    if 2 <= start.day <= 5:
        tag_person = os.environ.get("WA_TAG_PERSON_ALT")
        no_sir = True
    else:
        tag_person = WA_TAG_PERSON
        no_sir = False

    # Convert images to Base64 to support remote VPS transmission (since files are local on the runner)
    import base64
    for r in reports:
        if r.get("pendingCount", 0) > 0 and r.get("imagePath"):
            try:
                if os.path.exists(r["imagePath"]):
                    with open(r["imagePath"], "rb") as f:
                        r["imageBase64"] = base64.b64encode(f.read()).decode("utf-8")
                else:
                    r["imageBase64"] = ""
            except Exception as e:
                print(f"⚠️  Failed to read/encode image {r['imagePath']}: {e}")
                r["imageBase64"] = ""
        else:
            r["imageBase64"] = ""

    payload = {
        "monthName": month_name,
        "reports": reports,
        "groupId": WA_GROUP_ID,
        "tagPhone": tag_person,
        "noSir": no_sir
    }

    success = send_to_whatsapp_service("/send-report", payload)

    if success:
        print("\n✅ Pipeline completed successfully!")
    else:
        print("\n❌ WhatsApp send failed")

    if "--upto-step3" not in sys.argv and "--dry-run" not in sys.argv:
        run_logiwhiz_flash()

    print(f"⏱️  Total: {str(datetime.now()-start).split('.')[0]}")
    print("█"*60)


if __name__ == "__main__":
    if "--step4-only" in sys.argv:
        print("Skipping Steps 1-3. Running Step 4 only...")
        run_logiwhiz_flash()
    else:
        run_pipeline()
