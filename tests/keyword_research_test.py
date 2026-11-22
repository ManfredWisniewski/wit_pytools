#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.marketingautomation import (
    MarketingConfigError,
    config,
    google_analytics,
    google_search_console,
    keyword_research as kr,
    load_serper_settings,
    load_site_settings,
)


DOC = """# SEO Produkt: Datenaufbereitung für KI

**Produkt / Leistung:** Datenaufbereitung für KI (intern: Verldbridge)
**Übergeordnetes Thema:** Business Intelligence

## Keywords

### Primäres Keyword (Pillar)

`Business Intelligence`

### Sekundäre Keywords

```text
Firmendaten für KI aufbereiten
Unternehmendaten KI
```

### Long-Tail Keywords

```text
eigene Dokumente mit KI durchsuchen lassen
Kundendaten anonymisieren für KI
```

## Conversion

| Feld | Inhalt |
|---|---|
| CTA | "Anfragen" |
"""


class FakeSerper:
    def __init__(self):
        self.calls = 0

    def autocomplete(self, q, gl, hl):
        self.calls += 1
        return {f"{q}-ac" for q in [q]} | {"shared idea"}

    def search(self, q, gl, hl, num):
        self.calls += 1
        return {"related": [q + " verwandt"], "paa": ["Wie geht das?"],
                "organic": [{"title": "T", "link": "https://x.de"}]}


# --- product doc parsing ----------------------------------------------------

def test_parse_product_doc_fields():
    p = kr.parse_product_doc(DOC)
    assert p["product"] == "Datenaufbereitung für KI"  # intern name stripped
    assert p["topic"] == "Business Intelligence"
    assert p["pillar"] == "Business Intelligence"
    assert p["secondary"] == ["Firmendaten für KI aufbereiten",
                              "Unternehmendaten KI"]
    assert p["longtail"] == ["eigene Dokumente mit KI durchsuchen lassen",
                             "Kundendaten anonymisieren für KI"]


def test_parse_product_doc_backtick_and_bullet_fallback():
    doc = ("### Primäres Keyword (Pillar)\n\n- `Alpha`\n\n"
           "### Sekundäre Keywords\n\n- Beta\n- `Gamma`\n")
    p = kr.parse_product_doc(doc)
    assert p["pillar"] == "Alpha"
    assert p["secondary"] == ["Beta", "Gamma"]


def test_parse_product_doc_missing_fields_are_empty():
    p = kr.parse_product_doc("# nothing here\n")
    assert p["pillar"] == ""
    assert p["secondary"] == []


# --- seeds ------------------------------------------------------------------

def test_build_seeds_order_and_dedupe():
    parsed = {"product": "Prod", "topic": "Alpha", "pillar": "alpha",
              "secondary": ["Beta", " beta "], "longtail": ["Gamma"]}
    seeds = kr.build_seeds(parsed)
    kws = [s["kw"] for s in seeds]
    assert kws == ["alpha", "Beta", "Gamma", "Prod"]
    assert seeds[0]["kind"] == "pillar"
    # "Alpha" topic deduped against pillar
    assert seeds[-1]["kind"] == "produkt"


def test_build_seeds_extra_and_cap():
    parsed = {"product": "", "topic": "", "pillar": "a",
              "secondary": [], "longtail": []}
    seeds = kr.build_seeds(parsed, extra=["b", "c"], max_seeds=2)
    assert [s["kw"] for s in seeds] == ["a", "b"]


# --- harvest ----------------------------------------------------------------

def test_harvest_merge_sources_and_dedupe():
    seeds = [{"kw": "a", "kind": "pillar"}, {"kw": "b", "kind": "extra"}]
    c, paa, serp, warnings = kr.harvest(seeds, FakeSerper(), "de", "de", 5)
    shared = c["shared idea"]
    assert shared["sources"] == {"autocomplete"}
    assert shared["seeds"] == {"a", "b"}
    assert c["a verwandt"]["sources"] == {"related"}
    assert c["a"]["sources"] == {"seed"}
    assert len(paa) == 1  # deduped across seeds
    assert serp["a"] == [{"title": "T", "link": "https://x.de"}]
    assert warnings == []


def test_harvest_failing_call_warns_and_continues():
    class Flaky(FakeSerper):
        def autocomplete(self, q, gl, hl):
            self.calls += 1
            if q == "a":
                raise RuntimeError("Serper /autocomplete HTTP 400: Query too long.")
            return super().autocomplete(q, gl, hl)

    seeds = [{"kw": "a", "kind": "pillar"}, {"kw": "b", "kind": "extra"}]
    c, _paa, serp, warnings = kr.harvest(seeds, Flaky(), "de", "de", 5)
    assert len(warnings) == 1
    assert "a" in warnings[0]
    assert c["a verwandt"]["sources"] == {"related"}  # search still ran
    assert c["shared idea"]["seeds"] == {"b"}


# --- intent -----------------------------------------------------------------

@pytest.mark.parametrize("kw,expected", [
    ("Wie bereite ich Daten auf?", "Frage?"),
    ("KI Agentur Kosten", "kommerziell?"),
    ("Datenaufbereitung", "informational?"),
])
def test_guess_intent(kw, expected):
    assert kr.guess_intent(kw) == expected


# --- artefacts ----------------------------------------------------------------

def test_render_csv():
    c = {"b": {"kw": "B, mit Komma", "sources": {"seed"}, "seeds": {"s"}},
         "a": {"kw": "Alpha", "sources": {"seed"}, "seeds": {"s"}}}
    out = kr.render_csv(c, "prod-tag")
    lines = out.splitlines()
    assert lines[0] == "keyword,tags"
    assert lines[1] == "Alpha,prod-tag"
    assert '"B, mit Komma"' in lines[2]


def test_render_report_sections():
    parsed = {"product": "Prod", "topic": "T", "pillar": "Alpha",
              "secondary": [], "longtail": []}
    seeds = [{"kw": "Alpha", "kind": "pillar"}]
    c = {"alpha": {"kw": "Alpha", "sources": {"seed"}, "seeds": {"Alpha"}}}
    rep = kr.render_report(
        parsed, seeds, c, [{"question": "Q?", "seed": "Alpha"}],
        {"Alpha": [{"title": "T", "link": "https://x.de"}]},
        {"date": "2026-10-25", "gl": "de", "hl": "de", "calls": 2,
         "doc": "doc.md", "tag": "prod",
         "csv_name": "serpbear-keywords-2026-10-25.csv.md"})
    for marker in ("# Keyword-Recherche: Prod", "## Seeds", "## Kandidaten (1)",
                   "People Also Ask", "## SERP-Snapshot",
                   "serpbear-keywords-2026-10-25.csv.md"):
        assert marker in rep


def test_research_writes_artefacts(tmp_path):
    doc = tmp_path / "SEO_Produkt_x.md"
    doc.write_text(DOC, encoding="utf-8")
    summary = kr.research(doc, FakeSerper(), gl="de", hl="de", num=5)
    assert summary["candidates"] > 0
    for artefact in (summary["report"], summary["csv"]):
        assert os.path.isfile(artefact)
    csv_text = open(summary["csv"], encoding="utf-8").read()
    assert csv_text.startswith("keyword,tags")
    assert "datenaufbereitung-fuer-ki" in csv_text  # product slug as tag


# --- misc -------------------------------------------------------------------

def test_slugify_umlauts():
    assert kr.slugify("Datenaufbereitung für KI") == "datenaufbereitung-fuer-ki"


def test_seed_name_trims_marketing_tail():
    name = "Managed Backup — externe Datensicherung mit täglicher Prüfung"
    assert kr._seed_name(name) == "Managed Backup"
    assert kr._seed_name("Plain Name") == "Plain Name"
    # spaced hyphen is a marketing separator too — "E-Mail" itself stays intact
    assert kr._seed_name("Verwaltete E-Mail-Archivierung - jede Mail abgelegt") \
        == "Verwaltete E-Mail-Archivierung"


def test_load_serper_settings_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.setattr(config, "_repo_root", lambda: tmp_path)  # no .env there
    with pytest.raises(MarketingConfigError):
        load_serper_settings()


def test_load_serper_settings_ok(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "k")
    assert load_serper_settings() == {"api_key": "k"}


def test_load_serper_settings_repo_root_env(tmp_path, monkeypatch):
    """SERPER_API_KEY is read from .env at the (superproject) repo root."""
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    (tmp_path / ".env").write_text("SERPER_API_KEY=from-root\n",
                                   encoding="utf-8")
    monkeypatch.setattr(config, "_repo_root", lambda: tmp_path)
    assert load_serper_settings() == {"api_key": "from-root"}


def test_parse_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\nA=1\nB = \"two\"\n\nC='x'\nD=v1  # inline note\n"
        "E=keep #nospace\nF=\"quoted # kept\"\n",
        encoding="utf-8")
    assert config._parse_env_file(env) == {
        "A": "1", "B": "two", "C": "x",
        "D": "v1",           # inline comment stripped
        "E": "keep",         # dotenv semantics: unquoted value ends at " #"
        "F": "quoted # kept",
    }
    assert config._parse_env_file(tmp_path / "missing") == {}


# --- Google enrichment --------------------------------------------------------

class FakeGscQuery:
    def __init__(self, pages):
        self.pages = list(pages)
        self.bodies = []

    def query(self, siteUrl, body):
        self.bodies.append((siteUrl, body))
        return self

    def execute(self, num_retries=0):
        return self.pages[len(self.bodies) - 1]


class FakeGsc:
    def __init__(self, pages):
        self._query = FakeGscQuery(pages)

    def searchanalytics(self):
        return self._query


class FakeGaReport:
    def __init__(self, response):
        self.response = response
        self.bodies = []

    def runReport(self, property, body):
        self.bodies.append((property, body))
        return self

    def execute(self, num_retries=0):
        return self.response


class FakeGa:
    def __init__(self, response):
        self._report = FakeGaReport(response)

    def properties(self):
        return self._report


def test_query_search_analytics_paginates(monkeypatch):
    monkeypatch.setattr(google_search_console, "_SEARCH_ANALYTICS_ROW_LIMIT", 2)
    pages = [
        {"rows": [{"keys": ["a"], "clicks": 1, "impressions": 9,
                   "ctr": 0.1, "position": 3.0},
                  {"keys": ["b"], "clicks": 0, "impressions": 4,
                   "ctr": 0.0, "position": 8.0}]},
        {"rows": [{"keys": ["c"], "clicks": 2, "impressions": 7,
                   "ctr": 0.3, "position": 1.5}]},
    ]
    service = FakeGsc(pages)
    rows = google_search_console.query_search_analytics(
        service, "sc-domain:example.com", "2026-01-01", "2026-03-31",
        row_limit=3)
    assert [r["keys"] for r in rows] == [["a"], ["b"], ["c"]]
    bodies = service._query.bodies
    assert len(bodies) == 2  # full first page -> second request
    assert bodies[0][1]["startRow"] == 0 and bodies[1][1]["startRow"] == 2
    assert bodies[0][0] == "sc-domain:example.com"


def test_landing_page_report_parses_rows():
    response = {
        "dimensionHeaders": [{"name": "landingPage"}],
        "metricHeaders": [{"name": "sessions"}, {"name": "engagedSessions"},
                          {"name": "engagementRate"}],
        "rows": [{"dimensionValues": [{"value": "/a"}],
                  "metricValues": [{"value": "10"}, {"value": "8"},
                                   {"value": "0.8"}]}],
    }
    rows = google_analytics.landing_page_report(
        FakeGa(response), "properties/1", "2026-01-01", "2026-03-31")
    assert rows == [{"landingPage": "/a", "sessions": "10",
                     "engagedSessions": "8", "engagementRate": "0.8"}]


def test_report_date_range():
    start, end = kr.report_date_range(90)
    assert start < end  # ISO dates compare lexically
    from datetime import date, timedelta
    assert end == (date.today() - timedelta(days=3)).isoformat()


def test_merge_gsc_candidates():
    c = {"alpha": {"kw": "Alpha", "sources": {"seed"}, "seeds": {"a"}}}
    rows = [
        {"keys": ["alpha"], "clicks": 3, "impressions": 40,
         "ctr": 0.075, "position": 4.2},
        {"keys": ["neue anfrage"], "clicks": 1, "impressions": 5,
         "ctr": 0.2, "position": 2.0},
        {"keys": ["nur impressions"], "clicks": 0, "impressions": 9,
         "ctr": 0.0, "position": 40.0},
        {"keys": ["no data"], "clicks": 0, "impressions": 0,
         "ctr": 0.0, "position": 0.0},
    ]
    kr.merge_gsc_candidates(c, rows)
    assert c["alpha"]["gsc"]["clicks"] == 3
    assert "search-console" in c["alpha"]["sources"]
    # clicked real query becomes a candidate
    assert c["neue anfrage"]["gsc"]["position"] == 2.0
    assert "search-console" in c["neue anfrage"]["sources"]
    # impression-only real queries are merged too — the site already ranks
    assert "nur impressions" in c
    # rows without any data stay out
    assert "no data" not in c


def test_render_report_with_google_sections():
    parsed = {"product": "Prod", "topic": "T", "pillar": "Alpha",
              "secondary": [], "longtail": []}
    seeds = [{"kw": "Alpha", "kind": "pillar"}]
    c = {"alpha": {"kw": "Alpha", "sources": {"seed", "search-console"},
                   "seeds": {"Alpha"},
                   "gsc": {"clicks": 3, "impressions": 40, "ctr": 0.075,
                           "position": 4.2}}}
    meta = {"date": "2026-11-10", "gl": "de", "hl": "de", "calls": 2,
            "doc": "doc.md", "tag": "prod", "csv_name": "x.csv.md",
            "gsc": {"site_url": "sc-domain:example.com",
                    "start": "2026-08-01", "end": "2026-11-01"},
            "ga": {"property": "properties/1"}}
    ga_pages = [{"landingPage": "/a", "sessions": "10",
                 "engagedSessions": "8", "engagementRate": "0.8"}]
    rep = kr.render_report(parsed, seeds, c, [], {"Alpha": []}, meta,
                           ga_pages=ga_pages)
    assert "| Klicks | Impr. | Pos. |" in rep
    assert "| Alpha | search-console, seed |" in rep
    assert "sc-domain:example.com" in rep
    assert "## GA4 — Top-Landingpages (1)" in rep
    assert "| /a | 10 | 8 | 80% |" in rep


def test_load_site_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_repo_root", lambda: tmp_path)  # no .env there
    monkeypatch.setenv("GSC_SITE_URL", "example.com")
    monkeypatch.setenv("GA4_PROPERTY_ID", "12345")
    assert load_site_settings() == {
        "gsc_site_url": "sc-domain:example.com",
        "ga4_property": "properties/12345",
    }
    monkeypatch.setenv("GSC_SITE_URL", "https://x.example.com/")
    monkeypatch.setenv("GA4_PROPERTY_ID", "properties/9")
    assert load_site_settings() == {
        "gsc_site_url": "https://x.example.com/",
        "ga4_property": "properties/9",
    }
    monkeypatch.delenv("GSC_SITE_URL")
    monkeypatch.delenv("GA4_PROPERTY_ID")
    assert load_site_settings() == {"gsc_site_url": "", "ga4_property": ""}
