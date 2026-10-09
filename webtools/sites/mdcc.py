"""MDCC Onlineservice automation: login and invoice download."""

import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeout,
)

from ..config import load_credentials
from ..session import DEFAULT_PROFILE_DIR, browser_session

COMMAND = "mdcc-invoices"
DESCRIPTION = "Download the newest MDCC invoice as PDF."

LOGIN_URL = "https://service.mdcc.de/"
INVOICES_URL = "https://service.mdcc.de/rechnungen"
LOGOUT_URL = "https://service.mdcc.de/logout"

# links to invoice pdf downloads
_INVOICE_LINK = "a[href*='/rechnungen/download/'][href$='.pdf']"


def add_arguments(parser):
    """CLI flags for the mdcc-invoices subcommand."""
    parser.add_argument("--out", default="P:/Downloads")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--channel", default="chrome")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--count", type=int, default=1,
        help="number of recent invoices to download (default: 1)",
    )


def login(page, username, password, *, timeout=60):
    """Submit the MDCC login form; returns when Abmelden is visible."""
    print("Opening MDCC login page...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    # the public page also shows an Abmelden link; the login form is
    # the reliable signal for "not logged in"
    if page.query_selector("#username") is None:
        print("Existing session found, already logged in")
        return
    print("Filling login form...")
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("input[name='submit']")
    try:
        # login form disappears once authenticated
        page.wait_for_selector(
            "#username", state="detached", timeout=timeout * 1000
        )
    except PlaywrightTimeout:
        page.screenshot(path=".webtools/mdcc-login-fail.png")
        raise RuntimeError(f"MDCC login failed (last URL: {page.url})")
    print("Logged in")


def download_invoices(page, output_dir, *, count=1):
    """Download the newest invoices; returns list of saved Paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("Navigating to invoices page...")
    page.goto(INVOICES_URL, wait_until="domcontentloaded")
    page.wait_for_selector(_INVOICE_LINK, timeout=30000)

    # newest first; fetch the pdf in-process so no viewer opens
    saved = []
    for link in page.query_selector_all(_INVOICE_LINK)[:count]:
        href = link.get_attribute("href")
        url = urljoin(page.url, href)
        filename = url.rsplit("/", 1)[-1]
        try:
            response = page.context.request.get(url)
        except PlaywrightError as error:
            print(f"  {filename}: fetch failed: {error}")
            continue
        if response.status != 200:
            print(f"  {filename}: HTTP {response.status}")
            continue
        target = out / f"MDCC-{filename}"
        target.write_bytes(response.body())
        print(f"Saved {target}")
        saved.append(target)
        time.sleep(1)
    return saved


def logout(page):
    """Log out of the MDCC Onlineservice."""
    print("Logging out...")
    try:
        page.goto(LOGOUT_URL, wait_until="domcontentloaded")
    except PlaywrightError as error:
        print(f"  logout failed: {error}")


def run(args):
    """Full flow: credentials -> session -> login -> download invoices."""
    # env vars: MDCC_USERNAME / MDCC_PASSWORD
    username, password = load_credentials("mdcc")
    with browser_session(
        args.profile, headless=args.headless, channel=args.channel
    ) as (_context, page):
        try:
            login(page, username, password)
            saved = download_invoices(page, args.out, count=args.count)
            logout(page)
            return saved
        except PlaywrightError as error:
            if "closed" in str(error):
                raise RuntimeError(
                    "The browser window was closed before the run finished"
                ) from error
            raise
