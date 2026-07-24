import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import download_file


class DownloadM365File:
    """Downloads a file from OneDrive/SharePoint to a local folder, for a downstream
    tool (e.g. Import from Word, Read PowerPoint) to read. Reuses m365_graph_bridge's
    mock logic directly (no subprocess). Mock-mode until an Azure AD app registration
    exists."""

    def run(self, file_path: str, local_output_dir: str) -> dict:
        try:
            return {"success": True, **download_file(file_path, local_output_dir)}
        except Exception as e:
            return {"success": False, "response": f"download_m365_file error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"file_path": "...", "local_output_dir": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = DownloadM365File().run(file_path=params.get("file_path", ""), local_output_dir=params.get("local_output_dir", ""))
    except Exception as e:
        result = {"success": False, "response": f"download_m365_file error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
