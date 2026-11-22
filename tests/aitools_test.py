import base64
import json
import os
import sys

import pytest

# Allow importing wit_pytools when running tests directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from wit_pytools.aitools import chat, image_part, list_models
from wit_pytools.aitools import openrouter
from wit_pytools.aitools import generate_image as gi

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake"


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status
        self.ok = status < 400
        self.text = json.dumps(body)

    def json(self):
        return self._body


def install_fake_request(monkeypatch, handler):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        return handler(method, url, kwargs)

    monkeypatch.setattr(openrouter.requests, "request", fake_request)
    return calls


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_REFERER", raising=False)
    monkeypatch.delenv("OPENROUTER_TITLE", raising=False)


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        chat("hi", model="x/y")


def test_chat_wraps_prompt_and_uses_env_model(monkeypatch, api_key):
    monkeypatch.setenv("OPENROUTER_MODEL", "org/model")
    calls = install_fake_request(
        monkeypatch,
        lambda m, u, k: FakeResponse(
            {"choices": [{"message": {"role": "assistant", "content": "pong"}}]}
        ),
    )

    assert chat("ping", system="be brief", temperature=0.2) == "pong"

    call = calls[0]
    assert call["url"].endswith("/chat/completions")
    assert call["headers"]["Authorization"] == "Bearer test-key"
    assert call["json"]["model"] == "org/model"
    assert call["json"]["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "ping"},
    ]
    assert call["json"]["temperature"] == 0.2
    assert "HTTP-Referer" not in call["headers"]


def test_chat_requires_model(monkeypatch, api_key):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_MODEL"):
        chat("hi")


def test_attribution_headers_from_env(monkeypatch, api_key):
    monkeypatch.setenv("OPENROUTER_REFERER", "https://example.org")
    monkeypatch.setenv("OPENROUTER_TITLE", "witnctools")
    calls = install_fake_request(monkeypatch, lambda m, u, k: FakeResponse({"data": []}))

    list_models()

    assert calls[0]["headers"]["HTTP-Referer"] == "https://example.org"
    assert calls[0]["headers"]["X-OpenRouter-Title"] == "witnctools"


def test_api_error_is_surfaced(monkeypatch, api_key):
    install_fake_request(
        monkeypatch,
        lambda m, u, k: FakeResponse({"error": {"message": "bad model"}}, status=400),
    )
    with pytest.raises(RuntimeError, match="400: bad model"):
        chat("hi", model="x/y")


def test_list_models_trims_and_routes_image_endpoint(monkeypatch, api_key):
    calls = install_fake_request(
        monkeypatch,
        lambda m, u, k: FakeResponse(
            {
                "data": [
                    {
                        "id": "a/b",
                        "name": "B",
                        "architecture": {
                            "input_modalities": ["text"],
                            "output_modalities": ["image"],
                        },
                        "extra": "ignored",
                    }
                ]
            }
        ),
    )

    models = list_models("image")

    assert calls[0]["method"] == "GET"
    assert calls[0]["url"].endswith("/images/models")
    assert models == [
        {
            "id": "a/b",
            "name": "B",
            "input_modalities": ["text"],
            "output_modalities": ["image"],
            "pricing": None,
        }
    ]


def test_image_part_url_passthrough_and_detail():
    part = image_part("https://example.org/a.png", detail="high")
    assert part == {
        "type": "image_url",
        "image_url": {"url": "https://example.org/a.png", "detail": "high"},
    }


def test_image_part_encodes_local_file(tmp_path):
    file = tmp_path / "ref.PNG"
    file.write_bytes(PNG_BYTES)
    part = image_part(file)
    expected = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode()
    assert part["image_url"]["url"] == expected


def test_image_part_rejects_unknown_extension(tmp_path):
    file = tmp_path / "ref.bmp"
    file.write_bytes(b"x")
    with pytest.raises(ValueError, match="Unsupported image type"):
        image_part(file)


def image_api_handler(prices=(0.05,), n_images=1, media_type="image/png"):
    def handler(method, url, kwargs):
        if url.endswith("/endpoints"):
            return FakeResponse(
                {
                    "endpoints": [
                        {"pricing": [{"billable": "output_image", "unit": "image", "cost_usd": p}]}
                        for p in prices
                    ]
                }
            )
        if url.endswith("/images"):
            return FakeResponse(
                {
                    "data": [
                        {"b64_json": base64.b64encode(PNG_BYTES).decode(), "media_type": media_type}
                        for _ in range(n_images)
                    ],
                    "usage": {"cost": 0.04},
                }
            )
        raise AssertionError(url)

    return handler


def test_slugify():
    assert gi._slugify("A Red Panda, in Space!") == "a-red-panda-in-space"
    assert len(gi._slugify("x" * 100)) == 40
    assert gi._slugify("!!!") == "image"


def test_generate_image_writes_files_and_sidecar(monkeypatch, api_key, tmp_path):
    monkeypatch.setenv("OPENROUTER_IMAGE_MODEL", "img/model")
    calls = install_fake_request(monkeypatch, image_api_handler(n_images=2, media_type="image/webp"))

    paths = gi.generate_image(
        "Two cats",
        out_dir=tmp_path,
        n=2,
        negative_prompt="text, watermark",
        aspect_ratio="16:9",
        yes=True,
    )

    assert len(paths) == 2
    assert all(p.suffix == ".webp" for p in paths)
    assert paths[0].name.endswith("_two-cats_1.webp")
    assert paths[0].read_bytes() == PNG_BYTES
    sidecar = tmp_path / (paths[0].name.rsplit("_1.", 1)[0] + ".json")
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    assert meta["model"] == "img/model"
    assert meta["parameters"] == {
        "negative_prompt": "text, watermark",
        "n": 2,
        "aspect_ratio": "16:9",
    }
    assert meta["usage"] == {"cost": 0.04}
    assert meta["estimated_cost_usd"] == pytest.approx(0.10)

    post = [c for c in calls if c["url"].endswith("/images")][0]
    assert post["json"] == {
        "model": "img/model",
        "prompt": "Two cats",
        "negative_prompt": "text, watermark",
        "n": 2,
        "aspect_ratio": "16:9",
    }
    assert post["timeout"] == openrouter.IMAGE_TIMEOUT


def test_generate_image_basename_and_collision_suffix(monkeypatch, api_key, tmp_path):
    install_fake_request(monkeypatch, image_api_handler())
    first = gi.generate_image("p", model="img/model", out_dir=tmp_path, yes=True, basename="villa")
    assert [p.name for p in first] == ["villa.png"]
    assert (tmp_path / "villa.json").is_file()

    # villa.png/villa.json taken -> next free _k, sidecar shares the enumeration
    second = gi.generate_image("p", model="img/model", out_dir=tmp_path, yes=True, basename="villa")
    assert [p.name for p in second] == ["villa_1.png"]
    assert (tmp_path / "villa_1.json").is_file()

    (tmp_path / "villa_2.json").write_text("{}")  # orphan sidecar also blocks its index
    third = gi.generate_image("p", model="img/model", out_dir=tmp_path, yes=True, basename="villa")
    assert [p.name for p in third] == ["villa_3.png"]
    assert json.loads((tmp_path / "villa_3.json").read_text(encoding="utf-8"))["files"] == ["villa_3.png"]


def test_generate_image_basename_multi_skips_taken_indices(monkeypatch, api_key, tmp_path):
    install_fake_request(monkeypatch, image_api_handler(n_images=2))
    (tmp_path / "villa_1.png").write_bytes(b"x")
    paths = gi.generate_image("p", model="img/model", out_dir=tmp_path, n=2, yes=True, basename="villa")
    assert [p.name for p in paths] == ["villa_2.png", "villa_3.png"]
    assert (tmp_path / "villa_2.json").is_file() and (tmp_path / "villa_3.json").is_file()
    assert not (tmp_path / "villa.json").exists()


def test_generate_image_basename_does_not_reuse_stem_with_other_extension(monkeypatch, api_key, tmp_path):
    install_fake_request(monkeypatch, image_api_handler(media_type="image/png"))
    (tmp_path / "villa.jpg").write_bytes(b"existing")
    paths = gi.generate_image("p", model="img/model", out_dir=tmp_path, yes=True, basename="villa")
    assert [p.name for p in paths] == ["villa_1.png"]


def test_confirm_non_interactive_raises_instead_of_asking(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail("input() must not be called"))
    with pytest.raises(RuntimeError, match="non-interactive"):
        gi._confirm(1.0, 0.5, yes=False, interactive=False)
    with pytest.raises(RuntimeError, match="non-interactive"):
        gi._confirm(None, 0.5, yes=False, interactive=False)
    gi._confirm(0.2, 0.5, yes=False, interactive=False)


def test_generate_image_single_has_no_index(monkeypatch, api_key, tmp_path):
    install_fake_request(monkeypatch, image_api_handler())
    paths = gi.generate_image("solo", model="img/model", out_dir=tmp_path, yes=True)
    assert paths[0].name.endswith("_solo.png")


def test_generate_image_references_are_encoded(monkeypatch, api_key, tmp_path):
    ref = tmp_path / "ref.jpg"
    ref.write_bytes(b"jpg")
    calls = install_fake_request(monkeypatch, image_api_handler())

    gi.generate_image(
        "restyle", model="img/model", out_dir=tmp_path, yes=True,
        input_references=[ref, "https://example.org/b.png"],
    )

    post = [c for c in calls if c["url"].endswith("/images")][0]
    refs = post["json"]["input_references"]
    assert refs[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert refs[1]["image_url"]["url"] == "https://example.org/b.png"


def test_generate_image_refuses_overwrite(monkeypatch, api_key, tmp_path):
    install_fake_request(monkeypatch, image_api_handler())
    monkeypatch.setattr(gi, "datetime", _FixedDatetime)
    gi.generate_image("dup", model="img/model", out_dir=tmp_path, yes=True)
    with pytest.raises(FileExistsError):
        gi.generate_image("dup", model="img/model", out_dir=tmp_path, yes=True)
    gi.generate_image("dup", model="img/model", out_dir=tmp_path, yes=True, overwrite=True)


class _FixedDatetime:
    @staticmethod
    def now():
        from datetime import datetime
        return datetime(2026, 1, 2, 3, 4, 5)


def test_estimate_cost_uses_max_price_times_n(monkeypatch, api_key):
    install_fake_request(monkeypatch, image_api_handler(prices=(0.02, 0.07)))
    assert gi.estimate_cost("img/model", 3) == pytest.approx(0.21)


def test_estimate_cost_unknown_for_other_units(monkeypatch, api_key):
    def handler(method, url, kwargs):
        return FakeResponse(
            {"endpoints": [{"pricing": [{"billable": "output_image", "unit": "megapixel", "cost_usd": 0.01}]}]}
        )

    install_fake_request(monkeypatch, handler)
    assert gi.estimate_cost("img/model") is None


def test_confirmation_prompts_above_limit_and_for_unknown(monkeypatch):
    answers = iter(["n"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    with pytest.raises(RuntimeError, match="Aborted"):
        gi._confirm(1.0, 0.5, yes=False)

    asked = []
    monkeypatch.setattr("builtins.input", lambda q: asked.append(q) or "y")
    gi._confirm(None, 0.5, yes=False)
    assert "could not be determined" in asked[0]

    gi._confirm(0.2, 0.5, yes=False)  # below limit: no prompt
    assert len(asked) == 1


def test_cli_passes_arguments(monkeypatch, api_key, tmp_path):
    captured = {}

    def fake_generate(prompt, model, **kwargs):
        captured.update(prompt=prompt, model=model, **kwargs)
        return [tmp_path / "x.png"]

    monkeypatch.setattr(gi, "generate_image", fake_generate)
    rc = gi.main(
        ["a prompt", "--model", "m/n", "--out-dir", str(tmp_path), "-n", "2",
         "--reference", "r1.png", "--reference", "https://x/y.png", "--yes", "--max-cost", "1.5"]
    )
    assert rc == 0
    assert captured["prompt"] == "a prompt"
    assert captured["model"] == "m/n"
    assert captured["n"] == 2
    assert captured["input_references"] == ["r1.png", "https://x/y.png"]
    assert captured["yes"] is True
    assert captured["max_cost"] == 1.5


def test_cli_log_tees_output_and_reports_errors(monkeypatch, tmp_path, capsys):
    def failing_generate(prompt, model, **kwargs):
        print("progress line")
        raise RuntimeError("boom")

    monkeypatch.setattr(gi, "generate_image", failing_generate)
    log = tmp_path / "sub" / "run.log"

    rc = gi.main(["p", "--model", "m/n", "--yes", "--log", str(log)])

    assert rc == 1
    out = capsys.readouterr()
    assert "progress line" in out.out
    assert "Error: boom" in out.err
    text = log.read_text(encoding="utf-8")
    assert "'p'" in text and "progress line" in text and "Error: boom" in text
    assert sys.stdout is not None and not isinstance(sys.stdout, gi._Tee)
