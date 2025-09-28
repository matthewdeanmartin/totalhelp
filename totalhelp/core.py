from __future__ import annotations

import argparse
import io
import os
import re
import subprocess  # nosec
import sys
import tempfile
import textwrap
import webbrowser
from typing import (
    IO,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Mapping,
    NamedTuple,
    Optional,
    Tuple,
)

# Try to import rich for optional enhancements.
try:
    import rich
    import rich.console
    import rich.markdown

    # from rich_argparse import RichHelpFormatter

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


__version__ = "0.1.0"

# Type definitions
FormatType = Literal["text", "md", "html"]


class _ParserNode(NamedTuple):
    """Internal representation of a parser in the tree."""

    path: Tuple[str, ...]
    parser: argparse.ArgumentParser


def _get_help_string(
    parser: argparse.ArgumentParser, file: Optional[IO[str]] = None
) -> str:
    """Capture help output from a parser instance."""
    io.StringIO()
    # Note: argparse.ArgumentParser.print_help writes directly to a file-like object.
    # The `format_help` method returns the string directly. We prefer it.
    return parser.format_help()


def _walk_parser_tree(
    root_parser: argparse.ArgumentParser, prog: Optional[str] = None
) -> Iterable[_ParserNode]:
    """
    Recursively walk the parser and its subparsers.

    Yields a `_ParserNode` for each parser found in the tree.
    """
    q: List[_ParserNode] = [_ParserNode(path=(), parser=root_parser)]
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


def _render_text(nodes: List[_ParserNode], prog: str) -> str:
    """Render the collected help nodes as plain text."""
    output: List[str] = []
    for i, node in enumerate(nodes):
        path_str = " ".join((prog,) + node.path)
        title = f"$ {path_str} --help"
        output.append(title)
        output.append("=" * len(title))
        output.append(_get_help_string(node.parser).strip())
        if i < len(nodes) - 1:
            output.append("\n" + "-" * 78 + "\n")
    return "\n".join(output)


def _render_md(nodes: List[_ParserNode], prog: str) -> str:
    """Render the collected help nodes as Markdown."""
    output: List[str] = [f"# Help for `{prog}`\n"]
    for node in nodes:
        path_str = " ".join((prog,) + node.path)
        level = len(node.path) + 2  # ## for top-level, ### for next, etc.
        heading = "#" * level
        output.append(f"{heading} `{path_str}`\n")
        output.append("```text")
        output.append(_get_help_string(node.parser).strip())
        output.append("```\n")
    return "\n".join(output)


def _render_html(nodes: List[_ParserNode], prog: str) -> str:
    """Render the collected help nodes as a self-contained HTML file."""
    # Minimal, clean CSS for readability.
    css = textwrap.dedent(
        """
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; margin: 0; background-color: #f8f9fa; color: #212529; }
        .container { max-width: 800px; margin: 2rem auto; padding: 2rem; background-color: #fff; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); }
        h1, h2, h3 { margin-top: 2rem; margin-bottom: 1rem; color: #343a40; border-bottom: 1px solid #dee2e6; padding-bottom: 0.5rem; }
        h1 { font-size: 2.5rem; }
        h2 { font-size: 2rem; }
        h3 { font-size: 1.75rem; }
        pre { background-color: #e9ecef; padding: 1rem; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace; }
        code { font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace; font-size: 0.9em; color: #d6336c; }
        .command { font-weight: bold; }
        nav { padding: 1rem; background: #343a40; color: white; margin-bottom: 2rem; border-radius: 8px 8px 0 0; }
        nav h1 { border: none; margin: 0; }
        nav ul { list-style: none; padding: 0; margin: 0; }
        nav li { display: inline-block; margin-right: 1rem; }
        nav a { color: #adb5bd; text-decoration: none; }
        nav a:hover { color: white; }
    """
    )

    body_parts = []
    toc_parts = ["<ul>"]

    for i, node in enumerate(nodes):
        path_str = " ".join((prog,) + node.path)
        anchor = "cmd-" + "-".join(node.path) if node.path else "cmd-root"

        level = len(node.path)
        toc_parts.append(
            f'<li style="margin-left: {level * 20}px;"><a href="#{anchor}">{path_str or prog}</a></li>'
        )

        heading_level = min(level + 2, 6)
        body_parts.append(
            f'<h{heading_level} id="{anchor}" class="command"><code>{path_str} --help</code></h{heading_level}>'
        )
        help_text = _get_help_string(node.parser).strip()
        # Basic escaping for HTML
        help_text = (
            help_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        body_parts.append(f"<pre>{help_text}</pre>")

    toc_parts.append("</ul>")
    toc = "".join(toc_parts)
    body = "".join(body_parts)

    return textwrap.dedent(
        f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Superhelp for {prog}</title>
            <style>{css}</style>
        </head>
        <body>
            <div class="container">
                <nav>
                    <h1>Help for <code>{prog}</code></h1>
                    <h2>Table of Contents</h2>
                    {toc}
                </nav>
                <main>{body}</main>
            </div>
        </body>
        </html>
    """
    ).strip()


def full_help_from_parser(
    parser: argparse.ArgumentParser,
    prog: Optional[str] = None,
    fmt: FormatType = "text",
    *,
    use_rich: Optional[bool] = None,
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


def add_totalhelp_flag(
    parser: argparse.ArgumentParser,
    *,
    option_strings: Tuple[str, ...] = ("--totalhelp", "--superhelp"),
    add_format_options: bool = True,
    add_open_option: bool = True,
) -> None:
    """
    Augments an existing parser with a `--totalhelp` flag and related options.

    This should be called after all subparsers have been added.

    Args:
        parser: The `ArgumentParser` instance to modify.
        option_strings: The flag(s) to trigger superhelp (e.g., `("--totalhelp",)`).
        add_format_options: If True, adds a `--format` argument.
        add_open_option: If True, adds an `--open` argument for HTML mode.
    """
    # Use a group to keep the help output clean.
    group = parser.add_argument_group("SuperHelp Options")

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


def _find_subcommands_from_help(text: str) -> List[str]:
    """Heuristically parse subcommands from a command's help text."""
    # This function uses two patterns. The second is more reliable.

    # Pattern 1: Search for {cmd1,cmd2} in the usage block. This is common for
    # simple CLIs. We must be careful not to match choices for optional args.
    # We find the whole usage block (which can be multi-line), normalize it,
    # strip optional groups ([...]), and then search for the command group ({...}).
    usage_block_match = re.search(
        r"^usage:.*?(?=\n\n|\Z)", text, re.MULTILINE | re.IGNORECASE | re.DOTALL
    )
    if usage_block_match:
        usage_block = usage_block_match.group(0)
        # Normalize to a single line
        usage_line = " ".join(usage_block.split())
        # Greedily remove all optional argument blocks.
        usage_without_optionals = re.sub(r"\[.*?\]", "", usage_line)
        choices_match = re.search(r"\{([\w,-]+)\}", usage_without_optionals)
        if choices_match:
            # If we find it this way, it's very likely to be the list of subcommands.
            return [cmd.strip() for cmd in choices_match.group(1).split(",")]

    # Pattern 2: A section like "Commands:", "subcommands:", etc.
    # This is often more reliable than parsing the usage line.
    commands = []
    in_command_section = False
    # Added "positional arguments" to the list of possible headers.
    header_pattern = re.compile(
        r"^(Commands|Subcommands|Available commands|positional arguments):",
        re.IGNORECASE | re.MULTILINE,
    )

    if header_pattern.search(text):
        for line in text.splitlines():
            if header_pattern.match(line):
                in_command_section = True
                continue

            if in_command_section:
                # Stop if we hit a non-indented line or another section
                if not line.strip() or (
                    line.strip() and not line.startswith((" ", "\t"))
                ):
                    in_command_section = False
                    continue

                # Skip the summary line like {cmd1, cmd2} which is sometimes duplicated here
                if line.strip().startswith("{"):
                    continue

                # A command is usually the first word on an indented line.
                match = re.match(r"^\s+([\w-]+)", line)
                if match:
                    commands.append(match.group(1))
    return commands


def full_help_external(
    command: List[str],
    fmt: FormatType = "text",
    *,
    timeout: float = 5.0,
    max_depth: int = 4,
    env: Optional[Dict[str, str]] = None,
) -> str:
    """
    Best-effort external discovery of a command's help structure.

    This function recursively calls `<command> --help` to discover and
    document subcommands. It is intended for use with CLIs where direct
    parser access is not available.

    Args:
        command: The base command as a list of strings (e.g., `["pip"]`).
        fmt: The output format ("text", "md", or "html").
        timeout: Timeout in seconds for each subprocess call.
        max_depth: Maximum recursion depth for subcommand discovery.
        env: Optional environment variables for the subprocess.

    Returns:
        A string containing the discovered help document.
    """

    # We can't build a real parser tree, so we'll simulate _ParserNode
    # by creating dummy parsers that only have a pre-formatted help string.
    class _HelpOnlyParser(argparse.ArgumentParser):
        def __init__(self, help_text: str, prog: str):
            super().__init__(prog=prog, add_help=False)
            self._help_text = help_text

        def format_help(self) -> str:
            return self._help_text

    nodes: List[_ParserNode] = []
    q: List[Tuple[Tuple[str, ...], List[str]]] = [((), command)]  # (path, full_command)
    visited_paths = set()
    prog = command[0]

    while q:
        path, cmd_list = q.pop(0)

        if len(path) > max_depth:
            continue

        path_tuple = tuple(path)
        if path_tuple in visited_paths:
            continue
        visited_paths.add(path_tuple)

        current_prog = " ".join(cmd_list)
        try:
            result = subprocess.run(  # nosec
                cmd_list + ["--help"],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            # Combine stdout and stderr as some tools print help to stderr
            help_text = result.stdout + result.stderr
            if result.returncode != 0:
                help_text = (
                    f"[Warning: command exited with code {result.returncode}]\n\n"
                    + help_text
                )

        except FileNotFoundError:
            help_text = f"[Error: command not found: '{current_prog}']"
        except subprocess.TimeoutExpired:
            help_text = f"[Error: command timed out after {timeout} seconds]"
        except Exception as e:
            help_text = f"[Error: an unexpected error occurred: {e}]"

        parser = _HelpOnlyParser(help_text.strip(), prog=current_prog)
        nodes.append(_ParserNode(path=path_tuple, parser=parser))

        # Discover subcommands and add them to the queue
        subcommands = _find_subcommands_from_help(help_text)
        for sub_cmd in subcommands:
            new_path = path_tuple + (sub_cmd,)
            if new_path not in visited_paths:
                q.append((new_path, command + list(new_path)))

    # Now render the collected nodes
    renderers: Mapping[FormatType, Callable] = {
        "text": _render_text,
        "md": _render_md,
        "html": _render_html,
    }
    return renderers[fmt](nodes, prog)
