import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import notebooklm_bridge as nb


def test_create_notebook_returns_notebook_id():
    result = nb.create_notebook("Electrician Curriculum Review")
    assert result["notebook_id"].startswith("nb_")
    assert result["title"] == "Electrician Curriculum Review"


def test_upload_sources_validates_real_files():
    with tempfile.TemporaryDirectory() as tmp:
        real_file = Path(tmp) / "source1.pdf"
        real_file.write_text("fake pdf content")

        result = nb.upload_sources("nb_test", [str(real_file)])
        assert len(result["sources"]) == 1
        assert result["sources"][0]["filename"] == "source1.pdf"
        assert result["sources"][0]["status"] == "processed"

        try:
            nb.upload_sources("nb_test", [str(Path(tmp) / "missing.pdf")])
            assert False, "expected FileNotFoundError for a missing source path"
        except FileNotFoundError:
            pass


def test_upload_sources_requires_notebook_id():
    try:
        nb.upload_sources("", ["anything.pdf"])
        assert False, "expected ValueError for a missing notebook_id"
    except ValueError:
        pass


def test_prompt_loop_asks_each_prompt_in_order():
    prompts = ["What is Period 1 about?", "What is Period 2 about?"]
    result = nb.prompt_loop("nb_test", prompts)
    assert len(result["qa_pairs"]) == 2
    assert result["qa_pairs"][0]["prompt"] == prompts[0]
    assert result["qa_pairs"][1]["prompt"] == prompts[1]
    assert "nb_test" in result["qa_pairs"][0]["response"]


def test_mock_mode_off_fails_clearly():
    nb.MOCK_MODE = False
    try:
        try:
            nb.create_notebook("Anything")
            assert False, "expected RuntimeError when MOCK_MODE is off"
        except RuntimeError as e:
            assert "not configured" in str(e)
    finally:
        nb.MOCK_MODE = True


if __name__ == "__main__":
    test_create_notebook_returns_notebook_id()
    test_upload_sources_validates_real_files()
    test_upload_sources_requires_notebook_id()
    test_prompt_loop_asks_each_prompt_in_order()
    test_mock_mode_off_fails_clearly()
    print("All notebooklm_bridge self-checks passed.")
