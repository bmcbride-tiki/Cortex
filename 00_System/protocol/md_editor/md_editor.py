# =============================================================================
# md_editor.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A small, standalone desktop window app (not a web page) for viewing and
#   editing Markdown notes (the plain-text ".md" file format this whole
#   vault is written in), styled to look like the Obsidian note-taking app.
#   It opens as its own window, separate from the Cortex web app, and has
#   two modes you can flip between with one button: "Code View" (the raw
#   text, including the --- ... --- metadata block at the top of most vault
#   files) and "Human View" (that same content rendered as nicely formatted
#   text, headings, tables, etc., the way you'd expect to actually read it).
#
# WHAT IT INTERACTS WITH
#   - The `PyQt6` library, which provides the actual window, buttons, and
#     text boxes -- this is what makes it a real desktop app instead of
#     something running in a browser.
#   - The `markdown` library, which converts raw Markdown text into
#     formatted HTML (the same format web pages are built from) for the
#     "Human View" side.
#   - Any .md file on disk that you open through it, and an internal
#     `mde:` link format (e.g. `mde://C:/workbrain/some_note.md`) that lets
#     other parts of the system tell this editor to open a specific file
#     the moment it starts up.
#
# KEY FUNCTIONALITY NOTES
#   - This is launched as its own separate program (`python md_editor.py`,
#     optionally followed by a file path or an `mde:` link to open), not
#     called as a function from inside the Cortex web server the way the
#     adapter files are.
#   - The frontmatter block right below this comment (the part that starts
#     with `---` and lists `type:`, `domain:`, `status:`, etc.) is this
#     project's standard metadata header, required on every file in the
#     vault per this project's own documentation rules (see claude.md at
#     the project root) -- it is not something this program reads or acts
#     on itself; it is describing this .py file the same way it would
#     describe a vault note.
#   - "Human View" specifically understands the metadata block (the ---
#     delimited section) at the top of a note and renders it as a distinct
#     styled box instead of just plain text, including turning any listed
#     tags into clickable links.
# =============================================================================

"""
---
type: documentation
domain: 20-apps
belongs to: 20-apps
status: active
version: 1.0.0
created: 2026-07-09
updated: 2026-07-09
tags: [python, pyqt6, markdown, desktop-app, cortex, system/tool]
process: Development
---
"""

import sys
import os
import markdown
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QPlainTextEdit,
                             QTextBrowser, QStackedWidget, QFileDialog)
from PyQt6.QtCore import Qt

class ObsidianLiteEditor(QMainWindow):
    def __init__(self, file_to_load=None):
        super().__init__()
        self.current_file = None
        self.init_ui()

        # Parse and process initial file link payloads passed at instantiation.
        # This lets some other program open this editor already pointed at a
        # specific file, instead of always starting on a blank page.
        if file_to_load:
            self.load_routed_file(file_to_load)

    def init_ui(self):
        # Builds the actual window layout: a toolbar of buttons across the
        # top, and a big content area below it that can show either the raw
        # text box or the rendered preview (but never both at once).
        self.setWindowTitle("Obsidian-Lite Editor")
        self.setGeometry(100, 100, 950, 650)

        # Main Layout Setup
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Top Action & Toggle Toolbar
        toolbar = QHBoxLayout()

        self.btn_open = QPushButton("Open File")
        self.btn_open.clicked.connect(self.open_file)
        toolbar.addWidget(self.btn_open)

        self.btn_save = QPushButton("Save File")
        self.btn_save.clicked.connect(self.save_file)
        toolbar.addWidget(self.btn_save)

        # Spacer pushes the toggle button to the far right
        toolbar.addStretch()

        # The Mode Toggle Switch
        self.btn_toggle = QPushButton("Switch to Human View")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.clicked.connect(self.toggle_view)
        toolbar.addWidget(self.btn_toggle)

        layout.addLayout(toolbar)

        # Stacked Widget to cleanly swap views without layout shifting.
        # A "stacked widget" holds multiple full-size panels on top of each
        # other, showing only one at a time -- this is what makes switching
        # between Code View and Human View instant, without the window
        # resizing or jumping around.
        self.view_stack = QStackedWidget()

        # View 1: "Code" Mode (Raw editing) -- a plain text box showing the
        # file's actual Markdown source, editable like a simple text editor.
        self.code_view = QPlainTextEdit()
        self.code_view.setPlaceholderText("# Start writing your markdown here...")
        self.view_stack.addWidget(self.code_view)

        # View 2: "Human" Mode (Rendered view via QTextBrowser to support hyperlink intercepts)
        # -- shows the same content converted into formatted, read-only text.
        self.human_view = QTextBrowser()
        self.human_view.setReadOnly(True)
        self.human_view.setOpenLinks(False)
        self.human_view.anchorClicked.connect(self.handle_tag_clicked)
        self.view_stack.addWidget(self.human_view)

        self.view_stack.setCurrentWidget(self.code_view)
        layout.addWidget(self.view_stack)

        # Apply Obsidian Dark Theme UI Styling
        self.apply_ui_theme()

    def apply_ui_theme(self):
        """Styles the window components to mirror Obsidian's core UI."""
        # This block of text is CSS (styling instructions), the same kind
        # of thing used to style web pages, but here it's controlling the
        # look of the actual desktop window's buttons and text boxes
        # (colors, borders, fonts) to visually match the Obsidian app.
        self.setStyleSheet("""
            QMainWindow {
                background-color: #18181c;
            }
            QPushButton {
                background-color: #26262b;
                color: #b2b2b3;
                border: 1px solid #36363a;
                padding: 6px 14px;
                border-radius: 4px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2e2e33;
                color: #ffffff;
                border: 1px solid #48484f;
            }
            QPushButton:checked {
                background-color: #483699;
                color: #ffffff;
                border: 1px solid #6c5ce7;
            }
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #e2e2e3;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 14px;
                line-height: 1.5;
                border: 1px solid #2e2e33;
                border-radius: 6px;
                padding: 15px;
            }
            QTextBrowser {
                background-color: #1e1e1e;
                color: #e2e2e3;
                border: 1px solid #2e2e33;
                border-radius: 6px;
                padding: 15px;
            }
        """)

    def get_markdown_css(self):
        """Injects CSS to make the rendered HTML look identical to Obsidian's Reading Mode."""
        # This is a second, separate style sheet -- this one applies only
        # inside the rendered "Human View" preview (headings, code blocks,
        # tables, links, etc.), not to the window's buttons.
        return """
        <style>
            body {
                background-color: #1e1e1e;
                color: #dcddde;
                font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
                line-height: 1.6;
                padding: 20px;
            }
            .yaml-metadata-block {
                background-color: #242429;
                border: 1px solid #36363a;
                border-radius: 6px;
                padding: 12px 16px;
                margin-bottom: 16px;
            }
            .yaml-metadata-block ul {
                list-style-type: none;
                padding-left: 0;
                margin: 0;
            }
            .yaml-metadata-block li {
                margin-bottom: 4px;
                font-size: 13px;
                color: #b2b2b3;
                font-family: 'Segoe UI', sans-serif;
            }
            .yaml-metadata-block li strong {
                color: #FF9A4B;
                font-weight: 700;
                text-transform: uppercase;
                font-size: 11px;
                letter-spacing: 0.5px;
                display: inline-block;
                width: 90px;
            }
            .yaml-metadata-block a {
                color: #7f6df2;
                text-decoration: none;
                font-weight: 600;
                margin-right: 8px;
            }
            .yaml-metadata-block a:hover {
                text-decoration: underline;
                color: #9c8df6;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #ffffff;
                font-weight: 600;
                margin-top: 24px;
                margin-bottom: 12px;
            }
            h1 { font-size: 1.8em; border-bottom: 1px solid #36363a; padding-bottom: 8px; }
            h2 { font-size: 1.5em; border-bottom: 1px solid #2e2e33; padding-bottom: 6px; }
            h3 { font-size: 1.25em; }
            strong { color: #ffffff; font-weight: bold; }
            em { color: #e2e2e3; font-style: italic; }
            a { color: #7f6df2; text-decoration: none; }
            a:hover { text-decoration: underline; }
            code {
                background-color: #2a2a2e;
                color: #e48285;
                padding: 3px 6px;
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-size: 0.9em;
            }
            pre {
                background-color: #202023;
                padding: 14px;
                border-radius: 6px;
                border: 1px solid #2e2e33;
                overflow-x: auto;
            }
            pre code {
                background-color: transparent;
                color: #dcddde;
                padding: 0;
            }
            blockquote {
                margin: 14px 0;
                padding-left: 16px;
                border-left: 4px solid #7f6df2;
                color: #9da4ae;
                font-style: italic;
            }
            ul, ol { padding-left: 24px; }
            li { margin-bottom: 6px; }
            hr { border: 0; border-top: 1px solid #36363a; margin: 24px 0; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 15px; }
            th, td { border: 1px solid #36363a; padding: 8px; text-align: left; }
            th { background-color: #26262b; color: #ffffff; }
        </style>
        """

    def load_routed_file(self, target_path):
        """Extracts internal mde: protocol syntax, reading note content into the layout view."""
        # `mde:` is this editor's own custom link format -- similar in spirit
        # to how "https://" tells a browser to fetch a web page, "mde://"
        # tells this program "open this specific vault file." This function
        # strips that prefix off (if present) to get a normal file path.
        if target_path.startswith("mde:"):
            target_path = target_path.split("mde:", 1)[1]

        if target_path.startswith("//"):
            target_path = target_path.lstrip("//")

        normalized_path = os.path.normpath(target_path)
        self.current_file = normalized_path

        if os.path.exists(normalized_path):
            try:
                with open(normalized_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.code_view.setPlainText(content)
                self.setWindowTitle(f"Obsidian-Lite Editor - {os.path.basename(normalized_path)}")
            except Exception as e:
                self.code_view.setPlainText(f"# Error Accessing Vault File\nCould not open target matrix node:\n{str(e)}")
        else:
            # The requested file doesn't exist yet -- rather than failing,
            # pre-fill the editor with a blank note template (including an
            # empty metadata block) ready for the user to start writing,
            # matching this vault's usual note format.
            placeholder_text = f"--- \ntitle: New Note\ncategory: \ntags: [staged]\ndescription: \n---\n\n# Staged Document Workspace\n\nFile location targeted: `{normalized_path}`\n\nStart authoring content notes here..."
            self.code_view.setPlainText(placeholder_text)
            self.setWindowTitle(f"Obsidian-Lite Editor - [Staged New File]")

    def handle_tag_clicked(self, url):
        """Intercepts reading view hyperlink events and routes formatted tag parameters to standard output."""
        # In Human View, each #tag shown in the metadata box is turned into
        # a clickable link (see toggle_view() below). Clicking one doesn't
        # navigate anywhere -- it's intercepted here and just printed to the
        # terminal this program was launched from, as a simple way to
        # signal "the user is interested in this tag" to whatever launched
        # this editor (a fuller integration could react to this print
        # statement, e.g. to open a search).
        url_str = url.toString()
        if url_str.startswith("tag:/"):
            tag_term = url_str.split("tag:/", 1)[1]
            print(f"\n>> App Hub: Protocol URI Triggered: Criterion captured: {tag_term}")
            print(f">> App Hub: criterion: {tag_term}")

    def toggle_view(self):
        """Handles swapping between raw text editing and html reading mode with bracket-free YAML link parsing."""
        if self.btn_toggle.isChecked():
            # Switching INTO Human View: take the raw text currently in the
            # editor, pull the --- ... --- metadata block off the top of it
            # (if there is one) and turn it into a styled info box, then
            # convert everything else from Markdown into formatted HTML.
            raw_text = self.code_view.toPlainText()
            lines = raw_text.splitlines()
            yaml_html = ""
            markdown_body = raw_text

            if lines and lines[0].strip() == "---":
                end_index = -1
                for i in range(1, len(lines)):
                    if lines[i].strip() == "---":
                        end_index = i
                        break

                if end_index != -1:
                    yaml_lines = lines[1:end_index]
                    markdown_body = "\n".join(lines[end_index+1:])

                    if yaml_lines:
                        yaml_html = "<div class='yaml-metadata-block'><ul>"
                        for y_line in yaml_lines:
                            if ":" in y_line:
                                key, val = y_line.split(":", 1)
                                key_str = key.strip().lower()

                                # Process tags block by completely cleaning out code brackets and tokenizing.
                                # A "tags: [foo, bar]" line gets turned into individual
                                # clickable "#foo" and "#bar" links instead of showing
                                # the raw brackets/commas as plain text.
                                if key_str in ["tag", "tags"]:
                                    # Clear bounding braces/brackets out before execution splits
                                    clean_val = val.replace('[', '').replace(']', '').replace('{', '').replace('}', '')
                                    # Normalize standard list splitting structures
                                    clean_val = clean_val.replace(',', ' ')

                                    tags_list = clean_val.split()
                                    tag_links_html = ""
                                    for t in tags_list:
                                        t_sanitized = t.strip()
                                        if t_sanitized:
                                            tag_links_html += f"<a href='tag:/{t_sanitized}'>#{t_sanitized}</a>"
                                    yaml_html += f"<div><strong>{key.strip()}</strong> {tag_links_html}</div>"
                                else:
                                    yaml_html += f"<div><strong>{key.strip()}</strong> {val.strip()}</div>"
                            else:
                                if y_line.strip():
                                    yaml_html += f"<div>{y_line.strip()}</div>"
                        yaml_html += "</ul></div>"

            html_content = markdown.markdown(markdown_body, extensions=['fenced_code', 'tables'])
            full_html = f"<html><head>{self.get_markdown_css()}</head><body>{yaml_html}{html_content}</body></html>"

            self.human_view.setHtml(full_html)
            self.view_stack.setCurrentWidget(self.human_view)
            self.btn_toggle.setText("Switch to Code View")
        else:
            # Switching back INTO Code View just swaps the visible panel --
            # nothing needs to be re-parsed since the raw text was never
            # modified, only re-displayed differently.
            self.view_stack.setCurrentWidget(self.code_view)
            self.btn_toggle.setText("Switch to Human View")

    def open_file(self):
        # Shows the normal Windows "choose a file" dialog box, restricted by
        # default to .md/.txt files (though "All Files" is also offered).
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Markdown File", "", "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.load_routed_file(file_path)
            if self.btn_toggle.isChecked():
                self.toggle_view()

    def save_file(self):
        # If no file has been opened/named yet, prompt for where to save
        # (a normal "Save As" dialog); otherwise just overwrite the file
        # that's already open.
        if not self.current_file:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Markdown File", "", "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)"
            )
            if file_path:
                self.current_file = file_path
            else:
                return

        raw_text = self.code_view.toPlainText()
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(raw_text)
            self.setWindowTitle(f"Obsidian-Lite Editor - {os.path.basename(self.current_file)}")
        except Exception as e:
            self.setWindowTitle(f"Obsidian-Lite Editor - [SAVE FAILED: {str(e)}]")

if __name__ == "__main__":
    # Entry point when this file is run directly, e.g.:
    #   python md_editor.py
    #   python md_editor.py C:\workbrain\some_note.md
    # An optional file path (or mde: link) can be passed as the first
    # command-line argument to have the editor open already pointed at
    # that file.
    app = QApplication(sys.argv)
    initial_file_arg = sys.argv[1] if len(sys.argv) > 1 else None
    editor = ObsidianLiteEditor(initial_file_arg)
    editor.show()
    sys.exit(app.exec())
