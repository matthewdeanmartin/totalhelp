# Integrate with argparse

Build your parser as usual, then add `--totalhelp` after all subparsers have been created. Handle the flag after parsing:

```python
import argparse
import totalhelp

parser = argparse.ArgumentParser(prog="books")
commands = parser.add_subparsers(dest="command")
add = commands.add_parser("add", help="Add a book")
add.add_argument("title")
commands.add_parser("list", help="List books")

totalhelp.add_totalhelp_flag(parser)
args = parser.parse_args()

if args.totalhelp:
    document = totalhelp.full_help_from_parser(parser, fmt=args.format)
    totalhelp.print_output(document, fmt=args.format, open_browser=args.open)
    parser.exit()

# Continue with the application's normal command handling.
```

Run `books --totalhelp` for terminal output, or `books --totalhelp --format md` to generate Markdown. `--format html` writes a temporary HTML file; `--open` also opens it in a browser.

You can call `full_help_from_parser(parser, fmt="text")` directly without adding a flag. Supported formats are `text`, `md`, and `html`.

The parser-tree approach reads the `ArgumentParser` objects you already created. It does not need to guess command names from formatted help text.
