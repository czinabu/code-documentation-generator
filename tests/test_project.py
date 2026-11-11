import json
from pathlib import Path

import pytest

from docgen.cache import CACHE_FILE
from docgen.chunker import chunk_source
from docgen.cli import main
from docgen.files import find_source_files
from docgen.project import document_project, model_doc_function, parse_languages


class FakeModel:
    def __init__(self):
        self.calls = []

    def __call__(self, code, language, context):
        self.calls.append((code, language, context))
        return f"### Docs\n{language}: {len(code)} chars"


def make_project(root: Path):
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("def f():\n    return 1\n")
    (root / "web").mkdir()
    (root / "web" / "app.ts").write_text("export function g(): number { return 2 }\n")
    (root / "node_modules" / "x").mkdir(parents=True)
    (root / "node_modules" / "x" / "index.js").write_text("module.exports = 1\n")
    (root / "README.md").write_text("# not code\n")
    (root / "logo.png").write_bytes(b"\x89PNG\x00\x00")


def test_walker_finds_code_and_skips_vendor(tmp_path):
    make_project(tmp_path)
    files = find_source_files(tmp_path)
    assert [(f.rel_path, f.language) for f in files] == [
        ("pkg/a.py", "python"),
        ("web/app.ts", "typescript"),
    ]
    assert [f.rel_path for f in find_source_files(tmp_path, languages=["python"])] == ["pkg/a.py"]
    assert find_source_files(tmp_path, exclude=["web/*"])[0].rel_path == "pkg/a.py"
    assert len(find_source_files(tmp_path, exclude=["web"])) == 1


def test_writes_pages_index_and_skips_unchanged(tmp_path):
    src = tmp_path / "proj"
    out = tmp_path / "docs"
    make_project(src)
    model = FakeModel()

    report = document_project(src, out, doc_fn=model)
    assert report.generated == 2 and report.unchanged == 0
    assert (out / "pkg" / "a.py.md").read_text().startswith("# `pkg/a.py`")
    assert "../index.md" in (out / "pkg" / "a.py.md").read_text()
    index = (out / "index.md").read_text()
    assert "[a.py](pkg/a.py.md)" in index and "[app.ts](web/app.ts.md)" in index
    assert (out / CACHE_FILE).is_file()

    # Second run: nothing changed, so the model is not called again.
    model.calls.clear()
    report = document_project(src, out, doc_fn=model)
    assert report.generated == 0 and report.unchanged == 2 and model.calls == []

    # Edit one file: only that one is regenerated.
    (src / "pkg" / "a.py").write_text("def f():\n    return 42\n")
    report = document_project(src, out, doc_fn=model)
    assert report.generated == 1 and len(model.calls) == 1

    # --force regenerates everything; a deleted source removes its page.
    (src / "web" / "app.ts").unlink()
    report = document_project(src, out, doc_fn=model, force=True)
    assert report.generated == 1
    assert not (out / "web" / "app.ts.md").exists()
    assert "app.ts" not in (out / "index.md").read_text()


def test_output_inside_source_is_not_documented(tmp_path):
    make_project(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "conf.py").write_text("x = 1\n")
    report = document_project(tmp_path, tmp_path / "docs", doc_fn=FakeModel())
    assert all(not f.path.startswith("docs/") for f in report.files)


def test_failure_is_reported_and_retried(tmp_path):
    make_project(tmp_path / "p")

    def broken(code, language, context):
        raise RuntimeError("model said no")

    report = document_project(tmp_path / "p", tmp_path / "d", doc_fn=broken)
    assert report.failed == 2
    assert "model said no" in (tmp_path / "d" / "index.md").read_text()
    report = document_project(tmp_path / "p", tmp_path / "d", doc_fn=FakeModel())
    assert report.generated == 2


def test_stops_early_when_model_is_unreachable(tmp_path):
    make_project(tmp_path / "p")
    document_project(tmp_path / "p", tmp_path / "d", doc_fn=FakeModel())
    (tmp_path / "p" / "pkg" / "a.py").write_text("def f():\n    return 3\n")
    (tmp_path / "p" / "web" / "app.ts").write_text("export const x = 1\n")
    calls = []

    def down(code, language, context):
        calls.append(code)
        raise ConnectionError("refused")

    report = document_project(tmp_path / "p", tmp_path / "d", doc_fn=down)
    assert len(calls) == 1 and report.error and report.count("skipped") == 1
    # Existing pages survive and stay in the index.
    assert (tmp_path / "d" / "web" / "app.ts.md").is_file()
    assert "app.ts.md" in (tmp_path / "d" / "index.md").read_text()


def test_dry_run_writes_nothing(tmp_path):
    make_project(tmp_path / "p")
    model = FakeModel()
    report = document_project(tmp_path / "p", tmp_path / "d", doc_fn=model, dry_run=True)
    assert report.count("planned") == 2 and model.calls == []
    assert not (tmp_path / "d").exists()


def test_large_python_file_is_split_at_functions(tmp_path):
    body = "".join(
        f"@decorator\ndef func_{i}(x):\n    '''Doc.'''\n"
        + "    x += 1\n" * 30
        + "    return x\n\n\n"
        for i in range(20)
    )
    text = "import os\n\n" + body
    chunks = chunk_source(text, "python", max_chars=2000)
    assert len(chunks) > 1
    assert all(len(c.text) <= 2000 for c in chunks)
    assert "".join(c.text for c in chunks) == text  # nothing lost or duplicated
    # Every function starts a chunk or sits whole inside one, with its decorator.
    for c in chunks[1:]:
        assert c.text.startswith("@decorator\ndef func_")
    assert "func_0" in chunks[0].names


@pytest.mark.parametrize(
    "language,text,first",
    [
        (
            "go",
            "package main\n\n"
            + "".join(
                f"// F{i} does it.\nfunc F{i}() int {{\n" + "\tx := 1\n" * 40 + "\treturn x\n}\n\n"
                for i in range(10)
            ),
            "// F",
        ),
        (
            "javascript",
            "".join(
                f"export function f{i}() {{\n" + "  let a = 1;\n" * 40 + "}\n\n" for i in range(10)
            ),
            "export function f",
        ),
        (
            "java",
            "package x;\n\n"
            + "".join(
                f"public class C{i} {{\n" + "    int a = 1;\n" * 40 + "}\n\n" for i in range(10)
            ),
            "public class C",
        ),
        (
            "rust",
            "".join(
                f"/// Doc\npub fn f{i}() {{\n" + "    let a = 1;\n" * 40 + "}\n\n"
                for i in range(10)
            ),
            "/// Doc",
        ),
    ],
)
def test_other_languages_split_at_declarations(language, text, first):
    chunks = chunk_source(text, language, max_chars=1500)
    assert len(chunks) > 1
    assert "".join(c.text for c in chunks) == text
    assert all(len(c.text) <= 1500 for c in chunks)
    for c in chunks[1:]:
        assert c.text.startswith(first), c.text[:40]


def test_giant_function_is_split_into_parts():
    text = "def huge():\n" + "    x = 1\n" * 2000
    chunks = chunk_source(text, "python", max_chars=3000)
    assert len(chunks) > 1
    assert "".join(c.text for c in chunks) == text
    assert chunks[0].names == ["huge (part 1)"]


def test_multi_part_page_has_a_section_per_chunk(tmp_path):
    src = tmp_path / "p"
    src.mkdir()
    (src / "big.py").write_text(
        "".join(f"def f{i}():\n" + "    pass\n" * 50 + "\n" for i in range(10))
    )
    model = FakeModel()
    document_project(src, tmp_path / "d", doc_fn=model, max_chars=1000)
    page = (tmp_path / "d" / "big.py.md").read_text()
    assert page.count("\n## ") == len(model.calls) > 1
    assert "part 1 of" in model.calls[0][2]


def test_parse_languages():
    assert parse_languages("auto") is None
    assert parse_languages("py, ts,Go") == ["python", "typescript", "go"]
    with pytest.raises(ValueError):
        parse_languages("klingon")


def test_cli_dry_run_and_bad_language(tmp_path, capsys):
    make_project(tmp_path / "p")
    assert main([str(tmp_path / "p"), "--out", str(tmp_path / "d"), "--dry-run", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert {f["path"] for f in data["files"]} == {"pkg/a.py", "web/app.ts"}
    assert main([str(tmp_path / "p"), "--lang", "klingon"]) == 2
    assert main([str(tmp_path / "missing")]) == 2


def test_real_generator_gets_chunk_context(tmp_path, settings, fake_ollama):
    src = tmp_path / "p"
    src.mkdir()
    (src / "big.py").write_text(
        "".join(f"def f{i}():\n" + "    pass\n" * 50 + "\n" for i in range(10))
    )
    document_project(src, tmp_path / "d", doc_fn=model_doc_function(settings), max_chars=1000)
    first = fake_ollama.calls[0]["messages"][1]["content"]
    assert first.startswith("This is part 1 of") and "def f0" in first
    assert "Python" in fake_ollama.calls[0]["messages"][0]["content"]


def test_unreachable_ollama_stops_run(tmp_path, settings, fake_ollama):
    make_project(tmp_path / "p")
    fake_ollama.error = ConnectionError("refused")
    report = document_project(tmp_path / "p", tmp_path / "d", doc_fn=model_doc_function(settings))
    assert report.error and len(fake_ollama.calls) == 1


def test_api_endpoint_uses_same_logic(tmp_path, client, fake_ollama):
    make_project(tmp_path / "p")
    body = {"source": str(tmp_path / "p"), "out": str(tmp_path / "d")}
    r = client.post("/generate-project-docs", json=body)
    assert r.status_code == 200 and r.json()["generated"] == 2
    assert len(fake_ollama.calls) == 2
    r = client.post("/generate-project-docs", json=body)
    assert r.json()["unchanged"] == 2 and len(fake_ollama.calls) == 2
    r = client.post("/generate-project-docs", json={**body, "lang": "klingon"})
    assert r.status_code == 400
    fake_ollama.error = ConnectionError("refused")
    r = client.post("/generate-project-docs", json={**body, "force": True})
    assert r.status_code == 502
