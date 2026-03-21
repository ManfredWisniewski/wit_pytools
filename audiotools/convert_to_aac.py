"""AAC conversion helpers."""

from pathlib import Path
from typing import Optional, Sequence, Union

from . import encode_m4a

PathLike = Union[str, Path]

__all__ = [
    "convert_file_to_aac",
]

def convert_file_to_aac(
    source: PathLike,
    destination: PathLike,
    *,
    bitrate: str = "64k",
    sample_rate: Optional[int] = None,
    channels: Optional[int] = None,
    extra_args: Optional[Sequence[str]] = None,
    overwrite: bool = True,
) -> Path:
    """Encode *source* into AAC/M4A at *destination*."""

    result = encode_m4a(
        input_file=source,
        output_file=destination,
        bitrate=bitrate,
        audio_codec="aac",
        sample_rate=sample_rate,
        channels=channels,
        extra_args=extra_args,
        overwrite=overwrite,
    )

    if result.stat().st_size == 0:
        result.unlink(missing_ok=True)
        raise RuntimeError(f"Encoded file had zero length: {result}")

    return result
