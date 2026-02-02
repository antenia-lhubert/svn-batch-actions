# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python tool for automating batch SVN operations, specifically designed for managing complex merge and patch workflows across SVN branches. The tool executes sequences of SVN actions defined in JSON configuration files, handling merges, patches, and commits with comprehensive logging.

## Development Commands

### Setup
```bash
# Create and activate virtual environment (Windows)
python -m venv .venv
.venv\Scripts\activate

# Install in development mode
pip install -e .[dev]
```

### Code Formatting
```bash
# Format code with Black (line length 120)
black .
```

### Running the Tools
```bash
# Main tool: Execute SVN batch actions from a config file
svn-batch <config.json> [--dry-run] [--verbose] [-y]

# List SVN branches with filtering
list-svn-branches <repo_url> [-p pattern] [-v] [-f] [-o output.txt]
```

## Architecture

### Entry Points (pyproject.toml)
- **`svn-batch`**: Main CLI tool (`svn_batch_actions.__main__:main`)
- **`list-svn-branches`**: Branch listing utility (`list_svn_branches.__main__:main`)

### Core Components

#### 1. Action Execution Flow (`svn_batch_actions/actions.py`)
`ActionExecutor` orchestrates the entire action workflow:
- **Action Types**: Inferred from JSON config structure:
  - `PATCH`: Apply patches without merge (`to`, `patch=true`, `msg`)
  - `EMPTY_MERGE`: Record-only merge (`from`, `to`, `rev`, `empty=true`, `msg`)
  - `MERGE`: Real merge with changes (`from`, `to`, `rev`, `msg`)
  - `MERGE_WITH_PATCH`: Merge followed by patches (`from`, `to`, `rev`, `patch=true`, `msg`)

- **Execution Pattern**: For each action:
  1. Checkout target branch to workspace
  2. Perform merge/patch operations
  3. Apply patches if specified
  4. Commit changes with provided message
  5. Cleanup workspace directory

#### 2. SVN Operations (`svn_batch_actions/utils.py`)
Low-level SVN command wrappers:
- **`svn_checkout()`**: Supports `--depth` for sparse checkouts (used in empty merges)
- **`svn_merge()`**: Returns `(success, output)` tuple; detects conflicts differently for record-only vs regular merges
- **`svn_commit()`**: Auto-adds files with `svn add --force`
- **`fix_mergeinfo_inheritance()`**: Removes non-inheritable markers (`*`) from specific revisions in `svn:mergeinfo` property (addresses sparse checkout side effects)

**Windows-specific handling**: `cleanup_directory()` removes readonly attributes for SVN locked files.

#### 3. Logging System (`svn_batch_actions/logger.py`)
Dual-format logging (text + JSON):
- **Text log**: Human-readable with timestamps, steps, and error details
- **JSON log**: Structured data for post-processing/analysis
- Both files timestamped: `svn_actions_YYYYMMDD_HHMMSS.{log,json}`
- Logs saved to `./logs/` by default (configurable via `--log-dir`)

#### 4. Patch System (`svn_batch_actions/patches/`)
Modular patch application framework:
- **Registry pattern**: `AVAILABLE_PATCHES` dict in `__init__.py`
- **Patch interface**: Each patch module must implement `apply(working_dir: Path, verbose: bool)`
- **Current patches**: `jsp_utf8` (built-in)
- Called automatically when `"patch": true` in action config
- Applies all registered patches unless `enabled_patches` list specified

### Configuration Format

JSON structure validated at load time:
```json
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
      "msg": "Record merge"
    }
  ]
}
```

**Required fields**: `repository_base`, `actions`
**Action validation**: Done in `__main__.py:validate_action()`; stops execution on validation errors before any SVN operations.

### Error Handling

- **Stop on first failure**: Actions execute sequentially; first error stops execution
- **Conflict detection**: Merge conflicts trigger `svn revert -R` and raise `SVNCommandError`
- **Detailed failure reporting**: Shows failed action config, error type, message, and optional traceback (`--verbose`)
- **Workspace cleanup**: Always runs in `finally` blocks to ensure working directories are removed

## Key Implementation Details

- **Workspace isolation**: Each action checks out to `workspace/<branch-name>/` subdirectory
- **Sparse checkouts for empty merges**: Uses `--depth empty` to minimize checkout size when only recording mergeinfo
- **Mergeinfo fix**: After sparse checkout empty merge, non-inheritable markers must be removed manually (handled by `fix_mergeinfo_inheritance()`)
- **Windows compatibility**: Special handling for file locks and readonly attributes during cleanup
- **Dry run mode**: Skips all actual SVN operations but runs validation and shows execution plan
- **Confirmation prompt**: Interactive `[y/N]` confirmation before execution (skip with `-y`)

## Adding New Patches

1. Create `src/svn_batch_actions/patches/my_patch.py`
2. Implement: `def apply(working_dir: Path, verbose: bool = False) -> None:`
3. Import in `patches/__init__.py`: `from . import my_patch`
4. Add to `AVAILABLE_PATCHES`: `"my_patch": my_patch,`

The patch will automatically apply when `"patch": true` is set in any action.
