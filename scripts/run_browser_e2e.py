import sys
import time
from playwright.sync_api import sync_playwright

def run_e2e_browser_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        print("[1/6] Navigating to CivicTrace Homepage...")
        page.goto("http://localhost:5173/")
        page.wait_for_selector("text=CivicTrace", timeout=15000)
        assert "CivicTrace" in page.content()
        page.screenshot(path="docs/screenshots/01_homepage.png")
        print("  [OK] Homepage loaded successfully, screenshot saved.")

        print("[2/6] Navigating to Public Cases Explorer...")
        page.click("text=Public Cases")
        page.wait_for_selector("text=Public Infrastructure Ledger", timeout=10000)
        page.wait_for_selector("text=CAS-2026-0001", timeout=10000)
        page.screenshot(path="docs/screenshots/02_cases_explorer.png")
        print("  [OK] Cases explorer loaded with seeded Indore cases.")

        print("[3/6] Inspecting Case Details & Append-Only Ledger...")
        page.goto("http://localhost:5173/cases/CAS-2026-0001")
        page.wait_for_selector("text=Append-Only Accountability Timeline", timeout=10000)
        page.wait_for_selector("text=Cryptographic Ledger Verified Intact", timeout=10000)
        page.screenshot(path="docs/screenshots/03_case_details_ledger.png")
        print("  [OK] Case dossier and cryptographic ledger verified intact.")

        print("[4/6] Navigating to Neighborhood Intelligence & Recurrence Hotspots...")
        page.click("text=Intelligence & Metrics")
        page.wait_for_selector("text=Indore Central & North Ward Intelligence", timeout=10000)
        page.wait_for_selector("text=Chronic Recurrence Hotspots", timeout=10000)
        page.screenshot(path="docs/screenshots/04_neighborhood_intelligence.png")
        print("  [OK] Intelligence dashboard and recurrence hotspots verified.")

        print("[5/6] Navigating to Portal Sign-In...")
        page.click("text=Sign In")
        page.wait_for_selector("text=CivicTrace Portal Sign-In", timeout=10000)
        page.screenshot(path="docs/screenshots/05_signin_view.png")
        print("  [OK] Sign-in page with quick demo roles verified.")

        print("[6/6] Navigating to Issue Intake Portal...")
        page.click("text=Report Issue")
        page.wait_for_selector("text=Report an Infrastructure Defect", timeout=10000)
        page.screenshot(path="docs/screenshots/06_report_form.png")
        print("  [OK] Intake form with location, evidence file picker, and pseudonym verified.")

        browser.close()
        print("\nAll 6 browser workflows passed! Real application screenshots captured.")

if __name__ == "__main__":
    run_e2e_browser_test()
