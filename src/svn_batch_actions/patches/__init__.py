"""Patch application system for SVN batch actions.

This package contains various patches that can be applied to working directories
during SVN batch operations.

To add a new patch:
1. Create a new .py file in this directory (e.g., my_patch.py)
2. Implement an apply(working_dir: Path, verbose: bool = False) function
3. Import it and add it to AVAILABLE_PATCHES below
4. Add the patch name to enabled_patches when calling patch()

Configurable patches can declare CONFIG_KEY and accept its value between
working_dir and verbose in their apply function.
"""

from pathlib import Path
from typing import List

# Import available patches
from . import jsp_utf8
from . import editorconfig_encoding
from . import pom_version


# Registry of all available patches
# Each patch module must have an apply(working_dir: Path, verbose: bool) function
AVAILABLE_PATCHES = {
    "jsp_utf8": jsp_utf8,
    "editorconfig_encoding": editorconfig_encoding,
    "pom_version": pom_version,
}


def patch(
    working_dir: Path,
    enabled_patches: List[str] = None,
    verbose: bool = False,
    action_config: dict = None,
) -> None:
    """
    Apply patches to the working directory.

    Args:
        working_dir: Root directory to apply patches to
        enabled_patches: List of patch names to apply. If None, applies all patches.
                        Configurable patches are included only when their config is present.
        verbose: Enable verbose output
        action_config: Configuration for the action invoking the patches

    Raises:
        ValueError: If an unknown patch name is specified
        Exception: If any patch application fails

    Examples:
        # Apply all patches
        patch(working_dir, verbose=True)

        # Apply only specific patches
        patch(working_dir, enabled_patches=["jsp_utf8"], verbose=True)

        # Apply multiple patches
        patch(working_dir, enabled_patches=["jsp_utf8", "my_custom_patch"], verbose=True)
    """
    action_config = action_config or {}

    # Default to all patches that have the configuration they require.
    if enabled_patches is None:
        enabled_patches = [
            name
            for name, module in AVAILABLE_PATCHES.items()
            if not getattr(module, "CONFIG_KEY", None) or module.CONFIG_KEY in action_config
        ]

    if not enabled_patches:
        if verbose:
            print("No patches enabled, skipping patch application")
        return

    # Validate patch names
    unknown_patches = set(enabled_patches) - set(AVAILABLE_PATCHES.keys())
    if unknown_patches:
        raise ValueError(
            f"Unknown patch(es): {', '.join(unknown_patches)}. "
            f"Available patches: {', '.join(AVAILABLE_PATCHES.keys())}"
        )

    if verbose:
        print(f"Applying {len(enabled_patches)} patch(es): {', '.join(enabled_patches)}")

    # Apply each enabled patch
    for patch_name in enabled_patches:
        if verbose:
            print(f"\n--- Applying patch: {patch_name} ---")

        patch_module = AVAILABLE_PATCHES[patch_name]
        try:
            config_key = getattr(patch_module, "CONFIG_KEY", None)
            if config_key:
                if config_key not in action_config:
                    raise ValueError(f"Patch '{patch_name}' requires action field '{config_key}'")
                patch_module.apply(working_dir, action_config[config_key], verbose)
            else:
                patch_module.apply(working_dir, verbose)
        except Exception as e:
            raise Exception(f"Patch '{patch_name}' failed: {e}") from e

    if verbose:
        print(f"\nAll patches applied successfully")
