"""Command-line interface: payloadtools sync|media|theme|check."""

import argparse
import glob
import re
import sys
from pathlib import Path

import yaml
from eliot import log_message

from wit_pytools.logger import log_setup

from .client import PayloadAuthError, PayloadClient
from .config import PayloadConfigError, load_config, load_credentials
from .sync import sync_repo


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="payloadtools",
        description="Sync markdown webtexts/media/theme to Payload CMS.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sync_p = sub.add_parser("sync", help="full sync pass")
    sync_p.add_argument("--repo")
    sync_p.add_argument("--file", help="sync a single repo-relative file")
    sync_p.add_argument("--dry-run", action="store_true")
    sync_p.add_argument("-v", "--verbose", action="store_true")

    media_p = sub.add_parser("media", help="media upload pass only")
    media_p.add_argument("--repo")
    media_p.add_argument("--dry-run", action="store_true")
    media_p.add_argument("-v", "--verbose", action="store_true")

    theme_p = sub.add_parser("theme", help="push theme CSS global")
    theme_p.add_argument("--css-light", required=True)
    theme_p.add_argument("--css-dark")
    theme_p.add_argument("--logo", help="brand logo image file for the header")
    theme_p.add_argument(
        "--font", action="append", default=[], metavar="FAMILY=FILE[:WEIGHT]",
        help="upload font files to media and prepend @font-face "
        "(repeatable; FILE may be a file, directory or glob; WEIGHT "
        "e.g. 400 or '100 900', else inferred from the filename)",
    )
    theme_p.add_argument(
        "--font-var", action="append", default=[], metavar="VAR=FAMILY",
        help="set CSS var --VAR to FAMILY in :root (repeatable)",
    )

    site_p = sub.add_parser(
        "site", help="push site.yml (siteName, logo, favicon) to theme global"
    )
    site_p.add_argument("--repo")
    site_p.add_argument("--dry-run", action="store_true")
    site_p.add_argument("-v", "--verbose", action="store_true")

    check_p = sub.add_parser("check", help="dry validation, no writes")
    check_p.add_argument("--repo")
    check_p.add_argument("-v", "--verbose", action="store_true")
    return parser


def _print_results(results, verbose):
    for result in results:
        line = f"{result.status:10} {result.relpath}"
        if result.detail and (verbose or result.status in ("failed", "skipped")):
            line += f"  ({result.detail})"
        print(line)
        log_message(line, level="INFO")


def _ensure_media_doc(client, image_path, alt=""):
    """Upload image_path to media unless the hash already exists; -> doc.

    Syncs the alt text on an existing doc when it differs.
    """
    from .media import sha256_file

    try:
        digest = sha256_file(image_path)
    except OSError as error:
        raise PayloadConfigError(f"Cannot read media file: {error}") from error
    existing = client.find_doc("media", "sourceHash", digest)
    if existing is not None:
        alt = alt or existing.get("alt") or image_path.stem
        if (existing.get("alt") or "") != alt:
            client.update_doc("media", existing["id"], {"alt": alt})
            existing = dict(existing, alt=alt)
        return existing
    media_id = client.upload_media(
        image_path,
        collection="media",
        alt=alt or image_path.stem,
        source_hash=digest,
        source_path=image_path.name,
    )
    doc = client.find_doc("media", "sourceHash", digest) or {}
    return dict(doc, id=doc.get("id") or media_id)


def _ensure_media(client, image_path, alt=""):
    """Upload image_path to media unless the hash already exists; -> doc id."""
    return _ensure_media_doc(client, image_path, alt).get("id")


_FONT_SPEC = re.compile(
    r"^(?P<family>.+?)=(?P<file>.+?)"
    r"(?::(?P<weight>\d+(?:\s+\d+)?|normal|bold))?$"
)
_FONT_FORMATS = {
    ".woff2": "woff2",
    ".woff": "woff",
    ".ttf": "truetype",
    ".otf": "opentype",
}


def _parse_font_spec(spec):
    """Parse 'FAMILY=FILE[:WEIGHT]' -> (family, file_text, weight|None).

    FILE may be a single file, a directory, or a glob pattern.
    """
    match = _FONT_SPEC.match(spec.strip())
    if not match:
        raise PayloadConfigError(
            f"Invalid --font spec {spec!r} (want FAMILY=FILE[:WEIGHT])"
        )
    weight = (match.group("weight") or "").strip() or None
    return (
        match.group("family").strip(),
        match.group("file").strip(),
        weight,
    )


def _resolve_font_files(file_text):
    """Resolve FILE to font file paths: single file, directory, or glob."""
    path = Path(file_text)
    if path.is_dir():
        files = sorted(
            p for p in path.iterdir()
            if p.suffix.lower() in _FONT_FORMATS
        )
    elif any(c in file_text for c in "*?["):
        files = sorted(
            Path(p) for p in glob.glob(file_text)
            if Path(p).suffix.lower() in _FONT_FORMATS
        )
    else:
        files = [path]
    if not files:
        raise PayloadConfigError(
            f"--font spec matched no font files: {file_text!r}"
        )
    return files


def _infer_weight_style(path):
    """Infer (weight, style) from a font filename -> (weight|None, style).

    Handles google-webfonts-helper naming: '*-700', '*-700italic',
    '*-italic', '*-regular', plus '*variable' -> '100 900'.
    """
    stem = re.sub(r"[_-]+", "", path.stem.lower())
    style = "italic" if stem.endswith("italic") else "normal"
    if stem.endswith("variable"):
        return "100 900", "normal"
    digits = re.findall(r"\d{3}", stem)
    return (digits[-1] if digits else None), style


def _font_face_rule(family, url, weight, suffix, style="normal"):
    lines = [
        "@font-face {",
        f"  font-family: '{family}';",
    ]
    src = f"url('{url}')"
    fmt = _FONT_FORMATS.get(suffix.lower())
    if fmt:
        src += f" format('{fmt}')"
    lines.append(f"  src: {src};")
    if weight:
        lines.append(f"  font-weight: {weight};")
    if style != "normal":
        lines.append(f"  font-style: {style};")
    lines.append("  font-display: swap;")
    lines.append("}")
    return "\n".join(lines)


def _font_var_rules(specs):
    """Parse 'VAR=FAMILY' specs -> ':root { --VAR: 'FAMILY'; }' block."""
    lines = []
    for spec in specs:
        name, eq, family = spec.partition("=")
        name, family = name.strip().lstrip("-"), family.strip()
        if not eq or not name or not family:
            raise PayloadConfigError(
                f"Invalid --font-var spec {spec!r} (want VAR=FAMILY)"
            )
        lines.append(f"  --{name}: '{family}';")
    if not lines:
        return ""
    return ":root {\n" + "\n".join(lines) + "\n}"


def _font_css_prefix(client, font_specs, var_specs):
    """Upload fonts and build the CSS block prepended to cssLight."""
    parts = []
    for spec in font_specs:
        family, file_text, weight = _parse_font_spec(spec)
        for font_path in _resolve_font_files(file_text):
            doc = _ensure_media_doc(client, font_path, alt=family)
            url = doc.get("url") or f"/api/media/file/{font_path.name}"
            w_inf, style = _infer_weight_style(font_path)
            parts.append(
                _font_face_rule(
                    family, url, weight or w_inf, font_path.suffix, style
                )
            )
    var_block = _font_var_rules(var_specs)
    if var_block:
        parts.append(var_block)
    return "\n".join(parts) + "\n" if parts else ""


def _run_theme(args):
    base_url, api_key = load_credentials()
    client = PayloadClient(base_url, api_key)
    try:
        payload = {
            "cssLight": Path(args.css_light).read_text(encoding="utf-8")
        }
        if args.css_dark:
            payload["cssDark"] = Path(args.css_dark).read_text(
                encoding="utf-8"
            )
    except OSError as error:
        raise PayloadConfigError(f"Cannot read CSS file: {error}") from error
    if args.logo:
        payload["logo"] = _ensure_media(client, Path(args.logo))
    if args.font or args.font_var:
        prefix = _font_css_prefix(client, args.font, args.font_var)
        payload["cssLight"] = prefix + payload["cssLight"]
    try:
        client.update_global("theme", payload)
    finally:
        client.close()
    print("theme: updated")
    log_message("payloadtools theme updated", level="INFO")
    return 0


def _run_site(args, client=None):
    """Push site.yml values (siteName, logo, favicon) onto the theme global."""
    config = load_config(args.repo)
    site_path = config.repo / "site.yml"
    if not site_path.is_file():
        raise PayloadConfigError(f"Missing site.yml in {config.repo}")
    try:
        data = yaml.safe_load(site_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise PayloadConfigError(f"Cannot parse site.yml: {error}") from error
    if not isinstance(data, dict):
        raise PayloadConfigError("site.yml must contain a mapping")

    base_url, api_key = load_credentials()
    client = client or PayloadClient(base_url, api_key)
    try:
        payload = {}
        if data.get("logo"):
            payload["logo"] = _ensure_media(
                client,
                site_path.parent / str(data["logo"]),
                alt=str(data.get("logo_alt") or ""),
            )
        if data.get("favicon"):
            payload["favicon"] = _ensure_media(
                client,
                site_path.parent / str(data["favicon"]),
                alt=str(data.get("favicon_alt") or ""),
            )
        if data.get("site_name"):
            existing = client.get("globals/theme") or {}
            meta = dict(existing.get("meta") or {})
            meta["siteName"] = str(data["site_name"])
            payload["meta"] = meta
        if not payload:
            raise PayloadConfigError("site.yml contains no pushable keys")
        if not args.dry_run:
            client.update_global("theme", payload)
    finally:
        client.close()
    print(f"site: {'would update' if args.dry_run else 'updated'} "
          f"{sorted(payload)}")
    log_message("payloadtools site updated", level="INFO")
    return 0


def main(argv=None, *, client=None):
    args = _build_parser().parse_args(argv)
    log_setup()
    try:
        if args.command == "theme":
            return _run_theme(args)
        if args.command == "site":
            return _run_site(args, client=client)
        config = load_config(args.repo)
        injected = client is not None
        if client is None:
            base_url, api_key = load_credentials()
            client = PayloadClient(base_url, api_key)
        dry_run = args.command == "check" or getattr(args, "dry_run", False)
        try:
            results = sync_repo(
                config, client,
                only_file=getattr(args, "file", None),
                media_only=args.command == "media",
                dry_run=dry_run,
            )
        finally:
            if not injected:
                client.close()
        _print_results(results, getattr(args, "verbose", False))
        failed = sum(r.status == "failed" for r in results)
        log_message(
            f"payloadtools {args.command}: {len(results)} files, "
            f"{failed} failed",
            level="INFO",
        )
        return 1 if failed else 0
    except PayloadAuthError as error:
        log_message(f"payloadtools auth error: {error}", level="ERROR")
        print(f"auth error: {error}", file=sys.stderr)
        return 2
    except PayloadConfigError as error:
        log_message(f"payloadtools config error: {error}", level="ERROR")
        print(f"config error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
