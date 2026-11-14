# Inspect another CLI

The `totalhelp` console command can inspect a CLI that you do not control:

```bash
totalhelp pipx
```

It runs the target and discovered subcommands with `--help`, then combines their output. You can also call `full_help_external(["pipx"], fmt="text")` from Python.

This is a best-effort mode. CLI help is not a standard machine-readable format, so command discovery can miss subcommands or mistake prose for a command. Each subprocess has a timeout and recursion depth limit, but inspecting a slow or unusual CLI can still take time. Prefer [parser integration](integration.md) for applications you own.

For the exact public API and behavior, see the [source repository](https://github.com/matthewdeanmartin/totalhelp).
