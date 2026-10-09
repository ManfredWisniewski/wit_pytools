"""American Express DE automation: login and statement download."""

import re
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeout,
)

from ..config import load_credentials
from ..session import DEFAULT_PROFILE_DIR, browser_session, wait_for

COMMAND = "amex-de-statements"
DESCRIPTION = "Download the newest Amex DE statement (PDF and CSV)."

LOGIN_URL = "https://www.americanexpress.com/en-us/account/login/"
STATEMENTS_URL = "https://www.americanexpress.com/en-us/account/statements"

# URL fragments that only appear once authenticated
_POST_LOGIN_MARKERS = (
    "dashboard",
    "account/summary",
    "account/home",
    "account/activity",
    "kontouebersicht",
)

# dashboard links leading to the statement list (DE first, US fallback)
_STATEMENTS_LINK_TEXTS = (
    "Abrechnung(en) runterladen",
    "Kontobewegungen & Abrechnungen",
    "Statements & Activity",
)

# texts that expand the full statement list
_EXPANDER_TEXTS = (
    "Ältere Abrechnungen",
    "Statements and Year End Summaries",
    "Older Statements",
)

# label text of the options in the Amex download dialog
_FORMAT_LABELS = {"pdf": "PDF", "csv": "CSV", "excel": "Excel"}


# texts that only render on the authenticated account dashboard
_DASHBOARD_MARKERS = (
    "Aktueller Kontostand",
    "Kontostand",
    "Statement Balance",
    "Make a Payment",
)


def is_logged_in(page):
    """Heuristic: dashboard content is only rendered when authenticated."""
    url = page.url.lower()
    if any(marker in url for marker in _POST_LOGIN_MARKERS):
        return True
    for text in _DASHBOARD_MARKERS:
        element = page.query_selector(f"text='{text}'")
        if element and element.is_visible():
            return True
    return False


def dismiss_overlays(page):
    """Close promo modals/cookie banners that may block page elements."""
    page.keyboard.press("Escape")
    for selector in (
        "[role='dialog'] button:has-text('Close')",
        "[role='dialog'] button:has-text('Schließen')",
        "[role='dialog'] button:has-text('No thanks')",
        "[role='dialog'] button:has-text('Nein danke')",
        "[role='dialog'] button:has-text('Maybe later')",
        "[role='dialog'] button:has-text('Später')",
        # session-timeout modal: keep session alive (never click "Abmelden")
        "button:has-text('Fortfahren')",
        "button:has-text('Continue')",
        "button[aria-label='Close']",
        "button[aria-label='close']",
        "button[aria-label='Schließen']",
        "button.close",
    ):
        try:
            element = page.query_selector(selector)
            if element and element.is_visible():
                element.click(timeout=1000)
        except Exception:
            pass
    # amex promo overlay that blocks the whole page
    interruptor = page.query_selector(
        "[data-module-name='axp-user-interruptor']"
    )
    if interruptor:
        for text in ("Schließen", "Close", "Später", "Nicht jetzt",
                     "Nein danke", "No thanks", "×"):
            try:
                element = interruptor.query_selector(
                    f"button:has-text('{text}'), a:has-text('{text}')"
                )
                if element and element.is_visible():
                    element.click(timeout=1000)
                    break
            except Exception:
                pass


def login(page, username, password, *, mfa_timeout=300):
    """Log in; MFA/captcha must be completed manually in the open browser."""
    print("Opening Amex login page...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    # a valid persisted session redirects away from the login page
    if wait_for(
        page,
        is_logged_in,
        timeout=15,
        screenshot_path=".webtools/debug-login.png",
        on_wait=lambda: dismiss_overlays(page),
    ):
        print("Existing session found, already logged in")
        return
    dismiss_overlays(page)
    print("Filling login form...")
    page.fill("#eliloUserID", username)
    page.fill("#eliloPassword", password)
    page.click("#loginSubmit", timeout=10000)
    print("Submitted; complete verification in the browser if prompted")
    if not wait_for(
        page,
        is_logged_in,
        timeout=mfa_timeout,
        screenshot_path=".webtools/debug-login.png",
        on_wait=lambda: dismiss_overlays(page),
    ):
        page.screenshot(path="webtools-amex-login-fail.png")
        raise RuntimeError(
            f"Amex login did not complete; finish verification in the "
            f"browser (last URL: {page.url})"
        )
    print("Logged in")


def _js_click(element):
    """Click without pointer hit-testing (amex overlays intercept clicks)."""
    try:
        element.click(timeout=8000)
    except PlaywrightError:
        element.dispatch_event("click")


def _open_download_dialog(page, button):
    """Click a row's Herunterladen until the format dialog appears."""
    for _ in range(3):
        dismiss_overlays(page)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except PlaywrightTimeout:
            pass
        # a leftover dialog from the previous iteration may still be open
        stale = page.query_selector(
            "[data-test-id='axp-activity-download-content']"
        )
        if stale and stale.is_visible():
            page.keyboard.press("Escape")
            time.sleep(1)
        _js_click(button)
        try:
            # the content wrapper has no bounding box; the confirm
            # button is the reliable visibility signal
            page.wait_for_selector(
                "button[data-test-id="
                "'axp-activity-download-footer-download-confirm']",
                timeout=10000,
            )
            return page.query_selector(
                "[data-test-id='axp-activity-download-content']"
            )
        except PlaywrightTimeout:
            page.screenshot(path=".webtools/debug-click.png")
            time.sleep(2)
            continue
    return None


def _confirm_format_dialog(page, fmt, dialog=None):
    """Pick the format inside the download dialog and confirm."""
    if dialog is None:
        try:
            page.wait_for_selector(
                "button[data-test-id="
                "'axp-activity-download-footer-download-confirm']",
                timeout=10000,
            )
            dialog = page.query_selector(
                "[data-test-id='axp-activity-download-content']"
            )
        except PlaywrightTimeout:
            print("  format dialog did not appear")
            return
    if dialog is None:
        print("  format dialog not found")
        return
    # radio inputs are id'd ...-type_pdf / type_csv / type_excel; the input
    # itself is visually hidden, so click its label
    option = dialog.query_selector(f"label[for$='-type_{fmt.lower()}']")
    if not option:
        label = _FORMAT_LABELS.get(fmt.lower())
        option = dialog.query_selector(f"label:has-text('{label}')")
    if option:
        _js_click(option)
    else:
        print(f"  format option '{fmt}' not found; keeping default")
    confirm = dialog.query_selector(
        "button[data-test-id='axp-activity-download-footer-download-confirm']"
    ) or dialog.query_selector(
        "button:has-text('Herunterladen'), button:has-text('Download')"
    )
    if confirm:
        _js_click(confirm)
    else:
        print("  confirm button not found")


def _goto_statements(page):
    """Open the statement list; prefers the direct href since promo overlays
    (axp-user-interruptor) can block clicks on the dashboard link."""
    link = page.query_selector("a[data-locator-id='download_statement_cta']")
    if link and link.get_attribute("href"):
        page.goto(
            urljoin(page.url, link.get_attribute("href")),
            wait_until="domcontentloaded",
        )
        return
    for text in _STATEMENTS_LINK_TEXTS:
        try:
            page.click(f"text='{text}'", timeout=5000)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except PlaywrightTimeout:
                pass
            return
        except PlaywrightTimeout:
            continue
    page.goto(STATEMENTS_URL, wait_until="domcontentloaded")


def _download_buttons(page, include_older=False):
    """Statement download buttons; the date is embedded in data-test-id."""
    buttons = page.query_selector_all(
        "button[data-test-id*='recent-statements'][data-test-id*='download-button']"
    )
    if include_older:
        buttons += page.query_selector_all(
            "button[data-test-id*='older-statements']"
            "[data-test-id*='download-button']"
        )
    # generic fallback for layouts without the amex test ids
    if not buttons:
        buttons = page.query_selector_all(
            "a[download], a[href*='.pdf'], "
            "button:has-text('Download'), a:has-text('Download'), "
            "button:has-text('Herunterladen'), a:has-text('Herunterladen')"
        )
    return [b for b in buttons if b.is_visible()]


_FORMAT_EXTENSIONS = {"pdf": ".pdf", "csv": ".csv", "excel": ".xlsx"}


def _statement_filename(test_id, index, fmt):
    date = re.search(r"(\d{4}-\d{2}-\d{2})", test_id or "")
    ext = _FORMAT_EXTENSIONS.get(fmt, f".{fmt}")
    if date:
        return f"amex-statement-{date.group(1)}{ext}"
    return f"amex-statement-{index}{ext}"


def download_statements(
    page, output_dir, *, count=1, formats=("pdf", "csv"), include_older=False
):
    """Download the most recent statements; returns list of saved Paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("Navigating to statements page...")
    _goto_statements(page)

    # an expired session may have bounced back to login/MFA; keep waiting
    if not wait_for(
        page,
        is_logged_in,
        timeout=60,
        screenshot_path=".webtools/debug-statements.png",
        on_wait=lambda: dismiss_overlays(page),
    ):
        raise RuntimeError("Not logged in after navigating to statements")
    dismiss_overlays(page)

    # expand the full statement list when the sections are present
    for text in _EXPANDER_TEXTS:
        try:
            page.click(f"text='{text}'", timeout=4000)
        except PlaywrightTimeout:
            pass

    # wait for the statement table to render
    try:
        page.wait_for_selector(
            "button[data-test-id*='download-button']", timeout=60000
        )
    except PlaywrightTimeout:
        pass
    page.screenshot(path=".webtools/debug-statements.png", full_page=True)
    Path(".webtools/debug-statements.html").write_text(
        page.content(), encoding="utf-8"
    )

    buttons = _download_buttons(page)
    if include_older and buttons:
        # the older-statements accordion exists but is collapsed
        try:
            page.click("#header-older-statements", timeout=3000)
        except PlaywrightTimeout:
            pass
        buttons = _download_buttons(page, include_older=True)
    if count is not None:
        buttons = buttons[:count]

    print(f"Found {len(buttons)} download button(s)")

    # statement files are requested through /servicing/v1/documents/;
    # fetch them in-process (node side) so no viewer popup or browser
    # download is needed
    captured = {}
    downloads = []
    page.on("download", lambda download: downloads.append(download))

    def _intercept(route):
        # only hijack document navigations (the download popup); XHR
        # calls to the same endpoint (e.g. the statement list) must
        # pass through untouched
        if route.request.resource_type != "document":
            try:
                route.continue_()
            except PlaywrightError:
                pass
            return
        try:
            response = route.fetch()
            captured[route.request.url] = response.body()
        except PlaywrightError:
            pass
        # abort: we already have the body; letting chrome load the
        # document (pdf viewer/popup) destabilizes the session
        try:
            route.abort()
        except PlaywrightError:
            pass

    for pattern in (
        "**/servicing/v1/documents/statements/**",
        "**/api/servicing/v1/financials/documents*",
    ):
        page.context.route(pattern, _intercept)

    # collect test ids first; element handles go stale across navigations
    test_ids = [b.get_attribute("data-test-id") for b in buttons]
    statements_url = page.url

    saved = []
    for index, test_id in enumerate(test_ids, start=1):
        for fmt in formats:
            target = out / _statement_filename(test_id, index, fmt)
            # the download may navigate/close the tab; re-open the
            # statements page to recover
            try:
                gone = page.is_closed() or (
                    "activity/statements" not in page.url
                )
            except PlaywrightError:
                gone = True
            if gone:
                # amex sometimes shows a transient "statements not
                # available" error right after a download; retry reloads
                reopened = False
                for _ in range(4):
                    try:
                        if page.is_closed():
                            page = page.context.new_page()
                        page.goto(
                            statements_url, wait_until="domcontentloaded"
                        )
                        page.wait_for_selector(
                            "button[data-test-id*='download-button']",
                            timeout=30000,
                        )
                        reopened = True
                        break
                    except PlaywrightError:
                        time.sleep(10)
                if not reopened:
                    try:
                        page.screenshot(path=".webtools/debug-reopen.png")
                        print(f"  reopen state: {page.url}")
                    except PlaywrightError:
                        pass
                    print(f"  statement {index}: reopen failed")
                    break
            try:
                button = page.query_selector(
                    f"button[data-test-id='{test_id}']"
                ) or page.query_selector(
                    "button[data-test-id*='recent-statements']"
                    "[data-test-id*='download-button']"
                )
            except PlaywrightError:
                button = None
            if button is None:
                print(f"  statement {index}: download button gone")
                break
            try:
                dialog = _open_download_dialog(page, button)
            except PlaywrightError as error:
                print(f"  statement {index}: click failed: {error}")
                break
            if dialog is None:
                print(f"  statement {index}: format dialog did not appear")
                break
            before = set(captured)
            before_d = len(downloads)
            _confirm_format_dialog(page, fmt, dialog)

            deadline = time.monotonic() + 30
            received = False
            while time.monotonic() < deadline:
                new_urls = set(captured) - before
                if new_urls:
                    target.write_bytes(captured[new_urls.pop()])
                    received = True
                    break
                if len(downloads) > before_d:
                    downloads[-1].save_as(str(target))
                    received = True
                    break
                time.sleep(0.5)

            # close popup tabs the site opened for the download
            for extra in page.context.pages:
                if extra is not page:
                    try:
                        extra.close()
                    except Exception:
                        pass
            if received:
                print(f"Saved {target}")
                saved.append(target)
            else:
                print(f"  statement {index} ({fmt}): no file received")

    try:
        page.context.unroute("**/servicing/v1/documents/statements/**")
        page.context.unroute("**/api/servicing/v1/financials/documents*")
    except PlaywrightError:
        pass
    return saved


def logout(page):
    """Log out of Amex to end the persisted session."""
    print("Logging out...")
    # the logout link lives in a collapsed nav (never is_visible());
    # navigating its href is more reliable than clicking
    element = page.query_selector(
        "#gnav_logout, a[href*='logout']"
    )
    if element is None:
        print("  logout link not found")
        return
    try:
        page.goto(
            urljoin(page.url, element.get_attribute("href")),
            wait_until="domcontentloaded",
        )
    except PlaywrightError as error:
        print(f"  logout failed: {error}")


def add_arguments(parser):
    """CLI flags for the amex-de-statements subcommand."""
    parser.add_argument("--out", default="P:/Downloads")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--channel", default="chrome")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--count", type=int, default=1,
        help="number of recent statements to download (default: 1)",
    )
    parser.add_argument(
        "--formats", default="pdf,csv",
        help="comma-separated formats: pdf,csv,excel (default: pdf,csv)",
    )
    parser.add_argument(
        "--older", action="store_true",
        help="also download from the 'Vergangene Abrechnungen' section",
    )
    parser.add_argument("--mfa-timeout", type=int, default=300)


def run(args):
    """Full flow: credentials -> session -> login -> download statements."""
    # env vars stay AMEX_USERNAME / AMEX_PASSWORD
    username, password = load_credentials("amex")
    with browser_session(
        args.profile, headless=args.headless, channel=args.channel
    ) as (_context, page):
        try:
            login(page, username, password, mfa_timeout=args.mfa_timeout)
            saved = download_statements(
                page,
                args.out,
                count=args.count,
                formats=tuple(args.formats.split(",")),
                include_older=args.older,
            )
            logout(page)
            return saved
        except PlaywrightError as error:
            if "closed" in str(error):
                raise RuntimeError(
                    "The browser window was closed before the run finished"
                ) from error
            raise
