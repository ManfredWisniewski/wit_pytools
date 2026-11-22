# Intent: `<project>`

## Purpose

`<project>` provides `<short description>`.

State:

- where the work or implementation currently lives;
- who uses it (people, repositories, workflows);
- why it exists and which problem it solves.

Before the first grilling session, check `+team/+tasks/` for open tasks and use the first one as its goal. If initial research exists, integrate everything relevant here and in `knowledge/decisions.md` during that session, then remove the research file.

## Concepts

Define the domain terms used in this project:

- **`<term>`**: `<meaning>`.
- **`<term>`**: `<meaning>`.

## Scope

- In scope: `<what this project covers>`.
- Out of scope: `<what it deliberately does not cover, and where that lives instead>`.

## Software projects (optional — delete this section otherwise)

### Configuration

Describe the configuration format, sections, keys, defaults and precedence. State which files are modified and which remain unchanged.

- `<key>` — `<meaning and default>`.

### Processing order

1. `<validation or input discovery>`.
2. `<classification or matching>`.
3. `<transformation or handling>`.
4. `<output, cleanup or indexing>`.

Document the priority when multiple handlers or rules can match.

### Main workflows

Per workflow: input and output, matching criteria, side effects, failure behaviour, retry or idempotency behaviour.

### Public functions

- `<function_name>(...)` — `<purpose, important parameters, return value, raised errors, whether source files are modified>`.

### Data and file formats

Headers, required fields, status values, markers and compatibility rules of CSV, JSON, INI, Markdown or other formats used.

### Safety and preservation

- `<what is preserved>`.
- `<what may be modified or deleted, and how output collisions are handled>`.
- `<failure safety rule>`.

## Tests and verification

Acceptance criteria and test commands: `tests.md`.

## Non-goals and limitations

- `<unsupported format or behaviour>`.
- `<known limitation or deferred integration>`.

## Open items

Open tasks: `+team/+tasks/<persona>.md`. Unresolved design decisions: `knowledge/decisions.md`, section "Backlog".
