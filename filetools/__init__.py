"""General file comparison helpers."""

from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


def compare_file(first: PathLike, second: PathLike) -> bool:
    """Return whether two existing files have the same size."""
    first_path = Path(first)
    second_path = Path(second)
    if not first_path.is_file() or not second_path.is_file():
        return False
    return first_path.stat().st_size == second_path.stat().st_size
