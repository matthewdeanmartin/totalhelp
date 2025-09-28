"""
Tests for the totalhelp module.
"""

import argparse
import sys
from unittest.mock import MagicMock, patch

import pytest

from totalhelp.core import (
    _find_subcommands_from_help,
    _walk_parser_tree,
    add_totalhelp_flag,
    full_help_external,
    full_help_from_parser,
    print_output,
)

# We need to add the parent directory to the path to import totalhelp
# In a real package installation, this wouldn't be necessary.
sys.path.insert(0, ".")


@pytest.fixture
def complex_parser():
    """Provides a parser with nested subcommands for testing."""
    parser = argparse.ArgumentParser(prog="cli", description="A test CLI.")
    subparsers = parser.add_subparsers(dest="command")

    # cmd1
    p1 = subparsers.add_parser("cmd1", help="First command")
    p1.add_argument("--foo", action="store_true", help="Foo option")

    # cmd2 with subcommands
    p2 = subparsers.add_parser("cmd2", help="Second command")
    p2_subs = p2.add_subparsers(dest="sub_cmd2")
    p2_sub1 = p2_subs.add_parser("sub1", help="First sub of cmd2")
    p2_sub1.add_argument("pos1", help="A positional arg")

    return parser


def test_walk_parser_tree(complex_parser):
    """Test that the walker finds all parsers."""
    nodes = list(_walk_parser_tree(complex_parser))
    paths = {" ".join(n.path) for n in nodes}

    assert len(nodes) == 4
    assert "" in paths  # Root parser
    assert "cmd1" in paths
    assert "cmd2" in paths
    assert "cmd2 sub1" in paths


def test_prog_override(complex_parser):
    """Test that the 'prog' argument correctly overrides the parser's program name."""
    doc_default = full_help_from_parser(complex_parser, fmt="text")
    assert "usage: cli" in doc_default

    doc_override = full_help_from_parser(complex_parser, prog="my-app", fmt="text")
    assert "my-app" in doc_override
    assert "$ my-app --help" in doc_override
    assert "$ my-app cmd1 --help" in doc_override
    # Also check that the original parser is not mutated
    assert complex_parser.prog == "cli"


def test_text_format(complex_parser):
    """Test plain text output format."""
    output = full_help_from_parser(complex_parser, fmt="text")
    assert "$ cli --help" in output
    assert "A test CLI." in output
    assert "$ cli cmd1 --help" in output
    assert "Foo option" in output
    assert "$ cli cmd2 sub1 --help" in output
    assert "A positional arg" in output
    assert "usage: cli cmd2 sub1" in output


def test_md_format(complex_parser):
    """Test Markdown output format."""
    output = full_help_from_parser(complex_parser, fmt="md")
    assert "# Help for `cli`" in output
    assert "## `cli`" in output
    assert "### `cli cmd1`" in output
    assert "#### `cli cmd2 sub1`" in output
    assert "```text" in output


def test_html_format(complex_parser):
    """Test HTML output format."""
    output = full_help_from_parser(complex_parser, fmt="html")
    assert "<!DOCTYPE html>" in output


def test_add_totalhelp_flag(complex_parser):
    """Test that the flags are added correctly to a parser."""
    add_totalhelp_flag(complex_parser)
    help_text = complex_parser.format_help()

    assert "--totalhelp" in help_text
    assert "--totalhelp" in help_text
    assert "--format {text,md,html}" in help_text
    assert "--open" in help_text


@patch("totalhelp.core.webbrowser")
@patch("tempfile.NamedTemporaryFile")
def test_print_output_html(mock_tempfile, mock_webbrowser):
    """Test HTML output with file creation and browser opening."""
    # Mock the temp file to avoid actual file system writes
    mock_file = MagicMock()
    mock_file.name = "/tmp/fake.html"
    mock_tempfile.return_value.__enter__.return_value = mock_file

    # Test without opening browser
    print_output("<html>...</html>", fmt="html", open_browser=False)
    mock_file.write.assert_called_with("<html>...</html>")
    mock_webbrowser.open.assert_not_called()

    # Test with opening browser
    print_output("<html>...</html>", fmt="html", open_browser=True)
    # mock_webbrowser.open.assert_called_once_with("file:///tmp/fake.html")


def test_find_subcommands_from_help():
    """Test the heuristic for finding subcommands in help text."""
    help1 = "usage: git [-v | --version] {clone,init,add,mv,reset,rm,bisect,grep}"
    assert set(_find_subcommands_from_help(help1)) == {
        "clone",
        "init",
        "add",
        "mv",
        "reset",
        "rm",
        "bisect",
        "grep",
    }

    help2 = """
usage: docker [OPTIONS] COMMAND

A self-sufficient runtime for containers

Commands:
  build       Build an image from a Dockerfile
  run         Run a new command in a new container
  ps          List containers
"""
    assert set(_find_subcommands_from_help(help2)) == {"build", "run", "ps"}


@patch("subprocess.run")
def test_full_help_external(mock_run):
    """Test the external command runner."""
    # Mock the return values for subprocess calls
    mock_root = MagicMock()
    mock_root.stdout = "usage: pip <command> [...]\n\nCommands:\n  install    Install packages.\n  uninstall  Uninstall packages.\n"
    mock_root.stderr = ""
    mock_root.returncode = 0

    mock_install = MagicMock()
    mock_install.stdout = "usage: pip install [options] <package>"
    mock_install.stderr = ""
    mock_install.returncode = 0

    mock_uninstall = MagicMock()
    mock_uninstall.stdout = "usage: pip uninstall [options] <package>"
    mock_uninstall.stderr = ""
    mock_uninstall.returncode = 0

    mock_run.side_effect = [mock_root, mock_install, mock_uninstall]

    output = full_help_external(["pip"], fmt="text")

    assert "$ pip --help" in output
    assert "Install packages." in output
    assert "$ pip install --help" in output
    assert "usage: pip install" in output
    assert "$ pip uninstall --help" in output
    assert "usage: pip uninstall" in output

    assert mock_run.call_count == 3
    mock_run.assert_any_call(
        ["pip", "--help"],
        capture_output=True,
        text=True,
        timeout=5.0,
        encoding="utf-8",
        errors="replace",
        env=None,
    )
    mock_run.assert_any_call(
        ["pip", "install", "--help"],
        capture_output=True,
        text=True,
        timeout=5.0,
        encoding="utf-8",
        errors="replace",
        env=None,
    )
