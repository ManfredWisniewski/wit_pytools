"""Assisted Microsoft account signup for persona mail addresses.

The signup form and captcha are manual; the script keeps the browser open
and, with --mailbox, polls the persona mailbox for the verification mail
and fetches the confirmation link.
"""

from ..session import DEFAULT_PROFILE_DIR
from ._signup import add_common_arguments, run_signup

COMMAND = "ms-account"
DESCRIPTION = "Assisted Microsoft account signup for a persona address."

SIGNUP_URL = "https://signup.live.com/"


def add_arguments(parser):
    """CLI flags for the ms-account subcommand."""
    add_common_arguments(parser)


def run(args):
    """Open signup.live.com and assist the manual account creation."""
    return run_signup(
        args,
        provider="Microsoft",
        signup_url=SIGNUP_URL,
        sender="microsoft",
        profile_dir=DEFAULT_PROFILE_DIR.parent / "profile-ms-account",
    )
