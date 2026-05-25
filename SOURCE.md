## Tree for totalhelp
```
├── basic_types.py
├── external.py
├── library.py
├── parser.py
├── py.typed
├── ui.py
├── __about__.py
└── __main__.py
```

## File: basic_types.py
```python
from __future__ import annotations

import argparse
from typing import Literal, NamedTuple, Tuple


class _ParserNode(NamedTuple):
    """Internal representation of a parser in the tree."""

    path: Tuple[str, ...]
    parser: argparse.ArgumentParser


# Type definitions
FormatType = Literal["text", "md", "html"]
```
## File: external.py
```python
from __future__ import annotations

import argparse
import subprocess  # nosec
from typing import Callable, Dict, List, Mapping, Optional, Tuple

from totalhelp.basic_types import FormatType, _ParserNode
from totalhelp.parser import find_subcommands
from totalhelp.ui import _render_html, _render_md, _render_text


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
        subcommands = find_subcommands(help_text, root_command=cmd_list[-1])
        for sub_cmd in subcommands.subcommands:
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
```
## File: library.py
```python
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
```
## File: parser.py
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

# --- Add these helpers ---

_ALLOWED_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
)
_FORBIDDEN_TRAIL = set(").,:;!?]}'\"")  # if token ends with one of these -> reject


def _looks_like_shell_echo(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("$ ") or s.startswith("# ")  # shell prompt or comment echo


def _looks_like_report_or_error(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("[")  # e.g. "[Error: ...]"


def _token_is_reasonable_command(tok: str) -> bool:
    if not tok:
        return False
    if _token_is_optionish(tok):
        return False
    # No spaces or quotes
    if any(ch.isspace() for ch in tok):
        return False
    if any(ch in "\"'`()" for ch in tok):
        return False
    # No forbidden trailing punctuation
    if tok[-1] in _FORBIDDEN_TRAIL:
        return False
    # Must start alnum, contain only allowed chars
    if not tok[0].isalnum():
        return False
    if any(ch not in _ALLOWED_CHARS for ch in tok):
        return False
    return True


def _deflist_items(lines: list[str]) -> list[tuple[int, str]]:
    """
    Return [(indent, token)] for lines that look like definition-list items
    (indented; token; >=2 spaces; description). Does NOT validate token beyond shape.
    """
    items: list[tuple[int, str]] = []
    for ln in lines:
        if (
            _is_blank(ln)
            or _looks_like_shell_echo(ln)
            or _looks_like_report_or_error(ln)
        ):
            continue
        indent = _leading_spaces(ln)
        if indent == 0:
            continue
        # parse first word
        i = indent
        n = len(ln)
        j = i
        while j < n and not ln[j].isspace():
            j += 1
        token = ln[i:j]
        # require a visual gap of >= 2 spaces afterwards and some description
        k = j
        gap = 0
        while k < n and ln[k] == " ":
            gap += 1
            k += 1
        if token and gap >= 2 and k < n and not ln[k].isspace():
            items.append((indent, token))
    return items


def _mode_indent(items: list[tuple[int, str]]) -> int | None:
    """
    Given def-list shaped items [(indent, token)], return the most common indent.
    This is the baseline indent for commands in that section.
    """
    if not items:
        return None
    counts: dict[int, int] = {}
    for ind, _ in items:
        counts[ind] = counts.get(ind, 0) + 1
    # choose smallest indent among the highest counts (favors the leftmost column)
    max_count = max(counts.values())
    candidates = [ind for ind, c in counts.items() if c == max_count]
    return min(candidates)


# def extract_from_named_sections_with_baseline(sections: list[Section]) -> list[str]:
#     """
#     Strategy B’ (replacement/upgrade): for sections whose titles imply commands,
#     compute baseline indent and only accept tokens exactly at that indent + pass strict token check.
#     """
#     wanted = {"subcommands", "commands", "available commands", "positional arguments"}
#     out: list[str] = []
#     for sec in sections:
#         if sec.title.strip().lower() not in wanted:
#             continue
#         items = _deflist_items(sec.lines)
#         base = _mode_indent(items)
#         if base is None:
#             continue
#         for ind, tok in items:
#             if ind == base and _token_is_reasonable_command(tok) and tok not in out:
#                 out.append(tok)
#     # also, very carefully consider brace choices inside this section,
#     # but run through the strict token validator
#     for sec in sections:
#         if sec.title.strip().lower() not in wanted:
#             continue
#         collapsed = " ".join(p.strip() for p in sec.lines if p.strip())
#         for choice in _brace_choices(_strip_square_groups(collapsed)):
#             if _token_is_reasonable_command(choice) and choice not in out:
#                 out.append(choice)
#     return out


def extract_from_named_sections_with_baseline(sections: list[Section]) -> list[str]:
    """
    Accept commands from 'Subcommands'/'Commands' unconditionally (with indent baseline),
    but only accept from 'positional arguments' if the section contains a {a,b,c} list.
    """
    wanted_unconditional = {"subcommands", "commands", "available commands"}
    wanted_positional = {"positional arguments"}

    out: list[str] = []

    def parse_section(sec: Section) -> list[str]:
        items = _deflist_items(sec.lines)
        base = _mode_indent(items)
        if base is None:
            return []
        toks: list[str] = []
        for ind, tok in items:
            if ind == base and _token_is_reasonable_command(tok):
                toks.append(tok)
        return toks

    for sec in sections:
        title = sec.title.strip().lower()

        if title in wanted_unconditional:
            for tok in parse_section(sec):
                if tok not in out:
                    out.append(tok)
            # also accept brace choices here
            collapsed = " ".join(p.strip() for p in sec.lines if p.strip())
            for choice in _brace_choices(_strip_square_groups(collapsed)):
                if _token_is_reasonable_command(choice) and choice not in out:
                    out.append(choice)

        elif title in wanted_positional:
            collapsed = " ".join(p.strip() for p in sec.lines if p.strip())
            choices = _brace_choices(_strip_square_groups(collapsed))
            if choices:
                # Only in the brace-list case do we treat them as subcommands
                for choice in choices:
                    if _token_is_reasonable_command(choice) and choice not in out:
                        out.append(choice)
            # Otherwise: positional params are NOT subcommands → ignore definition-list items here.

    return out


# ---------------------------
# Small utilities (no regex)
# ---------------------------


def _lines(text: str) -> List[str]:
    """Normalize newlines and return raw lines (keep indentation)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _rstrip_lines(lines: Iterable[str]) -> List[str]:
    return [ln.rstrip("\n") for ln in lines]


def _leading_spaces(s: str) -> int:
    i = 0
    for ch in s:
        if ch == " ":
            i += 1
        elif ch == "\t":
            # Treat tab as 4 spaces (arbitrary but stable)
            i += 4
        else:
            break
    return i


def _is_heading(line: str) -> bool:
    """
    A simple, robust 'heading' heuristic:
    - No leading indentation
    - Ends with ':'
    - Not starting with 'usage:' (we treat usage specially)
    """
    s = line.strip()
    if not s.endswith(":"):
        return False
    if line[:1].strip():  # has leading space? (no)
        return False
    if s.lower().startswith("usage:"):
        return False
    return True


def _starts_with_usage(line: str) -> bool:
    return line.lstrip().lower().startswith("usage:")


def _is_blank(line: str) -> bool:
    return not line.strip()


def _token_is_optionish(tok: str) -> bool:
    """Exclude flags / options and placeholders."""
    if not tok:
        return True
    if tok.startswith("-"):  # -h, --help
        return True
    # Common placeholders or meta names that aren't subcommands:
    meta = {"command", "<command>", "subcommand", "<subcommand>", "module", "<module>"}
    return tok.lower() in meta


def _first_word_if_defitem(line: str) -> Optional[str]:
    """
    Return the 'term' of a definition-list style item:
       "  token    description..."
    We require at least two spaces (or a tab expanded above) between token and description.
    """
    if not line or line.strip() == "":
        return None
    if _leading_spaces(line) == 0:
        return None

    # Split by whitespace, but we need to ensure there's an actual "gap" after the token.
    # We'll scan for first run of non-space chars, then check for >=2 spaces next.
    i = _leading_spaces(line)
    n = len(line)

    # read token
    j = i
    while j < n and not line[j].isspace():
        j += 1
    token = line[i:j]

    # now count spaces after token
    k = j
    space_count = 0
    while k < n and line[k] == " ":
        space_count += 1
        k += 1

    # Require at least two spaces as a visual column separator (very common in help)
    if token and space_count >= 2 and not _token_is_optionish(token):
        return token
    return None


def _strip_square_groups(s: str) -> str:
    """
    Remove [...] groups from a string (non-nested is fine; nested behaves reasonably).
    Useful before scanning for {a,b,c}.
    """
    out = []
    depth = 0
    for ch in s:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def _brace_choices(s: str) -> List[str]:
    """
    Extract a single {a,b,c} group (first one) and split on commas (ignores spaces).
    """
    start = s.find("{")
    if start == -1:
        return []
    depth = 0
    buf = []
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "{":
            depth += 1
            if depth == 1:
                continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                break
        if depth >= 1:
            buf.append(ch)
    # we only handle a single group; that's enough for typical usage lines
    raw = "".join(buf)
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p and not _token_is_optionish(p)]


# ---------------------------
# Sectionizer
# ---------------------------


@dataclass
class Section:
    title: str
    lines: List[str] = field(default_factory=list)


def _sectionize(text: str) -> Tuple[Optional[List[str]], List[Section]]:
    """
    Split help text into:
      - a 'usage block' (list of lines) if present
      - a list of sections detected by headings (e.g. 'Subcommands:', 'Options:', etc.)
    A section runs until the next heading or EOF.
    """
    lines = _lines(text)
    lines = _rstrip_lines(lines)

    usage_block: Optional[List[str]] = None
    sections: List[Section] = []

    i = 0
    # 1) usage block: contiguous lines starting with 'usage:' and its wrapped lines
    while i < len(lines):
        if _starts_with_usage(lines[i]):
            buf = [lines[i]]
            i += 1
            # collect wrapped lines until blank-blank or a clear section heading
            while i < len(lines):
                ln = lines[i]
                if _is_blank(ln):
                    # keep a single blank in usage, but stop if double-blank
                    buf.append(ln)
                    # check ahead
                    if i + 1 < len(lines) and _is_blank(lines[i + 1]):
                        break
                    i += 1
                    continue
                if _is_heading(ln):
                    break
                # usage often wraps with leading spaces
                if _leading_spaces(ln) > 0:
                    buf.append(ln)
                    i += 1
                    continue
                # non-indented, non-heading, non-blank likely ends usage
                break
            usage_block = buf
            # do NOT return; more content follows; fall through for sections
            break
        i += 1

    # 2) sections by headings
    j = 0
    while j < len(lines):
        if _is_heading(lines[j]):
            title = lines[j].strip()[:-1]  # strip trailing ':'
            k = j + 1
            body: List[str] = []
            while k < len(lines) and not _is_heading(lines[k]):
                body.append(lines[k])
                k += 1
            sections.append(Section(title=title, lines=body))
            j = k
        else:
            j += 1

    return usage_block, sections


# ---------------------------
# Extractors (each testable)
# ---------------------------


def extract_from_usage(usage_lines: Optional[List[str]]) -> List[str]:
    """
    Strategy A: Parse {a,b,c} from usage.
    """
    if not usage_lines:
        return []
    # collapse to one line for ease, but keep content
    single = " ".join(ln.strip() for ln in usage_lines if ln.strip())
    # drop [...] groups to avoid optional-choices noise
    single = _strip_square_groups(single)
    return _brace_choices(single)


def extract_from_named_sections(sections: List[Section]) -> List[str]:
    """
    Strategy B: From sections named like 'Subcommands', 'Commands', 'Positional arguments'
    we parse definition-list styled items. We don't trust words inside braces here.
    """
    wanted = {"subcommands", "commands", "available commands", "positional arguments"}
    out: List[str] = []
    for sec in sections:
        if sec.title.strip().lower() in wanted:
            for ln in sec.lines:
                tok = _first_word_if_defitem(ln)
                if tok and tok not in out:
                    out.append(tok)
            # also try light-weight scan for brace choices inside the section
            collapsed = " ".join(p.strip() for p in sec.lines if p.strip())
            for choice in _brace_choices(_strip_square_groups(collapsed)):
                if choice not in out:
                    out.append(choice)
    return out


def extract_from_all_definition_lists(text: str) -> List[str]:
    """
    Strategy C: Scan *all* lines and collect tokens that look like left-column 'terms'
    in definition lists. This often finds commands even when sections are oddly named.
    """
    out: List[str] = []
    for ln in _lines(text):
        tok = _first_word_if_defitem(ln)
        if tok and tok not in out:
            out.append(tok)
    return out


def extract_frequency_candidates(text: str) -> List[str]:
    """
    Strategy D (weak but helpful): collect first words of many indented lines and
    score by frequency, filtering optionish. Useful for weird/non-argparse helps.
    """
    counts: Dict[str, int] = {}
    for ln in _lines(text):
        if _leading_spaces(ln) == 0:
            continue
        # first word
        s = ln.lstrip()
        if not s:
            continue
        tok = s.split()[0]
        if _token_is_optionish(tok):
            continue
        counts[tok] = counts.get(tok, 0) + 1
    # rank by count desc, then alpha
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked]


# ---------------------------
# Orchestrator
# ---------------------------


@dataclass
class ParseResult:
    subcommands: List[str]
    evidence: Dict[str, List[str]] = field(default_factory=dict)


def find_subcommands(help_text: str, root_command: Optional[str] = None) -> ParseResult:
    """
    Try multiple strategies, score + merge, then filter.
    """
    usage_block, sections = _sectionize(help_text)

    a = extract_from_usage(usage_block)  # Strategy A
    b = extract_from_named_sections(sections)  # Strategy B
    c = extract_from_all_definition_lists(help_text)  # Strategy C

    # Score/merge: A and B are higher-confidence than C, which is higher than D.
    weights = {id_: w for id_, w in zip("ABC", (3, 3, 2))}
    score: Dict[str, int] = {}
    order: List[str] = []  # preserve first-seen ordering across strategies

    def add_all(lst: List[str], w: int):
        for tok in lst:
            if tok not in order:
                order.append(tok)
            score[tok] = score.get(tok, 0) + w

    add_all(a, weights["A"])
    add_all(b, weights["B"])
    add_all(c, weights["C"])

    # Filter: remove very-likely-non-command tokens that slipped in
    deny = {"examples", "options", "usage", "help", "version", "get", "from"}
    filtered = []
    for t in order:
        if t.lower() in deny:
            continue
        if _token_is_optionish(t):
            continue
        if not _token_is_reasonable_command(t):
            continue
        if root_command and t == root_command:
            # e.g. 'pyroma' incorrectly detected as a subcommand of 'pyroma'
            continue
        filtered.append(t)
    # Final ordering by score (desc) while preserving tie-first-seen
    filtered.sort(key=lambda t: (-score[t], order.index(t)))

    return ParseResult(
        subcommands=filtered,
        evidence={
            "usage_choices": a,
            "named_sections": b,
            "deflists": c,
        },
    )
```
## File: ui.py
```python
from __future__ import annotations

import argparse
import io
import textwrap
from typing import IO, List, Optional

from totalhelp.basic_types import _ParserNode


def _get_help_string(
    parser: argparse.ArgumentParser, file: Optional[IO[str]] = None
) -> str:
    """Capture help output from a parser instance."""
    io.StringIO()
    # Note: argparse.ArgumentParser.print_help writes directly to a file-like object.
    # The `format_help` method returns the string directly. We prefer it.
    return parser.format_help()


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
            <title>totalhelp for {prog}</title>
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
```
## File: __about__.py
```python
"""Metadata for totalhelp."""

__all__ = [
    "__title__",
    "__version__",
    "__description__",
    "__readme__",
    "__requires_python__",
    "__status__",
]

__title__ = "totalhelp"
__version__ = "0.1.1"
__description__ = (
    "Print help for all commands and subcommands for argparse applications"
)
__readme__ = "README.md"
__requires_python__ = ">=3.8"
__status__ = "1 - Planning"
```
## File: __main__.py
```python
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
```
