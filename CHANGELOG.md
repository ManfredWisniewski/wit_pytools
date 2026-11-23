# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) (`+wit/common/conventions/changelog.md`); versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `payloadtools site` pushes `site.yml` `lang:` to `theme.meta.lang` —
  the default content-tree language driving `<html lang>` and hreflang
  on arr sites.
- Front matter `noindex: true` (also `meta.noindex`/`meta_noindex`) maps
  to `meta.noindex` on synced pages/posts; always pushed, so removing
  the flag clears a previously pushed noindex.

## [<version>] - <YYYY-MM-DD>

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security
