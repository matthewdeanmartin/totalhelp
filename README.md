## totalhelp

An implementation of the totalhelp PEP. 

This module provides monolithic help output for Python argparse
applications, including those with deeply nested subcommands.


## Usage

Works best with python tools that use Argparse. 

```bash
totalhelp llm
totalhelp pipx
```

Caveats

- Help text is not a standard parsable format, so discovery of command names may fail.
- Can surface problems with applications that have slow startup.

## Features

- Monolithic Help: Generate a single help document
for your entire CLI, including all subcommands.
- Multiple Formats: Output to plain text, Markdown, or self-contained
HTML.
- Drop-in Integration: Add a --totalhelp flag to your existing ArgumentParser with a single function call. No
subclassing required.
- Optional rich support: If totalhelp[rich] is installed, get beautifully formatted terminal
output.
- External Tool Inspection: A best-effort mode to generate help for third-party CLIs you don't
control.
- InstallationInstall the base package: `pip install .`

To include optional rich formatting support:`pip install .[rich]`

## Quick Start

Integrate it into your application in three steps.

1. Build your parser as usual.

```python
# my_cli.py
import argparse


def create_parser():
    parser = argparse.ArgumentParser(description="A complex tool.")
    subparsers = parser.add_subparsers(dest="command", title="Available Commands")

    # Command 'remote'
    remote_parser = subparsers.add_parser("remote", help="Manage remotes")
    remote_subparsers = remote_parser.add_subparsers(dest="remote_command")
    remote_add_parser = remote_subparsers.add_parser("add", help="Add a remote")
    remote_add_parser.add_argument("name", help="Name of the remote")
    remote_add_parser.add_argument("url", help="URL of the remote")

    # Command 'log'
    log_parser = subparsers.add_parser("log", help="Show commit logs")
    log_parser.add_argument("--oneline", action="store_true", help="Show logs in a compact format")

    return parser
```

2. Add the --totalhelp flag.

```python
# my_cli.py (continued)
import sys
import totalhelp

parser = create_parser()

# Add the flag. That's it.
totalhelp.add_totalhelp_flag(parser)
```

3. Check for the flag after parsing arguments.

```python
# my_cli.py (continued)
if __name__ == "__main__":
    args = parser.parse_args()

    # If --totalhelp was passed, generate and print the doc, then exit.
    if getattr(args, "totalhelp", False):
        doc = totalhelp.full_help_from_parser(
            parser,
            fmt=getattr(args, "format", "text")
        )
        totalhelp.print_output(
            doc,
            fmt=getattr(args, "format", "text"),
            open_browser=getattr(args, "open", False)
        )
        sys.exit(0)

    # --- Your normal CLI logic goes here ---
    print(f"Normal execution with args: {args}")
```

Now you can run your app to see the monolithic help:

#### Get full help in the terminal

```bash
python my_cli.py --totalhelp
```

#### Generate a Markdown document

```bash
python my_cli.py --totalhelp --format md > DOCS.md
```

#### Generate and open an HTML file in your browser

```bash
python my_cli.py --totalhelp --format html --open
```