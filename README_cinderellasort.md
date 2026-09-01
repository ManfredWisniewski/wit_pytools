# CinderellaSort

CinderellaSort is the shared file-sorting engine used by Mail-Sort and other
sorting tools.

## Common sorting rules

In Nextcloud mode, CinderellaSort loads common `[BOWLS]` and
`[BOWLS_EMAIL]` rules from the central configuration file:

```text
/etc/nctools/nctools.ini
```

The project configuration is loaded first. The central `[BOWLS]` and
`[BOWLS_EMAIL]` rules are merged into the effective configuration at runtime.
Neither configuration file is modified.

Example central configuration:

```ini
[BOWLS]
Documents=documents
Plans=plans,drawings
Archive=archive
```

A project configuration can contain additional local rules:

```ini
[BOWLS]
Project=project
Plans=project-plans
```

The effective rules are equivalent to:

```ini
[BOWLS]
Documents=documents
Plans=plans,drawings,project-plans
Archive=archive
Project=project
```

If the same bowl is defined in both configurations, its comma-separated
criteria are combined and duplicate criteria are removed. Central rules are
kept before project-specific rules when matching files.

The central file may contain other sections used by the server, but only its
`[BOWLS]` and `[BOWLS_EMAIL]` sections are merged as common rule sets.

Example for shared email rules:

```ini
[BOWLS_EMAIL]
Eingang/Trox=@troxgroup.com
Eingang=!DEFAULT
```

The same merge and precedence rules apply to `[BOWLS_EMAIL]`.

## Project configuration

Project configurations continue to define their own paths and settings:

```ini
[TABLE]
sourcedir=/path/to/source
targetdir=/path/to/target
filemode=nc

[BOWLS]
Project=project
```

For Nextcloud mode, the project configuration is normally named
`mailsort-ini.txt`. Standalone configurations can use `mailsort.ini`.

The common rule merge is enabled automatically when the effective
configuration uses `filemode=nc`. Existing configurations without central
`[BOWLS]` or `[BOWLS_EMAIL]` sections continue to work unchanged.

## Duplicate keys

Do not define the same bowl more than once within one configuration file.
Combine criteria on one line:

```ini
Plans=plans,drawings,project-plans
```

Duplicate keys within one file are rejected by `ConfigParser`. Duplicate bowl
names across the central and project files are handled by the runtime merge.
