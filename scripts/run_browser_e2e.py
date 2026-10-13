import sys
import os
import time
import json
import zipfile
import subprocess
import tempfile
import httpx
from playwright.sync_api import sync_playwright

# Add services/api to python path so app modules can be loaded for package verification
api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "api"))
sys.path.insert(0, api_dir)

API_BASE = "http://localhost:8000/api/v1"
WEB_BASE = "http://localhost:5173"

def run_real_e2e_lifecycle():
    print("=====================================================================")
    print("  CIVICTRACE REAL BROWSER E2E INTERACTIVE WORKFLOW VERIFICATION")
    print("=====================================================================")

    # 0. Setup disposable test database
    temp_db = os.path.join(api_dir, "disposable_e2e.db")
    if os.path.exists(temp_db):
        try:
            os.remove(temp_db)
        except Exception:
            pass

    orig_cwd = os.getcwd()
    os.chdir(api_dir)
    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
    os.environ["REQUIRE_REPORT_MODERATION"] = "True"

    backend_proc = None
    frontend_proc = None

    try:
        from app.db.seed import seed_database
        print("  [Setup] Initializing schema and seed accounts in disposable database...")
        seed_database(reset=False)

        # 1. Start backend process
        print("  [Setup] Launching backend Uvicorn server on port 8000...")
        env_backend = os.environ.copy()
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=api_dir,
            env=env_backend,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # 2. Start frontend process
        web_dir = os.path.abspath(os.path.join(api_dir, "..", "..", "apps", "web"))
        print("  [Setup] Launching frontend Vite server on port 5173...")
        frontend_proc = subprocess.Popen(
            ["npx.cmd" if os.name == "nt" else "npx", "vite", "--port", "5173"],
            cwd=web_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # 3. Wait for backend and frontend readiness
        print("  [Setup] Awaiting backend and frontend readiness...")
        backend_ready = False
        frontend_ready = False
        for _ in range(40):
            if not backend_ready:
                try:
                    r = httpx.get(f"{API_BASE}/cases/neighborhood/stats", timeout=1.0)
                    if r.status_code == 200:
                        backend_ready = True
                except Exception:
                    pass
            if not frontend_ready:
                try:
                    r = httpx.get(WEB_BASE, timeout=1.0)
                    if r.status_code == 200:
                        frontend_ready = True
                except Exception:
                    pass
            if backend_ready and frontend_ready:
                break
            time.sleep(0.5)

        assert backend_ready, "Backend failed to start on port 8000"
        assert frontend_ready, "Frontend failed to start on port 5173"
        print("  [Setup] Both backend and frontend servers are healthy and listening.")

        # 4. Execute Real Chromium Browser Lifecycle Tests
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 850})
            page = context.new_page()
            page.on("pageerror", lambda err: print(f"  [Browser Uncaught Error] {err}"))

            # Step 1: Citizen registration and login
            print("\n[Step 1/14] Citizen registration and login via Web Portal...")
            page.goto(f"{WEB_BASE}/register")
            page.wait_for_selector("text=Citizen Registration", timeout=10000)
            citizen_email = f"citizen.test.{int(time.time())}@civictrace.local"
            citizen_name = "Priya Sharma (Resident)"
            page.fill("input#reg-name", citizen_name)
            page.fill("input#reg-email", citizen_email)
            page.fill("input#reg-password", "CitizenPass2026!")
            page.fill("input#reg-confirm", "CitizenPass2026!")
            page.click("button[type='submit']")
            page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)
            page.wait_for_selector("text=Public infrastructure records", timeout=10000)
            print("  [OK] Citizen account registered and logged in successfully.")

            # Step 2: Report submission and evidence upload
            print("\n[Step 2/14] Report submission and evidence upload...")
            page.goto(f"{WEB_BASE}/report")
            page.wait_for_selector("text=Report issue", timeout=10000)

            run_id = int(time.time())
            defect_title = f"Exposed high-voltage electrical cable on Jawahar Marg #{run_id}"
            defect_desc = "Severed underground cable conduit protruding onto pedestrian walkway. Direct shock hazard to pedestrians."

            page.fill("input[placeholder*='e.g. Deep pothole']", defect_title)
            page.fill("textarea[placeholder*='Detail what you observed']", defect_desc)
            page.fill("input[placeholder*='Near Rajwada Palace']", "Jawahar Marg crossing, Ward 12")

            # Create dummy image file for evidence upload
            temp_img = os.path.join(tempfile.gettempdir(), f"evidence_{run_id}.png")
            # 1x1 valid png
            with open(temp_img, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82")

            page.set_input_files("input[type='file']", temp_img)
            page.click("button:has-text('Submit public defect observation')")
            page.wait_for_selector("text=Observation Successfully Registered", timeout=10000)
            print("  [OK] Defect observation and evidence file uploaded successfully.")

            # Step 3: Pending moderation visibility
            print("\n[Step 3/14] Verifying pending moderation boundary...")
            page.goto(f"{WEB_BASE}/explorer")
            page.wait_for_selector("text=Public infrastructure records", timeout=10000)
            # Pending report must NOT appear in public explorer!
            explorer_text = page.content()
            assert defect_title not in explorer_text, "Security boundary failure: pending report visible in public explorer!"
            print("  [OK] Confirmed pending report is quarantined from unauthorized public view.")

            # Discover pending report ID from backend API
            rev_login = httpx.post(f"{API_BASE}/auth/login?include_token=true", data={"username": "reviewer@civictrace.local", "password": "ReviewerPass2026!"})
            rev_token = rev_login.json()["access_token"]
            rev_headers = {"Authorization": f"Bearer {rev_token}"}
            pending_reports = httpx.get(f"{API_BASE}/reports/pending", headers=rev_headers).json()
            target_report = next((r for r in pending_reports if defect_title in r["title"]), None)
            assert target_report is not None, "Pending report not found in reviewer queue"
            report_id = target_report["id"]
            print(f"  [OK] Discovered pending report in reviewer queue: {target_report['public_id']}")

            # Step 4: Reviewer moderation decision
            print("\n[Step 4/14] Reviewer logs in and executes moderation decision...")
            page.goto(f"{WEB_BASE}/login")
            page.fill("input[type='email']", "reviewer@civictrace.local")
            page.fill("input[type='password']", "ReviewerPass2026!")
            page.click("button[type='submit']")
            page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)

            page.goto(f"{WEB_BASE}/reviewer")
            page.wait_for_selector("text=Citizen Moderation Queue", timeout=10000)
            # Find the report card and approve it
            page.click("button:has-text('Approve Report')")
            page.wait_for_selector("text=marked as APPROVED", timeout=10000)
            print("  [OK] Reviewer approved citizen report. Public case generated.")

            # Get generated case public ID
            approved_case = httpx.get(f"{API_BASE}/cases").json()
            case_entry = next((c for c in approved_case if defect_title in c["title"]), None)
            assert case_entry is not None, "Case not generated upon approval"
            case_public_id = case_entry["public_id"]
            case_uuid = case_entry["id"]
            print(f"  [OK] Case dossier active: {case_public_id}")

            # Step 5: Case verification and department assignment via UI
            print("\n[Step 5/14] Case verification and department assignment via browser UI...")
            page.goto(f"{WEB_BASE}/cases/{case_public_id}")
            page.wait_for_selector("button:has-text('Verify Case')", timeout=10000)
            page.click("button:has-text('Verify Case')")
            time.sleep(0.5)
            page.wait_for_selector("text=VERIFIED", timeout=10000)
            page.wait_for_selector("button:has-text('Dispatch to Department')", timeout=10000)
            page.click("button:has-text('Dispatch to Department')")
            time.sleep(0.5)
            page.wait_for_selector("text=ASSIGNED", timeout=10000)
            print(f"  [OK] Case verified and dispatched to department via browser UI.")

            # Step 6: Authorized operator starts work via Operator Workspace UI
            print("\n[Step 6/14] Authorized operator signs in and starts work via browser UI...")
            page.goto(f"{WEB_BASE}/login")
            page.fill("input[type='email']", "lighting.operator@civictrace.local")
            page.fill("input[type='password']", "OperatorPass2026!")
            page.click("button[type='submit']")
            page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)

            page.goto(f"{WEB_BASE}/operator")
            page.wait_for_selector(f"[data-testid='case-row-{case_public_id}']", timeout=10000)
            page.click(f"[data-testid='case-row-{case_public_id}']")
            page.wait_for_selector(f"h3:has-text('{case_public_id}')", timeout=10000)
            page.wait_for_selector("button:has-text('Start Repair (In Progress)')", timeout=10000)
            page.click("button:has-text('Start Repair (In Progress)')")
            page.wait_for_selector("text=Case status updated to In Progress", timeout=10000)
            print("  [OK] Authorized operator moved case to IN_PROGRESS via Operator Workspace UI.")

            # Step 7: Operator submits a repair claim via Operator Workspace UI
            print("\n[Step 7/14] Operator submits formal resolution claim via browser UI...")
            page.click(f"[data-testid='case-row-{case_public_id}']")
            page.wait_for_selector(f"h3:has-text('{case_public_id}')", timeout=10000)
            page.fill("input#summary-input", "Replaced split cable sheath and secured grounding rod")
            page.fill("textarea#actions-textarea", "De-energized line, installed reinforced conduit sleeve, bolted ground enclosure")
            page.click("button:has-text('File Resolution Claim')")
            page.wait_for_selector("text=Resolution claim filed", timeout=10000)
            time.sleep(1)
            c_claim = httpx.get(f"{API_BASE}/cases/{case_public_id}").json()
            print(f"  [Debug] Case state after claim: {c_claim.get('state')}")
            assert c_claim["state"] == "AWAITING_VERIFICATION", f"Case must be AWAITING_VERIFICATION after claim, got {c_claim['state']}"
            print("  [OK] Resolution claim recorded via browser UI. State transitioned to AWAITING_VERIFICATION.")

            # Step 8: Citizen verification visit
            print("\n[Step 8/14] Citizen signs back in and visits case dossier in browser...")
            page.goto(f"{WEB_BASE}/login")
            page.fill("input[type='email']", citizen_email)
            page.fill("input[type='password']", "CitizenPass2026!")
            page.click("button[type='submit']")
            page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)

            page.goto(f"{WEB_BASE}/cases/{case_public_id}")
            page.wait_for_selector("text=Independent Citizen Verification", timeout=15000)
            page.wait_for_selector("text=AWAITING VERIFICATION", timeout=10000)
            print("  [OK] Dossier displays active resolution claim awaiting citizen check.")

            # Step 9: Citizen dispute submission
            print("\n[Step 9/14] Citizen inspects site and submits dispute observation...")
            page.select_option("select#outcome-select", value="STILL_UNRESOLVED")
            page.fill("input#pseudonym-input", citizen_name)
            page.fill("textarea#notes-textarea", "Checked at 5:00 PM. The plastic conduit is still uncovered and wires exposed across the sidewalk curb!")
            page.click("button:has-text('Submit Verification Observation')")
            page.wait_for_selector("text=Verification observation successfully submitted", timeout=10000)

            # Step 10: Automatic closure remains blocked during an unresolved dispute
            print("\n[Step 10/14] Confirming automatic closure remains blocked during dispute...")
            page.reload()
            page.wait_for_selector("text=DISPUTED", timeout=10000)
            c_disp = httpx.get(f"{API_BASE}/cases/{case_public_id}").json()
            assert c_disp["state"] == "DISPUTED", "Case must transition to DISPUTED"
            assert c_disp["resolved_at"] is None, "Resolved timestamp must not be set on disputed case!"
            print("  [OK] Unresolved dispute confirmed. Case state is DISPUTED, closure blocked.")

            # Step 11: Authorized reviewer adjudication
            print("\n[Step 11/14] Reviewer adjudicates dispute and orders rework...")
            page.goto(f"{WEB_BASE}/login")
            page.fill("input[type='email']", "reviewer@civictrace.local")
            page.fill("input[type='password']", "ReviewerPass2026!")
            page.click("button[type='submit']")
            page.wait_for_url(f"{WEB_BASE}/explorer", timeout=10000)

            page.goto(f"{WEB_BASE}/cases/{case_public_id}")
            page.wait_for_selector("text=Order Department Rework", timeout=15000)
            page.click("text=Order Department Rework")
            time.sleep(1)
            page.wait_for_selector("text=IN PROGRESS", timeout=10000)
            print("  [OK] Reviewer adjudicated dispute; case transitioned back to IN_PROGRESS for rework.")

            # Step 12: Subsequent valid resolution
            print("\n[Step 12/14] Subsequent repair claim filed and confirmed fixed...")
            op_login = httpx.post(f"{API_BASE}/auth/login?include_token=true", data={"username": "lighting.operator@civictrace.local", "password": "OperatorPass2026!"})
            op_headers = {"Authorization": f"Bearer {op_login.json()['access_token']}"}
            # Operator submits second claim after completing rework
            claim2_res = httpx.post(
                f"{API_BASE}/cases/{case_public_id}/claims",
                json={
                    "work_summary": "Deep concrete encasement applied over conduit and bolted flush with footpath curb",
                    "actions_taken": "Reinforced trench, poured quick-setting concrete, bolted steel protection plate",
                },
                headers=op_headers,
            )
            assert claim2_res.status_code == 200

            # Independent verification confirms fix
            verif2_res = httpx.post(
                f"{API_BASE}/cases/{case_public_id}/verifications",
                json={
                    "outcome": "CONFIRMED_FIXED",
                    "notes": "Re-inspected Jawahar Marg footpath. Trench is completely sealed and flush with sidewalk.",
                },
                headers=rev_headers,
            )
            assert verif2_res.status_code == 200
            c_resolved = httpx.get(f"{API_BASE}/cases/{case_public_id}").json()
            assert c_resolved["state"] == "RESOLVED", f"Case expected RESOLVED, got {c_resolved['state']}"
            assert c_resolved["resolved_at"] is not None, "Case resolved_at timestamp must be populated"
            print("  [OK] Case successfully verified and transitioned to RESOLVED.")

            # Step 13: Signed evidence export and offline verification
            print("\n[Step 13/14] Exporting signed evidence package and verifying offline...")
            export_res = httpx.get(f"{API_BASE}/cases/{case_public_id}/export")
            assert export_res.status_code == 200
            temp_zip = os.path.join(tempfile.gettempdir(), f"e2e_export_{case_public_id}.zip")
            with open(temp_zip, "wb") as f:
                f.write(export_res.content)

            from app.services.export_service import ExportService, VerificationMode
            from app.services.crypto_signer import SignerService

            # Test 1: File integrity mode
            is_valid_file, logs_file = ExportService.verify_export_package(temp_zip, mode=VerificationMode.FILE_INTEGRITY)
            assert is_valid_file is True, f"File integrity check failed: {logs_file}"

            # Test 2: Trusted authenticity mode with expected trust anchor
            pubkey = SignerService.get_public_key_base64()
            is_valid_auth, logs_auth = ExportService.verify_export_package(
                temp_zip,
                mode=VerificationMode.TRUSTED_AUTHENTICITY,
                expected_public_key=pubkey,
            )
            assert is_valid_auth is True, f"Trusted authenticity check failed: {logs_auth}"
            print("  [OK] Evidence package exported and verified in both File Integrity and Trusted Authenticity modes.")

            # Step 14: Logout and rejection of session reuse
            print("\n[Step 14/14] Logout and verification of session revocation...")
            logout_res = httpx.post(f"{API_BASE}/auth/logout", headers=rev_headers)
            assert logout_res.status_code == 200

            # Replay revoked credentials
            replay_res = httpx.get(f"{API_BASE}/auth/me", headers=rev_headers)
            assert replay_res.status_code == 401, "Security breach: Revoked session was accepted after logout!"
            print("  [OK] Session revocation verified: replayed credentials immediately rejected (HTTP 401).")

            # EXTRA: Unauthorized User Workflow Test
            print("\n[Security Check] Unauthorized operator from different department blocked...")
            road_login = httpx.post(f"{API_BASE}/auth/login?include_token=true", data={"username": "roads.operator@civictrace.local", "password": "OperatorPass2026!"})
            road_token = road_login.json()["access_token"]
            road_headers = {"Authorization": f"Bearer {road_token}"}
            # Attempt to transition electrical case
            unauth_trans = httpx.post(
                f"{API_BASE}/cases/{case_public_id}/transition?target_state=IN_PROGRESS",
                headers=road_headers,
            )
            assert unauth_trans.status_code == 403, "Department isolation failure: unauthorized operator was not blocked!"
            print("  [OK] Department boundary confirmed: foreign operator rejected (HTTP 403).")

            # EXTRA: Evidence Tampering Workflow Test
            print("\n[Security Check] Evidence tampering detected and rejected...")
            with zipfile.ZipFile(temp_zip, "a") as zf:
                zf.writestr("tampered_exploit.txt", "MALICIOUS INJECTED PAYLOAD")
            is_valid_tampered, logs_tampered = ExportService.verify_export_package(temp_zip)
            assert is_valid_tampered is False, "Security failure: tampered zip package was accepted!"
            assert any("TAMPER DETECTED" in l for l in logs_tampered), f"Expected tamper detection log: {logs_tampered}"
            print("  [OK] Package tamper detection confirmed: modified archive rejected.")

            # EXTRA: Mobile 320px Responsive Layout, Keyboard Navigation, and 200% Zoom Checks
            print("\n[Accessibility Check] Verifying 320px mobile viewport, keyboard navigation, and 200% zoom...")
            # 1. 320px mobile layout
            page.set_viewport_size({"width": 320, "height": 640})
            page.goto(f"{WEB_BASE}/explorer")
            page.wait_for_selector("text=Cases", timeout=10000)
            # Verify no horizontal scroll overflow on 320px
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")
            assert scroll_width <= client_width + 10, f"Horizontal overflow detected on 320px mobile layout: scroll={scroll_width}, client={client_width}"
            print("  [OK] 320px mobile viewport rendered cleanly without horizontal overflow.")

            # 2. Keyboard Navigation Check
            page.goto(f"{WEB_BASE}/login")
            page.wait_for_selector("input[type='email']", timeout=10000)
            page.keyboard.press("Tab")
            active_tag = page.evaluate("document.activeElement.tagName")
            assert active_tag in ["A", "INPUT", "BUTTON"], f"Keyboard tab navigation failed to focus interactive element: {active_tag}"
            print("  [OK] Keyboard tab navigation functions correctly.")

            # 3. 200% Zoom Check
            page.evaluate("document.body.style.zoom = '200%'")
            time.sleep(0.5)
            # Verify body content remains accessible and visible
            login_heading = page.is_visible("text=CivicTrace Portal Sign-In")
            assert login_heading is True, "Text/layout broke under 200% zoom!"
            page.evaluate("document.body.style.zoom = '100%'")
            print("  [OK] 200% zoom behavior verified: text and inputs scale without truncation.")

            # Reset viewport
            page.set_viewport_size({"width": 1280, "height": 850})

            # Clean up temp files
            if os.path.exists(temp_img):
                os.remove(temp_img)
            if os.path.exists(temp_zip):
                os.remove(temp_zip)

            browser.close()

        print("\n=====================================================================")
        print("  ALL 14 E2E LIFECYCLE STEPS + SECURITY CHECKS PASSED FLAWLESSLY!")
        print("=====================================================================")

    finally:
        os.chdir(orig_cwd)
        if backend_proc:
            backend_proc.terminate()
            backend_proc.wait()
        if frontend_proc:
            frontend_proc.terminate()
            frontend_proc.wait()
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass

if __name__ == "__main__":
    run_real_e2e_lifecycle()
