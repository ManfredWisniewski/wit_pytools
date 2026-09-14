# Intent: `aitools`

## Package purpose

`aitools` provides modular Python functions for handling AI-related tasks.

Tasks:

1. Connect Python to the OpenRouter API and choose a model (implemented first).
2. Generate an image from a prompt using the OpenRouter Image API (implemented first).
3. Keyword research for SEO product documents via serper.dev (see `spec_keywordresearch.md`; later task, same package).

## OpenRouter client (`aitools/openrouter.py`)

Re-exported from `aitools/__init__.py`.

- HTTP via `requests` only; no SDK dependency.
- API key from `OPENROUTER_API_KEY` or an explicit `api_key=` argument. Missing key raises a clear error. Keys are never read from files in the repository.
- Optional attribution headers `HTTP-Referer` / `X-OpenRouter-Title`, sent only when `OPENROUTER_REFERER` / `OPENROUTER_TITLE` are set.
- Non-2xx responses raise `RuntimeError` carrying OpenRouter's error message.
- Timeouts: 60 s for chat and model listing, 120 s for image generation.
- Logging via `eliot.log_message`.

Functions:

- `request(endpoint, payload=None, *, method="POST", timeout=60, api_key=None) -> dict` — low-level call returning the raw JSON (for callers needing `usage`, cost, etc.).
- `chat(prompt_or_messages, model=None, *, system=None, api_key=None, **params) -> str` — accepts a `str` (wrapped as one user message) or a full `messages` list, including multimodal content parts. Returns `choices[0].message.content`. `model` falls back to `OPENROUTER_MODEL`; no model is hardcoded.
- `list_models(output_modality=None) -> list[dict]` — trimmed entries (`id`, `name`, `input_modalities`, `output_modalities`, `pricing`). `output_modality="image"` queries `/api/v1/images/models`, otherwise `/api/v1/models`.
- `image_part(source, detail=None) -> dict` — builds an `image_url` content part. `http(s)` URLs pass through; local files (`png`, `jpg`, `jpeg`, `webp`, `gif`) are embedded as base64 `data:` URLs. Other extensions are rejected; files above 5 MB log a warning. Usable for vision input to `chat()` and as `input_references` for image generation.

## Image generation (`aitools/generate_image.py`)

- Uses the dedicated `POST /api/v1/images` endpoint.
- `generate_image(prompt, model=None, *, negative_prompt=None, out_dir=".", n=1, aspect_ratio=None, resolution=None, quality=None, output_format=None, input_references=None, overwrite=False, max_cost=None, yes=False, api_key=None) -> list[Path]`. `negative_prompt`, when set, is passed to the image API as content to avoid.
- `model` falls back to `OPENROUTER_IMAGE_MODEL`; no hardcoded default.
- Parameters are passed through unchanged (`None` omitted); the API's 400 message is surfaced. No local validation against `supported_parameters`.
- Output files: `<YYYYMMDD-HHMMSS>_<slug>[_<i>].<ext>` in `out_dir`. Slug: lowercase, non-alphanumerics collapsed to `-`, max 40 chars. Index suffix only when `n > 1`. Extension from `media_type`. Existing files are never overwritten unless `overwrite=True`.
- One metadata sidecar `<basename>.json` per call: prompt, model, parameters, `media_type`, `usage` (incl. cost).
- Cost control: before generating, price is looked up via `/api/v1/images/models/<model>/endpoints`. Estimate = max `cost_usd` across endpoints for `billable == "output_image"` with `unit == "image"`, times `n`. Per-megapixel or per-token pricing (or none) counts as *unknown*. If the estimate exceeds `max_cost` (default 0.50 USD, env `OPENROUTER_MAX_COST`) or is unknown, confirmation is required unless `yes=True`. Actual `usage.cost` is printed after generation.
- CLI (`python -m wit_pytools.aitools.generate_image`): `prompt`, `--model`, `--out-dir`, `-n`, `--aspect-ratio`, `--resolution`, `--quality`, `--output-format`, `--reference <path-or-url>` (repeatable), `--overwrite`, `--max-cost`, `--yes`.

## Tests

- `tests/aitools_test.py`, pytest, `requests` mocked via `monkeypatch`; no network and no key required.
- Covers: missing key error, model fallback to env, message wrapping, `image_part` for URL and local file, base64 decode and extension from `media_type`, filename slug, overwrite refusal, cost estimate and confirmation logic.

## Non-goals (this iteration)

- Streaming (`stream: true`).
- Provider routing options (`provider.only/order/ignore/sort`).
- Retries / backoff.
- Local validation of image parameters against model capabilities.
- Any hardcoded default model.

## Documentation

- `README_aitools.md` — human-readable usage.
- `README_aitools_AI.md` — compact reference for AI agents.
- No new entries in `requirements.txt` (`requests`, `eliot` already present).
