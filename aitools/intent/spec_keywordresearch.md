Spec: Keyword-Research-Skript für SEO-Produktdokumente
Ziel
Für ein SEO-Produktdokument (SEO_Produkt_*.md) automatisch eine Kandidatenliste an Keywords erzeugen und in den Keywords-Abschnitt des Dokuments schreiben. Das Skript liefert Rohmaterial; die Entscheidungen (Pillar-Keyword, Zuordnung zu einer Seite, Ausschluss) trifft der Mensch anschließend im Dokument.

Kontext
Dokumente liegen unter P:\cloud-wit\projects\witconsult\witconsult.de\Marketing\SEO On-Page\<thema>\<kategorie>\<produkt>\SEO_Produkt_*.md (Markdown, deutsche Inhalte, Vorlage in _Vorlagen\SEO_Produkt_Vorlage.md).
Zielmarkt: Deutschland, Sprache Deutsch (gl=de, hl=de).
Datenquelle: serper.dev (Google-SERP-API), Free Tier. API-Key ausschließlich über Umgebungsvariable SERPER_API_KEY, niemals im Repo.
Kein Suchvolumen verfügbar — bewusst weggelassen. Stattdessen relative Nachfrage-Signale (siehe Schritt 4).
Budget: ~2 Credits pro Seed. Skript soll vor dem Lauf die erwarteten Credits ausgeben und bei > N (Default 100) eine Bestätigung verlangen.
Eingabe
Pfad zum Produktdokument (Pflicht).
seeds.txt im selben Ordner wie das Dokument (Pflicht, handgepflegt): eine Suchphrase pro Zeile, 15–30 Zeilen, in der Sprache des Käufers ("Firmenhandy Monteur einrichten", nicht "MDM Policy"). Zeilen mit # sind Kommentare.
Optional: --dry-run (nur Credits schätzen), --max-credits, --out (alternativer Ausgabepfad statt In-Place).
Keine automatische Seed-Generierung per LLM — Seeds sind bewusst manuell.

Verarbeitung
Schritt 1 – Seeds laden, deduplizieren, normalisieren (trim, lowercase für Vergleich, Original für Ausgabe).

Schritt 2 – Autocomplete je Seed: serper /autocomplete, Parameter q, gl=de, hl=de. Ergebnis: Liste Suggest-Phrasen.

Schritt 3 – SERP je Seed: serper /search, gl=de, hl=de, num=10. Aus der Antwort extrahieren:

peopleAlsoAsk → Fragen (Text)
relatedSearches → Phrasen
organic[0..4] → Domain, Titel, URL (für Wettbewerbstabelle)
Schritt 4 – Zusammenführen und bewerten. Alle Phrasen (Seeds, Suggests, Related, PAA) in eine Kandidatenmenge, dedupliziert (case-insensitive, Whitespace normalisiert). Pro Kandidat Flags:

A – kam aus Autocomplete
P – ist eine People-also-ask-Frage
R – kam aus Related Searches
S – ist selbst Seed
Zähler: wie viele Seeds haben diesen Kandidaten hervorgebracht (Häufigkeit = Nachfrage-Proxy)
Sortierung: Häufigkeit absteigend, dann Anzahl Flags absteigend.

Schritt 5 – Wettbewerb. Domains aus organic[0..4] über alle Seeds aggregieren: Domain, Anzahl Treffer, Beispiel-Titel. Top 10.

Ausgabe
In das Produktdokument, ausschließlich innerhalb des Abschnitts ## Keywords, als neuer Unterabschnitt am Ende des Abschnitts:



markdown
### Kandidaten (automatisch, YYYY-MM-DD, N Seeds, M Credits)
 
> Rohliste aus Autocomplete (A), People-also-ask (P), Related Searches (R), Seed (S).
> Zuordnung zu Pillar / Sekundär / Long-Tail / Irrelevant / Auszuschließend erfolgt manuell.
 
| Kandidat | Häufigkeit | Quellen | Ursprungs-Seeds |
|---|---|---|---|
| firmenhandy monteure verwalten | 4 | A,R,S | firmenhandy monteur, ... |
| wie sichere ich firmenhandys ab? | 2 | P | ... |
Sowie in den Abschnitt ## Wettbewerb als Unterabschnitt ### SERP-Domains (automatisch, YYYY-MM-DD) eine Tabelle: Domain | Treffer | Beispiel-Titel | Beispiel-URL.

Regeln fürs Schreiben:

Bestehende Inhalte in Primäres Keyword, Sekundäre Keywords, Long-Tail, Irrelevante, Auszuschließende werden nie verändert.
Existiert bereits ein ### Kandidaten (automatisch, …)-Block, wird er ersetzt (nicht angehängt), damit Wiederholungsläufe idempotent sind. Gleiches für den SERP-Domains-Block.
Das Dokument ist UTF-8; Umlaute erhalten; Zeilenenden nicht ändern.
Rohantworten der API zusätzlich als JSON neben das Dokument legen (keywords_raw_YYYY-MM-DD.json), um Credits bei Nachbearbeitung zu sparen. --from-cache liest daraus statt die API zu rufen.
Nicht-Ziele
Kein Suchvolumen, keine Bewertung "gut/schlecht", kein Pillar-Vorschlag.
Keine Änderung an H1, Slug, Meta-Feldern oder anderen Abschnitten.
Kein Scraping von Google direkt.
Keine Verarbeitung mehrerer Dokumente in einem Lauf (Abgrenzung zwischen Schwesterseiten ist eine manuelle Entscheidung; Batch käme später).
Erster Testfall
mobile-arbeit\mdm\_Knox-Profilkonzept\SEO_Produkt_KnoxProfilkonzept.md mit einer seeds.txt von ca. 20 Phrasen. Erwartung: ~40 Credits, Kandidatenblock mit 60–150 Zeilen, Wettbewerbstabelle mit MDM-Anbietern und Systemhäusern.

Erfolgskriterium
Ein Lauf pro Produkt, danach kann im Dokument in < 15 Minuten Pillar + Sekundär + Long-Tail + Auszuschließende aus der Kandidatenliste zugewiesen werden, ohne ein weiteres Tool zu öffnen.