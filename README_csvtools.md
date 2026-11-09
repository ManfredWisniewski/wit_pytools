# csvtools

`csvtools` transforms CSV exports between application formats using mapping
files.

## Application data formats

### Vaultwarden

**Folders** — personal vaults only. Purely cosmetic grouping for your own
items ("Work", "Finance", ...). No access control, not shared with anyone.

**Collections** — organization vaults only. The sharing unit: items in a
collection are visible to org members/groups assigned to that collection.
That is the actual access-control mechanism (who can view/edit which shared
secrets).

For imports: into a **personal vault** the `folder` column matters and
`collections` is ignored; into an **organization vault** fill `collections`.
Filling both is fine — Vaultwarden uses whichever applies to the target
vault.

**Type** — the item type, i.e. which kind of vault entry the row is:

- `login` — username/password/URI/TOTP
- `note` — secure note (uses `notes`, ignores `login_*` columns)
- `card` — payment card
- `identity` — personal identity record

Only `login` rows use the `login_uri`/`login_username`/`login_password`/
`login_totp` columns.

**Import gotchas**

- Select `Bitwarden (csv)` as the file format in the Import UI.
- Do not leave empty rows in the CSV — Vaultwarden creates an empty entry
  for each empty row.
- On import, Vaultwarden creates collections for names it does not
  recognize — always as **new** collections, even if a collection with the
  same name already exists (matching is by UUID, not name). To import into
  existing collections use the Collection picker in the Import UI or a
  Bitwarden-org `.json` with the existing collection UUIDs.
