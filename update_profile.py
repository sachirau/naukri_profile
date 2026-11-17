import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# ================= CONFIGURATION =================
NAUKRI_EMAIL = os.environ.get("NAUKRI_EMAIL")
NAUKRI_PASSWORD = os.environ.get("NAUKRI_PASSWORD")
CHROME_PROFILE_DIR = "./naukri_profile"

BASE_HEADLINE = "Senior AWS DevOps Engineer | 7+ Yrs Exp | AWS Certified Solutions Architect | Jenkins, GitHub Actions, Docker, Ansible, CloudFormation, Datadog, Wiz | CI/CD & Cloud Security"

def auto_login_if_needed(page):
    page.goto("https://www.naukri.com/mnjuser/profile", timeout=60000)
    time.sleep(4)

    if "nlogin" in page.url.lower() or page.locator("#login_Layer").is_visible():
        print("  -> Session expired. Logging in automatically...")
        if page.locator("#login_Layer").is_visible():
            page.locator("#login_Layer").click()
            time.sleep(2)
        try:
            page.locator("input[placeholder*='Email ID'], input[placeholder*='Username']").first.fill(NAUKRI_EMAIL)
            page.locator("input[type='password']").first.fill(NAUKRI_PASSWORD)
            page.locator("button[type='submit']").first.click()
            time.sleep(6)
            page.goto("https://www.naukri.com/mnjuser/profile", timeout=60000)
            time.sleep(4)
        except Exception as e:
            print(f"  [!] Login error: {e}")

def update_naukri_profile():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST] Starting Naukri Profile Refresh...")
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE_DIR,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            viewport={"width": 1280, "height": 800}
        )
        page = browser.pages[0] if browser.pages else browser.new_page()

        try:
            auto_login_if_needed(page)

            print("  -> Opening Resume Headline editor...")
            edit_btn = page.locator("#lazyResumeHead .edit.icon, .resumeHeadline .edit").first
            edit_btn.wait_for(state="visible", timeout=15000)
            edit_btn.click()
            time.sleep(2)

            textarea = page.locator("#resumeHeadlineTxt, textarea[placeholder*='Resume Headline']").first
            textarea.wait_for(state="visible", timeout=10000)
            current_text = textarea.input_value().strip()

            if current_text.endswith("."):
                new_text = current_text[:-1]
            else:
                new_text = (current_text if current_text else BASE_HEADLINE) + "."

            textarea.fill(new_text)
            time.sleep(1)

            save_btn = page.locator("form[name='resumeHeadlineForm'] button[type='submit'], button:has-text('Save')").last
            save_btn.click()
            time.sleep(4)

            print("  [+] SUCCESS: Naukri Profile successfully updated & refreshed!")

        except Exception as e:
            print(f"  [!] Profile update failed: {e}")

        finally:
            browser.close()

if __name__ == "__main__":
    update_naukri_profile()