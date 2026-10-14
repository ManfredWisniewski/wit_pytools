"""Shared assisted-signup flow for provider account site modules.

Signup forms are not automatable (captcha); the browser stays open for a
human while the script optionally polls a mailbox for the provider's
verification mail and GETs the confirmation link.
"""

from playwright.sync_api import Error as PlaywrightError

from ..mailbox import fetch, load_mailbox_config, wait_for_link
from ..session import wait_for

# manual steps the human must complete in the open browser window
CHECKLIST = (
    "  1. fill the signup form (name, desired address, password)",
    "  2. solve the captcha / phone challenge",
    "  3. confirm the verification mail when it arrives"
    " (auto-clicked if --mailbox is set)",
    "  4. upload the persona avatar as profile photo",
)


def assist_signup(
    page,
    *,
    provider,
    signup_url,
    mailbox=None,
    sender=None,
    subject=None,
    link_pattern=None,
    timeout=1800,
):
    """Open the provider signup page and assist the manual flow.

    Returns the verification URL that was fetched, or None.
    """
    print(f"Opening {provider} signup...")
    page.goto(signup_url, wait_until="domcontentloaded")
    print("Manual steps:")
    for step in CHECKLIST:
        print(step)

    verified = None
    if mailbox:
        config = load_mailbox_config(mailbox)
        print(
            f"Polling mailbox '{mailbox}' for the verification mail"
            f" (timeout {timeout // 60} min)..."
        )
        url = wait_for_link(
            config,
            sender=sender,
            subject=subject,
            link_pattern=link_pattern,
            timeout=timeout,
        )
        if url:
            status = fetch(url)
            print(f"Verification link fetched: HTTP {status}")
            verified = url
        else:
            print("No verification mail seen within the timeout")
    else:
        print("No --mailbox set; close the browser window when done.")
        wait_for(page, _all_closed, timeout=timeout, interval=5)
    return verified


def _all_closed(page):
    """True when the window was closed (context gone raises)."""
    try:
        return len(page.context.pages) == 0
    except PlaywrightError:
        return True


def add_common_arguments(parser):
    """Shared CLI flags for the account signup commands."""
    parser.add_argument("--profile", default=None)
    parser.add_argument("--channel", default="chrome")
    parser.add_argument(
        "--mailbox",
        default=None,
        help="mailbox tag for CLAUDIA_IMAP_* style env vars;"
        " the verification link is fetched automatically",
    )
    parser.add_argument("--subject", default=None, help="mail subject filter")
    parser.add_argument(
        "--link-pattern", default=None, help="regex for the verification URL"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="seconds to wait for the verification mail (default: 1800)",
    )


def run_signup(
    args,
    *,
    provider,
    signup_url,
    sender,
    profile_dir,
):
    """Site-module run() wrapper around assist_signup."""
    from ..session import browser_session

    try:
        with browser_session(
            args.profile or profile_dir,
            headless=False,
            channel=args.channel,
        ) as (_context, page):
            return assist_signup(
                page,
                provider=provider,
                signup_url=signup_url,
                mailbox=args.mailbox,
                sender=sender,
                subject=args.subject,
                link_pattern=args.link_pattern,
                timeout=args.timeout,
            )
    except PlaywrightError as error:
        if "closed" in str(error):
            return None
        raise
