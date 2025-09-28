"""
totalhelp: Monolithic help output for argparse applications.

This module provides a programmatic API and opt-in CLI flags to render
help for all subcommands of an argparse-based application in a single,
cohesive document.
"""

from __future__ import annotations

import argparse
import sys

from totalhelp.core import __version__, full_help_external, print_output


def main() -> None:
    """Console script entry point for superhelp."""
    # This parser is for the `superhelp` command itself.
    parser = argparse.ArgumentParser(
        prog="superhelp",
        description="Generate monolithic help for an external command by recursively calling its --help flag.",
        epilog="If no command is provided, it will attempt to inspect 'python'.",
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

    target_command = args.command or ["python"]

    try:
        doc = full_help_external(target_command, fmt=args.format)
        print_output(doc, fmt=args.format, open_browser=args.open)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
