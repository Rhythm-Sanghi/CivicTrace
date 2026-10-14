import sys
import os
import time
import subprocess
import tempfile
import httpx
from playwright.sync_api import sync_playwright

WEB_BASE = "http://127.0.0.1:5173"
API_BASE = "http://127.0.0.1:8000/api/v1"

api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "api"))
web_dir = os.path.abspath(os.path.join(api_dir, "..", "..", "apps", "web"))

VIEWPORTS = [
    {"name": "Mobile 320px", "width": 320, "height": 568},
    {"name": "Mobile 375px", "width": 375, "height": 667},
    {"name": "Mobile 390px", "width": 390, "height": 844},
    {"name": "Tablet 768px", "width": 768, "height": 1024},
    {"name": "Desktop 1024px", "width": 1024, "height": 768},
    {"name": "Desktop 1440px", "width": 1440, "height": 900},
    {"name": "Desktop 1920px", "width": 1920, "height": 1080},
]

ROUTES = [
    {"path": "/", "name": "Overview"},
    {"path": "/explorer", "name": "Cases Explorer"},
    {"path": "/cases/CAS-2026-0001", "name": "Case Dossier (CAS-0001)"},
    {"path": "/cases/CAS-2026-0002", "name": "Disputed Case (CAS-0002)"},
    {"path": "/report", "name": "Report Issue"},
    {"path": "/neighborhood", "name": "Neighborhood Intelligence"},
    {"path": "/login", "name": "Sign In"},
    {"path": "/register", "name": "Create Account"},
]


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
        print("Starting backend...")
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=api_dir,
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
        print("Starting frontend...")
        vite_log = open(os.path.join(tempfile.gettempdir(), "visual_vite.log"), "w", encoding="utf-8")
        frontend_proc = subprocess.Popen(
            ["npx.cmd" if os.name == "nt" else "npx", "vite", "--port", "5173", "--strictPort", "--host", "127.0.0.1"],
            cwd=web_dir,
            stdout=vite_log,
            stderr=vite_log,
        )

    for _ in range(30):
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


def run_visual_audit():
    backend_proc, frontend_proc = ensure_servers()
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            print("=" * 70)
            print("CIVICTRACE VISUAL & RESPONSIVE AUDIT ACROSS ALL REQUIRED VIEWPORTS")
            print("=" * 70)

            for vp in VIEWPORTS:
                context = browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
                page = context.new_page()

                for r in ROUTES:
                    page.goto(f"{WEB_BASE}{r['path']}")
                    page.wait_for_load_state("networkidle")
                    time.sleep(0.3)

                    # Check 1: Document level horizontal overflow
                    has_doc_overflow = page.evaluate("""
                        () => {
                            const scrollW = document.documentElement.scrollWidth;
                            const innerW = window.innerWidth;
                            return scrollW > innerW + 1; // 1px threshold for subpixel rounding
                        }
                    """)

                    scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
                    inner_width = page.evaluate("() => window.innerWidth")

                    # Check 2: Action buttons visibility & clipping
                    buttons_clipped = page.evaluate("""
                        () => {
                            const btns = Array.from(document.querySelectorAll('button.button-primary, a.button-primary'));
                            for (const b of btns) {
                                const rect = b.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    if (rect.right > window.innerWidth + 2 || rect.left < -2) {
                                        return true;
                                    }
                                }
                            }
                            return false;
                        }
                    """)

                    # Check 3: Table container containment
                    tables_scrollable = page.evaluate("""
                        () => {
                            const tables = Array.from(document.querySelectorAll('table'));
                            for (const t of tables) {
                                const parent = t.closest('.table-shell');
                                if (!parent) return false;
                            }
                            return true;
                        }
                    """)

                    status = "PASS" if not has_doc_overflow and not buttons_clipped else "FAIL"
                    results.append({
                        "viewport": vp["name"],
                        "route": r["name"],
                        "path": r["path"],
                        "inner_width": inner_width,
                        "scroll_width": scroll_width,
                        "has_doc_overflow": has_doc_overflow,
                        "buttons_clipped": buttons_clipped,
                        "tables_scrollable": tables_scrollable,
                        "status": status,
                    })

                    if status == "FAIL":
                        print(f"  [FAIL] {vp['name']} @ {r['name']} ({r['path']}): scrollW={scroll_width} vs innerW={inner_width}, buttons_clipped={buttons_clipped}")

                context.close()

            # Zoom check: 200% browser zoom simulation on desktop & mobile
            for zoom_vp in [{"name": "Desktop 1440px @ 200% Zoom", "width": 1440, "height": 900},
                            {"name": "Mobile 375px @ 200% Zoom", "width": 375, "height": 667}]:
                context = browser.new_context(
                    viewport={"width": zoom_vp["width"], "height": zoom_vp["height"]},
                    device_scale_factor=2.0
                )
                page = context.new_page()
                for r in ROUTES:
                    page.goto(f"{WEB_BASE}{r['path']}")
                    page.wait_for_load_state("networkidle")
                    page.evaluate("document.body.style.zoom = '200%'")
                    time.sleep(0.3)

                    has_doc_overflow = page.evaluate("""
                        () => {
                            const scrollW = document.documentElement.scrollWidth;
                            const innerW = window.innerWidth;
                            return scrollW > innerW + 1;
                        }
                    """)
                    scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
                    inner_width = page.evaluate("() => window.innerWidth")

                    status = "PASS" if not has_doc_overflow else "FAIL"
                    results.append({
                        "viewport": zoom_vp["name"],
                        "route": r["name"],
                        "path": r["path"],
                        "inner_width": inner_width,
                        "scroll_width": scroll_width,
                        "has_doc_overflow": has_doc_overflow,
                        "buttons_clipped": False,
                        "tables_scrollable": True,
                        "status": status,
                    })
                    if status == "FAIL":
                        print(f"  [FAIL] {zoom_vp['name']} @ {r['name']}: scrollW={scroll_width} vs innerW={inner_width}")
                context.close()

            browser.close()

            total = len(results)
            passed = sum(1 for r in results if r["status"] == "PASS")
            print("-" * 70)
            print(f"Audit Summary: {passed}/{total} viewport/route checks PASSED.")
            print("-" * 70)
            return results
    finally:
        if backend_proc:
            backend_proc.terminate()
            backend_proc.wait()
        if frontend_proc:
            frontend_proc.terminate()
            frontend_proc.wait()


if __name__ == "__main__":
    results = run_visual_audit()
    failures = [r for r in results if r["status"] == "FAIL"]
    if failures:
        sys.exit(1)
    else:
        print("Visual & responsive audit succeeded across all viewports!")
        sys.exit(0)
