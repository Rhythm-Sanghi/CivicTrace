import sys
import os
from playwright.sync_api import sync_playwright

WEB_BASE = "http://localhost:5173"
OUT_DIR = "docs/screenshots"

def capture_redesign_screens():
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 1440px desktop viewport
        context_1440 = browser.new_context(viewport={"width": 1440, "height": 900})
        page_1440 = context_1440.new_page()

        print("Capturing 1440px screenshots...")
        page_1440.goto(f"{WEB_BASE}/")
        page_1440.wait_for_selector("text=The state of your neighborhood", timeout=10000)
        page_1440.screenshot(path=f"{OUT_DIR}/01_homepage_1440.png")
        page_1440.screenshot(path=f"{OUT_DIR}/01_homepage.png")

        page_1440.goto(f"{WEB_BASE}/explorer")
        page_1440.wait_for_selector("text=Public Cases Explorer", timeout=10000)
        page_1440.screenshot(path=f"{OUT_DIR}/02_cases_explorer_1440.png")
        page_1440.screenshot(path=f"{OUT_DIR}/02_cases_explorer.png")

        page_1440.goto(f"{WEB_BASE}/cases/CAS-2026-0001")
        page_1440.wait_for_selector("text=Append-Only Accountability Timeline", timeout=10000)
        page_1440.screenshot(path=f"{OUT_DIR}/03_case_details_ledger_1440.png")
        page_1440.screenshot(path=f"{OUT_DIR}/03_case_details_ledger.png")

        page_1440.goto(f"{WEB_BASE}/neighborhood")
        page_1440.wait_for_selector("text=Indore Central & North Ward Intelligence", timeout=10000)
        page_1440.screenshot(path=f"{OUT_DIR}/04_neighborhood_intelligence_1440.png")
        page_1440.screenshot(path=f"{OUT_DIR}/04_neighborhood_intelligence.png")

        page_1440.goto(f"{WEB_BASE}/login")
        page_1440.wait_for_selector("text=CivicTrace Portal Sign-In", timeout=10000)
        page_1440.screenshot(path=f"{OUT_DIR}/05_signin_view_1440.png")
        page_1440.screenshot(path=f"{OUT_DIR}/05_signin_view.png")

        page_1440.goto(f"{WEB_BASE}/report")
        page_1440.wait_for_selector("text=Report an Infrastructure Defect", timeout=10000)
        page_1440.screenshot(path=f"{OUT_DIR}/06_report_form_1440.png")
        page_1440.screenshot(path=f"{OUT_DIR}/06_report_form.png")

        # 1920px widescreen viewport
        context_1920 = browser.new_context(viewport={"width": 1920, "height": 1080})
        page_1920 = context_1920.new_page()
        print("Capturing 1920px widescreen screenshots...")
        page_1920.goto(f"{WEB_BASE}/")
        page_1920.wait_for_selector("text=The state of your neighborhood", timeout=10000)
        page_1920.screenshot(path=f"{OUT_DIR}/01_homepage_1920.png")

        page_1920.goto(f"{WEB_BASE}/explorer")
        page_1920.wait_for_selector("text=Public Cases Explorer", timeout=10000)
        page_1920.screenshot(path=f"{OUT_DIR}/02_cases_explorer_1920.png")

        page_1920.goto(f"{WEB_BASE}/cases/CAS-2026-0001")
        page_1920.wait_for_selector("text=Append-Only Accountability Timeline", timeout=10000)
        page_1920.screenshot(path=f"{OUT_DIR}/03_case_details_ledger_1920.png")

        # Mobile viewport (375px)
        context_mobile = browser.new_context(viewport={"width": 375, "height": 812})
        page_mobile = context_mobile.new_page()
        print("Capturing 375px mobile screenshot...")
        page_mobile.goto(f"{WEB_BASE}/")
        page_mobile.wait_for_selector("text=The state of your neighborhood", timeout=10000)
        page_mobile.screenshot(path=f"{OUT_DIR}/01_homepage_mobile_375.png")

        browser.close()
        print("All screenshots successfully captured!")

if __name__ == "__main__":
    capture_redesign_screens()
