from totalhelp.parser import find_subcommands

CLI_TOOL_AUDIT = r"""
usage: cli_tool_audit [-h] [-V] [--verbose] [--quiet] [--demo {pipx,venv,npm}]
                      {interactive,freeze,audit,single,read,create,update,delete} ...

Audit for existence and version number of cli tools.

positional arguments:
  {interactive,freeze,audit,single,read,create,update,delete}
                        Subcommands.
    interactive         Interactively edit configuration
    freeze              Freeze the versions of specified tools
    audit               Audit environment with current configuration
    single              Audit one tool without configuration file
    read                Read and list all tool configurations
    create              Create a new tool configuration
    update              Update an existing tool configuration
    delete              Delete a tool configuration

options:
  -h, --help            show this help message and exit
"""

PIPX = r"""
usage: pipx [-h] [--quiet] [--verbose] [--version]
            {install,install-all,uninject,inject,pin,unpin,upgrade,upgrade-all,upgrade-shared,uninstall,uninstall-all,reinstall,reinstall-all,list,interpreter,run,runpip,ensurepath,environment,completions} ...

Install and execute apps from Python packages.

subcommands:
  Get help for commands with pipx COMMAND --help

  {install,install-all,uninject,inject,pin,unpin,upgrade,upgrade-all,upgrade-shared,uninstall,uninstall-all,reinstall,reinstall-all,list,interpreter,run,runpip,ensurepath,environment,completions}
    install             Install a package
    install-all         Install all packages
    uninject            Uninstall injected packages from an existing Virtual Environment
    inject              Install packages into an existing Virtual Environment
    pin                 Pin the specified package to prevent it from being upgraded
    unpin               Unpin the specified package
    upgrade             Upgrade a package
    upgrade-all         Upgrade all packages. Runs `pip install -U <pkgname>` for each package.
    upgrade-shared      Upgrade shared libraries.
    uninstall           Uninstall a package
    uninstall-all       Uninstall all packages
    reinstall           Reinstall a package
    reinstall-all       Reinstall all packages
    list                List installed packages
    interpreter         Interact with interpreters managed by pipx
    run                 Download the latest version of a package to a temporary virtual environment, then run an app
                        from it.
    runpip              Run pip in an existing pipx-managed Virtual Environment
    ensurepath          Ensure directories necessary for pipx operation are in your PATH environment variable.
    environment         Print a list of environment variables and paths used by pipx.
    completions         Print instructions on enabling shell completions for pipx
"""

WRAPPED_ODD = r"""
USAGE:
  oddtool [OPTIONS] <command>

Commands:
  walk      Move around
            (this wraps on a second line)
  jump      Leap upwards
  help      Print help
Options:
  -h, --help  Print help information
"""


def test_cli_tool_audit_commands():
    res = find_subcommands(CLI_TOOL_AUDIT)
    expect = [
        "interactive",
        "freeze",
        "audit",
        "single",
        "read",
        "create",
        "update",
        "delete",
    ]
    for cmd in expect:
        assert cmd in res.subcommands
    # Top few should be those:
    assert res.subcommands[:4] == ["interactive", "freeze", "audit", "single"]


def test_pipx_commands():
    res = find_subcommands(PIPX)
    expect = [
        "install",
        "install-all",
        "uninject",
        "inject",
        "pin",
        "unpin",
        "upgrade",
        "upgrade-all",
        "upgrade-shared",
        "uninstall",
        "uninstall-all",
        "reinstall",
        "reinstall-all",
        "list",
        "interpreter",
        "run",
        "runpip",
        "ensurepath",
        "environment",
        "completions",
    ]
    for cmd in expect:
        assert cmd in res.subcommands


def test_wrapped_definition_list_detection():
    res = find_subcommands(WRAPPED_ODD)
    assert "walk" in res.subcommands
    assert "jump" in res.subcommands
    # 'help' might be filtered; ensure the real commands survived
    assert res.subcommands[0] in ("walk", "jump")


# ---------------------------------------------------------------------------
# Live-argparse round-trip tests.
#
# The fixtures above are *frozen* strings captured from older Pythons. They
# prove the heuristics still parse historical output, but they cannot catch a
# change in how the running interpreter's argparse formats help.
#
# Python 3.15 changed argparse's *error* strings (it now appends
# "maybe you meant 'x'?" to "invalid choice:"). totalhelp only ever parses
# ``--help`` output, never error output, so it is unaffected -- but that is a
# property worth pinning down with a test rather than leaving to inspection.
# ---------------------------------------------------------------------------
import argparse

from totalhelp.library import full_help_from_parser


def _live_parser() -> argparse.ArgumentParser:
    """A parser built by the *running* interpreter's argparse."""
    parser = argparse.ArgumentParser(prog="tool", description="Live tool.")
    parser.add_argument("--level", choices=["low", "mid", "high"], help="Level")
    subs = parser.add_subparsers(dest="cmd")
    for name in ("install", "uninstall", "freeze", "audit", "single"):
        subs.add_parser(name, help=f"{name} things")
    return parser


def test_find_subcommands_on_live_argparse_help():
    """Discovery must work against help text this interpreter actually emits."""
    result = find_subcommands(_live_parser().format_help(), root_command="tool")
    assert set(result.subcommands) == {
        "install",
        "uninstall",
        "freeze",
        "audit",
        "single",
    }


def test_find_subcommands_ignores_option_choices():
    """`--level {low,mid,high}` must not be mistaken for subcommands."""
    result = find_subcommands(_live_parser().format_help(), root_command="tool")
    for not_a_command in ("low", "mid", "high"):
        assert not_a_command not in result.subcommands


def test_nested_live_help_renders_every_node():
    """The rendered document must contain a section per parser in the tree."""
    parser = _live_parser()
    doc = full_help_from_parser(parser, fmt="text", use_rich=False)
    for name in ("install", "uninstall", "freeze", "audit", "single"):
        assert f"$ tool {name} --help" in doc


def test_error_text_is_never_parsed_for_subcommands():
    """
    Python 3.15 appends "maybe you meant 'x'?" to argparse's invalid-choice
    error. Feeding such a message to the discovery heuristics must not produce
    bogus subcommands (totalhelp never does this, but the parser is public).
    """
    message = (
        "tool: error: argument cmd: invalid choice: 'instll', "
        "maybe you meant 'install'? (choose from 'install', 'freeze')"
    )
    result = find_subcommands(message, root_command="tool")
    assert result.subcommands == []
