# totalhelp

`totalhelp` gathers the help for an `argparse` command and its nested subcommands into one document. It can render plain text, Markdown, or a self-contained HTML file.

There are two ways to use it:

- If you own the parser, [integrate the library](integration.md) so the document is generated from the actual parser tree.
- If you do not own the CLI, [inspect its external `--help` output](external.md). This mode discovers subcommands on a best-effort basis.

Install with `pip install totalhelp`. The package requires Python 3.11 or newer.

The [draft PEP](PEP.md) describes the proposed convention and its motivation. It is a proposal, not a Python standard.
