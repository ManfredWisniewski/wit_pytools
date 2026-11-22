"""Harvest keyword candidates for a WIT SEO product document via Serper.dev.

Reads a product doc (``SEO_Produkt_*.md`` — fields ``Produkt / Leistung``,
``Übergeordnetes Thema``, ``Primäres Keyword``, ``Sekundäre Keywords``,
``Long-Tail Keywords``), expands the seed keywords through Google Autocomplete
and Serper ``/search`` (related searches, People-Also-Ask, SERP snapshot) and
writes two artefacts next to the product doc:

- ``keywords-research-YYYY-MM-DD.md`` — research report for the SEO owner (German)
- ``serpbear-keywords-YYYY-MM-DD.csv.md`` — ``keyword,tags`` rows for SerpBear

Serper delivers *candidates only* — no search volume or difficulty.
Standard library only so iac-n8n tools can wrap it (D09).
"""

import csv
import io
import json
import re
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from wit_pytools.sanitizers import normalize_spaces

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^```")

# crude intent heuristics (German market) — marked "?" in the report on purpose
_QUESTION_PREFIXES = ("was ", "wie ", "warum ", "wann ", "welche", "wo ", "womit ",
                      "kann ", "ist ", "sind ", "gibt es", "wer ", "wieso ")
_COMMERCIAL_WORDS = ("kaufen", "preis", "kosten", "kostenlos", "agentur", "anbieter",
                     "vergleich", "dienstleist", "beratung", "software", "tool")

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                          "Ä": "ae", "Ö": "oe", "Ü": "ue"})


def slugify(text):
    """Keyword tag slug: lowercase, umlauts expanded, runs of non-alnum -> '-'."""
    return re.sub(r"[^a-z0-9]+", "-", text.translate(_UMLAUTS).lower()).strip("-")


# -- product doc parsing ------------------------------------------------------


def _sections(text):
    """Split markdown into (level, title, body-lines) sections."""
    sections = []
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            sections.append((len(m.group(1)), m.group(2).strip(), []))
        elif sections:
            sections[-1][2].append(line)
    return sections


def _section_lines(text, title_re):
    for _level, title, lines in _sections(text):
        if re.search(title_re, title, re.IGNORECASE):
            return lines
    return []


def _field(text, label_re):
    m = re.search(rf"\*\*{label_re}:?\*\*[ \t]*(.+)", text)
    return m.group(1).strip() if m else ""


def _strip_internal(name):
    """Drop the internal product code name — ``(intern: X)`` never appears in copy."""
    return re.sub(r"\s*\((?:intern|internal)[^)]*\)", "", name, flags=re.IGNORECASE).strip()


def _seed_name(name):
    """Trim a marketing tail off the product name — ``X — long benefit claim``
    seeds Google with the whole sentence (Serper autocomplete rejects >~64
    chars); the head alone is the usable keyword seed."""
    return re.split(r"\s+[—–|-]\s+", name)[0].strip()


def _items(lines):
    """Extract keyword lines from a doc section: fenced block preferred, else
    backticked lines / bullets / bare lines."""
    fenced, in_fence = [], False
    for line in lines:
        if _FENCE.match(line.strip()):
            if in_fence:
                break
            in_fence = True
            continue
        if in_fence and line.strip():
            fenced.append(line.strip())
    if fenced:
        return fenced
    out = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith(("#", "|", "[ ]", "[x]", "---")):
            continue
        m = re.fullmatch(r"`(.+)`", line) or re.match(r"[-*]\s+`?([^`]+)`?$", line)
        out.append((m.group(1) if m else line).strip().strip("`"))
    return [x for x in out if x]


def parse_product_doc(text):
    """Pull the keyword fields out of a ``SEO_Produkt_*.md`` document."""
    pillar = (_items(_section_lines(text, r"primäres keyword")) or [""])[0]
    return {
        "product": _seed_name(_strip_internal(_field(text, r"Produkt / Leistung"))),
        "topic": _field(text, "Übergeordnetes Thema"),
        "pillar": pillar,
        "secondary": _items(_section_lines(text, r"sekundäre keywords?")),
        "longtail": _items(_section_lines(text, r"long[- ]tail")),
    }


def build_seeds(parsed, extra=None, max_seeds=12):
    """Ordered, case-insensitively deduped seed list.

    Explicit doc keywords come first (pillar, secondary, long-tail), then the
    product name and parent topic as context seeds, then extra seeds.
    """
    seeds = []
    seen = set()

    def add(kw, kind):
        kw = normalize_spaces(kw)
        norm = kw.lower()
        if norm and norm not in seen:
            seen.add(norm)
            seeds.append({"kw": kw, "kind": kind})

    add(parsed["pillar"], "pillar")
    for kw in parsed["secondary"]:
        add(kw, "sekundär")
    for kw in parsed["longtail"]:
        add(kw, "long-tail")
    add(parsed["product"], "produkt")
    add(parsed["topic"], "thema")
    for kw in (extra or []):
        add(kw, "extra")
    return seeds[:max_seeds]


# -- Serper client ------------------------------------------------------------


class Serper:
    """Minimal stdlib JSON client for the Serper.dev API."""

    BASE = "https://google.serper.dev"

    def __init__(self, api_key, timeout=30):
        self.api_key = api_key
        self.timeout = timeout
        self.calls = 0

    def _post(self, endpoint, payload):
        req = urllib.request.Request(
            self.BASE + endpoint,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self.calls += 1
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read()).get("message") or e.reason
            except Exception:
                detail = str(e)
            raise RuntimeError(f"Serper {endpoint} HTTP {e.code}: {detail}") from e

    def autocomplete(self, q, gl, hl):
        data = self._post("/autocomplete", {"q": q, "gl": gl, "hl": hl})
        return [s.get("value", "").strip() for s in data.get("suggestions", [])]

    def search(self, q, gl, hl, num):
        data = self._post("/search", {"q": q, "gl": gl, "hl": hl, "num": num})
        return {
            "related": [r.get("query", "").strip() for r in data.get("relatedSearches", [])],
            "paa": [p.get("question", "").strip() for p in data.get("peopleAlsoAsk", [])],
            "organic": [{"title": o.get("title", ""), "link": o.get("link", "")}
                        for o in data.get("organic", [])[:num]],
        }


# -- harvest + merge ----------------------------------------------------------


def harvest(seeds, client, gl, hl, num, verbose=False):
    """Run autocomplete + search per seed.

    Returns (candidates, paa, serp, warnings):
    - candidates: {normalized kw: {"kw", "sources": set, "seeds": set}}
    - paa: [{"question", "seed"}] deduped, order preserved
    - serp: {seed kw: [organic {title, link}]}
    - warnings: one entry per failed API call — a bad seed skips its call,
      it never aborts the run
    """
    candidates = {}
    paa = []
    paa_seen = set()
    serp = {}
    warnings = []

    for seed in seeds:
        q = seed["kw"]

        def add(kw, source):
            kw = normalize_spaces(kw)
            if not kw:
                return
            c = candidates.setdefault(kw.lower(), {"kw": kw, "sources": set(), "seeds": set()})
            c["sources"].add(source)
            c["seeds"].add(q)

        if verbose:
            print(f"seed {q!r} ({seed['kind']})")
        add(q, "seed")
        try:
            for v in client.autocomplete(q, gl, hl):
                add(v, "autocomplete")
        except Exception as e:
            warnings.append(f"autocomplete {q!r}: {e}")
        try:
            result = client.search(q, gl, hl, num)
        except Exception as e:
            warnings.append(f"search {q!r}: {e}")
            result = {"related": [], "paa": [], "organic": []}
        for v in result["related"]:
            add(v, "related")
        for question in result["paa"]:
            if question and question.lower() not in paa_seen:
                paa_seen.add(question.lower())
                paa.append({"question": question, "seed": q})
        serp[q] = result["organic"]

    return candidates, paa, serp, warnings


# -- Google data enrichment ---------------------------------------------------


def report_date_range(days=90, lag_days=3):
    """(start, end) ISO dates for GSC/GA4 pulls.

    end lags ``lag_days`` behind today — Search Console data is delayed by
    ~2-3 days, so the freshest complete day is today - 3.
    """
    end = date.today() - timedelta(days=lag_days)
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def merge_gsc_candidates(candidates, gsc_rows):
    """Merge Search Console query rows into the candidate dict.

    Matching candidates get a ``gsc`` metrics dict; GSC queries that no seed
    produced are added with source ``search-console`` — real searches the
    site already surfaces for (impressions > 0 by definition), which is
    stronger evidence than autocomplete guesses.
    """
    for row in gsc_rows:
        kw = normalize_spaces(" ".join(row.get("keys", [])))
        if not kw:
            continue
        metrics = {"clicks": row.get("clicks", 0),
                   "impressions": row.get("impressions", 0),
                   "ctr": row.get("ctr", 0.0),
                   "position": row.get("position", 0.0)}
        c = candidates.get(kw.lower())
        if c is None:
            if metrics["impressions"] <= 0:
                continue
            c = candidates.setdefault(
                kw.lower(), {"kw": kw, "sources": set(), "seeds": set()})
        c["sources"].add("search-console")
        c["gsc"] = metrics
    return candidates


def guess_intent(kw):
    """Coarse German intent hint — a starting point for the SEO owner, not data."""
    k = kw.lower().strip()
    if "?" in k or any(k.startswith(w) for w in _QUESTION_PREFIXES):
        return "Frage?"
    if any(w in k for w in _COMMERCIAL_WORDS):
        return "kommerziell?"
    return "informational?"


# -- artefacts ----------------------------------------------------------------


def render_csv(candidates, tag):
    """SerpBear import CSV: sorted ``keyword,tags`` rows."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["keyword", "tags"])
    for c in sorted(candidates.values(), key=lambda c: c["kw"].lower()):
        w.writerow([c["kw"], tag])
    return buf.getvalue()


def render_report(parsed, seeds, candidates, paa, serp, meta, ga_pages=None):
    """German research report markdown for the SEO owner.

    meta may carry ``gsc`` ({"site_url", "start", "end"}) when Search Console
    data was merged, and ``ga`` ({"property"}) when GA4 pages are passed.
    """
    product = parsed["product"] or meta["doc"]
    has_gsc = any("gsc" in c for c in candidates.values())
    lines = [
        f"# Keyword-Recherche: {product}",
        "",
        f"Erstellt: {meta['date']} · Quelle: Serper.dev (Autocomplete + Related Searches + PAA), "
        f"Markt `gl={meta['gl']}` / `hl={meta['hl']}` · {meta['calls']} API-Calls",
        f"Produktdokument: `{meta['doc']}` — generiert von "
        "`wit_pytools.marketingautomation.keyword_research` "
        "(bei Änderungen neu erzeugen statt händisch pflegen).",
        "",
    ]
    if meta.get("gsc"):
        g = meta["gsc"]
        lines += [
            f"> **Search Console:** echte Suchanfragen für `{g['site_url']}` "
            f"({g['start']} bis {g['end']}) sind als Quelle `search-console` mit "
            "Klicks/Impressionen/Position markiert.",
            "",
        ]
    else:
        lines += [
            "> **Kein Suchvolumen:** Serper liefert Kandidaten, keine Volumina/Difficulty. "
            "Volumen nur über Google-Ads-Keyword-Planner (SerpBear-Ideas) oder eine Paid-API "
            "(DataForSEO o. ä.).",
            "",
        ]
    lines += [
        "## Seeds",
        "",
        "| Seed | Herkunft |",
        "|---|---|",
    ]
    for s in seeds:
        lines.append(f"| `{s['kw']}` | {s['kind']} |")

    header = "| Keyword | Quellen | Intention¹ | aus Seed |"
    divider = "|---|---|---|---|"
    if has_gsc:
        header += " Klicks | Impr. | Pos. |"
        divider += "---|---|---|"
    lines += [
        "",
        f"## Kandidaten ({len(candidates)})",
        "",
        header,
        divider,
    ]
    for c in sorted(candidates.values(), key=lambda c: c["kw"].lower()):
        src = ", ".join(sorted(c["sources"]))
        seedlist = ", ".join(sorted(c["seeds"]))
        row = f"| {c['kw']} | {src} | {guess_intent(c['kw'])} | {seedlist} |"
        if has_gsc:
            g = c.get("gsc")
            row += (f" {g['clicks']} | {g['impressions']} | {g['position']:.1f} |"
                    if g else "  |  |  |")
        lines.append(row)
    lines += ["", "¹ Grobe Heuristik, bitte fachlich prüfen.", ""]

    if paa:
        lines += [f"## Fragen — People Also Ask ({len(paa)})", ""]
        for p in paa:
            lines.append(f"- {p['question']} *(Seed: {p['seed']})*")
        lines.append("")

    lines += ["## SERP-Snapshot", ""]
    for q, organic in serp.items():
        lines.append(f"### `{q}`")
        lines.append("")
        if organic:
            for i, o in enumerate(organic, 1):
                lines.append(f"{i}. [{o['title'] or o['link']}]({o['link']})")
        else:
            lines.append("- *(keine Ergebnisse)*")
        lines.append("")

    if ga_pages:
        prop = meta.get("ga", {}).get("property", "")
        lines += [
            f"## GA4 — Top-Landingpages ({len(ga_pages)})",
            "",
            f"Property `{prop}` · Metriken: Sessions, Engaged Sessions, Engagement Rate",
            "",
            "| Landingpage | Sessions | Engaged | Rate |",
            "|---|---|---|---|",
        ]
        for p in ga_pages:
            rate = p.get("engagementRate", "")
            rate = f"{float(rate) * 100:.0f}%" if rate else ""
            lines.append(f"| {p.get('landingPage', '')} | {p.get('sessions', '')} "
                         f"| {p.get('engagedSessions', '')} | {rate} |")
        lines.append("")

    if meta.get("warnings"):
        lines += ["## Warnungen", ""]
        for w in meta["warnings"]:
            lines.append(f"- `{w}`")
        lines.append("")

    lines += [
        "## SerpBear",
        "",
        f"`{meta['csv_name']}` (Spalten `keyword,tags`) — Keywords in SerpBear unter der",
        f"Domain hinzufügen, Tag `{meta['tag']}` gruppiert sie zum Produkt.",
        "",
    ]
    return "\n".join(lines)


# -- pipeline -----------------------------------------------------------------


def prepare(product_doc, extra=None, max_seeds=12):
    """Parse the doc and build the seed list — no API calls."""
    product_doc = Path(product_doc)
    parsed = parse_product_doc(product_doc.read_text(encoding="utf-8"))
    seeds = build_seeds(parsed, extra=list(extra or ()), max_seeds=max_seeds)
    return parsed, seeds


def research(product_doc, client, *, extra=None, max_seeds=12, gl="de", hl="de",
             num=5, out_dir=None, verbose=False,
             gsc_rows=None, ga_pages=None, gsc_meta=None, ga_meta=None,
             extra_warnings=None):
    """Full pipeline: parse -> seeds -> harvest -> write report + SerpBear CSV.

    gsc_rows: Search Console search-analytics rows — merged into candidates.
    ga_pages: GA4 landing-page report rows — rendered as a report section.
    gsc_meta/ga_meta: {"site_url"/"property", ...} context for the report.
    extra_warnings: fetch warnings to list alongside harvest warnings.

    Returns a summary dict with parsed doc, seeds, counts, artefact paths and
    warnings.
    """
    product_doc = Path(product_doc)
    parsed, seeds = prepare(product_doc, extra=extra, max_seeds=max_seeds)
    candidates, paa, serp, warnings = harvest(seeds, client, gl, hl, num, verbose)
    warnings = list(extra_warnings or ()) + warnings
    if gsc_rows:
        merge_gsc_candidates(candidates, gsc_rows)

    tag = slugify(parsed["product"] or product_doc.stem)
    target_dir = Path(out_dir) if out_dir else product_doc.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    meta = {"date": stamp, "gl": gl, "hl": hl,
            "calls": client.calls, "doc": product_doc.name, "tag": tag,
            "csv_name": f"serpbear-keywords-{stamp}.csv.md", "warnings": warnings}
    if gsc_meta:
        meta["gsc"] = gsc_meta
    if ga_meta:
        meta["ga"] = ga_meta

    md_path = target_dir / f"keywords-research-{stamp}.md"
    csv_path = target_dir / meta["csv_name"]
    md_path.write_text(
        render_report(parsed, seeds, candidates, paa, serp, meta,
                      ga_pages=ga_pages),
        encoding="utf-8")
    csv_path.write_text(render_csv(candidates, tag), encoding="utf-8")

    return {"parsed": parsed, "seeds": seeds, "warnings": warnings,
            "candidates": len(candidates), "paa": len(paa),
            "api_calls": client.calls, "tag": tag,
            "gsc_rows": len(gsc_rows or ()), "ga_pages": len(ga_pages or ()),
            "report": str(md_path), "csv": str(csv_path)}
