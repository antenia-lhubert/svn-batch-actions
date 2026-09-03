# SVN Batch Actions

Automate batch SVN operations with JSON-driven workflows. Execute merges, patches, and commits across multiple branches using modular, composable actions.

## Installation

Requires Python ≥3.11

```bash
pip install -e .
```

## Usage

```bash
svn-batch config.json [options]
```

**Options:**
- `--dry-run` - Validate config and show execution plan without making changes
- `--no-commit` - Checkout and apply patches but skip commit (preserves workspace for review)
- `--apply-only` - Skip checkout and apply patches to existing workspace only
- `-y` / `--yes` - Skip confirmation prompt
- `--verbose` / `-v` - Show detailed output

### Example 1: Apply patches and commit

**Command:**
```bash
svn-batch patch.json -y
```

**Config (patch.json):**
```json
{
  "repository_base": "svn://server/repo",
  "workspace": "./.temp",
  "actions": [
    {
      "to": "branches/feature",
      "patch": true,
      "enabled_patches": ["editorconfig_encoding"],
      "msg": "Apply encoding transformations"
    }
  ]
}
```

### Example 2: Merge revision with patches

**Command:**
```bash
svn-batch merge.json -y
```

**Config (merge.json):**
```json
{
  "repository_base": "svn://server/repo",
  "workspace": "./.temp",
  "actions": [
    {
      "from": "trunk",
      "to": "branches/feature",
      "rev": "12345",
      "author": "username",
      "conflict_resolution": "theirs-conflict",
      "patch": true,
      "enabled_patches": ["editorconfig_encoding"],
      "msg": "Merge r12345 from trunk and apply patches"
    }
  ]
}
```

### Example 3: Test configuration (dry run)

**Command:**
```bash
svn-batch merge.json --dry-run
```

Use any config file - validates without making changes.

### Example 4: Apply patches without committing

**Command:**
```bash
svn-batch patch.json --no-commit -y
```

Performs checkout and applies patches but skips commit. Workspace preserved for manual review.

### Example 5: Re-apply patches to existing workspace

**Command:**
```bash
svn-batch patch.json --apply-only -y
```

Skips checkout, applies patches to already-checked-out workspace, then commits.

### Example 6: Multiple actions in sequence

**Command:**
```bash
svn-batch batch.json -y
```

**Config (batch.json):**
```json
{
  "repository_base": "svn://server/repo",
  "workspace": "./.temp",
  "log_dir": "./logs",
  "actions": [
    {
      "from": "trunk",
      "to": "branches/v1.4",
      "rev": "12345",
      "author": "username",
      "empty": true,
      "msg": "Block r12345 from trunk"
    },
    {
      "from": "trunk",
      "to": "branches/v1.5",
      "rev": "12345",
      "author": "username",
      "msg": "Merge r12345 from trunk: Fix login bug"
    },
    {
      "to": "branches/v1.5",
      "patch": true,
      "msg": "Apply encoding patches"
    }
  ]
}
```

## Configuration

JSON config defines repository base, workspace, and action sequences:

```json
{
  "repository_base": "svn://server/repo",
  "workspace": "./.temp",
  "log_dir": "./logs",
  "checkout_depth": "files",
  "actions": [...]
}
```

To update the target project's root `pom.xml` version, enable the `pom_version` patch and provide the new version in the action:

```json
{
  "to": "branches/feature",
  "patch": true,
  "enabled_patches": ["pom_version"],
  "pom_version": "2.1.0",
  "msg": "Set project version to 2.1.0"
}
```

The patch changes only the `<version>` element directly under `<project>`. Parent, dependency, and plugin versions are not changed. If `enabled_patches` is omitted, this patch runs automatically when `pom_version` is present.

`checkout_depth` is optional and accepts SVN's `empty`, `files`, `immediates`, or `infinity` values. Use `"files"` to check out the project root and only the files directly in it. It can also be set on an individual action, which overrides the top-level value:

```json
{
  "to": "branches/feature",
  "patch": true,
  "checkout_depth": "files",
  "msg": "Patch project root files"
}
```

Record-only (`empty`) merges always use `--depth empty`, regardless of this setting. Successful commits always print the committed revision, even without `--verbose`.

Regular merge actions can opt into automatic resolution of text and property conflicts with `conflict_resolution`. It accepts SVN's conflict-resolution terminology:

- `mine-conflict`: Keep the current target-branch changes in conflicting regions.
- `theirs-conflict`: Keep the incoming merge changes in conflicting regions.

Both strategies preserve non-conflicting changes from the other side:

```json
{
  "from": "trunk",
  "to": "branches/feature",
  "rev": "12345",
  "conflict_resolution": "theirs-conflict",
  "msg": "Merge r12345 using incoming changes for conflicts"
}
```

The option is valid only for non-empty merge actions. Any conflict SVN cannot resolve automatically, including unresolved tree conflicts, still aborts the action and reverts the merge. Without `conflict_resolution`, the default abort-and-revert behavior is unchanged.

### Action Types

**PATCH (patches only):**
```json
{
  "to": "branches/feature",
  "patch": true,
  "enabled_patches": ["editorconfig_encoding"],
  "msg": "Apply encoding transformations"
}
```

**MERGE (real merge):**
```json
{
  "from": "trunk",
  "to": "branches/feature",
  "rev": "12345",
  "author": "username",
  "conflict_resolution": "theirs-conflict",
  "msg": "Merge r12345 from trunk: Fix login bug"
}
```

**EMPTY_MERGE (record-only merge):**
```json
{
  "from": "trunk",
  "to": "branches/feature",
  "rev": "12345",
  "author": "username",
  "empty": true,
  "msg": "Block r12345 from trunk"
}
```

**MERGE_WITH_PATCH (merge + patches):**
```json
{
  "from": "trunk",
  "to": "branches/feature",
  "rev": "12345",
  "author": "username",
  "patch": true,
  "enabled_patches": ["editorconfig_encoding"],
  "msg": "Merge r12345 and apply encoding patches"
}
```

## Adding New Patches

Patches are modular transformations applied to working directories during SVN operations.

**1. Create patch file:**

Create `src/svn_batch_actions/patches/my_patch.py`:

```python
from pathlib import Path

def apply(working_dir: Path, verbose: bool = False) -> None:
    """
    Apply your custom transformation.

    Args:
        working_dir: Root directory of checked-out SVN project
        verbose: Enable detailed output
    """
    if verbose:
        print("Applying my_patch...")

    # Your transformation logic here
    for file_path in working_dir.rglob("*.txt"):
        # Process files...
        pass

    if verbose:
        print("my_patch complete")
```

**2. Register patch:**

Edit `src/svn_batch_actions/patches/__init__.py`:

```python
# Import your patch
from . import my_patch

# Add to registry
AVAILABLE_PATCHES = {
    "jsp_utf8": jsp_utf8,
    "editorconfig_encoding": editorconfig_encoding,
    "my_patch": my_patch,  # Add this line
}
```

**3. Add dependencies (if needed):**

Edit `pyproject.toml` dependencies array, then run:

```bash
pip install -e .
```

**4. Use in config:**

```json
{
  "to": "branches/feature",
  "patch": true,
  "enabled_patches": ["my_patch"],
  "msg": "Apply custom transformation"
}
```

Done. The patch will now run when `"patch": true` is set.

## Built-in Patches

**`jsp_utf8`**: Converts JSP files to UTF-8 encoding

**`editorconfig_encoding`**: Transforms file encodings and line endings based on `.editorconfig` rules in the checked-out project
- Detects current encodings automatically
- Supports UTF-8, UTF-8-BOM, UTF-16BE/LE, Latin-1, Windows-1252
- Normalizes line endings (LF, CRLF, CR)
- Handles BOM addition/removal
- Skips binary files automatically

**`pom_version`**: Sets the direct project version in the target project's root `pom.xml` from the action's `pom_version` field
- Preserves parent, dependency, and plugin versions
- Preserves the rest of the POM without XML reformatting
- Requires a UTF-8 encoded `pom.xml` with an existing direct project `<version>` element
