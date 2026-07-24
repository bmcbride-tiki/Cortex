import sys
import json
from typing import Dict, Any


class FormatJson:
    """Parses text as JSON and re-serializes it pretty-printed; fails clearly if it
    isn't valid JSON. Extracted from workflow_engine.py's function_json_parse node so
    it can run standalone or be dropped into a workflow (dispatched via CoreRouter's
    generic 09_Functions path)."""

    def run(self, text: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            return {"success": False, "response": f"Invalid JSON: {e}"}
        return {"success": True, "text": json.dumps(parsed, indent=2)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"text": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = FormatJson().run(text=params.get("text", ""))
    except Exception as e:
        result = {"success": False, "response": f"format_json error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
