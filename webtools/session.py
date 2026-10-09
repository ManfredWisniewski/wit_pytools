"""Shared Playwright browser session helpers."""

import time
from contextlib import contextmanager
from pathlib import Path

DEFAULT_PROFILE_DIR = Path(".webtools/profile")


@contextmanager
def browser_session(
    profile_dir=DEFAULT_PROFILE_DIR, *, headless=False, channel=None
):
    """Yield a persistent (context, page) pair; cookies survive across runs."""
    from playwright.sync_api import sync_playwright

    profile = Path(profile_dir)
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile),
            # e.g. "chrome" uses the installed browser instead of bundled chromium
            channel=channel,
            headless=headless,
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True,
            # reduce automation detection (banking sites check for it)
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            yield context, page
        finally:
            context.close()


def wait_for(
    page,
    condition,
    *,
    timeout=180.0,
    interval=2.0,
    screenshot_path=None,
    on_wait=None,
):
    """Poll condition(page) until truthy or timeout; returns the result.

    If screenshot_path is set, the current page is captured there on every
    poll so the page state can be inspected while waiting. on_wait is an
    optional callable invoked on each poll (e.g. to dismiss popups).
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            result = condition(page)
        except Exception:
            result = False
        if result:
            return result
        if time.monotonic() >= deadline:
            return False
        if screenshot_path:
            try:
                page.screenshot(path=str(screenshot_path))
            except Exception:
                pass
        if on_wait:
            try:
                on_wait()
            except Exception:
                pass
        time.sleep(interval)
