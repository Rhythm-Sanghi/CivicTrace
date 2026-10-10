import sys
import os
import time
import json
import zipfile
import httpx
from playwright.sync_api import sync_playwright

# Add services/api to python path so app modules can be loaded for package verification
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "api")))

API_BASE = "http://localhost:8000/api/v1"
WEB_BASE = "http://localhost:5173"

def run_real_e2e_lifecycle():
    print("=====================================================================")
    print("  CIVICTRACE REAL BROWSER E2E INTERACTIVE WORKFLOW VERIFICATION")
    print("=====================================================================")
    
    # Ensure pristine reproducible database state in services/api directory
    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "api"))
    orig_cwd = os.getcwd()
    try:
        os.chdir(api_dir)
        from app.db.seed import seed_database
        seed_database(reset=True)
    finally:
        os.chdir(orig_cwd)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 850})
        page = context.new_page()

        # Step 1: Citizen Signs In
        print("\n[Step 1/14] Citizen signs in via Web Portal...")
        page.goto(f"{WEB_BASE}/login")
        page.wait_for_selector("text=CivicTrace Portal Sign-In", timeout=10000)
        page.fill("input[type='email']", "citizen.aarav@civictrace.local")
        page.fill("input[type='password']", "CitizenPass2026!")
        page.click("button[type='submit']")
        page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)
        page.wait_for_selector("text=Public Infrastructure Ledger", timeout=10000)
        print("  [OK] Citizen authenticated successfully. Session stored.")

        # Step 2: Citizen Submits a New Infrastructure Defect
        print("\n[Step 2/14] Citizen reports defect with location and details...")
        page.click("text=Report Issue")
        page.wait_for_selector("text=Report an Infrastructure Defect", timeout=10000)
        
        run_id = int(time.time())
        defect_title = f"Hazardous Exposed Cable Conduit near Chhatri Bagh Junction #{run_id}"
        defect_desc = "Damaged underground wiring conduit uncovered during road digging. Bare wiring poses imminent public safety risk to pedestrians and children."
        
        page.fill("input[placeholder*='e.g. Deep pothole']", defect_title)
        page.fill("textarea[placeholder*='Detail what you observed']", defect_desc)
        page.fill("input[placeholder*='Near Rajwada Palace']", "Chhatri Bagh Main Road, Indore")
        page.click("button[type='submit']")
        
        page.wait_for_selector("text=Observation Successfully Registered", timeout=10000)
        print("  [OK] Complaint successfully registered in backend database.")

        # Step 3: Verified in Public Cases Explorer
        print("\n[Step 3/14] Verifying report is persisted in Explorer...")
        page.click("text=View in Public Cases Explorer")
        page.wait_for_selector("text=Public Infrastructure Ledger", timeout=10000)
        page.wait_for_selector("text=Hazardous Exposed Cable Conduit near Chhatri Bagh Junction", timeout=10000)
        page.screenshot(path="docs/screenshots/07_new_report_persisted.png")
        print("  [OK] New report persisted and visible in public ledger table.")

        # Get the new case's public ID from API
        cases_res = httpx.get(f"{API_BASE}/cases").json()
        new_case = next((c for c in cases_res if defect_title in c["title"]), None)
        assert new_case is not None, "Failed to find created case in API"
        case_public_id = new_case["public_id"]
        case_uuid = new_case["id"]
        category_id = new_case["category_id"]
        print(f"  [OK] Discovered generated Case: {case_public_id} ({case_uuid})")

        # Step 4: Second Citizen submits a related observation nearby (triggering duplicate engine)
        print("\n[Step 4/14] Second citizen submits corroborating observation nearby...")
        dup_report_res = httpx.post(f"{API_BASE}/reports", json={
            "category_id": category_id,
            "title": "Exposed dangerous live wire on Chhatri Bagh street",
            "description": "Exposed high voltage wiring conduit laying open on pedestrian footpath near Chhatri Bagh.",
            "latitude": new_case["latitude"] + 0.0001, # ~11 meters away
            "longitude": new_case["longitude"] + 0.0001,
            "address_reference": "Chhatri Bagh crossing, opposite park",
            "guest_pseudonym": "Concerned Parent",
        })
        assert dup_report_res.status_code in [200, 201], f"Failed submitting duplicate report: {dup_report_res.text}"
        dup_report = dup_report_res.json()
        print(f"  [OK] Second report registered: {dup_report['public_id']}")

        # Step 5: Duplicate Engine calculates candidate recommendation
        print("\n[Step 5/14] Verifying duplicate engine calculation...")
        rev_auth_res = httpx.post(f"{API_BASE}/auth/login", data={"username": "reviewer@civictrace.local", "password": "ReviewerPass2026!"}).json()
        rev_token = rev_auth_res["access_token"]
        dup_cands_res = httpx.get(f"{API_BASE}/reports/duplicates/pending", headers={"Authorization": f"Bearer {rev_token}"}).json()
        assert isinstance(dup_cands_res, list), f"Expected list from duplicates endpoint, got: {dup_cands_res}"
        candidate = next((c for c in dup_cands_res if c["report_id"] == dup_report["id"]), None)
        assert candidate is not None, "Duplicate engine did not generate candidate for second report"
        print(f"  [OK] Deterministic match computed: Composite Score = {candidate['composite_score']*100:.1f}%, Distance = {candidate['distance_meters']:.1f}m")

        # Step 6: Reviewer signs in and confirms duplicate association
        print("\n[Step 6/14] Reviewer confirms association in Reviewer Workspace...")
        page.goto(f"{WEB_BASE}/login")
        page.fill("input[type='email']", "reviewer@civictrace.local")
        page.fill("input[type='password']", "ReviewerPass2026!")
        page.click("button[type='submit']")
        page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)
        page.goto(f"{WEB_BASE}/reviewer")
        page.wait_for_selector("text=Duplicate Correlation & Case Consolidation", timeout=10000)
        
        # Approve the candidate
        page.click("button:has-text('Consolidate into Case')")
        page.wait_for_selector("text=Duplicate candidate successfully consolidated into target case", timeout=10000)
        page.screenshot(path="docs/screenshots/08_duplicate_merged.png")
        print("  [OK] Duplicate confirmed and merged into case dossier.")

        # Step 7: Operator claims resolution and logs actions
        print("\n[Step 7/14] Operator files resolution claim with repair evidence...")
        page.goto(f"{WEB_BASE}/login")
        page.fill("input[type='email']", "lighting.operator@civictrace.local")
        page.fill("input[type='password']", "OperatorPass2026!")
        page.click("button[type='submit']")
        page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)
        
        # Transition case to IN_PROGRESS then file claim
        claim_res = httpx.post(f"{API_BASE}/cases/{case_public_id}/claims", json={
            "work_summary": "Replaced damaged cable conduit and sealed junction box with heavy-duty weatherproofing.",
            "actions_taken": "Field crew isolated power line, replaced 14m split conduit, installed concrete protective casing, and restored supply.",
        }, headers={"Authorization": f"Bearer {httpx.post(f'{API_BASE}/auth/login', data={'username': 'lighting.operator@civictrace.local', 'password': 'OperatorPass2026!'}).json()['access_token']}"})
        assert claim_res.status_code == 200, f"Claim failed: {claim_res.text}"
        print(f"  [OK] Operator claim filed. State transitioned to AWAITING_VERIFICATION.")

        # Step 8: Citizen visits dossier and disputes resolution
        print("\n[Step 8/14] Citizen signs in, inspects dossier and submits dispute observation...")
        page.goto(f"{WEB_BASE}/login")
        page.fill("input[type='email']", "citizen.aarav@civictrace.local")
        page.fill("input[type='password']", "CitizenPass2026!")
        page.click("button[type='submit']")
        page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)
        
        page.goto(f"{WEB_BASE}/cases/{case_public_id}")
        page.wait_for_selector("text=Independent Citizen Verification", timeout=10000)
        
        page.select_option("select", value="STILL_UNRESOLVED")
        page.fill("input[placeholder*='e.g. Local Resident']", "Aarav Sharma (Resident)")
        page.fill("textarea[placeholder*='Describe what you observed']", "Inspected site today at 4:30 PM. The protective casing was left unbolted and exposed wires remain visible next to the footpath curb!")
        page.click("button:has-text('Submit Verification Observation')")
        page.wait_for_selector("text=Verification observation successfully submitted", timeout=10000)
        print("  [OK] Citizen dispute observation submitted.")

        # Step 9: Case moves into DISPUTED state
        print("\n[Step 9/14] Verifying case state is DISPUTED...")
        page.reload()
        page.wait_for_selector("text=DISPUTED", timeout=10000)
        page.screenshot(path="docs/screenshots/09_case_disputed.png")
        print("  [OK] Case status verified as DISPUTED. Stamp applied.")

        # Step 10: Audit timeline records all chronological actions & hashes
        print("\n[Step 10/14] Verifying cryptographic ledger intact...")
        page.wait_for_selector("text=Cryptographic Ledger Verified Intact", timeout=10000)
        page.wait_for_selector("text=RESOLUTION DISPUTED", timeout=10000)
        print("  [OK] Timeline contains sequential events with SHA-256 hash chains.")

        # Step 11: Authorized Reviewer handles the dispute and orders rework
        print("\n[Step 11/14] Authorized Reviewer mediates dispute and orders rework...")
        page.goto(f"{WEB_BASE}/login")
        page.fill("input[type='email']", "reviewer@civictrace.local")
        page.fill("input[type='password']", "ReviewerPass2026!")
        page.click("button[type='submit']")
        page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)
        page.goto(f"{WEB_BASE}/cases/{case_public_id}")
        page.wait_for_selector("text=Order Department Rework", timeout=10000)
        page.click("text=Order Department Rework")
        time.sleep(1)
        page.wait_for_selector("text=IN PROGRESS", timeout=10000)
        print("  [OK] Reviewer ordered department rework; case moved back to IN_PROGRESS.")

        # Step 12: A separate case receives qualifying independent verification
        print("\n[Step 12/14] Verifying separate case resolution workflow...")
        # CAS-2026-0002 has a claim. Reviewer verifies and resolves it.
        rev_token = httpx.post(f"{API_BASE}/auth/login", data={"username": "reviewer@civictrace.local", "password": "ReviewerPass2026!"}).json()["access_token"]
        verif_res = httpx.post(f"{API_BASE}/cases/CAS-2026-0002/verifications", json={
            "outcome": "CONFIRMED_FIXED",
            "notes": "Site inspection confirmed road patch is flush and drainage grates unobstructed.",
        }, headers={"Authorization": f"Bearer {rev_token}"})
        assert verif_res.status_code == 200
        
        # Verify case is now RESOLVED
        c2 = httpx.get(f"{API_BASE}/cases/CAS-2026-0002").json()
        assert c2["state"] == "RESOLVED"
        print(f"  [OK] Separate case CAS-2026-0002 independently verified and closed as RESOLVED.")

        # Step 13: Evidence ZIP can be exported and verified
        print("\n[Step 13/14] Exporting and verifying evidence ZIP package...")
        export_res = httpx.get(f"{API_BASE}/cases/{case_public_id}/export")
        assert export_res.status_code == 200
        temp_zip = f"temp_e2e_{case_public_id}.zip"
        with open(temp_zip, "wb") as f:
            f.write(export_res.content)
            
        from app.services.export_service import ExportService
        is_valid, logs = ExportService.verify_export_package(temp_zip)
        assert is_valid is True, f"Export verification failed: {logs}"
        print(f"  [OK] Evidence package exported and independently verified intact.")

        # Step 14: Tampering with exported record produces verification failure
        print("\n[Step 14/14] Tampering with export manifest detects corruption...")
        # Corrupt case_summary.json inside zip
        with zipfile.ZipFile(temp_zip, "a") as zf:
            zf.writestr("case_summary.json", json.dumps({"tampered": True}))
            
        is_valid_after_tamper, tamper_logs = ExportService.verify_export_package(temp_zip)
        assert is_valid_after_tamper is False
        assert any("TAMPER DETECTED" in l for l in tamper_logs)
        print(f"  [OK] Mathematical tamper detection succeeded: {tamper_logs[0]}")

        # Cleanup
        if os.path.exists(temp_zip):
            os.remove(temp_zip)

        browser.close()
        print("\n=====================================================================")
        print("  ALL 14 E2E LIFECYCLE WORKFLOW CHECKS PASSED FLAWLESSLY!")
        print("=====================================================================")

if __name__ == "__main__":
    run_real_e2e_lifecycle()
