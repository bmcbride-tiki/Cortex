# =============================================================================
# generate_vault_map.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Walks the whole Cortex project folder and writes a plain-text tree
#   diagram of it (like the output of the `tree` command) to
#   `vault_map.txt`, right next to this script. A zero-input, one-click
#   Process -- no settings, just "map what's here right now."
#
# WHAT IT INTERACTS WITH
#   - The entire project folder tree, read-only (skips `venv`, `.git`,
#     `__pycache__`).
#   - `vault_map.txt`, overwritten each time this runs.
#   - `core_router.py`, which discovers and launches this script the same
#     way as every other Process (see CLAUDE.md's directory rules).
# =============================================================================

from pathlib import Path
from typing import Dict, Any

class VaultMapGenerator:
    def __init__(self):
        self.root_dir = Path(__file__).resolve().parents[2]
        self.output_txt = Path(__file__).resolve().parent / "vault_map.txt"

    def _build_tree(self, directory: Path, prefix: str = "") -> list:
        tree = []
        try:
            # Exclude virtual environments and hidden metadata parameters
            items = sorted([x for x in directory.iterdir() if x.name not in ["venv", ".git", "__pycache__"]])
            for i, item in enumerate(items):
                is_last = (i == len(items) - 1)
                connector = "└── " if is_last else "├── "
                tree.append(f"{prefix}{connector}{item.name}")
                if item.is_dir():
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    tree.extend(self._build_tree(item, next_prefix))
        except Exception:
            pass
        return tree

    def run(self) -> Dict[str, Any]:
        report = {"success": True, "mapped_nodes": 0, "output_file": "vault_map.txt", "errors": []}
        try:
            lines = [f"Workbrain Workspace Architecture Map", "=" * 40]
            tree_lines = self._build_tree(self.root_dir)
            lines.extend(tree_lines)
            report["mapped_nodes"] = len(tree_lines)
            
            with open(self.output_txt, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            report["errors"].append(f"Map construction failed: {str(e)}")
            report["success"] = False
        return report

if __name__ == "__main__":
    print(VaultMapGenerator().run())