"""Opt-in real browser acceptance with a per-test SQLite database."""
import os
import socket
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import pytest
import uvicorn
from sqlalchemy.orm import Session

from app.db import build_engine, upgrade_schema
from app.demo_seed import create_demo_csv
from app.demo_restore import mark_empty_database
from app.main import create_app
from app.pipeline import import_csv_bytes

pytestmark = pytest.mark.skipif(os.getenv("RUN_BROWSER") != "1", reason="set RUN_BROWSER=1 for Playwright")


@pytest.fixture
def live_dashboard(tmp_path, monkeypatch, request):
    monkeypatch.setenv("DEMO_RESET_ENABLED", "1")
    for name in ("GPS_WINDOW_START", "GPS_WINDOW_END", "GPS_EXPECTED_INTERVAL_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    mode = getattr(request, "param", None)
    if mode == "public":
        monkeypatch.setenv("DEMO_PUBLIC_READONLY", "true")
    if mode is True:
        monkeypatch.setenv("GPS_WINDOW_START", "2026-11-16T16:00:00Z")
        monkeypatch.setenv("GPS_WINDOW_END", "2026-11-16T21:05:00Z")
        monkeypatch.setenv("GPS_EXPECTED_INTERVAL_SECONDS", "300")
    engine = build_engine(f"sqlite:///{tmp_path / 'browser.db'}")
    upgrade_schema(engine)
    demo = create_demo_csv(tmp_path / "synthetic_demo.csv")
    with Session(engine) as session, session.begin():
        mark_empty_database(session)
        import_csv_bytes(session, demo.read_bytes(), demo.name)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_app(engine), log_level="warning"))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 10
            while not server.started and monotonic() < deadline:
                sleep(0.05)
            assert server.started, "Local browser test service failed to start"
            yield f"http://127.0.0.1:{port}", demo
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            engine.dispose()


def test_dashboard_workflow(live_dashboard):
    from playwright.sync_api import expect, sync_playwright

    url, demo = live_dashboard
    screenshot_root = os.getenv("DEMO_SCREENSHOTS")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.getenv("BROWSER_CHANNEL"))
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(url + "/") else route.abort())
        page.goto(f"{url}/?basemap=none", wait_until="domcontentloaded")
        expect(page.locator("#metric-observations")).to_have_text("366")
        expect(page.locator(".gps-route").first).to_be_visible()
        expect(page.locator(".map-placeholder")).to_have_count(0)
        expect(page.locator(".activity-area")).to_be_visible()
        expect(page.locator(".start-marker")).to_be_visible()
        expect(page.locator(".end-marker")).to_be_visible()

        def capture(name, selector=None):
            if screenshot_root:
                path = Path(screenshot_root) / f"{name}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                if selector:
                    page.locator(selector).screenshot(path=path, animations="disabled")
                else:
                    page.screenshot(path=path, animations="disabled")

        capture("dashboard")
        page.locator("#participant").select_option("SYN-P002")
        expect(page.locator("#analytics-context")).to_contain_text("SYN-P002")
        expect(page.locator("#daily-metrics tr")).to_have_count(2)
        expect(page.locator("#daily-metrics").get_by_role("cell", name="N/A", exact=True)).to_have_count(2)
        capture("analytics", "#analytics")
        page.locator("#day").select_option("2026-11-17")
        expect(page.locator("#selected-samples")).to_have_text("61")
        expect(page.locator("#analytics-context")).to_have_text("SYN-P002 · 2026-11-17")
        expect(page.locator("#daily-metrics tr")).to_have_count(1)
        expect(page.locator(".gps-route")).to_have_count(1)
        page.get_by_label("Activity area", exact=True).uncheck()
        expect(page.locator(".activity-area")).to_have_count(0)
        page.get_by_label("Activity area", exact=True).check()
        expect(page.locator(".activity-area")).to_be_visible()
        capture("gis-map", "#explorer")

        for fmt, extension in (("observations", ".csv"), ("route", ".geojson")):
            page.locator("#export-format").select_option(fmt)
            with page.expect_download() as event:
                page.locator("#export-btn").click()
            download = event.value
            assert download.suggested_filename.endswith(extension)
            assert download.path().stat().st_size > 0

        page.locator("#csv-file").set_input_files(demo)
        expect(page.locator("#import-preview")).to_contain_text("timestamp_utc")
        page.locator("#upload-form button").click()
        expect(page.locator("#import-result")).to_contain_text("duplicates: 366")
        page.locator("#csv-file").set_input_files({
            "name": "synthetic_quality.csv", "mimeType": "text/csv",
            "buffer": b"participant_id,timestamp_utc,latitude,longitude,steps\n"
                      b"SYN-WEB,2026-11-16T12:00:00Z,34,-118,2\n"
                      b"SYN-WEB,2026-11-16T12:05:00Z,100,-118,4\n"
                      b"SYN-WEB,2026-11-16T12:10:00Z,34,-118,-1\n"
                      b"SYN-WEB,2026-11-16T12:15:00Z,35,-118,4\n"
                      b"SYN-WEB,2026-11-16T12:20:00Z,35,-118,4\n",
        })
        page.locator("#upload-form button").click()
        expect(page.locator("#import-result")).to_contain_text("Accepted: 3")
        expect(page.locator("#metric-observations")).to_have_text("369")
        expect(page.locator("#quality-records li")).to_have_count(2)
        page.locator("#participant").select_option("SYN-WEB")
        expect(page.locator("#trajectory-flags li")).to_have_count(2)
        capture("data-quality", "#quality")
        page.locator("#trajectory-reason").select_option("speed_outlier")
        expect(page.locator("#trajectory-flags li")).to_have_count(1)
        page.locator("#quality-reason").select_option("coordinates outside valid WGS84 range")
        expect(page.locator("#quality-records li")).to_have_count(1)

        page.once("dialog", lambda dialog: dialog.dismiss())
        page.get_by_role("button", name="Restore demo data").click()
        expect(page.locator("#metric-observations")).to_have_text("369")
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="Restore demo data").click()
        expect(page.locator("#metric-observations")).to_have_text("366")

        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        expect(page.get_by_role("button", name="Download")).to_be_visible()
        assert not errors
        browser.close()


@pytest.mark.parametrize("live_dashboard", [True], indirect=True)
def test_dashboard_shows_expected_sampling_when_configured(live_dashboard):
    from playwright.sync_api import expect, sync_playwright

    url, _ = live_dashboard
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.getenv("BROWSER_CHANNEL"))
        page = browser.new_page()
        page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(url + "/") else route.abort())
        page.goto(f"{url}/?basemap=none", wait_until="domcontentloaded")
        rows = page.locator("#daily-metrics tr")
        expect(rows).to_have_count(2)
        expect(rows.first.locator("td").nth(5)).to_have_text("100.0%")
        expect(rows.last.locator("td").nth(5)).to_have_text("N/A")
        browser.close()

@pytest.mark.parametrize("live_dashboard", ["public"], indirect=True)
def test_public_dashboard_hides_writes_and_keeps_map_and_export(live_dashboard):
    from playwright.sync_api import expect, sync_playwright

    url, _ = live_dashboard
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.getenv("BROWSER_CHANNEL"))
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(url + "/") else route.abort())
        page.goto(f"{url}/?basemap=none")
        expect(page.locator(".gps-route").first).to_be_visible()
        expect(page.locator("#upload-form")).to_be_hidden()
        expect(page.locator("#restore-demo")).to_be_hidden()
        expect(page.locator("#import-result")).to_contain_text("disabled")
        page.locator("#participant").select_option("SYN-P002")
        page.locator("#day").select_option("2026-11-17")
        expect(page.locator("#daily-metrics tr")).to_have_count(1)
        with page.expect_download() as download:
            page.locator("#export-btn").click()
        assert download.value.suggested_filename.endswith(".csv")
        assert page.request.post(url + "/api/import").status == 403
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        browser.close()
