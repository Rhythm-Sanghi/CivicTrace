import sys
import os
import time
import subprocess
import tempfile
import httpx
from playwright.sync_api import sync_playwright

WEB_BASE = "http://127.0.0.1:5173"
API_BASE = "http://127.0.0.1:8000/api/v1"
OUT_DIR = "docs/screenshots"

api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "api"))
web_dir = os.path.abspath(os.path.join(api_dir, "..", "..", "apps", "web"))

def ensure_servers():
    backend_proc = None
    frontend_proc = None

    backend_alive = False
    try:
        r = httpx.get(f"{API_BASE}/cases/neighborhood/stats", timeout=1.0)
        if r.status_code == 200:
            backend_alive = True
    except Exception:
        pass

    if not backend_alive:
        print("Starting backend for screenshot capture...")
        env = os.environ.copy()
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=api_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    frontend_alive = False
    try:
        r = httpx.get(WEB_BASE, timeout=1.0)
        if r.status_code == 200:
            frontend_alive = True
    except Exception:
        pass

    if not frontend_alive:
        print("Starting frontend for screenshot capture...")
        vite_log = open(os.path.join(tempfile.gettempdir(), "screenshot_vite.log"), "w", encoding="utf-8")
        frontend_proc = subprocess.Popen(
            ["npx.cmd" if os.name == "nt" else "npx", "vite", "--port", "5173", "--strictPort", "--host", "127.0.0.1"],
            cwd=web_dir,
            stdout=vite_log,
            stderr=vite_log,
        )

    for _ in range(40):
        b_ok = False
        f_ok = False
        try:
            if httpx.get(f"{API_BASE}/cases/neighborhood/stats", timeout=0.5).status_code == 200:
                b_ok = True
        except Exception:
            pass
        try:
            if httpx.get(WEB_BASE, timeout=0.5).status_code == 200:
                f_ok = True
        except Exception:
            pass
        if b_ok and f_ok:
            break
        time.sleep(0.5)

    return backend_proc, frontend_proc

def capture_ten_desktop_screenshots():
    backend_proc, frontend_proc = ensure_servers()
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Consistent desktop viewport (1440x900)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            print("Capturing 10 consistent desktop screenshots...")

            # 1. Overview (Home View)
            page.goto(f"{WEB_BASE}/")
            page.wait_for_selector("h1:has-text('Overview')", timeout=10000)
            page.wait_for_selector(".measurement", timeout=10000)
            page.screenshot(path=f"{OUT_DIR}/01_overview.png")
            page.screenshot(path=f"{OUT_DIR}/01_homepage.png")
            print("  [OK] 01_overview.png")

            # 2. Cases Explorer
            page.goto(f"{WEB_BASE}/explorer")
            page.wait_for_selector("h1:has-text('Cases')", timeout=10000)
            page.wait_for_selector("tr:has-text('CAS-')", timeout=10000)
            page.screenshot(path=f"{OUT_DIR}/02_cases_explorer.png")
            print("  [OK] 02_cases_explorer.png")

            # 3. Selected Case Inspector
            # Ensure inspector is open and focused on CAS-2026-0001
            page.click("tr:has-text('CAS-2026-0001')")
            page.wait_for_selector("aside.inspector", timeout=5000)
            page.screenshot(path=f"{OUT_DIR}/03_selected_case_inspector.png")
            print("  [OK] 03_selected_case_inspector.png")

            # 4. Geographic Investigation (Map Canvas & Controls)
            page.goto(f"{WEB_BASE}/")
            page.wait_for_selector("text=Issue map", timeout=10000)
            page.wait_for_selector(".measurement", timeout=10000)
            # Click pan right once to demonstrate interactive canvas state
            if page.is_visible("button[title*='an right'], button[title*='an Right']"):
                page.click("button[title*='an right'], button[title*='an Right']")
            page.screenshot(path=f"{OUT_DIR}/04_geographic_investigation.png")
            print("  [OK] 04_geographic_investigation.png")

            # 5. Case Dossier
            page.goto(f"{WEB_BASE}/cases/CAS-2026-0001")
            page.wait_for_selector("text=Export evidence package", timeout=10000)
            page.wait_for_selector(".measurement", timeout=10000)
            page.screenshot(path=f"{OUT_DIR}/05_case_dossier.png")
            page.screenshot(path=f"{OUT_DIR}/03_case_details_ledger.png")
            print("  [OK] 05_case_dossier.png")

            # 6. Duplicate Suggestion (Reviewer Workspace)
            # Sign in as reviewer
            page.goto(f"{WEB_BASE}/login")
            page.fill("input[type='email']", "reviewer@civictrace.local")
            page.fill("input[type='password']", "ReviewerPass2026!")
            page.click("button[type='submit']")
            page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)
            page.goto(f"{WEB_BASE}/reviewer")
            page.wait_for_selector("text=Duplicate Correlation", timeout=10000)
            page.wait_for_selector("text=Loading duplicate candidates", state="detached", timeout=10000)
            page.screenshot(path=f"{OUT_DIR}/06_duplicate_suggestion.png")
            print("  [OK] 06_duplicate_suggestion.png")

            # 7. Resolution Dispute (Disputed Case CAS-2026-0002)
            page.goto(f"{WEB_BASE}/cases/CAS-2026-0002")
            page.wait_for_selector("text=DISPUTED", timeout=10000)
            page.screenshot(path=f"{OUT_DIR}/07_resolution_dispute.png")
            print("  [OK] 07_resolution_dispute.png")

            # 8. Evidence Timeline (Append-Only Cryptographic Event Chain)
            page.goto(f"{WEB_BASE}/cases/CAS-2026-0001")
            page.wait_for_selector("text=Case history", timeout=10000)
            page.screenshot(path=f"{OUT_DIR}/08_evidence_timeline.png")
            print("  [OK] 08_evidence_timeline.png")

            # 9. Intelligence
            page.goto(f"{WEB_BASE}/neighborhood")
            page.wait_for_selector("h1:has-text('Intelligence')", timeout=10000)
            page.wait_for_selector(".measurement", timeout=10000)
            page.screenshot(path=f"{OUT_DIR}/09_intelligence.png")
            page.screenshot(path=f"{OUT_DIR}/04_neighborhood_intelligence.png")
            print("  [OK] 09_intelligence.png")

            # 10. Report Issue Form
            page.goto(f"{WEB_BASE}/report")
            page.wait_for_selector("h1:has-text('Report an issue')", timeout=10000)
            page.screenshot(path=f"{OUT_DIR}/10_report_issue_form.png")
            page.screenshot(path=f"{OUT_DIR}/06_report_form.png")
            print("  [OK] 10_report_issue_form.png")

            # 11. Mobile 375px Viewport verification
            page.set_viewport_size({"width": 375, "height": 667})
            page.goto(f"{WEB_BASE}/")
            page.wait_for_selector("h1:has-text('Overview')", timeout=10000)
            page.wait_for_selector(".measurement", timeout=10000)
            page.screenshot(path=f"{OUT_DIR}/01_homepage_mobile_375.png")
            print("  [OK] 01_homepage_mobile_375.png")

            browser.close()
            print("\nAll required screenshots successfully captured!")
    finally:
        if backend_proc:
            backend_proc.terminate()
            backend_proc.wait()
        if frontend_proc:
            frontend_proc.terminate()
            frontend_proc.wait()

if __name__ == "__main__":
    capture_ten_desktop_screenshots()
