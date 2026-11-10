"""Command-line entry point for marketingautomation.

All commands print JSON to stdout so Ansible can register the output.
"""

import argparse
import json
import os
import sys

from . import (
    google_analytics,
    google_search_console,
    keyword_research,
    meta_conversions,
)
from .auth import (
    analytics_admin_service,
    search_console_service,
    site_verification_service,
)
from .config import (
    MarketingConfigError,
    load_google_settings,
    load_meta_settings,
    load_serper_settings,
)
from .util import normalize_domain


def _print(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


def _domain_arg(value):
    try:
        return normalize_domain(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="marketingautomation",
        description="Marketing platform automation (Google, Meta).",
    )
    sub = parser.add_subparsers(dest="group", required=True)

    gsc = sub.add_parser("search-console", help="Google Search Console")
    gsc_sub = gsc.add_subparsers(dest="command", required=True)

    gsc_sub.add_parser("list", help="List Search Console properties")

    add = gsc_sub.add_parser("add", help="Add a domain property")
    add.add_argument("--domain", required=True, type=_domain_arg)
    add.add_argument(
        "--type", choices=["domain", "url_prefix"], default="domain"
    )

    delete = gsc_sub.add_parser("delete", help="Delete a property")
    delete.add_argument("--site-url", required=True)

    token = gsc_sub.add_parser(
        "verification-token", help="Get DNS TXT verification token"
    )
    token.add_argument("--domain", required=True, type=_domain_arg)

    verify = gsc_sub.add_parser(
        "verify", help="Verify domain ownership via DNS TXT"
    )
    verify.add_argument("--domain", required=True, type=_domain_arg)

    ga = sub.add_parser("analytics", help="Google Analytics 4 Admin API")
    ga_sub = ga.add_subparsers(dest="command", required=True)

    ga_sub.add_parser("accounts", help="List GA4 accounts and properties")

    props = ga_sub.add_parser("properties", help="List properties of an account")
    props.add_argument("--account", required=True,
                       help="Account resource name, e.g. accounts/123")

    create_prop = ga_sub.add_parser("create-property", help="Create GA4 property")
    create_prop.add_argument("--account-name", required=True,
                             help="GA4 account display name")
    create_prop.add_argument("--display-name", required=True)
    create_prop.add_argument("--timezone", default="Europe/Berlin")
    create_prop.add_argument("--currency", default="EUR")

    ensure_prop = ga_sub.add_parser(
        "ensure-property", help="Create GA4 property if missing"
    )
    ensure_prop.add_argument("--account-name", required=True,
                             help="GA4 account display name")
    ensure_prop.add_argument("--display-name", required=True)
    ensure_prop.add_argument("--timezone", default="Europe/Berlin")
    ensure_prop.add_argument("--currency", default="EUR")

    streams = ga_sub.add_parser("streams", help="List data streams of a property")
    streams.add_argument("--property", required=True,
                         help="Property resource name, e.g. properties/123")

    create_stream = ga_sub.add_parser(
        "create-stream", help="Create a GA4 web data stream"
    )
    create_stream.add_argument("--property", required=True)
    create_stream.add_argument("--display-name", required=True)
    create_stream.add_argument("--uri", required=True)

    ensure_stream = ga_sub.add_parser(
        "ensure-stream", help="Create GA4 web data stream if missing"
    )
    ensure_stream.add_argument("--property", required=True)
    ensure_stream.add_argument("--display-name", required=True)
    ensure_stream.add_argument("--uri", required=True)

    meta = sub.add_parser("meta", help="Meta (Facebook) APIs")
    meta_sub = meta.add_subparsers(dest="command", required=True)

    test = meta_sub.add_parser("test-event", help="Send a Conversions API test event")
    test.add_argument("--pixel-id", required=True)
    test.add_argument("--event-name", default="PageView")
    test.add_argument("--event-source-url", default="")
    test.add_argument("--test-event-code", default="")

    kw = sub.add_parser("keywords", help="Keyword research via Serper.dev")
    kw_sub = kw.add_subparsers(dest="command", required=True)

    harvest = kw_sub.add_parser(
        "harvest", help="Expand a SEO_Produkt doc into keyword candidates"
    )
    harvest.add_argument("product", help="Path to the SEO_Produkt_*.md file")
    harvest.add_argument("--out", help="Output directory (default: doc directory)")
    harvest.add_argument("--seed", action="append", default=[],
                         help="Extra seed keyword (repeatable)")
    harvest.add_argument("--max-seeds", type=int, default=12)
    harvest.add_argument("--gl", default="de", help="Serper geo location")
    harvest.add_argument("--hl", default="de", help="Serper interface language")
    harvest.add_argument("--num", type=int, default=5,
                         help="Organic results per seed in the SERP snapshot")
    harvest.add_argument("--dry-run", action="store_true",
                         help="Parse and list seeds only, no API calls")
    harvest.add_argument("--verbose", "-v", action="store_true")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.group == "search-console":
            return _run_search_console(args)
        if args.group == "analytics":
            return _run_analytics(args)
        if args.group == "keywords":
            return _run_keywords(args)
        return _run_meta(args)
    except MarketingConfigError as error:
        print(error, file=sys.stderr)
        return 2
    except LookupError as error:
        print(error, file=sys.stderr)
        return 3


def _run_search_console(args):
    if args.command == "list":
        _print(google_search_console.list_properties(search_console_service()))
    elif args.command == "add":
        _print(google_search_console.add_domain_property(
            search_console_service(), args.domain, args.type
        ))
    elif args.command == "delete":
        google_search_console.delete_property(
            search_console_service(), args.site_url
        )
        _print({"deleted": args.site_url})
    elif args.command == "verification-token":
        _print(google_search_console.get_verification_token(
            site_verification_service(), args.domain
        ))
    elif args.command == "verify":
        _print(google_search_console.verify_domain(
            site_verification_service(), args.domain
        ))
    return 0


def _run_analytics(args):
    service = analytics_admin_service()
    if args.command == "accounts":
        _print(google_analytics.list_accounts(service))
    elif args.command == "properties":
        _print({"account": args.account,
                "properties": _list_account_properties(service, args.account)})
    elif args.command == "create-property":
        _print({
            "property": google_analytics.create_property(
                service, args.account_name, args.display_name,
                timezone=args.timezone, currency=args.currency,
            )
        })
    elif args.command == "ensure-property":
        _print(google_analytics.ensure_property(
            service, args.account_name, args.display_name,
            timezone=args.timezone, currency=args.currency,
        ))
    elif args.command == "streams":
        _print(google_analytics.list_data_streams(service, args.property))
    elif args.command == "create-stream":
        _print(google_analytics.create_web_data_stream(
            service, args.property, args.display_name, args.uri
        ))
    elif args.command == "ensure-stream":
        _print(google_analytics.ensure_web_data_stream(
            service, args.property, args.display_name, args.uri
        ))
    return 0


def _list_account_properties(service, account):
    """List propertySummaries of an account (resource name or display name)."""
    for summary in google_analytics.list_accounts(service):
        info = summary.get("account", {})
        if account in (info.get("name"), info.get("displayName")):
            return summary.get("propertySummaries", [])
    return []


def _run_keywords(args):
    if args.command == "harvest":
        if not os.path.isfile(args.product):
            raise LookupError(f"{args.product} not found")
        parsed, seeds = keyword_research.prepare(
            args.product, extra=args.seed, max_seeds=args.max_seeds
        )
        if not seeds:
            raise LookupError(
                f"no keywords found in {args.product} — "
                "expected the ØK-SEO product template"
            )
        if args.dry_run:
            _print({"product": parsed["product"], "topic": parsed["topic"],
                    "seeds": seeds})
            return 0
        client = keyword_research.Serper(load_serper_settings()["api_key"])
        summary = keyword_research.research(
            args.product, client, extra=args.seed, max_seeds=args.max_seeds,
            gl=args.gl, hl=args.hl, num=args.num, out_dir=args.out,
            verbose=args.verbose,
        )
        _print(summary)
    return 0


def _run_meta(args):
    settings = load_meta_settings()
    if args.command == "test-event":
        _print(meta_conversions.send_test_event(
            settings["access_token"],
            args.pixel_id,
            event_name=args.event_name,
            event_source_url=args.event_source_url or None,
            test_event_code=args.test_event_code or None,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
