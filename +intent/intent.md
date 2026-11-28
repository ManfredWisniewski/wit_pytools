# Intent: `wit_pytools`

## Purpose

`wit_pytools` is a collection of reusable Python modules and command-line tools
for WIT workflows. The code covers data and file handling, document conversion
and anonymization, media, communication, web and marketing automation, and
content synchronization.

Implementations live in root-level modules and package directories. Package
documentation and package-specific intent files describe their own contracts.
The root `tests/` directory contains the repository's pytest suites and
fixtures.

## Concepts

- **Tool module**: a top-level Python module or package that exposes reusable
  functions, a command-line interface, or both.
- **Consumer**: a Python script, runner, or project that imports or invokes a
  tool from this repository.
- **Package-specific contract**: the configuration, behavior, and limits
  documented with an individual tool; there is no single configuration format
  for the entire repository.

## Scope

- In scope: reusable Python tools, their command-line runners, repository
  scripts, tests, and test fixtures.
- Out of scope: shared WIT conventions and agent skills, which are maintained
  in the `+wit` submodule; live project data and environment-specific
  credentials.

## Tests and verification

Acceptance criteria and test commands: `tests.md`.

## Non-goals and limitations

- This repository is not one deployable application or service.
- A uniform configuration format or public API across all tools is not
  specified; each tool's documentation is authoritative for that tool.
