"""
LogiWhiz Actual Cost - Playwright Automation Script
====================================================
This script:
1. Logs into https://logiwhizdevelopment.com
2. Navigates to /actual-cost
3. Sets date filter to previous month
4. Selects Entity: MLL, Payment Category: Vendor
5. Takes screenshots of both tables
6. Selects Entity: WZ, Payment Category: Vendor
7. Takes screenshots of both tables
"""

import env_loader
import asyncio
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from playwright.async_api import async_playwright
from PIL import Image
import os

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
URL_LOGIN     = "https://logiwhizdevelopment.com"
URL_COST      = "https://logiwhizdevelopment.com/actual-cost"
USERNAME      = os.environ.get("LOGIWHIZ_USERNAME")
PASSWORD      = os.environ.get("LOGIWHIZ_PASSWORD")
SCREENSHOT_DIR = "output"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)
for f in os.listdir(SCREENSHOT_DIR):
    if f.startswith(("MLL_", "WZ_")) and f.endswith(".png"):
        try: os.remove(os.path.join(SCREENSHOT_DIR, f))
        except: pass


# Compute target month label based on the day of the month
today = date.today()
if today.day <= 7:
    target_date = today - relativedelta(months=2)
else:
    target_date = today - relativedelta(months=1)

PREV_MONTH_LABEL = target_date.strftime("%b")   # e.g. "Mar" or "Feb"
PREV_YEAR        = str(target_date.year)         # e.g. "2026"

print(f"[INFO] Target month: {PREV_MONTH_LABEL} {PREV_YEAR}")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
async def screenshot(page, name: str):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    await page.screenshot(path=path, full_page=False)
    print(f"[SCREENSHOT] Saved → {path}")
    return path


async def screenshot_element(page, xpath: str, name: str):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    el = page.locator(f"xpath={xpath}").first
    await el.scroll_into_view_if_needed()
    await el.screenshot(path=path)
    print(f"[SCREENSHOT] Saved → {path}")
    return path


async def select_month(page):
    """Click the date button, navigate to correct year, select previous month, click Apply."""
    print("[STEP] Opening date picker...")

    # Try multiple strategies to find and click the date picker button
    date_clicked = False
    strategies = [
        # Strategy 1: aria-label="Service month" (confirmed by browser inspection)
        lambda: page.locator("button[aria-label='Service month']").click(),
        # Strategy 2: any button containing an svg in section[1]
        lambda: page.locator("section").first.locator("button svg").first.click(),
        # Strategy 3: button with calendar-like aria or title
        lambda: page.locator("button[aria-label*='month'], button[aria-label*='date'], button[aria-label*='calendar']").first.click(),
        # Strategy 4: just click any button in the first section
        lambda: page.locator("section").first.locator("button").first.click(),
    ]

    for i, strategy in enumerate(strategies):
        try:
            await strategy()
            await page.wait_for_timeout(800)
            # Check if calendar/month picker appeared
            if await page.get_by_role("button", name=PREV_MONTH_LABEL, exact=True).is_visible():
                date_clicked = True
                print(f"[STEP] Date picker opened with strategy {i+1}")
                break
            # Also check for Apply button
            if await page.get_by_role("button", name="Apply").is_visible():
                date_clicked = True
                print(f"[STEP] Date picker opened with strategy {i+1}")
                break
        except Exception as e:
            print(f"[INFO] Strategy {i+1} failed: {e}")
            continue

    if not date_clicked:
        print("[WARN] Could not open date picker automatically. Please share the correct XPath.")
        return

    # Navigate year if needed (click < or > arrows)
    for _ in range(5):
        try:
            # Look for year display
            year_visible = await page.get_by_text(PREV_YEAR, exact=True).is_visible()
            if year_visible:
                break
            # Try clicking left arrow (< or ‹)
            for arrow in ["<", "‹", "←", "chevron"]:
                try:
                    await page.get_by_role("button", name=arrow).click()
                    await page.wait_for_timeout(400)
                    break
                except:
                    continue
        except:
            break

    print(f"[STEP] Scanning calendar to enforce only {PREV_MONTH_LABEL} is selected...")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    for m in months:
        try:
            btn = page.get_by_role("button", name=m, exact=True).first
            if not await btn.is_visible(timeout=200):
                continue

            # Check if the button is selected by looking for a blue background or active class
            is_selected = await page.evaluate("""(element) => {
                const ariaSel = element.getAttribute('aria-selected');
                const dataState = element.getAttribute('data-state');
                if (ariaSel === 'true' || dataState === 'checked') return true;
                
                const cls = element.className.toLowerCase();
                if (cls.includes('active') || cls.includes('selected') || cls.includes('bg-blue')) return true;
                
                const bg = window.getComputedStyle(element).backgroundColor;
                const match = bg.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                if (match) {
                    const r = parseInt(match[1]);
                    const g = parseInt(match[2]);
                    const b = parseInt(match[3]);
                    // If Blue is significantly higher than Red and Green, it's a blue background
                    if (b > 130 && b > r + 30 && b > g + 10) return true;
                }
                return false;
            }""", await btn.element_handle())

            if m == PREV_MONTH_LABEL:
                if not is_selected:
                    print(f"[STEP] Clicking to select target month: {m}")
                    await btn.click()
                    await page.wait_for_timeout(400)
                else:
                    print(f"[STEP] Target month {m} is already selected.")
            else:
                if is_selected:
                    print(f"[STEP] Unselecting unwanted month: {m} (Blue background detected)")
                    await btn.click()
                    await page.wait_for_timeout(400)
        except Exception:
            pass

    # Click Apply
    await page.get_by_role("button", name="Apply").click()
    await page.wait_for_timeout(1000)
    print("[STEP] Date filter applied.")


async def select_entity(page, entity_name: str):
    """Open entity dropdown and select the given entity."""
    print(f"[STEP] Selecting entity: {entity_name}")
    entity_input = page.locator("#actual-filter-entity")

    # Clear previous selection first — click the parent to open dropdown
    await entity_input.click()
    await page.wait_for_timeout(600)

    # Uncheck all currently checked items
    checkboxes = page.locator("input[type='checkbox']")
    count = await checkboxes.count()
    for i in range(count):
        cb = checkboxes.nth(i)
        try:
            if await cb.is_checked(timeout=500):
                await cb.click(force=True)
                await page.wait_for_timeout(200)
        except Exception:
            pass

    # Now select the desired entity by its label text
    label = page.get_by_text(entity_name, exact=True).first
    
    # Check if the label is visible. If not, the dropdown might have closed after unchecking.
    if not await label.is_visible(timeout=1000):
        try:
            await entity_input.click(timeout=1000)
            await page.wait_for_timeout(600)
        except Exception:
            pass

    # If still not visible, it might need scrolling or filtering
    if not await label.is_visible(timeout=1000):
        try:
            await entity_input.fill(entity_name)
            await page.wait_for_timeout(600)
        except Exception:
            pass

    try:
        await label.click(timeout=3000)
    except Exception:
        # Fallback to partial text match if exact fails
        fallback_label = page.get_by_text(entity_name).first
        await fallback_label.click(timeout=3000)

    await page.wait_for_timeout(400)

    # Close dropdown by pressing Escape
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(600)
    print(f"[STEP] Entity '{entity_name}' selected.")


async def select_payment_category(page, category: str):
    """Open Payment Category dropdown and select the given option."""
    print(f"[STEP] Selecting payment category: {category}")
    
    # Click the Payment Category dropdown using its stable ID
    await page.locator("#actual-filter-paymentCategory").click()
    await page.wait_for_timeout(600)

    # The dropdown is now open. Find the option.
    option = page.get_by_text(category, exact=True).first
    
    # Determine if it's already selected
    is_selected = False
    try:
        if await option.get_attribute("aria-selected") == "true":
            is_selected = True
        elif await option.get_attribute("data-state") == "checked":
            is_selected = True
        elif await option.get_attribute("aria-checked") == "true":
            is_selected = True
        else:
            # Check if there's an active native checkbox inside or right next to it
            checkbox = option.locator("..").locator("input[type='checkbox']")
            if await checkbox.count() > 0 and await checkbox.first.is_checked():
                is_selected = True
    except Exception:
        pass

    if not is_selected:
        await option.click()
        await page.wait_for_timeout(800)
        print(f"[STEP] Payment category '{category}' selected.")
    else:
        print(f"[STEP] Payment category '{category}' was already selected. Skipped click.")

    # Close dropdown by pressing Escape just in case
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(400)


async def take_table_screenshots(page, label: str):
    """Scroll to and screenshot both tables, then combine them."""
    table1_xpath = "/html/body/div/div/main/div/div/div/div/div/div[3]/section[2]/div"
    table2_xpath = "/html/body/div/div/main/div/div/div/div/div/div[3]/section[3]/div"

    print(f"[STEP] Taking table screenshots for: {label}")

    path1 = os.path.join(SCREENSHOT_DIR, f"{label}_table1_pending_by_status.png")
    path2 = os.path.join(SCREENSHOT_DIR, f"{label}_table2_pending_by_category.png")

    # Table 1 — Pending cost by status (by PH level)
    t1 = page.locator(f"xpath={table1_xpath}").first
    await t1.scroll_into_view_if_needed()
    await page.wait_for_timeout(1500)
    await t1.screenshot(path=path1, animations="disabled")
    print(f"[SCREENSHOT] {label}_table1_pending_by_status.png saved")

    # Table 2 — Pending cost by category
    t2 = page.locator(f"xpath={table2_xpath}").first
    await t2.scroll_into_view_if_needed()
    await page.wait_for_timeout(1500)
    await t2.screenshot(path=path2, animations="disabled")
    print(f"[SCREENSHOT] {label}_table2_pending_by_category.png saved")

    # Combine images vertically using Pillow
    try:
        img1 = Image.open(path1)
        img2 = Image.open(path2)
        
        padding = 20
        max_width = max(img1.width, img2.width)
        total_height = img1.height + img2.height + padding
        
        combined_img = Image.new("RGB", (max_width, total_height), "white")
        combined_img.paste(img1, (0, 0))
        combined_img.paste(img2, (0, img1.height + padding))
        
        combined_path = os.path.join(SCREENSHOT_DIR, f"{label}_combined.png")
        combined_img.save(combined_path, dpi=(384, 384))
        print(f"[SCREENSHOT] Combined image saved: {label}_combined.png")
    except Exception as e:
        print(f"[WARN] Failed to combine images for {label}: {e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=300)
        # We use a scale factor of 2.0. If we go too high (like 4.0), the image becomes so massive
        # that WhatsApp's compression algorithm aggressively crushes it, which ironically causes more blur.
        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=2.0)
        
        # Inject CSS to force sharp text rendering and disable animations
        await context.add_init_script("""
            document.addEventListener("DOMContentLoaded", () => {
                const style = document.createElement('style');
                style.textContent = `
                    * {
                        -webkit-font-smoothing: antialiased !important;
                        -moz-osx-font-smoothing: grayscale !important;
                        text-rendering: optimizeLegibility !important;
                        animation: none !important;
                        transition: none !important;
                    }
                `;
                document.head.append(style);
            });
        """)
        
        page = await context.new_page()

        print("[STEP] Navigating to login page...")
        await page.goto(URL_LOGIN, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        print("[STEP] Logging in...")
        try:
            await page.locator("input[placeholder*='Mobile'], input[type='text']").first.fill(USERNAME)
            await page.locator("input[type='password'], input[placeholder*='Password']").first.fill(PASSWORD)
            await page.keyboard.press("Enter")
            # Wait for redirect to overview to complete
            await page.wait_for_url("**/overview", timeout=15000)
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"[WARN] Login steps failed: {e}")

        print("[STEP] Navigating to /actual-cost...")
        await page.goto(URL_COST, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # ── 3. Open Pending Cost tab (stable role+attribute selector) ──
        print("[STEP] Clicking Pending Cost tab...")
        await page.locator("button[role='tab'][id$='trigger-pending-cost']").click()
        await page.wait_for_timeout(1500)

        # ── 4. Set Date Filter ────────────────────
        await select_month(page)

        # ════════════════════════════════════════
        #  RUN 1 — Entity: MLL, Category: Vendor
        # ════════════════════════════════════════
        await select_entity(page, "MLL")
        await select_payment_category(page, "Vendor")
        await page.wait_for_timeout(1500)
        await take_table_screenshots(page, "MLL_Vendor")

        # ════════════════════════════════════════
        #  RUN 2 — Entity: WZ, Category: Vendor
        # ════════════════════════════════════════
        await select_entity(page, "WZ")
        await page.wait_for_timeout(1500)
        await take_table_screenshots(page, "WZ_Vendor")

        # ════════════════════════════════════════
        #  RESET FILTERS FOR EXPENSE RUN
        # ════════════════════════════════════════
        print("[STEP] Resetting filters for Expense run...")
        await page.get_by_role("button", name="Reset").first.click()
        await page.wait_for_timeout(1500)
        
        # Re-apply Pending Cost tab and Date Filter after Reset
        print("[STEP] Clicking Pending Cost tab...")
        await page.locator("button[role='tab'][id$='trigger-pending-cost']").click()
        await page.wait_for_timeout(1500)
        await select_month(page)

        # ════════════════════════════════════════
        #  RUN 3 — Entity: MLL, Category: Expense
        # ════════════════════════════════════════
        await select_entity(page, "MLL")
        await select_payment_category(page, "Expense")
        await page.wait_for_timeout(1500)
        await take_table_screenshots(page, "MLL_Expense")

        # ════════════════════════════════════════
        #  RUN 4 — Entity: WZ, Category: Expense
        # ════════════════════════════════════════
        await select_entity(page, "WZ")
        await page.wait_for_timeout(1500)
        await take_table_screenshots(page, "WZ_Expense")

        print("\nAll done! Screenshots saved in the 'output/' folder.")
        await browser.close()

        # Trigger WhatsApp Node script
        print("[STEP] Sending WhatsApp message...")
        import urllib.request, json
        
        # Helper to parse tag list from env or fallback
        def get_env_tags(env_name, default_list):
            val = os.environ.get(env_name)
            if val:
                return [t.strip() for t in val.split(",") if t.strip()]
            return default_list

        wa_group_id = os.environ.get("WA_GROUP_ID")
        mll_vendor_tags = get_env_tags("WA_TAGS_MLL_VENDOR", [])
        wz_vendor_tags  = get_env_tags("WA_TAGS_WZ_VENDOR", [])
        mll_expense_tags = get_env_tags("WA_TAGS_MLL_EXPENSE", [])
        wz_expense_tags  = get_env_tags("WA_TAGS_WZ_EXPENSE", [])

        reports_list = [
            { "file": "MLL_Vendor_combined.png", "entity": "MLL", "tags": mll_vendor_tags },
            { "file": "WZ_Vendor_combined.png", "entity": "WZ", "tags": wz_vendor_tags },
            { "file": "MLL_Expense_combined.png", "entity": "MLL (Expense)", "tags": mll_expense_tags },
            { "file": "WZ_Expense_combined.png", "entity": "WZ (Expense)", "tags": wz_expense_tags }
        ]

        import base64
        for r in reports_list:
            filepath = os.path.join(SCREENSHOT_DIR, r["file"])
            if os.path.exists(filepath):
                try:
                    with open(filepath, "rb") as f:
                        r["fileBase64"] = base64.b64encode(f.read()).decode("utf-8")
                except Exception as e:
                    print(f"[WARN] Failed to read/encode file {filepath}: {e}")
                    r["fileBase64"] = ""
            else:
                r["fileBase64"] = ""

        payload = {
            "monthName": PREV_MONTH_LABEL,
            "groupId": wa_group_id,
            "screenshotDir": "output",
            "reports": reports_list
        }
        
        try:
            service_url = os.environ.get("WA_SERVICE_URL", "http://localhost:3000").rstrip("/")
            api_key = os.environ.get("WA_API_KEY")
            url = f"{service_url}/send-flash"
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': api_key
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=90) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                if res_data.get('success'):
                    print("[SUCCESS] WhatsApp messages sent successfully!")
                else:
                    print(f"[ERROR] Failed to send WhatsApp message: {res_data.get('error')}")
        except Exception as e:
            print(f"[ERROR] Failed to send WhatsApp message via HTTP: {e}")
            print(f"        Target URL tried: {url}")
            print("        Make sure the WhatsApp Service is running and reachable.")

if __name__ == "__main__":
    asyncio.run(main())