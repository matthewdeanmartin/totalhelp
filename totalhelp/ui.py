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
