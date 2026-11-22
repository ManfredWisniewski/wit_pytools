# Test strategy

## Acceptance criteria

Spec: `+wit/specs/wit_pytools/ytdlptools/spec.md`.

- **A01** One call with a single YouTube video URL produces one audio file in the target directory — SC-001; verified by `tests/ytdlptools_test.py` (mocked subprocess) + demonstration.
- **A02** One call with a playlist URL of N videos produces N audio files in the target directory — SC-002; verified by `tests/ytdlptools_test.py` + demonstration.
- **A03** A failed playlist item is reported per item and does not lose the other items — SC-003; verified by `tests/ytdlptools_test.py` (per-item failure fixture).
- **A04** Module imports cleanly with stdlib only; no `.env` access or absolute paths inside `ytdlptools` — SC-004; import check + grep inspection.
- **A05** The pytest suite passes without network access — SC-005; `python -m pytest tests/ytdlptools_test.py`.

## Test files

```text
tests/ytdlptools_test.py    pytest — mocked subprocess; command construction,
                            resolve_items, per-item failure, dir creation,
                            missing-binary error
tests/ytdlptools/           fixtures (canned --flat-playlist JSON)
```
