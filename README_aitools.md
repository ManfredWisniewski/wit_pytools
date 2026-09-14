# aitools

`aitools` provides small, dependency-light Python functions for AI-related tasks. The current implementation covers the OpenRouter API: chat completions with model selection, model discovery, and image generation from a prompt.

## Setup

No additional dependencies beyond `requirements.txt` (`requests`, `eliot`).

Environment variables:

| Variable                 | Required | Purpose                                                        |
| ------------------------ | -------- | -------------------------------------------------------------- |
| `OPENROUTER_API_KEY`     | yes      | API key. Never stored in the repository.                        |
| `OPENROUTER_MODEL`       | no       | Default model for `chat()` when `model=` is not passed.          |
| `OPENROUTER_IMAGE_MODEL` | no       | Default model for `generate_image()`.                            |
| `OPENROUTER_MAX_COST`    | no       | Cost threshold in USD for image generation (default `0.50`).     |
| `OPENROUTER_REFERER`     | no       | Sent as `HTTP-Referer` for app attribution on openrouter.ai.     |
| `OPENROUTER_TITLE`       | no       | Sent as `X-OpenRouter-Title` for app attribution.                |

No model is hardcoded. Pass `model=` explicitly or set the env variable.

Run scripts from the repository root with `PYTHONPATH=P:\git\witnctools` (or the equivalent for your shell).

## Chat

```python
from wit_pytools.aitools import chat, image_part

# simplest form: prompt string, model from OPENROUTER_MODEL
answer = chat("Summarize the attached notes in three bullet points.")

# explicit model, system prompt, extra parameters passed through
answer = chat(
    "Translate to German: good morning",
    model="openai/gpt-4o-mini",
    system="You are a concise translator.",
    temperature=0.2,
    max_tokens=200,
)

# full message list, including an image as reference material
answer = chat(
    [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is shown on this receipt?"},
                image_part("scans/receipt.jpg"),
            ],
        }
    ],
    model="openai/gpt-4o",
)
```

`chat()` returns the assistant text. Use `request()` if you need the raw JSON (for example `usage`):

```python
from wit_pytools.aitools import request

body = request("chat/completions", {"model": "openai/gpt-4o-mini", "messages": [...]})
print(body["usage"])
```

## Choosing a model

```python
from wit_pytools.aitools import list_models

for m in list_models():                       # all models
    print(m["id"], m["output_modalities"])

for m in list_models("image"):                # image-generating models with pricing
    print(m["id"], m["pricing"])
```

Each entry contains `id`, `name`, `input_modalities`, `output_modalities`, `pricing`.

## Image generation

### CLI

```bat
set OPENROUTER_API_KEY=...
set OPENROUTER_IMAGE_MODEL=bytedance-seed/seedream-4.5

python -m wit_pytools.aitools.generate_image "a red panda astronaut, studio lighting" --out-dir images --aspect-ratio 16:9 --resolution 2K
```

For long or non-ASCII prompts, prefer UTF-8 text files:

```bat
python -m wit_pytools.aitools.generate_image --prompt-file prompt.txt --negative-prompt-file negative_prompt.txt --out-dir images
```

The `generate_image_runner.bat` uses this file-based approach so Windows `cmd.exe` does not reinterpret German or other non-ASCII characters from the batch source.

Options:

| Option                  | Meaning                                                          |
| ----------------------- | ---------------------------------------------------------------- |
| `--model`               | Image model id (default `OPENROUTER_IMAGE_MODEL`).                 |
| `--negative-prompt`     | Content to avoid in the generated image.                          |
| `--out-dir`             | Target directory (default current directory).                     |
| `-n`                    | Number of images, 1-10 (provider permitting).                     |
| `--aspect-ratio`        | e.g. `1:1`, `16:9`, `9:16`.                                        |
| `--resolution`          | `512`, `1K`, `2K`, `4K`.                                          |
| `--quality`             | `auto`, `low`, `medium`, `high`.                                   |
| `--output-format`       | `png`, `jpeg`, `webp`, `svg`.                                      |
| `--reference PATH_OR_URL` | Reference image for image-to-image; repeatable.                  |
| `--overwrite`           | Allow replacing existing output files.                            |
| `--max-cost`            | Confirm above this USD amount (default `0.50`).                    |
| `--yes`                 | Skip the cost confirmation.                                        |

Unsupported parameter values are rejected by OpenRouter with a 400 error that is shown as-is. Check a model's `supported_parameters` via `list_models("image")` or the OpenRouter models page.

### Cost control

Before generating, the per-image price is looked up from OpenRouter's endpoint records. The estimate is the highest per-image price among providers, multiplied by `n`. If the estimate exceeds `--max-cost` (or `OPENROUTER_MAX_COST`), or the price cannot be converted (per-megapixel or per-token pricing), you are asked to confirm. `--yes` skips the prompt. The actual `usage.cost` is printed after generation.

### Output

Files are written to `out_dir`:

```text
20260914-153012_a-red-panda-astronaut-studio-lighting.png
20260914-153012_a-red-panda-astronaut-studio-lighting.json
```

With `-n 2`: `..._1.png`, `..._2.png` and one shared `.json`. The extension comes from the returned `media_type`. Existing files are never overwritten unless `--overwrite` is given.

The `.json` sidecar records prompt, model, parameters, reference images, media types, file names, `usage` (including cost) and the pre-generation estimate.

### Python

```python
from wit_pytools.aitools.generate_image import generate_image

paths = generate_image(
    "a watercolor version of this photo",
    negative_prompt="text, watermark, blur",
    model="openai/gpt-image-1",
    out_dir="images",
    input_references=["photos/original.jpg"],
    yes=True,
)
```

## Errors

- Missing key or model: `RuntimeError` naming the env variable to set.
- API error: `RuntimeError("OpenRouter <status>: <message>")`.
- Existing output: `FileExistsError`.
- Unsupported local image type for `image_part()`: `ValueError` (allowed: png, jpg, jpeg, webp, gif). Files above 5 MB log a warning.

## Tests

```bat
python -m pytest tests\aitools_test.py
```

Tests mock `requests`; no network access or API key is needed.

## Not covered (yet)

Streaming responses, provider routing options, automatic retries, local validation of image parameters against model capabilities.
