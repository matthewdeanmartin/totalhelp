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
