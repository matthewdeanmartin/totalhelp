# PEP: totalhelp — A module for monolithic help across subcommands

## PEP Metadata

* **Title:** totalhelp: Monolithic help output for `argparse` applications (including nested subcommands)
* **Author:** TBD
* **Status:** Draft
* **Type:** Standards Track (Packaging/Library Convention)
* **Created:** 2025-09-28
* **Target Python Version:** 3.8+
* **Requires:** None (optional extra: `superhelp[rich]`)
* **Discussions-To:** TBD

---

## Abstract

This PEP specifies an optional, library-only module **`superhelp`** that augments Python’s `argparse`-based CLIs with *monolithic* help output. It provides:

1. A programmatic API to render help for **all** subcommands (and nested sub-subcommands) in a single document.
2. An opt-in CLI flag (e.g., `--totalhelp` / `--superhelp`) that application authors can expose without subclassing or replacing their existing parser.
3. Multiple output formats: plain text, Markdown, and single-file HTML (with an optional browser opener).
4. An optional integration with `rich-argparse` via an **extras** dependency (`superhelp[rich]`), preserving zero-dependency defaults.

The module is non-invasive (no base classes), opt-in, and compatible with existing `argparse` applications.

## Motivation

`argparse` prints help for the current parser only. Applications with subcommands (and deeper nesting) force users to run `--help` repeatedly for each subcommand. This slows discovery, complicates documentation, and frustrates users. A single, complete help view is frequently requested and often re-implemented ad hoc.

A standard, reusable module helps:

* End users: discover capabilities quickly via one command.
* Authors: generate docs/readmes (Markdown/HTML) directly from the source parser tree.
* Tooling: enable consistent help scraping and indexing.

## Rationale and Goals

* **Drop-in:** Work with any existing `argparse.ArgumentParser` without subclassing or refactoring. Authors opt-in by calling a function and/or adding a flag.
* **Accurate:** Traverse the actual parser/subparser objects rather than heuristically scraping terminal output (though a best-effort external mode is included for third-party commands the author does not control).
* **Format-neutral:** Produce text, Markdown, or HTML from the same traversal.
* **Optional Richness:** If users install `superhelp[rich]`, offer enhanced terminal rendering and better integration with `rich-argparse` formatting.
* **Safety:** Avoid executing arbitrary code paths; when external inspection is used, sandbox shell-outs with timeouts and depth limits.

Non-goals:

* Replacing `argparse` with a new parser.
* Standardizing CLI UX beyond help aggregation.

## Specification

### Terminology

* **Parser tree**: A root `ArgumentParser` plus any nested subparsers reachable via `_SubParsersAction`.
* **Node**: A parser or subparser in the tree.
* **Path**: Command tokens from root to a node (e.g., `git remote add`).

### Public API (module `superhelp`)

The module exports the following functions; all are importable and do **not** require subclassing:

#### 1. `full_help_from_parser(parser: argparse.ArgumentParser, prog: str | None = None, fmt: Literal["text","md","html"] = "text", *, rich: bool | None = None, width: int | None = None) -> str`

Traverses `parser` and all nested subparsers to produce a single document containing each node’s standard help.

* **`prog`**: override program name shown at the root (defaults to `parser.prog`).
* **`fmt`**: output format (`text` | `md` | `html`).
* **`rich`**: if `True`, and `superhelp[rich]` is installed and a TTY is detected, include richer styling for the *root* text rendering (best-effort; Markdown/HTML unaffected). If `None`, auto-detect.
* **`width`**: optional wrapping width for plain text mode; default mirrors `argparse` behavior.

#### 2. `add_totalhelp_flag(parser: argparse.ArgumentParser, *, option_strings: tuple[str, ...] = ("--totalhelp", "--superhelp"), add_format_options: bool = True, add_open_option: bool = True) -> None`

Augments an existing parser by adding a boolean flag (default aliases `--totalhelp` and `--superhelp`). When present in parsed args, calling code can generate and print full help and exit.

* If **`add_format_options`** is true, also adds `--format {text,md,html}`.
* If **`add_open_option`** is true, adds `--open` (HTML mode only) to open a temporary file in a web browser.

#### 3. `print_output(doc: str, *, fmt: Literal["text","md","html"] = "text", open_browser: bool = False) -> None`

Helper to print to stdout (text/Markdown) or write to a temporary `.html` file and optionally open a browser (HTML mode). Returns `None`.

#### 4. `full_help_external(command: list[str], fmt: Literal["text","md","html"] = "text", *, timeout: float = 5.0, max_depth: int = 4, env: dict[str,str] | None = None) -> str`

Best-effort external discovery using `command + ["--help"]` to parse subcommand names out of help text and recurse. Included for users who don’t control the target CLI. Uses timeouts, caps recursion depth, and avoids infinite loops.

> **Note**: Internal traversal (`full_help_from_parser`) is authoritative and preferred when you own the code; external traversal is heuristic.

### Integration Pattern (Application Author)

1. Build your parser as usual.
2. Call `add_totalhelp_flag(parser)` after defining all subparsers.
3. After parsing arguments:

   ```python
   if args.totalhelp:
       doc = superhelp.full_help_from_parser(parser, fmt=args.format)
       superhelp.print_output(doc, fmt=args.format, open_browser=getattr(args, "open", False))
       sys.exit(0)
   ```
4. Ship your CLI unchanged otherwise.

This preserves your existing structure and avoids base classes or custom `ArgumentParser` types.

### Output Formats

* **text**: A linear document containing root help and each subcommand section. Titles are underlined with `=` and each section shows `$ <path> --help` followed by the captured help text.
* **md**: Markdown document with `#`/`##` headings and fenced code blocks of help output.
* **html**: Minimal, self-contained HTML with inline CSS suitable for opening directly or publishing. Created as a temp file via `print_output(..., fmt="html")` with optional browser open.

### Rich Integration (`superhelp[rich]`)

If the extra is installed and the output stream is a TTY, text-mode output may:

* Use `rich` to better wrap and colorize headings.
* Respect `rich-argparse` formatting if the target parser uses it (the module defers to the parser’s own `print_help`).

Markdown/HTML outputs are unaffected by `rich` (they rely on the raw help strings to keep determinism and portability).

### External Mode Behavior

* Calls `<command> --help` to capture top-level help; parses subcommand names from common `argparse` patterns (choice sets `{a,b}` and `Commands:`/`Subcommands:` sections).
* Recurses into `<command> <sub> --help` up to `max_depth`.
* Timeouts per call; merges stdout and stderr; never raises on non-zero exit, but embeds the captured output (annotated if needed).
* Intended for situations where authors can’t call `full_help_from_parser` directly.

### Environment & Configuration

* `SUPPORTS_BROWSER_OPEN`: not required; `print_output(..., open_browser=True)` uses `webbrowser.open()`.
* Locale/encoding follow the current Python process.
* No global state; callers manage their own parser instances.

## Backwards Compatibility

The module is additive and opt-in. It neither replaces nor modifies `argparse` internals. It reads `parser._actions` to discover `_SubParsersAction`, which is a stable de facto interface in practice across Python versions; should this change, the module will adapt in future releases.

## Security Considerations

* **Internal traversal** executes no external processes.
* **External traversal** (if used):

  * Runs child processes with user-provided command lines only.
  * Applies per-invocation timeouts and a recursion depth cap.
  * Does not attempt shell interpretation; uses `subprocess.run(list[str], shell=False)`.
  * Documents that authors should avoid using external mode on untrusted commands.

HTML output is static; there is no embedded script content.

## Internationalization / Accessibility

* Output mirrors the help text produced by the target application; non-ASCII text is preserved.
* HTML output uses semantic headings and sufficient contrast. Authors can post-process or re-style as needed.

## Performance Considerations

* The cost is proportional to the number of parsers in the tree plus the cost of generating each help string.
* For very large trees, authors may provide `width` or omit rich styling for speed.
* External mode may be slower due to subprocess calls; caching could be added later.

## Alternatives Considered

* **Subclassing `ArgumentParser`**: Rejected; invasive and incompatible with many existing apps.
* **Patching `print_help`**: Rejected; brittle and surprising.
* **Only external scraping**: Rejected; inaccurate for non-standard help layouts and loses structure.
* **Do nothing**: Leaves every project to reinvent the wheel.

## Rejected Ideas

* **Implicit global activation** (e.g., via sitecustomize): too surprising and difficult to scope.
* **Auto-install `rich`**: violates zero-dependency goal.
* **Forcing a pager by default**: environment-specific; leave to callers.

## Reference Implementation Sketch

* **Traversal**: walk `parser._actions`; for each `_SubParsersAction`, iterate `choices.items()` mapping names to subparsers; recurse with path accumulation.
* **Capture**: call `parser.print_help(file=io.StringIO())` to get canonical help per node.
* **Rendering**: combine sections with simple templates per format; keep CSS minimal for HTML.
* **Rich**: if available and elected, wrap headings and blocks via `rich.console.Console` and `rich.markdown` for terminal display *only*.
* **External**: detect subcommands via regexes on help text; recurse with safeguards.

## API Examples

### Add a flag to your app

```python
import argparse, sys
import superhelp

def build_parser():
    p = argparse.ArgumentParser(prog="hardcommand")
    subs = p.add_subparsers(dest="cmd")
    a = subs.add_parser("alpha")
    b = subs.add_parser("beta")
    superhelp.add_totalhelp_flag(p)  # adds --totalhelp/--superhelp, --format, --open
    return p

p = build_parser()
args = p.parse_args()
if getattr(args, "totalhelp", False):
    doc = superhelp.full_help_from_parser(p, fmt=getattr(args, "format", "text"))
    superhelp.print_output(doc, fmt=getattr(args, "format", "text"), open_browser=getattr(args, "open", False))
    sys.exit(0)
```

### Generate docs for README

```python
import superhelp
from myapp import build_parser

doc = superhelp.full_help_from_parser(build_parser(), prog="hardcommand", fmt="md")
open("HARDHELP.md", "w", encoding="utf-8").write(doc)
```

### Inspect a third-party tool (heuristic)

```python
import superhelp
print(superhelp.full_help_external(["pip"], fmt="text"))
```

## Packaging and Distribution

* Package name: `superhelp`
* Extras: `superhelp[rich]` installs `rich` and `rich-argparse`.
* Optional console script (not required by this PEP): `superhelp` that invokes `full_help_external(sys.argv[1:] or ["python"], ...)`.

## Versioning and Evolution

* SemVer for the library API.
* Future additions may include: custom render hooks, JSON AST output of the parser tree, pluggable subcommand detectors for external mode, and pager integration.

## Testing Strategy

* Unit tests for:

  * Single-level and nested subparsers traversal.
  * Alias subcommands and hidden subcommands (where present).
  * Deterministic text/markdown/html generation.
  * Rich optional path (skipped if `rich` not installed).
  * External mode: mock subprocess with sample help outputs.
* Property tests for idempotent formatting across widths.

## Open Issues

* How to represent *very* large help trees in terminal contexts (auto-pager?).
* Standardized discovery for non-argparse CLIs (out of scope for now).
* Detecting and honoring parser-level localization settings.

## References

* Python `argparse` documentation
* `rich` and `rich-argparse` projects
* Common recipes for walking `argparse` subparsers (community prior art)

---

*End of PEP draft.*
