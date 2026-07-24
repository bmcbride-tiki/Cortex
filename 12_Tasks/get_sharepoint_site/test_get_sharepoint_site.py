import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from get_sharepoint_site import GetSharepointSite


def test_run_returns_site():
    result = GetSharepointSite().run("example.sharepoint.com:/sites/apprenticeship")
    assert result["success"] is True
    assert result["id"].startswith("site_")


if __name__ == "__main__":
    test_run_returns_site()
    print("All get_sharepoint_site self-checks passed.")
