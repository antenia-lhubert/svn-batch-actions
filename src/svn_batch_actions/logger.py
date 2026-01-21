"""Comprehensive logging system for SVN batch actions."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class ActionLogger:
    """Logger for tracking all SVN batch actions."""

    def __init__(self, log_dir: Path, verbose: bool = False):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"svn_actions_{timestamp}.log"
        self.json_log_file = self.log_dir / f"svn_actions_{timestamp}.json"

        self.actions_log = []
        self.current_action = None

        self._write_header()

    def _write_header(self):
        """Write log file header."""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("SVN Batch Actions Log\n")
            f.write(f"Started: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")

    def start_action(self, action_index: int, action_data: dict):
        """Start logging a new action."""
        self.current_action = {
            "index": action_index,
            "action": action_data.copy(),
            "start_time": datetime.now().isoformat(),
            "status": "in_progress",
            "steps": [],
            "files_modified": [],
            "errors": []
        }

        action_type = self._infer_action_type(action_data)
        msg = f"\n{'=' * 80}\n"
        msg += f"Action {action_index + 1}: {action_type}\n"
        msg += f"Started: {self.current_action['start_time']}\n"
        msg += f"Configuration: {json.dumps(action_data, indent=2)}\n"
        msg += "=" * 80 + "\n"

        self._log(msg)

    def log_step(self, step_name: str, details: str = ""):
        """Log a step within the current action."""
        timestamp = datetime.now().isoformat()
        step_data = {
            "step": step_name,
            "timestamp": timestamp,
            "details": details
        }

        if self.current_action:
            self.current_action["steps"].append(step_data)

        msg = f"[{timestamp}] {step_name}"
        if details:
            msg += f"\n  {details}"
        msg += "\n"

        self._log(msg)

    def log_files_modified(self, files: list[str]):
        """Log modified files."""
        if self.current_action:
            self.current_action["files_modified"] = files

        if files:
            msg = f"Modified files ({len(files)}):\n"
            for file in files:
                msg += f"  - {file}\n"
            self._log(msg)

    def log_error(self, error: str):
        """Log an error."""
        timestamp = datetime.now().isoformat()

        if self.current_action:
            self.current_action["errors"].append({
                "timestamp": timestamp,
                "error": error
            })

        msg = f"[{timestamp}] ERROR: {error}\n"
        self._log(msg, file=sys.stderr)

    def complete_action(self, success: bool, summary: str = ""):
        """Complete the current action."""
        if not self.current_action:
            return

        self.current_action["end_time"] = datetime.now().isoformat()
        self.current_action["status"] = "success" if success else "failed"
        self.current_action["summary"] = summary

        self.actions_log.append(self.current_action)

        status = "SUCCESS" if success else "FAILED"
        msg = f"\n{status}: {summary}\n"
        msg += f"Completed: {self.current_action['end_time']}\n"
        msg += "-" * 80 + "\n"

        self._log(msg)

        self.current_action = None

    def finalize(self, total_actions: int, successful: int, failed: int):
        """Finalize and save all logs."""
        summary_msg = f"\n{'=' * 80}\n"
        summary_msg += "FINAL SUMMARY\n"
        summary_msg += f"{'=' * 80}\n"
        summary_msg += f"Total actions: {total_actions}\n"
        summary_msg += f"Successful: {successful}\n"
        summary_msg += f"Failed: {failed}\n"
        summary_msg += f"Completed: {datetime.now().isoformat()}\n"
        summary_msg += "=" * 80 + "\n"

        self._log(summary_msg)

        # Save JSON log
        json_data = {
            "start_time": self._get_first_action_time(),
            "end_time": datetime.now().isoformat(),
            "summary": {
                "total": total_actions,
                "successful": successful,
                "failed": failed
            },
            "actions": self.actions_log
        }

        with open(self.json_log_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        print(f"\nLogs saved:")
        print(f"  Text log: {self.log_file}")
        print(f"  JSON log: {self.json_log_file}")

    def _get_first_action_time(self) -> str:
        """Get the start time of the first action."""
        if self.actions_log:
            return self.actions_log[0].get("start_time", datetime.now().isoformat())
        return datetime.now().isoformat()

    def _log(self, message: str, file=sys.stdout):
        """Write message to log file and optionally to console."""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(message)

        if self.verbose:
            print(message, end='', file=file)

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
            return "UNKNOWN"
