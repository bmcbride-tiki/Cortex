import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_sharepoint_list_item import CreateSharepointListItem


def test_run_creates_item():
    result = CreateSharepointListItem().run("site_1", "list_1", {"Title": "New Item"})
    assert result["success"] is True
    assert result["item_id"].startswith("item_")


if __name__ == "__main__":
    test_run_creates_item()
    print("All create_sharepoint_list_item self-checks passed.")
