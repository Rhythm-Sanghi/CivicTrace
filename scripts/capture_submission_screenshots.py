import sys
import os
from playwright.sync_api import sync_playwright

WEB_BASE = "http://localhost:5173"
OUT_DIR = "docs/screenshots"

def capture_ten_desktop_screenshots():
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Consistent desktop viewport (1440x900)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("Capturing 10 consistent desktop screenshots...")

        # 1. Overview (Home View)
        page.goto(f"{WEB_BASE}/")
        page.wait_for_selector("text=The state of your neighborhood", timeout=10000)
        page.screenshot(path=f"{OUT_DIR}/01_overview.png")
        page.screenshot(path=f"{OUT_DIR}/01_homepage.png")
        print("  [OK] 01_overview.png")

        # 2. Cases Explorer
        page.goto(f"{WEB_BASE}/explorer")
        page.wait_for_selector("text=Public Cases Explorer", timeout=10000)
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
        page.wait_for_selector("text=Geographic inspection canvas", timeout=10000)
        # Click pan right once to demonstrate interactive canvas state
        page.click("button[title='Pan Right']")
        page.screenshot(path=f"{OUT_DIR}/04_geographic_investigation.png")
        print("  [OK] 04_geographic_investigation.png")

        # 5. Case Dossier
        page.goto(f"{WEB_BASE}/cases/CAS-2026-0001")
        page.wait_for_selector("text=Case summary & provenance", timeout=10000)
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
        page.wait_for_selector("text=Duplicate Correlation & Case Consolidation", timeout=10000)
        page.screenshot(path=f"{OUT_DIR}/06_duplicate_suggestion.png")
        print("  [OK] 06_duplicate_suggestion.png")

        # 7. Resolution Dispute (Disputed Case CAS-2026-0002)
        page.goto(f"{WEB_BASE}/cases/CAS-2026-0002")
        page.wait_for_selector("text=DISPUTED", timeout=10000)
        page.screenshot(path=f"{OUT_DIR}/07_resolution_dispute.png")
        print("  [OK] 07_resolution_dispute.png")

        # 8. Evidence Timeline (Append-Only Cryptographic Event Chain)
        page.goto(f"{WEB_BASE}/cases/CAS-2026-0001")
        page.wait_for_selector("text=Append-Only Accountability Timeline", timeout=10000)
        page.screenshot(path=f"{OUT_DIR}/08_evidence_timeline.png")
        print("  [OK] 08_evidence_timeline.png")

        # 9. Intelligence
        page.goto(f"{WEB_BASE}/neighborhood")
        page.wait_for_selector("text=Indore Central & North Ward Intelligence", timeout=10000)
        page.screenshot(path=f"{OUT_DIR}/09_intelligence.png")
        page.screenshot(path=f"{OUT_DIR}/04_neighborhood_intelligence.png")
        print("  [OK] 09_intelligence.png")

        # 10. Report Issue Form
        page.goto(f"{WEB_BASE}/report")
        page.wait_for_selector("text=Report an Infrastructure Defect", timeout=10000)
        page.screenshot(path=f"{OUT_DIR}/10_report_issue_form.png")
        page.screenshot(path=f"{OUT_DIR}/06_report_form.png")
        print("  [OK] 10_report_issue_form.png")

        browser.close()
        print("\nAll 10 required desktop screenshots successfully captured!")

if __name__ == "__main__":
    capture_ten_desktop_screenshots()
