"""Opt-in real Chromium end-to-end check. Requires a running app and Playwright.

Uses actual authentication/APIs/database/processing; no network mocks. Creates an
isolated development sample user for screenshots and a temporary account for
CRUD flows. Passwords/tokens are never written to the report or printed.
"""

import argparse
import json
from pathlib import Path
import re
import secrets
import tempfile
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    screenshots = ROOT / "docs" / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    report = {
        "base_url": base,
        "flows": [],
        "responsive_views": [],
        "browser_errors": [],
        "api_errors": [],
    }
    with (
        sync_playwright() as p,
        tempfile.TemporaryDirectory(prefix="grounded-browser-") as temporary,
    ):
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 1440, "height": 1050}, accept_downloads=True
        )
        page = context.new_page()
        page.on("pageerror", lambda error: report["browser_errors"].append(str(error)))
        page.on(
            "response",
            lambda response: (
                report["api_errors"].append(
                    {"path": response.url.split("/api/")[-1], "status": response.status}
                )
                if "/api/" in response.url and response.status >= 500
                else None
            ),
        )
        page.goto(base + "/login", wait_until="networkidle")
        page.screenshot(path=str(screenshots / "login.png"), full_page=True)
        page.get_by_role("link", name="Create an account", exact=False).click()
        email = f"browser-{uuid4().hex[:16]}@example.com"
        password = secrets.token_urlsafe(20) + "9a"
        page.locator('input[autocomplete="name"]').fill("Test Engineer")
        page.locator('input[autocomplete="email"]').fill(email)
        page.locator('input[autocomplete="new-password"]').fill(password)
        page.get_by_role("button", name="Create account", exact=True).click()
        expect(page).to_have_url(re.compile(r"/dashboard$"))
        expect(page.get_by_text("Clarity starts with your first meeting.")).to_be_visible()
        report["flows"].append("registration and authenticated empty dashboard")
        page.get_by_role("link", name="New meeting", exact=True).first.click()
        page.get_by_label("Meeting title", exact=False).fill("Browser verification meeting")
        page.get_by_label("Participants", exact=False).fill("Maya, Rahul, Test Engineer")
        page.get_by_label("Project / team", exact=False).fill("Atlas")
        transcript = """Maya: Topic: deployment. Project: Atlas. We discussed a staged deployment.
Maya: Decision: We agreed to use a canary release.
Rahul: I'll add deployment rollback tests by 2026-10-08. High priority.
Maya: Action: document the deployment runbook. No owner or deadline is specified.
Maya: Risk: delivery may be delayed because staging is blocked.
Rahul: Open question: Who will approve the production deployment?
Maya: Follow-up: revisit the rollout checklist in the next meeting."""
        page.get_by_label("Meeting transcript", exact=True).fill(transcript)
        page.get_by_role("button", name="Save & analyse", exact=False).click()
        expect(page.locator(".meeting-health-row")).to_be_visible(timeout=30000)
        meeting_id = page.url.split("/meetings/")[-1].split("?")[0]
        expect(
            page.locator("#action-items").get_by_text("Unassigned", exact=True).first
        ).to_be_visible()
        expect(
            page.locator("#action-items").get_by_text("Not specified", exact=True).first
        ).to_be_visible()
        report["flows"].append(
            "meeting creation, persisted background processing, explicit owners/deadlines and missing-field fallbacks"
        )
        page.locator("#summary .evidence-trigger").first.click()
        page.locator("#summary").get_by_role("button", name="View in transcript").first.click()
        expect(page.locator("#transcript")).to_have_attribute("open", "")
        expect(page.locator(".transcript-line.highlight").first).to_be_visible()
        report["flows"].append("source evidence expansion and transcript line navigation")
        page.get_by_role("button", name="Add action", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Task", exact=False).fill("Write end-to-end test report")
        dialog.get_by_label("Owner", exact=True).fill("Test Engineer")
        dialog.get_by_label("Notes", exact=True).fill("Human-created action")
        dialog.get_by_role("button", name="Save action", exact=True).click()
        expect(dialog).not_to_be_visible()
        expect(
            page.locator("#action-items").get_by_text("Write end-to-end test report", exact=True)
        ).to_be_visible()
        page.get_by_role("button", name="Complete Write end-to-end test report", exact=True).click()
        expect(
            page.get_by_role("button", name="Reopen Write end-to-end test report", exact=True)
        ).to_be_visible()
        report["flows"].append("manual action creation, notes and real completion state")
        page.locator("#risks").get_by_role("button", name="Mark resolved", exact=True).first.click()
        expect(page.locator("#risks").get_by_text("Resolved", exact=True)).to_be_visible()
        page.locator("#questions").get_by_role(
            "button", name="Add an answer", exact=True
        ).first.click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Your answer", exact=False).fill("The release lead will approve it.")
        dialog.get_by_role("button", name="Save answer", exact=True).click()
        expect(
            page.locator("#questions").get_by_text("Human-provided answer", exact=True)
        ).to_be_visible()
        report["flows"].append("risk resolution and human-provided question answers")
        for fmt, label in [
            ("pdf", "PDF document"),
            ("docx", "Word document"),
            ("json", "Structured JSON"),
            ("markdown", "Markdown notes"),
            ("csv", "Actions CSV"),
        ]:
            page.get_by_role("button", name="Export", exact=False).first.click()
            with page.expect_download() as download_info:
                page.get_by_role("button", name=label, exact=True).click()
            destination = Path(temporary) / download_info.value.suggested_filename
            download_info.value.save_as(str(destination))
            assert destination.stat().st_size > 50
        report["flows"].append("PDF, DOCX, JSON, Markdown and CSV browser downloads")
        page.goto(base + "/actions?filter=My%20Tasks", wait_until="networkidle")
        expect(page.get_by_text("Write end-to-end test report", exact=True)).to_be_visible()
        page.get_by_role("button", name="Edit Write end-to-end test report", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Priority", exact=True).select_option("Critical")
        dialog.get_by_role("button", name="Save action", exact=True).click()
        expect(page.locator(".action-table").get_by_text("Critical", exact=True)).to_be_visible()
        report["flows"].append("My Tasks filtering and action editing")
        page.goto(base + "/documents", wait_until="networkidle")
        document = Path(temporary) / "additional.txt"
        document.write_text("Rahul: Action: prepare the deployment handover by 2026-10-09.")
        page.locator('input[type="file"]').set_input_files(str(document))
        page.get_by_role("button", name="Upload document", exact=True).click()
        expect(
            page.locator(".document-table").get_by_text("additional.txt", exact=True)
        ).to_be_visible()
        page.get_by_role("button", name="Preview additional.txt", exact=True).click()
        expect(page.get_by_role("dialog").locator(".document-preview")).to_contain_text(
            "deployment handover"
        )
        page.get_by_role("button", name="Close dialog", exact=True).click()
        page.get_by_role("button", name="Attach additional.txt", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Select meeting", exact=False).select_option(meeting_id)
        dialog.get_by_role("button", name="Attach document", exact=True).click()
        expect(dialog).not_to_be_visible()
        page.goto(base + f"/meetings/{meeting_id}", wait_until="networkidle")
        expect(
            page.get_by_text("The conversation is here. Let’s find the clarity.", exact=True)
        ).to_be_visible()
        page.get_by_role("button", name="Analyse meeting", exact=True).first.click()
        expect(page.locator(".meeting-health-row")).to_be_visible(timeout=30000)
        report["flows"].append(
            "real TXT upload, extraction preview, attachment, stale-result invalidation and reprocessing"
        )
        page.goto(base + "/search", wait_until="networkidle")
        page.get_by_label("Semantic search query", exact=True).fill("deployment")
        page.get_by_role("button", name="Search", exact=True).click()
        expect(page.locator(".search-result").first).to_be_visible()
        page.goto(base + "/assistant", wait_until="networkidle")
        page.get_by_label("Ask about your meeting history", exact=True).fill(
            "What tasks are assigned to me?"
        )
        page.get_by_role("button", name="Send question", exact=True).click()
        expect(page.locator(".answer-claim").first).to_be_visible(timeout=30000)
        expect(page.locator(".inline-citations a").first).to_be_visible()
        page.get_by_role("button", name=re.compile("retrieved source")).click()
        expect(page.locator(".answer-source").first).to_be_visible()
        report["flows"].append(
            "hybrid retrieval, own-history assistant answers and source citations"
        )
        page.goto(base + "/settings", wait_until="networkidle")
        page.get_by_label("Full name", exact=False).fill("Test Engineer Updated")
        page.get_by_role("button", name="Save changes", exact=True).click()
        expect(
            page.locator(".profile-summary").get_by_text("Test Engineer Updated", exact=True)
        ).to_be_visible()
        page.get_by_role("button", name="Log out", exact=True).click()
        expect(page).to_have_url(re.compile("/login$"))
        page.locator('input[autocomplete="email"]').fill(email)
        page.locator('input[autocomplete="current-password"]').fill(password)
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(page).to_have_url(re.compile("/dashboard$"))
        report["flows"].append("profile update, JWT logout/revocation and re-login")
        # Sample account creates real labelled records via the development endpoint.
        seed = httpx.post(base + "/api/dev/demo-session", json={}, timeout=60)
        if seed.status_code == 201:
            token = seed.json()["access_token"]
            page.evaluate("token => sessionStorage.setItem('grounded_access_token', token)", token)
            for route, filename in [
                ("dashboard", "dashboard"),
                ("meetings", "meetings"),
                ("actions", "actions"),
                ("documents", "documents"),
                ("assistant", "assistant"),
                ("search", "search"),
                ("settings", "settings"),
            ]:
                page.goto(base + "/" + route, wait_until="networkidle")
                page.screenshot(path=str(screenshots / (filename + ".png")), full_page=True)
            headers = {"Authorization": "Bearer " + token}
            first = httpx.get(base + "/api/meetings", headers=headers).json()["items"][0]
            page.goto(base + "/meetings/" + first["id"], wait_until="networkidle")
            page.screenshot(path=str(screenshots / "meeting-detail.png"), full_page=True)
            for width, height in [(1440, 1050), (1024, 900), (768, 1024), (390, 844)]:
                page.set_viewport_size({"width": width, "height": height})
                for route in [
                    "dashboard",
                    "meetings",
                    "actions",
                    "documents",
                    "search",
                    "assistant",
                    "settings",
                    "meetings/new",
                    "meetings/" + first["id"],
                ]:
                    page.goto(base + "/" + route, wait_until="networkidle")
                    overflow = page.evaluate(
                        "document.documentElement.scrollWidth > innerWidth + 1"
                    )
                    assert not overflow, f"Horizontal overflow on {route} at {width}px"
                    report["responsive_views"].append(
                        {"route": route, "width": width, "overflow": False}
                    )
                if width == 390:
                    page.goto(base + "/dashboard", wait_until="networkidle")
                    page.screenshot(path=str(screenshots / "dashboard-mobile.png"), full_page=True)
                    page.get_by_role("button", name="Open navigation", exact=True).click()
                    expect(page.locator(".sidebar")).to_have_class(re.compile(r"\bopen\b"))
                    page.get_by_role("link", name="Meetings", exact=True).click()
                    expect(page).to_have_url(re.compile("/meetings$"))
            report["flows"].append("development sample data and responsive navigation")
        assert not report["browser_errors"], report["browser_errors"]
        assert not report["api_errors"], report["api_errors"]
        browser.close()
    report["status"] = "passed"
    (ROOT / "docs" / "browser-verification.json").write_text(json.dumps(report, indent=2))
    print(
        f"Browser checks passed: {len(report['flows'])} flows, {len(report['responsive_views'])} responsive views; no browser/API runtime errors."
    )


if __name__ == "__main__":
    main()
