"""Action handlers for SVN batch operations."""

from pathlib import Path
from typing import Optional

from .logger import ActionLogger
from .utils import (
    cleanup_directory,
    fix_mergeinfo_inheritance,
    get_modified_files,
    svn_checkout,
    svn_commit,
    svn_merge,
    svn_revert_all,
    SVNCommandError,
)


class ActionExecutor:
    """Executes SVN batch actions."""

    def __init__(
        self,
        repository_base: str,
        workspace: Path,
        logger: ActionLogger,
        dry_run: bool = False
    ):
        self.repository_base = repository_base.rstrip('/')
        self.workspace = Path(workspace)
        self.logger = logger
        self.dry_run = dry_run

        # Ensure workspace exists
        self.workspace.mkdir(parents=True, exist_ok=True)

    def execute_action(self, action_index: int, action: dict) -> bool:
        """Execute a single action based on its configuration."""
        self.logger.start_action(action_index, action)

        try:
            # Infer action type
            action_type = self._infer_action_type(action)

            if action_type == "PATCH":
                return self._execute_patch(action)
            elif action_type == "EMPTY_MERGE":
                return self._execute_empty_merge(action)
            elif action_type == "MERGE":
                return self._execute_merge(action, with_patch=False)
            elif action_type == "MERGE_WITH_PATCH":
                return self._execute_merge(action, with_patch=True)
            else:
                raise ValueError(f"Unknown action type: {action}")

        except SVNCommandError as e:
            # SVN errors already have detailed context
            self.logger.log_error(str(e))
            self.logger.complete_action(False, f"SVN operation failed")
            raise
        except Exception as e:
            # Add context to other errors
            error_msg = f"{type(e).__name__}: {e}"
            self.logger.log_error(error_msg)
            self.logger.complete_action(False, f"Unexpected error: {type(e).__name__}")
            raise

    def _execute_patch(self, action: dict) -> bool:
        """Execute a patch-only action."""
        to_branch = action["to"]
        author = action.get("author")
        msg = action["msg"]

        self.logger.log_step("Starting patch operation")

        # Build full URL
        target_url = f"{self.repository_base}/{to_branch}"
        branch_name = to_branch.split('/')[-1]
        working_dir = self.workspace / branch_name

        try:
            # Clean up existing directory
            cleanup_directory(working_dir, self.logger.verbose)

            # Checkout target branch
            self.logger.log_step("Checkout", f"Checking out {target_url}")
            if not self.dry_run:
                try:
                    svn_checkout(target_url, working_dir, self.logger.verbose)
                except Exception as e:
                    raise SVNCommandError(f"Checkout failed for {target_url}\n{e}") from e

            # Apply patches
            self.logger.log_step("Apply patches", "Running patch script")
            if not self.dry_run:
                try:
                    self._apply_patches(working_dir)
                except Exception as e:
                    raise SVNCommandError(f"Patch application failed\n{e}") from e

            # Get modified files
            if not self.dry_run:
                modified_files = get_modified_files(working_dir)
                self.logger.log_files_modified(modified_files)

                if not modified_files:
                    self.logger.complete_action(True, "No changes after patch")
                    return True

            # Commit
            self.logger.log_step("Commit", f"Committing with message: {msg}")
            if not self.dry_run:
                try:
                    has_changes, output = svn_commit(working_dir, msg, author, self.logger.verbose)
                    self.logger.log_step("Commit result", output)
                except Exception as e:
                    raise SVNCommandError(f"Commit failed\n{e}") from e

            self.logger.complete_action(True, "Patch applied and committed successfully")
            return True

        finally:
            if not self.dry_run:
                cleanup_directory(working_dir, self.logger.verbose)

    def _execute_empty_merge(self, action: dict) -> bool:
        """Execute an empty merge (merge info only)."""
        from_branch = action["from"]
        to_branch = action["to"]
        revision = int(action["rev"])
        author = action.get("author")
        msg = action["msg"]

        self.logger.log_step("Starting empty merge (record-only)")

        # Build URLs
        source_url = f"{self.repository_base}/{from_branch}"
        target_url = f"{self.repository_base}/{to_branch}"
        branch_name = to_branch.split('/')[-1]
        working_dir = self.workspace / branch_name

        try:
            # Clean up existing directory
            cleanup_directory(working_dir, self.logger.verbose)

            # Checkout target branch (sparse checkout for empty merge)
            self.logger.log_step("Checkout", f"Checking out {target_url} (--depth empty)")
            if not self.dry_run:
                try:
                    svn_checkout(target_url, working_dir, self.logger.verbose, depth="empty")
                except Exception as e:
                    raise SVNCommandError(f"Checkout failed for {target_url}\n{e}") from e

            # Record merge
            self.logger.log_step("Record merge", f"From {from_branch} r{revision}")
            if not self.dry_run:
                success, output = svn_merge(
                    working_dir,
                    source_url,
                    revision,
                    record_only=True,
                    verbose=self.logger.verbose
                )

                if not success:
                    raise SVNCommandError(f"Empty merge failed from {from_branch} r{revision}\n{output}")

                self.logger.log_step("Merge result", output)

                # Fix non-inheritable marker for this revision (caused by sparse checkout)
                self.logger.log_step("Fix mergeinfo", f"Removing non-inheritable marker from r{revision}")
                fix_mergeinfo_inheritance(working_dir, revision, self.logger.verbose)

                # Get modified files
                modified_files = get_modified_files(working_dir)
                self.logger.log_files_modified(modified_files)

                if not modified_files:
                    self.logger.complete_action(True, "No changes (already merged)")
                    return True

            # Commit
            self.logger.log_step("Commit", f"Committing merge info")
            if not self.dry_run:
                try:
                    has_changes, output = svn_commit(working_dir, msg, author, self.logger.verbose)
                    self.logger.log_step("Commit result", output)
                except Exception as e:
                    raise SVNCommandError(f"Commit failed\n{e}") from e

            self.logger.complete_action(True, "Empty merge completed successfully")
            return True

        finally:
            if not self.dry_run:
                cleanup_directory(working_dir, self.logger.verbose)

    def _execute_merge(self, action: dict, with_patch: bool = False) -> bool:
        """Execute a real merge, optionally with patch."""
        from_branch = action["from"]
        to_branch = action["to"]
        revision = int(action["rev"])
        author = action.get("author")
        msg = action["msg"]

        merge_type = "merge with patch" if with_patch else "merge"
        self.logger.log_step(f"Starting {merge_type}")

        # Build URLs
        source_url = f"{self.repository_base}/{from_branch}"
        target_url = f"{self.repository_base}/{to_branch}"
        branch_name = to_branch.split('/')[-1]
        working_dir = self.workspace / branch_name

        try:
            # Clean up existing directory
            cleanup_directory(working_dir, self.logger.verbose)

            # Checkout target branch
            self.logger.log_step("Checkout", f"Checking out {target_url}")
            if not self.dry_run:
                try:
                    svn_checkout(target_url, working_dir, self.logger.verbose)
                except Exception as e:
                    raise SVNCommandError(f"Checkout failed for {target_url}\n{e}") from e

            # Perform merge
            self.logger.log_step("Merge", f"From {from_branch} r{revision}")
            if not self.dry_run:
                success, output = svn_merge(
                    working_dir,
                    source_url,
                    revision,
                    record_only=False,
                    verbose=self.logger.verbose
                )

                if not success:
                    # Revert on conflict
                    self.logger.log_step("Conflict detected", "Reverting changes")
                    svn_revert_all(working_dir, self.logger.verbose)
                    raise SVNCommandError(
                        f"Merge failed from {from_branch} r{revision} to {to_branch}\n"
                        f"Conflicts detected and changes reverted.\n{output}"
                    )

                self.logger.log_step("Merge result", output)

            # Apply patches if requested
            if with_patch:
                self.logger.log_step("Apply patches", "Running patch script")
                if not self.dry_run:
                    try:
                        self._apply_patches(working_dir)
                    except Exception as e:
                        raise SVNCommandError(f"Patch application failed after merge\n{e}") from e

            # Get modified files
            if not self.dry_run:
                modified_files = get_modified_files(working_dir)
                self.logger.log_files_modified(modified_files)

                if not modified_files:
                    self.logger.complete_action(True, "No changes after merge")
                    return True

            # Commit
            self.logger.log_step("Commit", f"Committing changes")
            if not self.dry_run:
                try:
                    has_changes, output = svn_commit(working_dir, msg, author, self.logger.verbose)
                    self.logger.log_step("Commit result", output)
                except Exception as e:
                    raise SVNCommandError(f"Commit failed\n{e}") from e

            self.logger.complete_action(True, f"{merge_type.capitalize()} completed successfully")
            return True

        finally:
            if not self.dry_run:
                cleanup_directory(working_dir, self.logger.verbose)

    def _apply_patches(self, working_dir: Path, enabled_patches: list[str] = None):
        """
        Apply patches using the patch system.

        Args:
            working_dir: Working directory to apply patches to
            enabled_patches: List of patch names to apply. If None, applies all available patches.
        """
        try:
            from .patches import patch

            # Apply patches (defaults to all if not specified)
            patch(working_dir, enabled_patches=enabled_patches, verbose=self.logger.verbose)

        except Exception as e:
            raise SVNCommandError(f"Patch application failed: {e}") from e

    @staticmethod
    def _infer_action_type(action: dict) -> str:
        """Infer action type from configuration."""
        has_from = "from" in action
        has_to = "to" in action
        has_rev = "rev" in action
        empty = action.get("empty", False)
        patch = action.get("patch", False)

        if not has_from and has_to and patch:
            return "PATCH"
        elif has_from and has_to and has_rev and empty:
            return "EMPTY_MERGE"
        elif has_from and has_to and has_rev and patch:
            return "MERGE_WITH_PATCH"
        elif has_from and has_to and has_rev:
            return "MERGE"
        else:
            raise ValueError(f"Cannot infer action type from: {action}")
