"""
totalhelp: Monolithic help output for argparse applications.

This module provides a programmatic API and opt-in CLI flags to render
help for all subcommands of an argparse-based application in a single,
cohesive document.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import webbrowser

from rich_argparse import RichHelpFormatter

from totalhelp.__about__ import __version__
from totalhelp.basic_types import FormatType
from totalhelp.external import full_help_external


def print_output(
    doc: str,
    *,
    fmt: FormatType = "text",
    open_browser: bool = False,
) -> None:
    """
    Prints the help document or saves to a temp file and opens it.

    Args:
        doc: The help document string.
        fmt: The format of the document.
        open_browser: If True and format is "html", open in a browser.
    """
    if fmt == "html":
        try:
            # Use delete=False to keep the file around after the handle is closed on Windows.
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".html", encoding="utf-8"
            ) as f:
                f.write(doc)
                filepath = f.name

            print(f"HTML help written to: file://{filepath}", file=sys.stderr)

            if open_browser:
                try:
                    webbrowser.open(f"file://{os.path.realpath(filepath)}")
                except webbrowser.Error as e:
                    print(f"Warning: Could not open web browser: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing temporary HTML file: {e}", file=sys.stderr)
            # Fallback to printing to stdout
            print(doc)
    else:
        # For text and markdown, just print to stdout.
        # Rich handling is done in `full_help_from_parser`.
        print(doc)


def main() -> None:
    """Console script entry point for totalhelp."""
    # This parser is for the `totalhelp` command itself.
    parser = argparse.ArgumentParser(
        prog="totalhelp",
        description="Generate monolithic help for an external command by recursively calling its --help flag.",
        # epilog="If no command is provided, it will attempt to inspect 'python'.",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="The command and its arguments to inspect (e.g., pip install).",
    )
    # Re-using the same options for consistency.
    parser.add_argument(
        "--format",
        choices=["text", "md", "html"],
        default="text",
        help="The output format for the generated help document.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated help in a web browser (HTML format only).",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()

    target_command = args.command or []

    if not target_command:
        print("No command provided")
        return

    try:
        doc = full_help_external(target_command, fmt=args.format)
        print_output(doc, fmt=args.format, open_browser=args.open)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
