# Test strategy

## Name dataset acceptance criteria

- **A01** Configured forename and surname datasets classify single-token names.
- **A02** Configured forename and surname datasets classify compound names when a given-name and surname token are present.
- **A03** Comparison is Unicode-normalized and case-insensitive while original text is preserved.
- **A04** The repository commit is checked and unchanged cached data is reused.
- **A05** Changed repository data refreshes the cache.
- **A06** A connection failure uses an available cache.
- **A07** A connection failure without a cache raises `NameDatasetUnavailableError`.
- **A08** Unknown country codes fail validation.
- **A09** `use_name_datasets=False` skips dataset loading.
- **A10** Protected spans are excluded from dataset-backed detection.
- **A11** German nouns exclude single-token German name candidates.
- **A12** German first-name and surname lists add positive name evidence.

## Test files

```text
tests/anonymization/test_core.py
tests/anonymization/test_name_datasets.py
```

## Verification command

```text
python tests/runtests.py
```

Network behavior is tested with mocked repository metadata and dataset
responses. Tests do not access GitHub or use real credentials.
