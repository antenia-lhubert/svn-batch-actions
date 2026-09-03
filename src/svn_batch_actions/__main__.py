"""Main entry point for SVN batch actions utility."""

import argparse
import json
import sys
from pathlib import Path

from .actions import ActionExecutor
from .logger import ActionLogger


VALID_CHECKOUT_DEPTHS = ("empty", "files", "immediates", "infinity")
VALID_CONFLICT_RESOLUTIONS = ("mine-conflict", "theirs-conflict")


def validate_action(action: dict, index: int) -> list[str]:
    """
    Validate a single action configuration.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Check required fields based on action type
    has_from = "from" in action
    has_to = "to" in action
    has_rev = "rev" in action
    has_msg = "msg" in action

    # All actions require 'to' and 'msg'
    if not has_to:
        errors.append(f"Action {index + 1}: Missing required field 'to'")
    if not has_msg:
        errors.append(f"Action {index + 1}: Missing required field 'msg'")

    # Determine expected action type
    if has_from:
        # Merge-type actions require 'rev'
        if not has_rev:
            errors.append(f"Action {index + 1}: Merge actions require 'rev' field")
    else:
        # Patch-only actions must have patch=true
        if not action.get("patch", False):
            errors.append(f"Action {index + 1}: Non-merge actions must have 'patch': true")

    # Validate types
    if has_rev:
        try:
            int(action["rev"])
        except (ValueError, TypeError):
            errors.append(f"Action {index + 1}: 'rev' must be a number")

    if "empty" in action and not isinstance(action["empty"], bool):
        errors.append(f"Action {index + 1}: 'empty' must be true or false")

    if "patch" in action and not isinstance(action["patch"], bool):
        errors.append(f"Action {index + 1}: 'patch' must be true or false")

    if "conflict_resolution" in action:
        if action["conflict_resolution"] not in VALID_CONFLICT_RESOLUTIONS:
            valid_resolutions = ", ".join(VALID_CONFLICT_RESOLUTIONS)
            errors.append(
                f"Action {index + 1}: 'conflict_resolution' must be one of: {valid_resolutions}"
            )
        if not has_from or action.get("empty", False):
            errors.append(f"Action {index + 1}: 'conflict_resolution' is only valid for non-empty merge actions")

    enabled_patches = action.get("enabled_patches")
    if enabled_patches is not None and (
        not isinstance(enabled_patches, list) or not all(isinstance(name, str) for name in enabled_patches)
    ):
        errors.append(f"Action {index + 1}: 'enabled_patches' must be a list of patch names")
        enabled_patches = None

    if "pom_version" in action:
        if not isinstance(action["pom_version"], str) or not action["pom_version"].strip():
            errors.append(f"Action {index + 1}: 'pom_version' must be a non-empty string")
        if not action.get("patch", False):
            errors.append(f"Action {index + 1}: 'pom_version' requires 'patch': true")
        if enabled_patches is not None and "pom_version" not in enabled_patches:
            errors.append(f"Action {index + 1}: 'pom_version' must be included in 'enabled_patches'")
    elif enabled_patches is not None and "pom_version" in enabled_patches:
        errors.append(f"Action {index + 1}: Patch 'pom_version' requires field 'pom_version'")

    if "checkout_depth" in action and action["checkout_depth"] not in VALID_CHECKOUT_DEPTHS:
        valid_depths = ", ".join(VALID_CHECKOUT_DEPTHS)
        errors.append(f"Action {index + 1}: 'checkout_depth' must be one of: {valid_depths}")

    return errors


def validate_config(config: dict) -> list[str]:
    """
    Validate entire configuration.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Check required top-level fields
    if "repository_base" not in config:
        errors.append("Missing required field 'repository_base'")

    if "checkout_depth" in config and config["checkout_depth"] not in VALID_CHECKOUT_DEPTHS:
        valid_depths = ", ".join(VALID_CHECKOUT_DEPTHS)
        errors.append(f"Field 'checkout_depth' must be one of: {valid_depths}")

    if "actions" not in config:
        errors.append("Missing required field 'actions'")
    elif not isinstance(config["actions"], list):
        errors.append("Field 'actions' must be a list")
    elif len(config["actions"]) == 0:
        errors.append("Field 'actions' cannot be empty")
    else:
        # Validate each action
        for i, action in enumerate(config["actions"]):
            if not isinstance(action, dict):
                errors.append(f"Action {i + 1}: Must be an object")
            else:
                errors.extend(validate_action(action, i))

    return errors


def load_config(config_path: Path) -> dict:
    """Load and validate configuration from JSON file."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in configuration file: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate configuration
    errors = validate_config(config)
    if errors:
        print("Configuration validation errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)

    return config


def print_action_summary(config: dict):
    """Print a summary of actions to be executed."""
    print("\n" + "=" * 80)
    print("ACTION SUMMARY")
    print("=" * 80)
    print(f"Repository: {config['repository_base']}")
    if "checkout_depth" in config:
        print(f"Checkout depth: {config['checkout_depth']}")
    print(f"Total actions: {len(config['actions'])}")
    print("\nActions to execute:")

    for i, action in enumerate(config["actions"], 1):
        action_type = ActionLogger._infer_action_type(action)
        print(f"\n  {i}. {action_type}")

        if "from" in action:
            print(f"     From: {action['from']} (r{action.get('rev', 'N/A')})")
        print(f"     To: {action['to']}")
        if "checkout_depth" in action:
            print(f"     Checkout depth: {action['checkout_depth']}")
        if "conflict_resolution" in action:
            print(f"     Conflict resolution: {action['conflict_resolution']}")
        if "pom_version" in action:
            print(f"     POM version: {action['pom_version']}")
        print(f"     Message: {action['msg'][:60]}{'...' if len(action['msg']) > 60 else ''}")

    print("\n" + "=" * 80)


def confirm_execution() -> bool:
    """Ask user to confirm execution."""
    while True:
        response = input("\nProceed with execution? [y/N]: ").strip().lower()
        if response in ["y", "yes"]:
            return True
        elif response in ["n", "no", ""]:
            return False
        else:
            print("Please answer 'y' or 'n'")


def main():
    parser = argparse.ArgumentParser(
        description="Execute SVN batch actions from JSON configuration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example configuration file:
{
  "repository_base": "svn://server/repo",
  "workspace": "./.temp",
  "log_dir": "./logs",
  "actions": [
    {
      "from": "versions/v1.4",
      "to": "versions/v1.5",
      "rev": "12345",
      "author": "username",
      "empty": true,
      "msg": "Record merge from v1.4"
    }
  ]
}

Action types:
  - PATCH: Only 'to', 'patch': true, 'msg'
  - EMPTY_MERGE: 'from', 'to', 'rev', 'empty': true, 'msg'
  - MERGE: 'from', 'to', 'rev', 'msg'
  - MERGE_WITH_PATCH: 'from', 'to', 'rev', 'patch': true, 'msg'
        """,
    )

    parser.add_argument("config", type=str, help="Path to JSON configuration file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without making changes")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--log-dir", type=str, help="Override log directory from config")
    parser.add_argument("--workspace", type=str, help="Override workspace directory from config")
    parser.add_argument("--no-commit", action="store_true", help="Apply patches but skip commit and preserve workspace")
    parser.add_argument(
        "--apply-only", action="store_true", help="Skip checkout; apply patches to existing workspace only"
    )

    args = parser.parse_args()

    # Load and validate configuration
    config_path = Path(args.config).resolve()
    config = load_config(config_path)

    # Apply command line overrides
    workspace = Path(args.workspace) if args.workspace else Path(config.get("workspace", "./.temp"))
    log_dir = Path(args.log_dir) if args.log_dir else Path(config.get("log_dir", "./logs"))

    # Validate --apply-only is only used with PATCH actions
    if args.apply_only:
        for i, action in enumerate(config["actions"]):
            action_type = ActionLogger._infer_action_type(action)
            if action_type != "PATCH":
                print(f"Error: --apply-only can only be used with PATCH actions", file=sys.stderr)
                print(
                    f"Action {i + 1} is of type {action_type}, which requires checkout and merge operations",
                    file=sys.stderr,
                )
                sys.exit(1)

    # Print summary
    print_action_summary(config)

    if args.dry_run:
        print("\n[DRY RUN MODE] - No actual changes will be made")

    if args.no_commit:
        print("\n[NO COMMIT MODE] - Changes will be applied but not committed")
        print(f"Workspace will be preserved at: {workspace.resolve()}")

    if args.apply_only:
        print("\n[APPLY ONLY MODE] - Skipping checkout; patches will be applied to existing workspace")
        print(f"Expected workspace location: {workspace.resolve()}")

    # Confirm execution
    if not args.yes and not args.dry_run:
        if not confirm_execution():
            print("Execution cancelled.")
            sys.exit(0)

    # Initialize logger
    logger = ActionLogger(log_dir, verbose=args.verbose)

    # Initialize executor
    executor = ActionExecutor(
        repository_base=config["repository_base"],
        workspace=workspace,
        logger=logger,
        dry_run=args.dry_run,
        no_commit=args.no_commit,
        apply_only=args.apply_only,
        checkout_depth=config.get("checkout_depth"),
    )

    # Execute actions
    print("\n" + "=" * 80)
    print("EXECUTION STARTED")
    print("=" * 80)

    successful = 0
    failed = 0
    failed_action_index = None
    failed_action = None
    failure_exception = None

    try:
        for i, action in enumerate(config["actions"]):
            try:
                executor.execute_action(i, action)
                successful += 1
            except Exception as e:
                failed += 1
                failed_action_index = i
                failed_action = action
                failure_exception = e

                # Stop on first failure
                break

    finally:
        # Finalize logging
        logger.finalize(len(config["actions"]), successful, failed)

        # Print detailed failure information
        if failed > 0:
            print("\n" + "=" * 80, file=sys.stderr)
            print("FAILURE DETAILS", file=sys.stderr)
            print("=" * 80, file=sys.stderr)
            print(f"\n✗ Action {failed_action_index + 1} of {len(config['actions'])} FAILED\n", file=sys.stderr)

            print("Failed action configuration:", file=sys.stderr)
            print(json.dumps(failed_action, indent=2), file=sys.stderr)

            print(f"\nAction type: {ActionLogger._infer_action_type(failed_action)}", file=sys.stderr)

            print(f"\nError type: {type(failure_exception).__name__}", file=sys.stderr)
            print(f"Error message:\n{failure_exception}\n", file=sys.stderr)

            if args.verbose:
                import traceback

                print("Full traceback:", file=sys.stderr)
                traceback.print_exception(type(failure_exception), failure_exception, failure_exception.__traceback__)

            print("=" * 80, file=sys.stderr)
            print(f"\nExecution stopped. {successful} action(s) completed before failure.", file=sys.stderr)
            print(f"Check logs for complete details: {logger.log_file}", file=sys.stderr)
            print("=" * 80, file=sys.stderr)

        # Print final summary
        print("\n" + "=" * 80)
        print("EXECUTION COMPLETE")
        print("=" * 80)
        print(f"Successful: {successful}/{len(config['actions'])}")
        print(f"Failed: {failed}/{len(config['actions'])}")
        print("=" * 80)

    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
