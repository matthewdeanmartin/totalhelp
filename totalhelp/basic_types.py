from __future__ import annotations

import argparse
from typing import Literal, NamedTuple


class _ParserNode(NamedTuple):
    """Internal representation of a parser in the tree."""

    path: tuple[str, ...]
    parser: argparse.ArgumentParser


# Type definitions
FormatType = Literal["text", "md", "html"]
