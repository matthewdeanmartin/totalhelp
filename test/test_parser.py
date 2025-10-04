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
