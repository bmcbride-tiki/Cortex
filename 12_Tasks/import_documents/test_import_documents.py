import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from import_documents import DocumentsImporter


def test_extract_labeled_fields():
    importer = DocumentsImporter()
    text = "Report Title: Q1 Safety Audit\nTrade: Electrical, Plumbing\nDate: 2026-01-15\nSome free-text line without a colon"
    fields = importer._extract_labeled_fields(text)
    assert fields["Report Title"] == "Q1 Safety Audit"
    assert fields["Trade"] == "Electrical, Plumbing"
    assert fields["Date"] == "2026-01-15"
    assert "Some free-text line without a colon" not in fields


def test_split_trades():
    importer = DocumentsImporter()
    assert importer._split_trades("Electrical, Plumbing; Carpentry") == ["Electrical", "Plumbing", "Carpentry"]
    assert importer._split_trades("") == []


def test_filename_fallback_used_when_body_missing_fields():
    importer = DocumentsImporter()
    fields = importer._extract_labeled_fields("no labeled lines here")
    fallback = importer._parse_filename_fallback("2026-03-01_Annual-Report.pdf")
    title = importer._lookup_field(fields, ["title"]) or fallback["title"]
    doc_date = importer._lookup_field(fields, ["date"]) or fallback["date"]
    assert title == "Annual Report"
    assert doc_date == "2026-03-01"


def test_body_field_overrides_filename():
    importer = DocumentsImporter()
    fields = importer._extract_labeled_fields("Title: Real Title\nDate: 2026-05-05")
    fallback = importer._parse_filename_fallback("2026-01-01_Fallback-Title.docx")
    title = importer._lookup_field(fields, ["title"]) or fallback["title"]
    doc_date = importer._lookup_field(fields, ["date"]) or fallback["date"]
    assert title == "Real Title"
    assert doc_date == "2026-05-05"


if __name__ == "__main__":
    test_extract_labeled_fields()
    test_split_trades()
    test_filename_fallback_used_when_body_missing_fields()
    test_body_field_overrides_filename()
    print("All import_documents self-checks passed.")
