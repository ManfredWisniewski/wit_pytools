"""American Express (US) automation: login and statement download."""

from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from ..config import load_credentials
from ..session import browser_session, wait_for

LOGIN_URL = "https://www.americanexpress.com/en-us/account/login/"
STATEMENTS_URL = "https://www.americanexpress.com/en-us/account/statements"

# URL fragments that only appear once authenticated
_POST_LOGIN_MARKERS = (
    "dashboard",
    "account/summary",
    "account/home",
    "account/activity",
)

# label text of the options in the Amex download dialog
_FORMAT_LABELS = {"pdf": "PDF", "csv": "CSV", "excel": "Excel"}


def is_logged_in(page):
    """Heuristic: on an Amex page past the login form."""
    url = page.url.lower()
    if "americanexpress.com" not in url:
        return False
    if any(marker in url for marker in _POST_LOGIN_MARKERS):
        return True
    return "login" not in url and not page.query_selector("#eliloUserID")


def login(page, username, password, *, mfa_timeout=300):
    """Log in; MFA/captcha must be completed manually in the open browser."""
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    # a valid persisted session redirects away from the login page
    if wait_for(page, is_logged_in, timeout=15):
        return
    page.fill("#eliloUserID", username)
    page.fill("#eliloPassword", password)
    page.click("#loginSubmit")
    if not wait_for(page, is_logged_in, timeout=mfa_timeout):
        raise RuntimeError(
            "Amex login did not complete; finish verification in the browser"
        )


def _confirm_format_dialog(page, fmt):
    """Pick the format inside the download dialog, if one opened."""
    try:
        dialog = page.wait_for_selector("[role='dialog']", timeout=4000)
    except PlaywrightTimeout:
        return
    if dialog is None:
        return
    label = _FORMAT_LABELS.get(fmt.lower())
    option = dialog.query_selector(f"text='{label}'")
    if option:
        option.click()
    confirm = dialog.query_selector("button:has-text('Download')")
    if confirm:
        confirm.click()


def download_statements(page, output_dir, *, count=None, fmt="pdf"):
    """Download recent statements; returns list of saved Paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    page.goto(STATEMENTS_URL, wait_until="domcontentloaded")
    # an expired session may have bounced back to login/MFA; keep waiting
    if not wait_for(page, is_logged_in, timeout=60):
        raise RuntimeError("Not logged in after navigating to statements")

    # expand the full statement list when the sections are present
    for text in ("Statements and Year End Summaries", "Older Statements"):
        try:
            page.click(f"text='{text}'", timeout=4000)
        except PlaywrightTimeout:
            pass

    buttons = page.query_selector_all(
        "button:has-text('Download'), a:has-text('Download')"
    )
    if count is not None:
        buttons = buttons[:count]

    saved = []
    for index, button in enumerate(buttons, start=1):
        with page.expect_download(timeout=60000) as download_info:
            button.click()
            _confirm_format_dialog(page, fmt)
        download = download_info.value
        filename = download.suggested_filename or f"amex-statement-{index}.pdf"
        target = out / filename
        download.save_as(str(target))
        saved.append(target)
    return saved


def run(output_dir="downloads/amex", **kwargs):
    """Full flow: credentials -> session -> login -> download statements."""
    username, password = load_credentials("amex")
    profile_dir = kwargs.pop("profile_dir")
    headless = kwargs.pop("headless", False)
    channel = kwargs.pop("channel", None)
    mfa_timeout = kwargs.pop("mfa_timeout", 300)
    with browser_session(
        profile_dir, headless=headless, channel=channel
    ) as (_context, page):
        login(page, username, password, mfa_timeout=mfa_timeout)
        return download_statements(page, output_dir, **kwargs)
