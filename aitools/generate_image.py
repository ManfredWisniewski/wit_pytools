"""Generate images from a prompt via the OpenRouter Image API."""

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from eliot import log_message

from .openrouter import IMAGE_TIMEOUT, image_part, request

DEFAULT_MAX_COST = 0.50
_SLUG_MAX_LENGTH = 40
_MEDIA_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
}


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:_SLUG_MAX_LENGTH].rstrip("-") or "image"


def _extension(media_type: Optional[str]) -> str:
    return _MEDIA_EXTENSIONS.get((media_type or "").lower(), "png")


def estimate_cost(model: str, n: int = 1, *, api_key: Optional[str] = None) -> Optional[float]:
    """Return the worst-case per-call price in USD, or ``None`` if unknown."""
    body = request(f"images/models/{model}/endpoints", method="GET", api_key=api_key)
    prices = [
        line.get("cost_usd")
        for endpoint in body.get("endpoints", [])
        for line in endpoint.get("pricing", [])
        if line.get("billable") == "output_image"
        and line.get("unit") == "image"
        and isinstance(line.get("cost_usd"), (int, float))
    ]
    if not prices:
        return None
    return max(prices) * n


def _confirm(estimate: Optional[float], max_cost: float, yes: bool) -> None:
    if yes:
        return
    if estimate is None:
        question = "Price per image could not be determined."
    elif estimate <= max_cost:
        return
    else:
        question = f"Estimated cost {estimate:.2f} USD exceeds limit {max_cost:.2f} USD."
    answer = input(f"{question} Continue? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        raise RuntimeError("Aborted by user before generating")


def _check_targets(paths: Sequence[Path], overwrite: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(existing[0])


def generate_image(
    prompt: str,
    model: Optional[str] = None,
    *,
    negative_prompt: Optional[str] = None,
    out_dir: Union[str, Path] = ".",
    n: int = 1,
    aspect_ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    quality: Optional[str] = None,
    output_format: Optional[str] = None,
    input_references: Optional[Sequence[Union[str, Path, Dict[str, Any]]]] = None,
    overwrite: bool = False,
    max_cost: Optional[float] = None,
    yes: bool = False,
    api_key: Optional[str] = None,
) -> List[Path]:
    """Generate ``n`` images and write them plus a JSON sidecar to ``out_dir``."""
    chosen_model = model or os.environ.get("OPENROUTER_IMAGE_MODEL", "")
    if not chosen_model:
        raise RuntimeError("No model given: pass model= or set OPENROUTER_IMAGE_MODEL")
    if n < 1:
        raise ValueError("n must be at least 1")

    limit = max_cost if max_cost is not None else float(
        os.environ.get("OPENROUTER_MAX_COST", DEFAULT_MAX_COST)
    )
    estimate = estimate_cost(chosen_model, n, api_key=api_key)
    _confirm(estimate, limit, yes)

    payload: Dict[str, Any] = {"model": chosen_model, "prompt": prompt}
    optional = {
        "negative_prompt": negative_prompt,
        "n": n if n > 1 else None,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "quality": quality,
        "output_format": output_format,
    }
    payload.update({key: value for key, value in optional.items() if value is not None})
    if input_references:
        payload["input_references"] = [
            reference if isinstance(reference, dict) else image_part(reference)
            for reference in input_references
        ]

    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    basename = f"{datetime.now():%Y%m%d-%H%M%S}_{_slugify(prompt)}"
    sidecar = directory / f"{basename}.json"

    body = request("images", payload, timeout=IMAGE_TIMEOUT, api_key=api_key)
    images = body.get("data") or []
    if not images:
        raise RuntimeError(f"OpenRouter returned no images: {body}")

    targets = []
    for index, image in enumerate(images, start=1):
        suffix = f"_{index}" if len(images) > 1 else ""
        targets.append(directory / f"{basename}{suffix}.{_extension(image.get('media_type'))}")
    _check_targets([*targets, sidecar], overwrite)

    for target, image in zip(targets, images):
        target.write_bytes(base64.b64decode(image["b64_json"]))

    usage = body.get("usage") or {}
    sidecar.write_text(
        json.dumps(
            {
                "prompt": prompt,
                "model": chosen_model,
                "parameters": {key: payload[key] for key in payload if key not in ("model", "prompt", "input_references")},
                "input_references": [str(r) for r in input_references] if input_references else [],
                "media_types": [image.get("media_type") for image in images],
                "files": [target.name for target in targets],
                "usage": usage,
                "estimated_cost_usd": estimate,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    cost = usage.get("cost")
    log_message(
        f"Generated {len(targets)} image(s) with {chosen_model}; cost {cost} USD",
        level="INFO",
    )
    print(f"Cost: {cost if cost is not None else 'unknown'} USD")
    return targets


class _Tee:
    """Write to the console stream and a log file at the same time."""

    def __init__(self, stream, log_file):
        self._stream = stream
        self._log = log_file

    def write(self, text):
        self._stream.write(text)
        self._log.write(text)
        self._log.flush()

    def flush(self):
        self._stream.flush()
        self._log.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate images via OpenRouter.")
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--prompt-file", type=Path, help="UTF-8 prompt text file")
    parser.add_argument("--negative-prompt", help="Content to avoid in the generated image")
    parser.add_argument("--negative-prompt-file", type=Path, help="UTF-8 negative prompt text file")
    parser.add_argument("--model", help="Model id; default from OPENROUTER_IMAGE_MODEL")
    parser.add_argument("--out-dir", default=".", type=Path)
    parser.add_argument("-n", type=int, default=1, help="Number of images (1-10)")
    parser.add_argument("--aspect-ratio")
    parser.add_argument("--resolution", help="512, 1K, 2K or 4K")
    parser.add_argument("--quality", help="auto, low, medium or high")
    parser.add_argument("--output-format", help="png, jpeg, webp or svg")
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        metavar="PATH_OR_URL",
        help="Reference image (repeatable)",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--max-cost",
        type=float,
        help=f"Confirm above this USD amount (default {DEFAULT_MAX_COST}, env OPENROUTER_MAX_COST)",
    )
    parser.add_argument("--yes", action="store_true", help="Skip cost confirmation")
    parser.add_argument(
        "--log",
        type=Path,
        metavar="FILE",
        help="Append console output to this file (prompts stay interactive)",
    )
    args = parser.parse_args(argv)
    if args.prompt_file:
        prompt = args.prompt_file.read_text(encoding="utf-8").strip()
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.error("prompt or --prompt-file is required")
    negative_prompt = args.negative_prompt
    if args.negative_prompt_file:
        negative_prompt = args.negative_prompt_file.read_text(encoding="utf-8").strip()

    log_file = None
    stdout, stderr = sys.stdout, sys.stderr
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        log_file = args.log.open("a", encoding="utf-8")
        log_file.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} {prompt!r}\n")
        sys.stdout = _Tee(stdout, log_file)
        sys.stderr = _Tee(stderr, log_file)
    try:
        paths = generate_image(
            prompt,
            args.model,
            negative_prompt=negative_prompt,
            out_dir=args.out_dir,
            n=args.n,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
            quality=args.quality,
            output_format=args.output_format,
            input_references=args.reference or None,
            overwrite=args.overwrite,
            max_cost=args.max_cost,
            yes=args.yes,
        )
        for path in paths:
            print(path)
        return 0
    except Exception as exc:  # report to console and log, exit non-zero
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        sys.stdout, sys.stderr = stdout, stderr
        if log_file:
            log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
