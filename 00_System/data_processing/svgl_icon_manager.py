# =============================================================================
# svgl_icon_manager.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Resolves a brand name (like "m365" or "openai") to the web address of
#   its real logo, hosted by SVGL (https://svgl.app), a free public library
#   of app/company logos. This is what puts a real Microsoft Outlook icon
#   next to an Outlook building block instead of a generic placeholder.
#   Can also download and cache a logo's actual SVG file locally, for future
#   use somewhere that needs the raw image rather than just a URL.
#
# WHAT IT INTERACTS WITH
#   - `https://svgl.app`, the external logo library this queries/downloads
#     from. `get_icon_url()` never makes a network call itself -- it just
#     builds the URL string; only `fetch_and_cache_svg()` actually reaches
#     out over the network (via the `httpx` package).
#   - `server.py`, which calls `get_icon_url()`-equivalent lookups (via its
#     own `TOOL_SVGL_MAP`) to attach a real product logo to each Workflow
#     Builder palette entry and canvas node.
#   - `canvas_schema.py`'s `CanvasNode`, which auto-resolves its own SVGL
#     icon URL through this file when a node's style says `icon_source: svgl`.
#   - `00_System/data_processing/svg_cache/`, created next to this file the
#     first time `fetch_and_cache_svg()` is used -- holds downloaded `.svg`
#     files so repeat lookups for the same brand don't re-download it.
#
# KEY FUNCTIONALITY NOTES
#   - `get_icon_url()` never fails or raises -- if a brand key isn't in the
#     known `SVGL_FALLBACK_MAP`, it just builds a best-guess URL from the
#     brand name directly (`https://svgl.app/library/<name>.svg`), which
#     may or may not actually exist on SVGL's site.
#   - `fetch_and_cache_svg()` is the "actually download the picture" method
#     -- if the network call fails for any reason, it falls back to a tiny
#     generated placeholder SVG (a colored square with the brand's first
#     two letters) rather than leaving the caller with nothing at all.
# =============================================================================

from pathlib import Path
import httpx

# SVGL Base Endpoints
SVGL_API_SEARCH = "https://api.svgl.app?search="
SVGL_BASE_URL = "https://svgl.app/"

# Local Fallback Mapping for Core Connectors
SVGL_FALLBACK_MAP = {
    "m365": "https://svgl.app/library/microsoft.svg",
    "google": "https://svgl.app/library/google.svg",
    "google_drive": "https://svgl.app/library/google-drive.svg",
    "notion": "https://svgl.app/library/notion.svg",
    "openai": "https://svgl.app/library/openai.svg",
    "telegram": "https://svgl.app/library/telegram.svg",
    "postgres": "https://svgl.app/library/postgresql.svg",
    "brightdata": "https://svgl.app/library/brightdata.svg"
}

class SvglIconManager:
    """Fetches, caches, and resolves brand SVGs from SVGL (https://svgl.app)."""

    CACHE_DIR = Path(__file__).resolve().parent / "svg_cache"

    @classmethod
    def ensure_cache_dir(cls):
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_icon_url(cls, brand_key: str) -> str:
        """Returns the cached or direct SVGL URL for a brand logo."""
        key_lower = brand_key.lower().replace(" ", "")

        for k, url in SVGL_FALLBACK_MAP.items():
            if k in key_lower:
                return url

        return f"{SVGL_BASE_URL}library/{key_lower}.svg"

    @classmethod
    def fetch_and_cache_svg(cls, brand_key: str) -> str:
        """Downloads the SVG from SVGL and stores it locally inside 00_System/data_processing/svg_cache/."""
        cls.ensure_cache_dir()
        local_path = cls.CACHE_DIR / f"{brand_key.lower()}.svg"

        if local_path.exists():
            return local_path.read_text(encoding="utf-8")

        url = cls.get_icon_url(brand_key)
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                svg_content = response.text
                local_path.write_text(svg_content, encoding="utf-8")
                return svg_content
        except Exception:
            pass

        # Generic Fallback inline SVG
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><rect width="24" height="24" fill="#3B82F6" rx="4"/><text x="12" y="16" font-size="10" fill="#FFF" text-anchor="middle">{brand_key[:2].upper()}</text></svg>'
