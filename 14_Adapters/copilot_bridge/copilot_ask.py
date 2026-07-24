# =============================================================================
# copilot_ask.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   An earlier, experimental version of the Microsoft 365 Copilot automation
#   engine, built as a reusable class (`CopilotBridge`) rather than a set of
#   standalone functions. It can do everything `copilot_bridge.py` can for
#   plain text questions, plus two things that file's current production
#   version does not: attaching a local file to the question (so Copilot can
#   read/summarize it) and detecting + downloading a file Copilot generates
#   in its reply (e.g. a Word document it creates for you).
#
# WHAT IT INTERACTS WITH
#   - Microsoft Edge, automated via the Playwright library, exactly like
#     `copilot_bridge.py` -- opens a browser window (visible or invisible),
#     types your question in, and reads back the answer that appears.
#   - Your saved Microsoft Edge login session, stored in a folder called
#     "copilot_browser_profile" (or a suffixed variant -- see `profile_name`
#     below) next to this file.
#   - m365.cloud.microsoft (Microsoft's Copilot chat website).
#   - SharePoint / OneDrive links, when Copilot's reply includes a document
#     it generated -- this file has extra logic to turn those "open in
#     browser" links into direct download links.
#   - The local filesystem, both for reading a file you want to hand to
#     Copilot and for saving a file Copilot hands back to you.
#
# KEY FUNCTIONALITY NOTES
#   - THIS FILE IS NOT CURRENTLY WIRED INTO THE ROUTER OR THE CORTEX WEB APP.
#     Only the small manual test scripts in this folder
#     (run_copilot_test.py, run_copilot_download_test.py,
#     copilot_prompt_engineer.py) use it. The system's actual production
#     Copilot integration is `copilot_bridge.py`, which the router,
#     workflow builder, and Cortex "M365 Copilot" page all call. Think of
#     this file as a more advanced prototype whose file-upload and
#     file-download features haven't been merged into the production
#     adapter yet.
#   - `profile_name` lets you run more than one of these automations at the
#     same time without them fighting over the same saved login files --
#     each distinct profile_name gets its own separate folder on disk.
#   - The class watches the page for a settled/finished answer using the
#     same basic idea as `copilot_bridge.py`: check the visible text
#     repeatedly, and consider Copilot "done" once the text stops growing
#     for a few seconds in a row (rather than growing because it's still
#     typing, or still researching).
# =============================================================================

import os
import sys
import time
import urllib.parse
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright, Page, Locator

# Resolve directories relative to this file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROFILE_DIR = os.path.join(SCRIPT_DIR, "copilot_browser_profile")


class CopilotBridge:
    """A highly robust, scalable automation bridge for Microsoft 365 Copilot (BizChat).

    Handles authentication persistence, file uploads, smart wait times, and direct
    downloads of generated assets via localized message scanning.
    """

    def __init__(
        self,
        profile_name: str = "default",
        headless: bool = True,
        download_dir: Optional[str] = None,
    ):
        """Initializes the Copilot Bridge.

        Args:
            profile_name (str): Suffix appended to the browser profile folder.
                                Allows concurrent workers to avoid locking conflicts.
            headless (bool): Run browser in background (headless) or foreground.
            download_dir (str): Base folder to store downloaded files.
        """
        self.headless = headless

        # Concurrency protection: dynamically route to separate folders if profiles differ.
        # If you ever need two of these bridges running at once (e.g. two scripts
        # at the same time), giving each a different profile_name stops them from
        # trying to use the exact same saved-login folder simultaneously, which
        # Edge does not allow.
        if profile_name == "default":
            self.user_data_dir = DEFAULT_PROFILE_DIR
        else:
            self.user_data_dir = os.path.join(SCRIPT_DIR, f"copilot_browser_profile_{profile_name}")

        # Resolve the default downloads directory
        if download_dir:
            self.download_dir = os.path.abspath(download_dir)
        else:
            self.download_dir = os.path.join(SCRIPT_DIR, "downloads")

    @staticmethod
    def _clean_response(raw_text: str) -> str:
        """Strips Microsoft's interactive UI controls and feedback strings from the response."""
        # When we read the text off the page, it comes bundled together with
        # button labels that are visually separate but textually part of the
        # same block (e.g. "Copy", "Share", "Thumbs up"). This function
        # removes that clutter so what's returned is just Copilot's actual
        # written answer.
        if not raw_text:
            return ""
        clean_text = raw_text.strip()
        ui_footers = [
            "Provide your feedback on BizChat",
            "Provide your feedback",
            "Feedback",
            "Copy response",
            "Share response",
            "Copy",
            "Share",
            "Thumbs up",
            "Thumbs down",
        ]
        for footer in ui_footers:
            clean_text = clean_text.replace(footer, "")
        return clean_text.strip()

    @staticmethod
    def _extract_prompt_from_url(url: str) -> str:
        """Extracts the 'q' query parameter from a constructed Microsoft Copilot URL."""
        # This is the reverse of what copilot_prompt_engineer.py's
        # generate_copilot_url() does: given a URL like
        # ".../chat/?q=what%20is%20the%20time", this pulls "what is the time"
        # back out, so the rest of this class can log/track what question was
        # actually asked even when it arrived as part of a web address.
        try:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            return params.get("q", [""])[0]
        except Exception as e:
            print(f"[Warning] Failed to parse prompt query from URL: {e}")
            return ""

    @staticmethod
    def _make_sharepoint_direct_download(href: str) -> str:
        """Converts a SharePoint/OneDrive viewer URL into a direct-download API call."""
        # When Copilot generates a document, the link it shows you usually
        # opens that document in a web viewer (like opening a Word doc in
        # your browser), not a "Save As" download. This function rewrites
        # that viewer link into a special address that tells SharePoint/
        # OneDrive to hand over the actual file bytes instead, so the
        # automation can save a real local copy of it.
        try:
            parsed = urllib.parse.urlparse(href)
            params = urllib.parse.parse_qs(parsed.query)

            # Extract the unique document GUID if available
            sourcedoc = (
                params.get('sourcedoc', [None])[0] or
                params.get('UniqueId', [None])[0] or
                params.get('id', [None])[0]
            )

            # Scenario A: Standard SharePoint Viewer page
            if "_layouts/15" in parsed.path and sourcedoc:
                path_parts = parsed.path.split("/_layouts/15")
                base_path = path_parts[0]
                return f"{parsed.scheme}://{parsed.netloc}{base_path}/_layouts/15/download.aspx?UniqueId={sourcedoc}"

            # Scenario B: Sharing URL patterns
            if any(pattern in parsed.path for pattern in ["/:w:/", "/:x:/", "/:p:/", "/:b:/", "/:u:/"]):
                if "download=1" not in parsed.query:
                    separator = "&" if parsed.query else "?"
                    return f"{href}{separator}download=1"

        except Exception as e:
            print(f"[Warning] Failed to convert SharePoint link: {e}")

        return href

    def ask(
        self,
        prompt_text: str = "",
        target_url: str = "",
        file_to_upload: Optional[str] = None,
        expect_file_download: bool = False,
        custom_download_dir: Optional[str] = None,
        timeout: int = 180,
    ) -> Dict[str, Any]:
        """Submits a query to Microsoft 365 Copilot and extracts text/file outputs.

        Args:
            prompt_text (str): The natural language query.
            target_url (str): If provided, navigates directly to this pre-encoded URL.
            file_to_upload (str): Absolute or relative path to a local file to attach.
            expect_file_download (bool): If True, parses output elements for downloadable files.
            custom_download_dir (str): Override path to store files for this specific call.
            timeout (int): Seconds to wait for Copilot's generating sequence to settle.

        Returns:
            dict: {"text": "Cleaned response text", "downloaded_file": "/path/to/downloaded/file or None"}
        """
        # This is the single big method that does the entire job end-to-end:
        # open the browser, go to the right page, optionally attach a file,
        # type and submit the question, wait for the answer, optionally find
        # and download a generated file, then close the browser and hand
        # back the result. Read it top to bottom -- it runs in that order.

        # 1. Parameter Handoff
        # You can either pass a plain prompt_text (normal case), or a
        # pre-built target_url (used by copilot_prompt_engineer.py) that
        # already has the question baked into the web address.
        if target_url:
            navigation_url = target_url
            extracted_prompt = self._extract_prompt_from_url(target_url)
        else:
            navigation_url = "https://m365.cloud.microsoft/chat/"
            extracted_prompt = prompt_text

        if not extracted_prompt:
            return {"text": "Error: No prompt provided.", "downloaded_file": None}

        downloaded_file_path = None
        print(f"Initializing Playwright for profile: {os.path.basename(self.user_data_dir)}")

        # `launch_persistent_context` opens Edge using the saved login found
        # in self.user_data_dir. `accept_downloads=True` is required so that
        # if Copilot generates a file, Playwright is allowed to actually
        # capture the resulting download instead of blocking it.
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                channel="msedge",
                headless=self.headless,
                accept_downloads=True,
                args=["--disable-blink-features=AutomationControlled"],
            )

            page = context.new_page()
            print(f"Navigating to: {navigation_url}")
            page.goto(navigation_url)

            # 2. Input Box Target
            # Locate the chat's text box on the page. `.first` guards
            # against the page briefly containing more than one matching
            # element while it's still loading.
            print("Locating chat input container...")
            chat_box = page.locator("textarea, [role='textbox']").first
            chat_box.wait_for(state="visible", timeout=30000)

            # 3. Handle File Uploads
            # If a file was supplied, find the (usually hidden) file-picker
            # input on the page and hand it the file path directly --
            # this is the automation equivalent of clicking "attach file"
            # and picking a file from a dialog box.
            if file_to_upload:
                abs_file_path = os.path.abspath(file_to_upload)
                if os.path.exists(abs_file_path):
                    print(f"Attaching local document: {abs_file_path}")
                    try:
                        file_input = page.locator("input[type='file']").first
                        file_input.set_input_files(abs_file_path)
                        page.wait_for_timeout(3000)  # Wait for UI upload bar
                    except Exception as upload_err:
                        print(f"-> Upload action blocked: {upload_err}")
                else:
                    print(f"[ERROR] Target file not found: {abs_file_path}")

            # 4. Fill Prompt & Submit
            chat_box.click()
            try:
                current_val = chat_box.input_value()
            except Exception:
                current_val = chat_box.text_content()

            # Only type the prompt in if the box is actually empty -- if
            # target_url already pre-filled it via the "?q=" web address
            # trick, typing again here would duplicate the question.
            if not current_val or len(current_val.strip()) == 0:
                print(f"Injecting prompt text...")
                chat_box.fill(extracted_prompt)

            print("Submitting prompt...")
            chat_box.press("Enter")

            # Fallback Click trigger if Enter did not submit
            page.wait_for_timeout(2000)
            try:
                current_val = chat_box.input_value() or chat_box.text_content()
            except Exception:
                current_val = ""

            # If pressing Enter didn't clear the box (meaning the message
            # wasn't actually sent), fall back to physically clicking
            # whatever "Send" button is visible.
            if current_val and len(current_val.strip()) > 0:
                print("-> Clicking physical send button...")
                send_btn = page.locator(
                    "button[aria-label*='Send'], button[aria-label*='Submit'], button:has-text('Send')"
                ).first
                if send_btn.is_visible():
                    send_btn.click()
                else:
                    page.keyboard.press("Enter")

            # 5. Smart Text Generation Wait (Up to Timeout)
            # Copilot "streams" its answer in gradually, like watching text
            # get typed out live. We can't just grab the text once -- we
            # have to keep checking it repeatedly and wait until it stops
            # changing (i.e. Copilot has finished), or give up after
            # `timeout` seconds.
            print(f"Awaiting Copilot response generation (Max {timeout}s)...")
            start_time = time.time()
            last_length = 0
            stable_count = 0
            final_response = ""

            # Copilot's web page can render its answer inside any of these
            # different container types depending on the kind of response
            # (plain text, a card, a file preview, etc.), so we check all
            # of them and use whichever currently holds real content.
            selectors = [
                "[data-content='ai-message']",
                ".ac-container",
                "[role='presentation']",
                "[role='article']",
                ".message-content",
            ]
            # If the visible text contains one of these words, Copilot is
            # still "thinking" or searching -- not actually done yet, even
            # if the text briefly stops growing.
            transitional_phrases = ["checking", "working on it", "searching", "analyzing", "gathering"]

            while time.time() - start_time < timeout:
                current_text = ""
                for selector in selectors:
                    try:
                        loc = page.locator(selector)
                        if loc.count() > 0:
                            current_text = loc.last.text_content()
                            if current_text and len(current_text.strip()) > 10:
                                break
                    except Exception:
                        pass

                current_length = len(current_text) if current_text else 0

                # Verify if Stop button is still present (meaning it's typing)
                stop_visible = False
                try:
                    stop_btn = page.locator("button:has-text('Stop'), button[aria-label*='Stop']").first
                    if stop_btn.is_visible():
                        stop_visible = True
                except Exception:
                    pass

                # Check for transitional phrases
                is_transitional = False
                if current_text:
                    lower_txt = current_text.lower()
                    is_transitional = any(p in lower_txt for p in transitional_phrases)

                # Stabilizer evaluation: only treat the answer as "finished"
                # once the text length has held steady for 3 checks in a
                # row AND there's no "Stop" button and no in-progress phrase
                # still showing. This avoids cutting off the answer early
                # just because it briefly paused mid-stream.
                if current_length > 0 and current_length == last_length:
                    if stop_visible or (is_transitional and current_length < 250):
                        stable_count = 0  # Still writing or researching
                    else:
                        stable_count += 1
                    if stable_count >= 3:
                        final_response = current_text
                        break
                else:
                    stable_count = 0
                    last_length = current_length

                time.sleep(1)

            # Fallback raw HTML dump: if none of the expected containers
            # ever produced usable text within the timeout, grab the whole
            # visible page text instead and try to salvage an answer from
            # whatever comes after the prompt we sent.
            if not final_response:
                print("\n[DEBUG] Selector timeout. Running body parser fallback...")
                try:
                    page_text = page.locator("body").text_content()
                    if extracted_prompt in page_text:
                        final_response = page_text.split(extracted_prompt)[-1].strip()
                    else:
                        final_response = page_text[-1500:].strip()
                except Exception as e:
                    final_response = f"Failed fallback parsing: {e}"

            # 6. Scoped Link Scorer & Downloader
            # If the caller wants a generated file (expect_file_download),
            # search the most recent answer block for the link/button most
            # likely to be the actual "download this file" control, as
            # opposed to unrelated links Copilot might also show (citations,
            # feedback buttons, etc.).
            if expect_file_download:
                print("Scanning latest message block for generated files...")
                page.wait_for_timeout(5000)  # Wait for OneDrive provisioning

                last_block = None
                for selector in ["[data-content='ai-message']", "[role='article']", ".ac-container"]:
                    try:
                        loc = page.locator(selector)
                        if loc.count() > 0:
                            for i in reversed(range(loc.count())):
                                block = loc.nth(i)
                                if block.is_visible():
                                    last_block = block
                                    break
                        if last_block:
                            break
                    except Exception:
                        pass

                candidates = last_block.locator("a, button, [role='button']").all() if last_block else page.locator("a, button, [role='button']").all()
                best_candidate = None
                best_score = 0

                # Score links (ignores stale browser history and citations).
                # Higher score = more likely to be the real download control.
                # A link/button that both says "download" AND names a file
                # extension like ".docx" is the strongest signal; a bare
                # SharePoint/OneDrive domain link with none of those words
                # is the weakest (still possible, but a last resort).
                for el in reversed(candidates):
                    try:
                        if not el.is_visible():
                            continue
                        text = (el.text_content() or "").lower()
                        href = (el.get_attribute("href") or "").lower()

                        if any(exc in text for exc in ["feedback", "thumbs", "copy response", "share response"]):
                            continue

                        score = 0
                        has_ext = any(ext in text for ext in [".docx", ".xlsx", ".csv", ".pdf", ".txt"])
                        has_action = any(v in text for v in ["download", "export"])

                        if has_action and has_ext:
                            score += 100
                        elif has_action:
                            score += 80
                        elif has_ext:
                            score += 60
                        elif any(t in href for t in ["download", "export"]):
                            score += 40
                        elif any(dom in href for dom in ["sharepoint.com", "onedrive.live.com"]):
                            score += 5

                        if score > best_score:
                            best_score = score
                            best_candidate = el
                    except Exception:
                        pass

                if best_candidate and best_score >= 5:
                    target_name = best_candidate.text_content().strip()[:50]
                    print(f"-> Target matched: '{target_name}...' (Score={best_score})")

                    try:
                        href = best_candidate.get_attribute("href") or ""
                    except Exception:
                        href = ""

                    # Intercept and rewrite SharePoint/OneDrive link redirects
                    # into a direct-download link before following it, so we
                    # get the actual file instead of a viewer page.
                    if href and ("sharepoint.com" in href or "onedrive.live.com" in href):
                        direct_url = self._make_sharepoint_direct_download(href)
                        if direct_url != href:
                            print(f"-> Rewrote SharePoint viewer link to direct-download endpoint.")
                            href = direct_url

                    # Run download execution. `expect_download()` tells
                    # Playwright to watch for a real file download to start
                    # as a result of whatever happens inside this block
                    # (either navigating straight to the rewritten link, or
                    # clicking the matched button/link).
                    print("Initiating file download...")
                    try:
                        with page.expect_download() as download_info:
                            if href and href.startswith("http"):
                                page.goto(href)
                            else:
                                best_candidate.click()
                        download = download_info.value

                        target_dir = custom_download_dir or self.download_dir
                        os.makedirs(target_dir, exist_ok=True)

                        downloaded_file_path = os.path.normpath(
                            os.path.join(target_dir, download.suggested_filename)
                        )
                        download.save_as(downloaded_file_path)
                        print(f"-> Success! File stored: {downloaded_file_path}")
                    except Exception as dl_err:
                        print(f"-> Error downloading file stream: {dl_err}")
                else:
                    print("-> No file elements detected in Copilot's response.")

            context.close()

            return {
                "text": self._clean_response(final_response),
                "downloaded_file": downloaded_file_path,
            }


# Legacy Backward Compatibility Helper
def ask_copilot(
    prompt_text: str = "",
    target_url: str = "",
    file_to_upload: Optional[str] = None,
    expect_file_download: bool = False,
    download_dir: Optional[str] = None,
    headless: bool = False,
    timeout: int = 180,
) -> dict:
    """Wraps the class instance for backward compatibility with existing legacy scripts."""
    # This plain function exists so older scripts (like
    # copilot_prompt_engineer.py) that expect a simple function call, rather
    # than creating a CopilotBridge object themselves, still work unchanged.
    # It just creates a one-off CopilotBridge behind the scenes and calls
    # its .ask() method.
    bridge = CopilotBridge(headless=headless, download_dir=download_dir)
    return bridge.ask(
        prompt_text=prompt_text,
        target_url=target_url,
        file_to_upload=file_to_upload,
        expect_file_download=expect_file_download,
        timeout=timeout,
    )
