# =============================================================================
# generate_pptx_from_word_with_copilot.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: has M365 Copilot generate/populate a PowerPoint from a Word
#   file. Tagged model="copilot" in server.py's TOOL_MODELS (not plain
#   "m365"), even though it dispatches through m365_graph_bridge, since it
#   represents Copilot's presentation-generation feature specifically.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `generate_pptx_from_word()`, called directly in-process (no
#     subprocess). Mock mode performs a mechanical conversion, not genuine
#     AI restructuring -- see that function's own docstring.
#   - `test_generate_pptx_from_word_with_copilot.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `word_file_path`/`output_dir`/`filename` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import generate_pptx_from_word


class GeneratePptxFromWordWithCopilot:
    """Has M365 Copilot generate/populate a PowerPoint from a Word file. Classified as
    a Copilot connection, not plain M365 (see server.py's TOOL_MODELS -- this tool_id
    is tagged model="copilot"). Reuses m365_graph_bridge's mock logic directly (no
    subprocess); see that function's docstring for the honest limitation that mock
    mode performs a mechanical conversion, not genuine AI restructuring."""

    def run(self, word_file_path: str, output_dir: str, filename: str) -> dict:
        try:
            return {"success": True, **generate_pptx_from_word(word_file_path, output_dir, filename)}
        except Exception as e:
            return {"success": False, "response": f"generate_pptx_from_word_with_copilot error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"word_file_path": "...", "output_dir": "...", "filename": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = GeneratePptxFromWordWithCopilot().run(
            word_file_path=params.get("word_file_path", ""),
            output_dir=params.get("output_dir", ""),
            filename=params.get("filename", ""),
        )
    except Exception as e:
        result = {"success": False, "response": f"generate_pptx_from_word_with_copilot error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
