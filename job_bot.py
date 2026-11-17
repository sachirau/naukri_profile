import os
import json
import time
from datetime import datetime
import pandas as pd
from playwright.sync_api import sync_playwright
from google import genai
from pydantic import BaseModel

# ================= CONFIGURATION (AWS Environment Variables se load hoga) =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NAUKRI_EMAIL = os.environ.get("NAUKRI_EMAIL")
NAUKRI_PASSWORD = os.environ.get("NAUKRI_PASSWORD")

# Linux / AWS Server Paths
CHROME_PROFILE_DIR = "./naukri_profile"
OUTPUT_CSV = "./shortlisted_jobs.csv"
HISTORY_FILE = "./seen_jobs.txt"

# Naukri Search URLs (Target Roles + Pune/Bangalore/Remote + 7 Yrs Exp + Last 1 Day)
SEARCH_URLS = [
    "https://www.naukri.com/senior-devops-engineer-jobs-in-pune-bengaluru?experience=7&jobAge=1",
    "https://www.naukri.com/devops-lead-jobs-in-pune-bengaluru?experience=7&jobAge=1",
    "https://www.naukri.com/site-reliability-engineer-jobs-in-pune-bengaluru?experience=7&jobAge=1",
    "https://www.naukri.com/cloud-engineer-jobs-in-pune-bengaluru?experience=7&jobAge=1",
    "https://www.naukri.com/senior-devops-engineer-jobs?experience=7&jobAge=1&wfhType=2"
]

# Resume Profile
MY_RESUME = """
Name: Sachin Raut
Role: Senior AWS DevOps Engineer / Cloud Engineer
Total Experience: 8+ years in IT (7+ years relevant in AWS Cloud & DevOps across TCS, Synechron, Capgemini)
Certifications: AWS Certified Solutions Architect - Associate, AWS Cloud Practitioner
Core Skills: AWS (EC2, S3, VPC, IAM, Lambda, Route 53, CloudFront, ALB, Target Groups, NACL, Security Groups, AMI, ACM, CloudFormation, CloudWatch, AWS WAF), CI/CD, Jenkins, GitHub, GitHub Actions, Webhooks, Git, Docker, Ansible, SonarQube, Datadog (Dashboards, SLOs, Apdex), Wiz (CSPM), OS Patching, DDoS Mitigation, Linux (Ubuntu), Windows, Networking.
Leadership & SRE: Led a 7-10 member AWS administrator team, post-mortems, root-cause analysis (RCA), production escalations, client coordination.
"""

# ================= GEMINI AI SETUP =================
client = genai.Client(api_key=GEMINI_API_KEY)

class JobMatch(BaseModel):
    match_score: int
    tier: str
    missing_skills: str
    cover_note: str

def evaluate_job_with_gemini(title, company, jd_text):
    prompt = f"""
    Act as an expert IT recruiter. Compare the following Job Description with the candidate's resume.
    Give a realistic match_score from 0 to 100 based on AWS, DevOps, CI/CD, Docker, Ansible, and experience alignment.
    Set tier to "High Match" if score >= 70, "Medium Match" if 55-69, else "Low Match".
    List key missing_skills briefly. Write a crisp 2-sentence cover_note tailored to this role.

    Candidate Resume:
    {MY_RESUME}

    Job Title: {title}
    Company: {company}
    Job Description:
    {jd_text[:4000]}
    """
    models_to_try = ["gemini-3.8-flash", "gemini-3.8-flash-lite"]

    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": JobMatch,
                        "temperature": 0.2,
                    },
                )
                return json.loads(response.text)
            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    print(f"    [~] {model_name} busy hai, 4 sec mein retry kar rahe hain...")
                    time.sleep(4)
                else:
                    print(f"  [!] Gemini API Error ({model_name}): {e}")
                    break
    return None

# ================= HELPER FUNCTIONS =================
def load_seen_jobs():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen_job(url):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")

def append_to_csv(row_dict):
    df = pd.DataFrame([row_dict])
    file_exists = os.path.exists(OUTPUT_CSV)
    df.to_csv(OUTPUT_CSV, mode="a", header=not file_exists, index=False, encoding="utf-8-sig")

def auto_login_naukri(page):
    print("Checking Naukri login status...")
    page.goto("https://www.naukri.com/", timeout=60000)
    time.sleep(3)

    login_btn = page.locator("#login_Layer")
    if login_btn.count() > 0 and login_btn.is_visible():
        print("  -> Logging in automatically with Email & Password...")
        login_btn.click()
        time.sleep(2)
        try:
            page.locator("input[placeholder*='Email ID'], input[placeholder*='Username']").first.fill(NAUKRI_EMAIL)
            page.locator("input[type='password']").first.fill(NAUKRI_PASSWORD)
            page.locator("button[type='submit']").first.click()
            time.sleep(6)
            print("  [+] Auto-login submitted!")
        except Exception as e:
            print(f"  [!] Auto-login error: {e}")
    else:
        print("  [+] Already logged in!")

def try_auto_apply(job_page):
    try:
        job_page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        if job_page.locator("text='Applied'").count() > 0:
            return "Already Applied"

        if job_page.locator("button:has-text('Apply on company site'), a:has-text('Apply on company site')").count() > 0:
            return "External Company Site (Manual Apply)"

        apply_btn = job_page.locator("#apply-button, .apply-button, button[id*='apply'], button:has-text('Apply')").first

        if apply_btn.count() > 0 and apply_btn.is_visible():
            apply_btn.scroll_into_view_if_needed()
            apply_btn.click(force=True)
            time.sleep(4)

            if job_page.locator("input[placeholder*='Email ID'], .login-layer").count() > 0:
                return "Failed: Not Logged In (Login Popup Opened)"

            if job_page.locator(".chatbot_Drawer, .apply-questionnaire, [class*='chatbot']").count() > 0:
                return "Questionnaire Opened (Manual Finish Needed)"

            if job_page.locator("text='Applied', .applied-job-msg").count() > 0:
                return "Applied Successfully"

            return "Clicked Apply (Verify in CSV/Naukri)"
        else:
            return "Apply Button Not Found on Page"
    except Exception as e:
        return f"Apply Error: {str(e)[:50]}"

# ================= MAIN SCRAPER & APPLY LOGIC =================
def run_job_search():
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    seen_jobs = load_seen_jobs()

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Starting Naukri Auto-Search & Apply...")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE_DIR,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            viewport={"width": 1280, "height": 800}
        )
        page = browser.pages[0] if browser.pages else browser.new_page()

        auto_login_naukri(page)

        for search_url in SEARCH_URLS:
            print(f"\nSearching: {search_url}")
            try:
                page.goto(search_url, timeout=60000)
                page.wait_for_selector(".srp-jobtuple-wrapper", timeout=15000)
                time.sleep(2)
            except Exception:
                print("  [-] No new results or slow page load.")
                continue

            job_cards = page.locator(".srp-jobtuple-wrapper").all()[:10]
            job_links = []

            for card in job_cards:
                try:
                    title_el = card.locator("a.title").first
                    href = title_el.get_attribute("href")
                    title = title_el.inner_text().strip()
                    company = card.locator("a.comp-name").first.inner_text().strip() if card.locator("a.comp-name").count() else "Unknown"
                    location = card.locator(".locWdth").first.inner_text().strip() if card.locator(".locWdth").count() else "Not Specified"
                    if href:
                        clean_url = href.split("?")[0]
                        job_links.append((title, company, location, clean_url))
                except Exception:
                    continue

            for title, company, location, url in job_links:
                if url in seen_jobs:
                    continue

                print(f"  Checking: {title} @ {company} ({location})")

                try:
                    job_page = browser.new_page()
                    job_page.goto(url, timeout=45000)
                    time.sleep(2)

                    jd_locator = job_page.locator("section.styles_job-desc-container__txpYf, .job-desc, .dang-inner-html").first
                    jd_text = jd_locator.inner_text() if jd_locator.count() else job_page.locator("body").inner_text()

                    result = evaluate_job_with_gemini(title, company, jd_text)
                    if not result:
                        job_page.close()
                        continue

                    save_seen_job(url)
                    seen_jobs.add(url)

                    score = result.get("match_score", 0)
                    print(f"    -> Match Score: {score}% ({result.get('tier')})")

                    if score >= 70:
                        apply_status = try_auto_apply(job_page)
                        print(f"    -> Apply Status: {apply_status}")

                        append_to_csv({
                            "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Match %": score,
                            "Tier": result.get("tier"),
                            "Job Title": title,
                            "Company": company,
                            "Location": location,
                            "Apply Status": apply_status,
                            "Missing Skills": result.get("missing_skills"),
                            "Cover Note": result.get("cover_note"),
                            "Job Link": url
                        })
                        print("    [+] SAVED to shortlisted_jobs.csv!")

                    job_page.close()

                except Exception as e:
                    print(f"    [!] Error processing job: {e}")
                    try:
                        job_page.close()
                    except Exception:
                        pass

        print("\n[Done] Process complete! Report saved to shortlisted_jobs.csv.")
        browser.close()

if __name__ == "__main__":
    run_job_search()