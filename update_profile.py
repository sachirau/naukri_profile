import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# ================= CONFIGURATION =================
NAUKRI_EMAIL = os.environ.get("NAUKRI_EMAIL", "sachinraut0110@gmail.com")
NAUKRI_PASSWORD = os.environ.get("NAUKRI_PASSWORD", "")
CHROME_PROFILE_DIR = "./naukri_profile"
RESUME_FILE_PATH = os.path.abspath("Sachin_Raut_DevOps.pdf")

def auto_login_if_needed(page):
    page.goto("https://www.naukri.com/mnjuser/profile", timeout=60000)
    time.sleep(4)

    if "nlogin" in page.url.lower() or page.locator("#login_Layer").count() > 0:
        print("  -> Not logged in. Attempting login...")
        if page.locator("#login_Layer").is_visible():
            page.locator("#login_Layer").click()
            time.sleep(2)

        if NAUKRI_PASSWORD:
            try:
                page.locator("input[placeholder*='Email ID'], input[placeholder*='Username'], #usernameField").first.fill(NAUKRI_EMAIL)
                page.locator("input[type='password'], #passwordField").first.fill(NAUKRI_PASSWORD)
                page.locator("button[type='submit'], button:has-text('Login')").first.click()
                time.sleep(6)
            except Exception as e:
                print(f"  [!] Auto-login fill error: {e}")

        if "mnjuser/profile" not in page.url:
            print("  >>> ACTION: Browser mein manually login complete karein (30 sec)...")
            time.sleep(30)
            page.goto("https://www.naukri.com/mnjuser/profile", timeout=60000)
            time.sleep(4)

def update_naukri_profile():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST] Starting Naukri Profile Refresh...")
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)

    if not os.path.exists(RESUME_FILE_PATH):
        print(f"  [!] ERROR: Resume file nahi mili: {RESUME_FILE_PATH}")
        print("  [i] Kripya 'Sachin_Raut_DevOps.pdf' ko isi folder mein rakhein.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE_DIR,
            headless=False,  # Testing ke liye False; AWS EC2 par push karne se pehle True kar dein
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            viewport={"width": 1280, "height": 800}
        )
        page = browser.pages[0] if browser.pages else browser.new_page()

        try:
            auto_login_if_needed(page)
            print(f"  -> Profile Page Loaded: {page.url}")
            time.sleep(3)

            # Direct Resume File Input dhundh kar PDF upload karein (Bina modal khole)
            print("  -> Uploading latest resume to trigger profile refresh...")
            file_input = page.locator("input[type='file']").first
            file_input.set_input_files(RESUME_FILE_PATH)
            time.sleep(6)

            print("  [+] SUCCESS: Resume re-uploaded! Naukri Profile is now 'Updated Today'.")

        except Exception as e:
            page.screenshot(path="debug_profile.png")
            print(f"  [!] Profile update failed: {e}")

        finally:
            browser.close()

if __name__ == "__main__":
    update_naukri_profile()