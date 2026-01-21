# SVN Batch Actions - Example Configurations

This directory contains example configuration files for the `svn-batch` utility.

## Quick Start

```bash
# Review and execute actions
svn-batch example_configs/simple_patch.json

# Dry run (no actual changes)
svn-batch --dry-run example_configs/empty_merges.json

# Skip confirmation prompt
svn-batch -y example_configs/mixed_actions.json

# Verbose output
svn-batch -v example_configs/simple_patch.json
```

## Configuration Format

### Basic Structure

```json
{
  "repository_base": "svn://server/repo/path",
  "workspace": "./.temp",
  "log_dir": "./logs",
  "actions": [
    { /* action 1 */ },
    { /* action 2 */ }
  ]
}
```

### Configuration Fields

- **repository_base** (required): Base URL for the SVN repository
- **workspace** (optional): Directory for temporary checkouts (default: `./.temp`)
- **log_dir** (optional): Directory for log files (default: `./logs`)
- **actions** (required): Array of actions to execute

## Action Types

### 1. PATCH - Apply patches to a branch

Apply JSP UTF-8 patches to a specific branch without merging.

```json
{
  "to": "versions/version-1.5_mudetaf",
  "author": "username",
  "patch": true,
  "msg": "Apply UTF-8 encoding patches"
}
```

**Required fields:**
- `to`: Target branch path (relative to repository_base)
- `patch`: Must be `true`
- `msg`: Commit message

**Optional fields:**
- `author`: SVN username for commit

### 2. EMPTY_MERGE - Record merge info only

Record that a revision has been merged without applying actual changes.

```json
{
  "from": "versions/version-1.4_mudetaf",
  "to": "versions/version-1.5_mudetaf",
  "rev": "68000",
  "author": "username",
  "empty": true,
  "msg": "Record merge from version-1.4_mudetaf r68000"
}
```

**Required fields:**
- `from`: Source branch path
- `to`: Target branch path
- `rev`: Revision number to record
- `empty`: Must be `true`
- `msg`: Commit message

**Optional fields:**
- `author`: SVN username for commit

### 3. MERGE - Real merge with conflict detection

Merge changes from one branch to another. Aborts if conflicts are detected.

```json
{
  "from": "versions/version-1.4_mudetaf",
  "to": "versions/version-1.5_mudetaf",
  "rev": "68000",
  "author": "username",
  "empty": false,
  "msg": "Merge from version-1.4_mudetaf r68000"
}
```

**Required fields:**
- `from`: Source branch path
- `to`: Target branch path
- `rev`: Revision number to merge
- `msg`: Commit message

**Optional fields:**
- `author`: SVN username for commit
- `empty`: Set to `false` (default)
- `patch`: Set to `false` (default)

### 4. MERGE_WITH_PATCH - Merge + apply patches

Merge changes and then apply JSP UTF-8 patches.

```json
{
  "from": "versions/version-1.4_mudetaf",
  "to": "versions/version-1.5_mudetaf",
  "rev": "68000",
  "author": "username",
  "empty": false,
  "patch": true,
  "msg": "Merge from version-1.4_mudetaf r68000 with patches"
}
```

**Required fields:**
- `from`: Source branch path
- `to`: Target branch path
- `rev`: Revision number to merge
- `patch`: Must be `true`
- `msg`: Commit message

**Optional fields:**
- `author`: SVN username for commit
- `empty`: Set to `false` (default)

## Command Line Options

```
svn-batch [OPTIONS] CONFIG_FILE

Positional Arguments:
  CONFIG_FILE           Path to JSON configuration file

Options:
  -v, --verbose         Enable verbose output
  --dry-run             Simulate actions without making changes
  -y, --yes             Skip confirmation prompt
  --log-dir DIR         Override log directory from config
  --workspace DIR       Override workspace directory from config
  -h, --help            Show help message
```

## Logging

The utility creates comprehensive logs in the specified log directory:

- **Text log**: `svn_actions_YYYYMMDD_HHMMSS.log`
  - Human-readable log of all operations
  - Includes timestamps, steps, and errors

- **JSON log**: `svn_actions_YYYYMMDD_HHMMSS.json`
  - Machine-readable structured log
  - Contains complete action history
  - Tracks all modified files
  - Includes error details

### Log Contents

Each action is logged with:
- Configuration details
- Execution steps (checkout, merge, patch, commit)
- List of modified files
- Timestamps for each step
- Success/failure status
- Error messages if applicable

## Safety Features

1. **Validation**: Configuration is validated before execution
2. **Confirmation**: Requires user confirmation before running (unless `-y` flag is used)
3. **Conflict Detection**: Merges abort on conflicts and revert changes
4. **Stop on Error**: Execution stops at first error
5. **Comprehensive Logging**: All actions are logged for audit trail
6. **Workspace Cleanup**: Temporary directories are cleaned before and after each action
7. **Dry Run Mode**: Test configurations without making changes

## Examples

See the example configuration files:
- `simple_patch.json` - Apply patches to a single branch
- `empty_merges.json` - Record merge info for multiple branches
- `mixed_actions.json` - Combination of merge and patch operations

## Tips

1. **Always test first**: Use `--dry-run` to verify your configuration
2. **Use verbose mode**: Add `-v` when troubleshooting
3. **Check logs**: Review log files after execution
4. **Backup important branches**: Make backups before running merge operations
5. **Test on one branch**: Start with a single action before running multiple
