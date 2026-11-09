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
