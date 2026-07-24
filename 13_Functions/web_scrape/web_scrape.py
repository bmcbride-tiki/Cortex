import sys
import json
from typing import Dict, Any


class WebScrape:
    """Fetches a URL and extracts its visible, readable text (strips script/style
    blocks). Only use this for pages you have the right to access. Extracted from
    workflow_engine.py's function_web_scrape node (_scrape_url) so it can run
    standalone or be dropped into a workflow (dispatched via CoreRouter's generic
    09_Functions path)."""

    def run(self, url: str) -> Dict[str, Any]:
        if not url:
            return {"success": False, "response": "A url is required."}

        import requests
        from lxml import html as lxml_html

        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (Workbrain Workflow Builder)"})
        resp.raise_for_status()
        tree = lxml_html.fromstring(resp.text)
        for bad in tree.xpath("//script | //style"):
            bad.getparent().remove(bad)
        text = " ".join(t.strip() for t in tree.xpath("//text()") if t.strip())

        return {"success": True, "text": text[:5000]}  # capped so one scrape can't flood downstream context


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"url": "https://..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = WebScrape().run(url=params.get("url", ""))
    except Exception as e:
        result = {"success": False, "response": f"web_scrape error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
