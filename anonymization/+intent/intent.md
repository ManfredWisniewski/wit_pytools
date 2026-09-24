# Intent: `<package-or-feature>`

## Package purpose

`<package-or-feature>` provides `<short description of the package or feature>`.

State:

- where the implementation currently lives;
- which packages, applications or workflows use it;
- why it exists and which problem it solves.

## Concepts

Define the domain terms used by the implementation:

- **`<term>`**: `<meaning>`.
- **`<term>`**: `<meaning>`.
- **`<term>`**: `<meaning>`.

## Configuration

Describe the configuration format, sections, keys, defaults and precedence.

### `[<SECTION>]`

- `<key>` — `<meaning and default>`.
- `<key>` — `<meaning and default>`.

### Common configuration

Document shared or central configuration, inheritance, merge rules and local
overrides. State clearly which files are modified and which remain unchanged.

## Processing order

Describe the end-to-end processing order in numbered steps:

1. `<validation or input discovery>`.
2. `<classification or matching>`.
3. `<transformation or handling>`.
4. `<output, cleanup or indexing>`.

Document the priority when multiple handlers or rules can match.

## Main workflows

### `<workflow name>`

Describe:

- input and output;
- matching criteria;
- side effects;
- failure behavior;
- retry or idempotency behavior.

Example:

```text
<input>
    |
    +-- <output>
```

## Public functions

List public functions with their purpose and important parameters:

- `<function_name>(...)` — `<purpose>`.
- `<function_name>(...)` — `<purpose>`.

Mention return values, raised errors and whether source files are modified.

## Data and file formats

Document CSV, JSON, INI, Markdown or other formats used by the feature.
Include headers, required fields, status values, markers and compatibility
rules where relevant.

## Safety and preservation

Document what is preserved, what may be modified or deleted, and how output
collisions are handled.

- `<source preservation rule>`.
- `<overwrite or duplicate rule>`.
- `<failure safety rule>`.

## Tests and verification

List the test files, commands and acceptance criteria. Include evidence of
verified behavior and state what has not been tested.

```text
<test command>
```

## Non-goals and limitations

- `<unsupported format or behavior>`.
- `<known limitation>`.
- `<deferred integration>`.

## Open items

Link or summarize the feature TODO list. Separate planned work from completed
behavior and record unresolved design decisions explicitly.
