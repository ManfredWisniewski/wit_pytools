# Intent: `aufmass`

## Package purpose

`aufmass` converts KLIMAX-XLS exports (Wuttke Klimatechnik, digitales
Aufmaß) into the CSV target format and imports them into Nextcloud
Tables. Spec: `+wit/specs/wuttkeklimatechnik/aufmass/001-mvp/`.

- `converter.py` — NC-independent XLS→CSV core. Merges all source lists
  into one table per type: `bauelemente.csv` (Bauelemente/Bauteile),
  `kanal.csv` (Eckig/Formteile), `rohr.csv` (Rund/Runde); `Pos.Nr.`+
  `LV-Nummer` guaranteed; `Raum`/`Verbaut` appended; `<type>.summen.csv`
  for list sums. Generic XLS helpers live in `wit_pytools.xlstools`.
- `tablesimport.py` — WebDAV upload + Tables `POST /api/1/import/…`
  with `ImportState` verification (the only NC-dependent part).
- `aufmass.ini` — Kbez→Beschreibung replacement table (~55 mappings).

## Scope (from witnctools `+intent/aufmass`)

- Tasks `T001–T005` (converter consolidation: paths/config cleaned,
  `Pos.Nr.`+`LV-Nummer` in target format, sums, pytest against
  `P:\tmp\aufmass-data`)
- Tasks `T010–T012` (import path: CSV via WebDAV → Nextcloud Tables
  `POST /api/1/import/table/{id}`, `ImportState` verification;
  Einbauteilliste once format known)
- Converter is NC-independent; only the import step talks to Nextcloud
- Sample data outside the repo (`P:\tmp\aufmass-data`) — referenced
  via `AUFMASS_DATA`, never copied
