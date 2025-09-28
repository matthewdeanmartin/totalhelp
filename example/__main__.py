"""
An example command-line application demonstrating how to integrate `totalhelp`.
"""
import argparse
import sys

# In a real application, you would `import totalhelp`.
# For this example, we assume it's on the python path.
import totalhelp


def create_parser() -> argparse.ArgumentParser:
    """Builds the ArgumentParser object for our example CLI."""
    parser = argparse.ArgumentParser(
        prog="git",
        description="A pretend Git CLI to demonstrate totalhelp.",
        epilog="Thanks for using our fake tool!",
    )
    subparsers = parser.add_subparsers(dest="command", title="Available Commands", required=True)

    # --- 'remote' command with its own subcommands ---
    remote_parser = subparsers.add_parser(
        "remote", help="Manage set of tracked repositories."
    )
    remote_subparsers = remote_parser.add_subparsers(
        dest="remote_command", title="Remote Commands", required=True
    )

    # `git remote add`
    remote_add_parser = remote_subparsers.add_parser(
        "add", help="Add a remote repository."
    )
    remote_add_parser.add_argument("name", help="Name for the new remote.")
    remote_add_parser.add_argument("url", help="URL for the new remote.")

    # `git remote remove`
    remote_remove_parser = remote_subparsers.add_parser(
        "remove", help="Remove a remote."
    )
    remote_remove_parser.add_argument("name", help="Name of the remote to remove.")

    # --- 'log' command ---
    log_parser = subparsers.add_parser("log", help="Show commit logs.")
    log_parser.add_argument(
        "--oneline", action="store_true", help="Show logs in a compact one-line format."
    )
    log_parser.add_argument(
        "-n", "--max-count", type=int, help="Limit the number of commits to show."
    )

    # --- 'config' command ---
    config_parser = subparsers.add_parser(
        "config", help="Get and set repository or global options."
    )
    config_parser.add_argument(
        "--global",
        action="store_true",
        dest="is_global",
        help="Use global configuration file.",
    )
    config_parser.add_argument("key", help="Configuration key (e.g., user.name).")
    config_parser.add_argument("value", nargs="?", help="Value to set for the key.")

    return parser


def main():
    """Main entry point for the CLI application."""
    parser = create_parser()

    # STEP 1: Add the totalhelp flag after the parser is fully constructed.
    totalhelp.add_totalhelp_flag(parser)

    # STEP 2: Parse arguments as usual.
    args = parser.parse_args()

    # STEP 3: Check if the totalhelp flag was passed and handle it.
    if getattr(args, "totalhelp", False):
        # Generate the monolithic help document
        doc = totalhelp.full_help_from_parser(
            parser,
            fmt=getattr(args, "format", "text")
        )
        # Print it using the helper (which handles HTML file creation)
        totalhelp.print_output(
            doc,
            fmt=getattr(args, "format", "text"),
            open_browser=getattr(args, "open", False)
        )
        # Exit cleanly
        sys.exit(0)

    # --- Your normal application logic begins here ---
    print("--- Normal Application Execution ---")
    print(f"Received arguments: {vars(args)}")
    print("------------------------------------")
    # Example logic
    if args.command == "remote" and args.remote_command == "add":
        print(f"Adding remote '{args.name}' with URL '{args.url}'...")
    elif args.command == "log":
        print("Displaying logs...")
        if args.oneline:
            print(" (in oneline format)")


if __name__ == "__main__":
    main()
