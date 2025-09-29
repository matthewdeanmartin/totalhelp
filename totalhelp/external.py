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
