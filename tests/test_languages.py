import pytest

from docgen.languages import (
    GENERIC,
    LANGUAGES,
    UnknownLanguageError,
    detect_language,
    from_filename,
    get_language,
)


@pytest.mark.parametrize(
    "filename,key",
    [
        ("app.py", "python"),
        ("index.js", "javascript"),
        ("App.tsx", "typescript"),
        ("Main.java", "java"),
        ("main.go", "go"),
        ("lib.rs", "rust"),
        ("Program.cs", "csharp"),
        ("vec.hpp", "cpp"),
        ("util.c", "c"),
        ("model.rb", "ruby"),
        ("index.php", "php"),
        ("Build.kt", "kotlin"),
        ("dir/SCRIPT.PY", "python"),
    ],
)
def test_from_filename(filename, key):
    assert from_filename(filename).key == key


def test_from_filename_unknown():
    assert from_filename("notes.txt") is None
    assert from_filename("Makefile") is None


def test_extensions_are_unique():
    seen = [ext for lang in LANGUAGES for ext in lang.extensions]
    assert len(seen) == len(set(seen))


@pytest.mark.parametrize(
    "name,key",
    [
        ("Python", "python"),
        ("ts", "typescript"),
        ("golang", "go"),
        ("C#", "csharp"),
        ("c++", "cpp"),
    ],
)
def test_get_language_aliases(name, key):
    assert get_language(name).key == key


def test_get_language_unknown():
    with pytest.raises(UnknownLanguageError):
        get_language("cobol")


@pytest.mark.parametrize(
    "code,key",
    [
        ("def add(a, b):\n    return a + b\n", "python"),
        ("#!/usr/bin/env python3\nprint('hi')\n", "python"),
        ("function add(a, b) {\n  return a + b;\n}\n", "javascript"),
        ("const add = (a, b) => a + b;\n", "javascript"),
        ("interface Point { x: number; y: number }\n", "typescript"),
        ("package main\n\nfunc Add(a, b int) int {\n\treturn a + b\n}\n", "go"),
        ("pub fn add(a: i32, b: i32) -> i32 {\n    a + b\n}\n", "rust"),
        (
            "public class Calc {\n  public static int add(int a, int b) {\n"
            "    return a + b;\n  }\n}\n",
            "java",
        ),
        ("using System;\nnamespace Demo {\n}\n", "csharp"),
        ("#include <vector>\nstd::vector<int> v;\n", "cpp"),
        ("#include <stdio.h>\nint add(int a, int b) { return a + b; }\n", "c"),
        ("<?php\nfunction add($a, $b) { return $a + $b; }\n", "php"),
        ("def greet\n  puts 'hi'\nend\n", "ruby"),
    ],
)
def test_detect_from_content(code, key):
    lang, source = detect_language(code)
    assert (lang.key, source) == (key, "content")


def test_detect_precedence():
    code = "def add(a, b):\n    return a + b\n"
    assert detect_language(code, language="go")[0].key == "go"
    assert detect_language(code, language="go")[1] == "request"
    assert detect_language(code, filename="x.rs") == (get_language("rust"), "filename")
    # Unknown extension falls through to content detection.
    assert detect_language(code, filename="x.txt") == (get_language("python"), "content")
    # Blank language string is treated as not given.
    assert detect_language(code, language="  ")[1] == "content"


def test_detect_fallback():
    assert detect_language("SELECT 1;") == (GENERIC, "fallback")


def test_detect_unknown_explicit_language():
    with pytest.raises(UnknownLanguageError):
        detect_language("x", language="brainfuck")
