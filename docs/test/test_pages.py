"""
Comprehensive page-by-page test of the myteam web application (v2 SPA).
Uses Playwright to navigate each route, take screenshots, and check for errors.
The frontend is served under /v2/ as a single-page application.
"""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, Error as PlaywrightError

BASE_URL = "http://localhost:8765/v2"
SCREENSHOT_DIR = Path("/Users/kuanghualong/Project/Cursor/myteam/docs/test/screenshots")
RESULTS_FILE = Path("/Users/kuanghualong/Project/Cursor/myteam/docs/test/TEST-RESULTS.md")

PAGES = {
    "dashboard": "/",
    "chat": "/chat",
    "groups": "/groups",
    "projects": "/projects",
    "execute": "/execute",
    "manage": "/manage",
    "workflows": "/workflows",
    "skills": "/skills",
    "mcp": "/mcp",
    "settings": "/settings",
}

def run_tests():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    all_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})

        page = context.new_page()

        def handle_console(msg):
            if msg.type == "error":
                all_errors.append(f"[{msg.type}] {msg.text}")

        page.on("console", handle_console)

        # Test each page
        for page_name, route in PAGES.items():
            print(f"\n--- Testing: {page_name} ({route}) ---")
            page_errors_before = len(all_errors)

            test_result = {
                "page": page_name,
                "route": route,
                "passed": False,
                "status": None,
                "errors": [],
                "console_errors": [],
                "screenshot": f"screenshots/{page_name}.png",
            }

            try:
                full_url = BASE_URL + route
                resp = page.goto(full_url, wait_until="domcontentloaded", timeout=15000)
                test_result["status"] = resp.status

                # Wait for JS to render
                page.wait_for_timeout(3000)

                # Check if page rendered correctly
                body_text = page.inner_text("body") if page.query_selector("body") else ""
                is_blank = len(body_text.strip()) < 50

                # Take screenshot
                screenshot_path = SCREENSHOT_DIR / f"{page_name}.png"
                page.screenshot(path=str(screenshot_path), full_page=False)
                print(f"  Screenshot saved: {screenshot_path}")

                # Console errors on this page
                console_errors = all_errors[page_errors_before:]
                test_result["console_errors"] = console_errors

                # Check key UI elements for the v2 frontend
                ui_checks = {}

                # Look for the main app container and key components
                selectors_to_check = {
                    "has_navbar": bool(page.query_selector("[class*='nav'], [class*='Nav'], nav, [data-testid='nav']")),
                    "has_main_content": bool(page.query_selector("main, [class*='main'], [class*='Main'], [data-testid='content']")),
                    "has_title_or_heading": bool(page.query_selector("h1, h2, [class*='title'], [class*='Title'], [class*='heading']")),
                    "has_sidebar_or_menu": bool(page.query_selector("aside, [class*='side'], [class*='menu'], [class*='Sidebar'], [class*='Panel']")),
                    "has_app_mount": bool(page.query_selector("#root, #app, [data-reactroot]")),
                    "has_discord_layout": bool(page.query_selector("[class*='layout'], [class*='Layout'], [class*='container'], [class*='Container']")),
                }

                # Check for specific page content indicators
                page_indicators = {
                    "dashboard_has_stats": bool(page.query_selector("[class*='stat'], [class*='Stat'], [class*='card'], [class*='Card']")),
                    "dashboard_has_table": bool(page.query_selector("table, [class*='table'], [class*='Table']")),
                    "chat_has_messages": bool(page.query_selector("[class*='message'], [class*='Message'], [class*='chat'], [class*='Chat']")),
                    "manage_has_form": bool(page.query_selector("form, [class*='form'], [class*='Form'], input, button")),
                }

                for k, v in selectors_to_check.items():
                    ui_checks[k] = v
                for k, v in page_indicators.items():
                    ui_checks[k] = v

                test_result["ui_checks"] = ui_checks

                # Determine pass/fail
                # For SPA: check for React mount point or meaningful content
                has_mount = page.query_selector("#root, #app")
                has_content = page.query_selector("main, [class*='main'], [class*='content'], [class*='Content']")
                has_nav = page.query_selector("nav, [class*='nav'], [class*='Nav']")

                # Check page title from document
                doc_title = page.evaluate("document.title")

                # Also check for specific UI class patterns common in React apps
                has_react_elements = bool(page.query_selector('[class*="Section"], [class*="section"], [class*="Panel"], [class*="panel"]'))

                # A page passes if:
                # 1. HTTP 200
                # 2. Has React mount point OR meaningful rendered content
                # 3. Not blank
                passed = (resp.status == 200 and
                         (has_mount or has_content or has_react_elements) and
                         not is_blank)

                test_result["passed"] = passed
                test_result["doc_title"] = doc_title

                status_str = "PASS" if passed else "FAIL"
                print(f"  [{status_str}] Status: {resp.status}, Title: '{doc_title}', Blank: {is_blank}")
                print(f"  Mount: {bool(has_mount)}, Content: {bool(has_content)}, Nav: {bool(has_nav)}, React: {bool(has_react_elements)}")
                print(f"  UI Checks: {json.dumps(ui_checks)}")
                if console_errors:
                    for err in console_errors[:3]:
                        print(f"  Console Error: {err}")

            except PlaywrightError as e:
                test_result["errors"] = [str(e)]
                test_result["notes"] = f"Navigation error: {e}"
                results.append(test_result)
                print(f"  [ERROR] {e}")
            except Exception as e:
                test_result["errors"] = [str(e)]
                results.append(test_result)
                print(f"  [ERROR] {e}")

        browser.close()

    # Print summary
    print("\n\n=== SUMMARY ===")
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count
    print(f"Total: {len(results)}, Passed: {passed_count}, Failed: {failed_count}")

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['page']} ({r['route']}) - Status: {r.get('status')}, Title: {r.get('doc_title', '')}")

    # Write results markdown
    write_results(results, all_errors)

    return results


def write_results(results, all_errors):
    lines = []
    lines.append("# TEST RESULTS - myteam Web Application (v2)")
    lines.append("")
    lines.append(f"**Date**: 2026-06-26")
    lines.append(f"**Base URL**: http://localhost:8765/v2")
    lines.append(f"**Viewport**: 1440x900")
    lines.append("")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    lines.append(f"## Summary: {passed}/{total} pages passed")
    lines.append("")

    lines.append("| Page | Route | HTTP | Result | Title |")
    lines.append("|------|-------|------|--------|-------|")

    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        title = r.get("doc_title", "N/A")
        lines.append(f"| {r['page']} | `{r['route']}` | {r.get('status', 'N/A')} | {status_str} | {title} |")

    lines.append("")

    # UI layout checks
    lines.append("## UI Layout Checks")
    lines.append("")
    lines.append("| Page | Navbar | Main Content | Heading | Sidebar/Menu | React Mount |")
    lines.append("|------|--------|-------------|---------|-------------|-------------|")

    for r in results:
        ui = r.get("ui_checks", {})
        lines.append(f"| {r['page']} | {'OK' if ui.get('has_navbar') else 'MISSING'} | {'OK' if ui.get('has_main_content') else 'MISSING'} | {'OK' if ui.get('has_title_or_heading') else 'MISSING'} | {'OK' if ui.get('has_sidebar_or_menu') else 'MISSING'} | {'OK' if ui.get('has_app_mount') else 'MISSING'} |")

    lines.append("")

    # Content-specific checks
    lines.append("## Content-Specific Checks")
    lines.append("")
    lines.append("| Page | Stats/Cards | Tables | Forms |")
    lines.append("|------|------------|--------|-------|")

    for r in results:
        ui = r.get("ui_checks", {})
        lines.append(f"| {r['page']} | {'OK' if ui.get('dashboard_has_stats') else '-'} | {'OK' if ui.get('dashboard_has_table') else '-'} | {'OK' if ui.get('manage_has_form') else '-'} |")

    lines.append("")

    # Screenshots
    lines.append("## Screenshots")
    lines.append("")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"- **{r['page']}** [{status}]: ![{r['page']}](screenshots/{r['page']}.png)")

    lines.append("")

    # Console errors
    if all_errors:
        lines.append("## Console Errors")
        lines.append("")
        lines.append(f"Total: {len(all_errors)} errors detected")
        lines.append("")
        lines.append("```")
        for err in all_errors[:50]:
            lines.append(err)
        lines.append("```")
    else:
        lines.append("## Console Errors")
        lines.append("")
        lines.append("No console errors detected.")

    lines.append("")

    # Detailed per-page
    lines.append("## Detailed Per-Page Results")
    lines.append("")

    for r in results:
        lines.append(f"### {r['page'].title()} (`{r['route']}`)")
        lines.append("")
        lines.append(f"- **Result**: {'PASS' if r['passed'] else 'FAIL'}")
        if r.get("status"):
            lines.append(f"- **HTTP Status**: {r['status']}")
        if r.get("doc_title"):
            lines.append(f"- **Document Title**: {r['doc_title']}")
        if r.get("ui_checks"):
            lines.append(f"- **UI Elements**:")
            for k, v in r["ui_checks"].items():
                lines.append(f"  - {k}: {'present' if v else 'missing'}")
        if r.get("console_errors"):
            lines.append(f"- **Console Errors** ({len(r['console_errors'])}):")
            for err in r["console_errors"][:5]:
                lines.append(f"  - {err}")
        if r.get("notes"):
            lines.append(f"- **Notes**: {r['notes']}")
        lines.append("")

    RESULTS_FILE.write_text("\n".join(lines))
    print(f"\nResults written to: {RESULTS_FILE}")


if __name__ == "__main__":
    run_tests()
