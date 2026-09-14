# aitools — agent reference

Compact facts for AI agents working on or with `wit_pytools.aitools`. Human documentation: `README_aitools.md`. Design decisions and non-goals: `aitools/+intent/intent.md`.

Before making changes, read the shared WIT development guidance in `+wit-dev/` in this repository. Start with `+wit-dev/README.md` and `+wit-dev/AGENTS.md`, then read the relevant convention or best-practice files. These shared definitions apply independently of which skill or AI agent is performing the work.

## Layout

```text
wit_pytools/aitools/
  __init__.py          re-exports chat, image_part, list_models, request
  openrouter.py        client: request, chat, list_models, image_part, BASE_URL, CHAT_TIMEOUT=60, IMAGE_TIMEOUT=120
  generate_image.py    generate_image, estimate_cost, main (argparse CLI)
  +intent/             intent.md, spec_keywordresearch.md (later task), SEO_Produkt_Example.md
wit_pytools/tests/aitools_test.py   pytest, requests.request is monkeypatched; no network
```

## Contracts

```python
request(endpoint: str, payload: dict | None = None, *, method="POST", timeout=60, api_key=None) -> dict
# GET sends payload as query params. Raises RuntimeError("OpenRouter <status>: <message>") on non-2xx.

chat(prompt_or_messages: str | list[dict], model=None, *, system=None, api_key=None, **params) -> str
# str -> [{"role":"user","content":str}]; system inserted at index 0; params with value None are dropped.
# model fallback: env OPENROUTER_MODEL. Returns choices[0].message.content.

list_models(output_modality: str | None = None, *, api_key=None) -> list[dict]
# "image" -> GET images/models; else GET models[?output_modalities=...].
# entry keys: id, name, input_modalities, output_modalities, pricing

image_part(source: str | Path, detail=None) -> {"type":"image_url","image_url":{"url":..., ["detail":...]}}
# http(s)/data: URLs pass through; local .png/.jpg/.jpeg/.webp/.gif -> base64 data URL; else ValueError.
# >5 MB -> eliot WARNING only.

generate_image(prompt, model=None, *, negative_prompt=None, out_dir=".", n=1, aspect_ratio=None,
               resolution=None, quality=None, output_format=None, input_references=None,
               overwrite=False, max_cost=None, yes=False, api_key=None) -> list[Path]
# model fallback: env OPENROUTER_IMAGE_MODEL. POST images. negative_prompt is passed through when set; n omitted when 1.
# CLI also accepts --prompt-file and --negative-prompt-file; both are UTF-8 and avoid Windows cmd encoding issues.
# input_references items: dict passthrough or anything image_part() accepts.
# Files: <YYYYMMDD-HHMMSS>_<slug<=40>[_<i>].<ext from media_type>; sidecar <basename>.json (one per call).
# FileExistsError if any target exists and overwrite=False (checked before writing).

estimate_cost(model, n=1, *, api_key=None) -> float | None
# GET images/models/<model>/endpoints; max cost_usd where billable=="output_image" and unit=="image", times n.
# None when no per-image price exists (megapixel/token pricing).
```

Confirmation rule (`_confirm`): no prompt if `yes`; prompt via `input()` when estimate is `None` or `> max_cost`; reject unless answer is `y`/`yes`. `max_cost` default: arg, else env `OPENROUTER_MAX_COST`, else `0.50`.

## Environment

`OPENROUTER_API_KEY` (required), `OPENROUTER_MODEL`, `OPENROUTER_IMAGE_MODEL`, `OPENROUTER_MAX_COST`, `OPENROUTER_REFERER` (-> `HTTP-Referer`), `OPENROUTER_TITLE` (-> `X-OpenRouter-Title`). Attribution headers are omitted when unset. Keys are never read from files.

## OpenRouter endpoints used

- `POST /api/v1/chat/completions` — OpenAI-compatible body.
- `GET /api/v1/models`, `GET /api/v1/images/models`, `GET /api/v1/images/models/{model}/endpoints`.
- `POST /api/v1/images` — body: `model`, `prompt`, optional `n`, `aspect_ratio`, `resolution`, `size`, `quality`, `output_format`, `background`, `input_references`. Response: `data[].b64_json`, `data[].media_type`, `usage.cost`.

## Conventions to keep

- `requests` only; no OpenAI/OpenRouter SDK.
- No hardcoded model ids anywhere in code or tests' expectations of real ids.
- Never overwrite outputs without an explicit `overwrite` flag.
- Log via `eliot.log_message`; surface API error text unchanged.
- Parameter values are passed through, not validated locally (the API's 400 is authoritative).
- Tests must not hit the network: patch `wit_pytools.aitools.openrouter.requests.request`.

## Extension points

- Streaming, provider routing, retries: intentionally absent (see intent non-goals).
- Keyword research (serper.dev) is the next task in this package; reuse `openrouter.request`-style patterns (env key, `requests`, `RuntimeError` on non-2xx).

## Run

```bat
python -m pytest tests\aitools_test.py
python -m wit_pytools.aitools.generate_image "<prompt>" --model <id> --out-dir <dir> [--yes]
```

Run from the repository root with `PYTHONPATH` including `P:\git\witnctools`.
