"""Library usage"""

from __future__ import annotations

import argparse
import io
import sys
from typing import Callable, Iterable, Mapping, Optional

from totalhelp.basic_types import FormatType, _ParserNode
from totalhelp.ui import _render_html, _render_md, _render_text

# Try to import rich for optional enhancements.
try:
    import rich
    import rich.console
    import rich.markdown

    # from rich_argparse import RichHelpFormatter

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


def add_totalhelp_flag(
    parser: argparse.ArgumentParser,
    *,
    option_strings: tuple[str, ...] = ("--totalhelp", "--totalhelp"),
    add_format_options: bool = True,
    add_open_option: bool = True,
) -> None:
    """
    Augments an existing parser with a `--totalhelp` flag and related options.

    This should be called after all subparsers have been added.

    Args:
        parser: The `ArgumentParser` instance to modify.
        option_strings: The flag(s) to trigger totalhelp (e.g., `("--totalhelp",)`).
        add_format_options: If True, adds a `--format` argument.
        add_open_option: If True, adds an `--open` argument for HTML mode.
    """
    # Use a group to keep the help output clean.
    group = parser.add_argument_group("totalhelp Options")

    group.add_argument(
        *option_strings,
        action="store_true",
        dest="totalhelp",
        help="Show a monolithic help document for all commands and exit.",
    )

    if add_format_options:
        group.add_argument(
            "--format",
            choices=["text", "md", "html"],
            default="text",
            help="The output format for --totalhelp.",
        )

    if add_open_option:
        group.add_argument(
            "--open",
            action="store_true",
            help="Open the generated help in a web browser (HTML format only).",
        )


def _walk_parser_tree(
    root_parser: argparse.ArgumentParser, prog: Optional[str] = None
) -> Iterable[_ParserNode]:
    """
    Recursively walk the parser and its subparsers.

    Yields a `_ParserNode` for each parser found in the tree.
    """
    q: list[_ParserNode] = [_ParserNode(path=(), parser=root_parser)]
    visited_parsers = {id(root_parser)}

    # Override the program name at the root if specified.
    # This is tricky because `prog` is used to build help messages.
    # We temporarily patch it.
    original_prog = root_parser.prog
    if prog:
        root_parser.prog = prog

    try:
        while q:
            node = q.pop(0)
            yield node

            for action in node.parser._actions:
                # _SubParsersAction holds the mapping from command name to subparser
                if isinstance(action, argparse._SubParsersAction):
                    for name, subparser in action.choices.items():
                        if id(subparser) not in visited_parsers:
                            new_path = node.path + (name,)
                            q.append(_ParserNode(path=new_path, parser=subparser))
                            visited_parsers.add(id(subparser))
    finally:
        # Restore the original program name to avoid side effects.
        root_parser.prog = original_prog


def full_help_from_parser(
    parser: argparse.ArgumentParser,
    prog: Optional[str] = None,
    fmt: FormatType = "text",
    *,
    use_rich: Optional[bool] = True,
    width: Optional[int] = None,
) -> str:
    """
    Traverses a parser and all nested subparsers to produce a single help document.

    Args:
        parser: The root `ArgumentParser` instance.
        prog: Override the program name shown at the root (defaults to `parser.prog`).
        fmt: The output format ("text", "md", or "html").
        use_rich: If True, and `rich` is installed, use it for terminal output.
              If None, auto-detects based on TTY and `rich` availability.
        width: Optional wrapping width for plain text mode. Not yet implemented.

    Returns:
        A string containing the complete help document.
    """
    if use_rich is None:
        use_rich = _RICH_AVAILABLE and sys.stdout.isatty()

    program_name = prog or parser.prog or ""
    nodes = list(_walk_parser_tree(parser, prog=program_name))

    renderers: Mapping[FormatType, Callable] = {
        "text": _render_text,
        "md": _render_md,
        "html": _render_html,
    }

    if fmt not in renderers:
        raise ValueError(
            f"Invalid format '{fmt}'. Must be one of {list(renderers.keys())}"
        )

    doc = renderers[fmt](nodes, program_name)

    # If rich is requested for text format, re-render the doc through rich.
    if fmt == "text" and use_rich and _RICH_AVAILABLE:
        # Use rich to print, which gives us color and better wrapping.
        # This is a bit of a trick: we render to Markdown internally and then
        # have rich render that Markdown to the console. This gives nice headings.
        md_doc = _render_md(nodes, program_name)
        console = rich.console.Console()
        io.StringIO()
        console.print(
            rich.markdown.Markdown(md_doc),
            # file=s
        )
        # return s.getvalue()

    return doc
