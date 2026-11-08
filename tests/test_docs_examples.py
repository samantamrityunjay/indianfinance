"""Run the Python examples in docs/**/*.md and in package docstrings (T-005).

The harness (top half) and its self-tests are test code owned by qa. The real tests
guard the docs from now on.
"""

import ast
import contextlib
import doctest
import importlib
import importlib.util
import pkgutil
import re
import socket
import traceback
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import pytest

import indianfinance

DOCS_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "docs"
DOCTEST_FLAGS: Final[int] = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
PYTHON_ALIASES: Final[frozenset[str]] = frozenset(
    {"py", "py3", "python3", "pycon", "pyi", "ipython", "ipython3"}
)
NETWORK_MESSAGE: Final[str] = (
    "network access in a docs example: mark the block <!-- docs-test: live -->"
)
_OPEN = re.compile(r"^( *)(`{3,}|~{3,})(.*)$")
_MARKER = re.compile(r"^\s*<!--\s*docs-test:\s*(\S+)\s*-->\s*$")
_SNIPPET = re.compile(r"^\s*-+8<-+")
_ATTR_PROBLEM: Final[str] = "example in an attribute docstring is not run"
_EXAMPLE_HEADER = re.compile(r"^\s*Examples?:\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class CodeBlock:
    path: str
    line: int  # 1-based line of the first code line
    language: str
    code: str
    marker: Literal["skip", "live"] | None


class DocsExampleError(Exception):
    """A docs page is malformed in a way that would leave an example untested."""


def extract_code_blocks(text: str, path: str) -> list[CodeBlock]:
    """Return every fenced code block (all languages) in document order."""
    lines = text.splitlines()
    blocks: list[CodeBlock] = []
    pending: tuple[int, str] | None = None  # (1-based marker line, value)

    def orphan(at: int) -> DocsExampleError:
        return DocsExampleError(
            f"{path}:{at}: docs-test marker is not followed by a code block"
        )

    i = 0
    while i < len(lines):
        line = lines[i]
        marker_match = _MARKER.match(line)
        if marker_match:
            if pending:
                raise orphan(pending[0])
            value = marker_match.group(1)
            if value not in ("skip", "live"):
                raise DocsExampleError(
                    f"{path}:{i + 1}: unknown docs-test marker '{value}'"
                )
            pending = (i + 1, value)
            i += 1
            continue
        fence = _OPEN.match(line)
        if fence and fence.group(2)[0] == "`" and "`" in fence.group(3):
            fence = None  # inline code, not a fence
        if fence is None:
            if line.strip() and pending:
                raise orphan(pending[0])
            i += 1
            continue
        indent, run, info = fence.group(1), fence.group(2), fence.group(3).strip()
        close = re.compile(
            rf"^ {{{len(indent)}}}{re.escape(run[0])}{{{len(run)},}}\s*$"
        )
        end = next((j for j in range(i + 1, len(lines)) if close.match(lines[j])), None)
        if end is None:
            raise DocsExampleError(f"{path}:{i + 1}: unclosed fence")
        language = info.split()[0].lower() if info else ""
        if language in PYTHON_ALIASES or (
            info.startswith("{") and re.search(r"\.(py\w*|ipython\w*)\b", info)
        ):
            raise DocsExampleError(f"{path}:{i + 1}: use ```python")
        if pending and language != "python":
            raise DocsExampleError(
                f"{path}:{pending[0]}: docs-test marker on a non-python block"
            )
        body = [
            ln[min(len(ln) - len(ln.lstrip(" ")), len(indent)) :]
            for ln in lines[i + 1 : end]
        ]
        if language == "python":
            for offset, ln in enumerate(body):
                if _SNIPPET.match(ln):
                    raise DocsExampleError(
                        f"{path}:{i + 2 + offset}: snippet include in a python block"
                    )
        marker: Literal["skip", "live"] | None = None
        if pending:
            marker = "live" if pending[1] == "live" else "skip"
        pending = None
        code = "".join(f"{ln}\n" for ln in body)
        blocks.append(CodeBlock(path, i + 2, language, code, marker))
        i = end + 1
    if pending:
        raise orphan(pending[0])
    return blocks


def page_is_live(blocks: list[CodeBlock]) -> bool:
    """True if any python block is marked "live"."""
    return any(b.language == "python" and b.marker == "live" for b in blocks)


def run_page(blocks: list[CodeBlock]) -> int:
    """Run the python blocks in order in one namespace; return how many ran."""
    namespace: dict[str, object] = {"__name__": "__main__"}
    ran = 0
    for block in blocks:
        if block.language != "python" or block.marker == "skip":
            continue
        source = "\n" * (block.line - 1) + block.code
        exec(compile(source, block.path, "exec"), namespace)
        ran += 1
    return ran


def run_docstring_examples(module: types.ModuleType) -> int:
    """Run the `>>>` examples in the docstrings of `module` with stdlib doctest."""
    finder = doctest.DocTestFinder(exclude_empty=True)
    runner = doctest.DocTestRunner(optionflags=DOCTEST_FLAGS)
    report: list[str] = []
    attempted = 0
    for test in finder.find(module):
        attempted += runner.run(test, out=report.append).attempted
    if runner.failures:
        pytest.fail("\n".join(report), pytrace=False)
    return attempted


def example_sections_without_doctest(source: str, name: str) -> list[str]:
    """Return problems in a module's source, as "<name>:<lineno>: <problem>"."""
    problems: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        doc = ast.get_docstring(node, clean=False)
        if doc and _EXAMPLE_HEADER.search(doc) and ">>>" not in doc:
            problems.append(
                f"{name}:{node.body[0].lineno}: Example section without >>>"
            )
        for stmt in node.body[1:]:
            if (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
                and ">>>" in stmt.value.value
            ):
                problems.append(f"{name}:{stmt.lineno}: {_ATTR_PROBLEM}")
    return problems


def iter_pages() -> list[str]:
    """All `*.md` files under DOCS_DIR as sorted "/" paths; [] if missing."""
    if not DOCS_DIR.is_dir():
        return []
    return sorted(p.relative_to(DOCS_DIR).as_posix() for p in DOCS_DIR.rglob("*.md"))


def iter_package_modules() -> list[str]:
    """'indianfinance' plus every submodule name, sorted."""
    package = importlib.import_module("indianfinance")
    names = [m.name for m in pkgutil.walk_packages(package.__path__, "indianfinance.")]
    return sorted(["indianfinance", *names])


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args: object, **kwargs: object) -> None:
        raise RuntimeError(NETWORK_MESSAGE)

    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "gethostbyname", _blocked)
    monkeypatch.setattr(socket, "gethostbyname_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)


def _page_params() -> list[pytest.ParameterSet]:
    pages = iter_pages()
    if not pages:
        skip = pytest.mark.skip(reason="docs/ not present")
        return [pytest.param("docs-missing", marks=skip)]
    params: list[pytest.ParameterSet] = []
    for page in pages:
        try:
            text = (DOCS_DIR / page).read_text(encoding="utf-8")
            live = page_is_live(extract_code_blocks(text, page))
        except DocsExampleError:
            live = False  # the page test itself reports the error
        params.append(pytest.param(page, marks=pytest.mark.live if live else ()))
    return params


def _execute_page(
    text: str,
    path: str,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> int:
    blocks = extract_code_blocks(text, path)
    monkeypatch.chdir(tmp_path)
    if not page_is_live(blocks):
        request.getfixturevalue("no_network")
    return run_page(blocks)


def _md(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def _module(source: str) -> types.ModuleType:
    module = types.ModuleType("fakemod")
    exec(source, module.__dict__)
    return module


# ---- real tests: these guard the docs from now on ---------------------------------


@pytest.mark.parametrize("page", _page_params(), ids=str)
def test_docs_page_examples_run(
    page: str,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:  # AC1
    text = (DOCS_DIR / page).read_text(encoding="utf-8")
    _execute_page(text, page, request, monkeypatch, tmp_path)


@pytest.mark.parametrize("module_name", iter_package_modules())
def test_docstring_examples_pass(module_name: str, no_network: None) -> None:  # AC6
    run_docstring_examples(importlib.import_module(module_name))


@pytest.mark.parametrize("module_name", iter_package_modules())
def test_example_sections_have_doctests(module_name: str) -> None:  # AC7
    spec = importlib.util.find_spec(module_name)
    assert spec is not None
    assert spec.origin is not None
    source = Path(spec.origin).read_text(encoding="utf-8")
    assert example_sections_without_doctest(source, module_name) == []


def test_docs_pages_are_collected() -> None:  # AC1
    if not DOCS_DIR.is_dir():
        pytest.skip("docs/ not present")
    assert "install.md" in iter_pages()


def test_install_page_block_runs_once(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:  # AC1
    path = DOCS_DIR / "install.md"
    if not path.is_file():
        pytest.skip("docs/ not present")
    text = path.read_text(encoding="utf-8")
    assert _execute_page(text, "install.md", request, monkeypatch, tmp_path) == 1
    assert capsys.readouterr().out == indianfinance.__version__ + "\n"


# ---- self-tests: extract_code_blocks ----------------------------------------------

_SKIP, _LIVE = "<!-- docs-test: skip -->", "<!-- docs-test: live -->"
# id -> (markdown lines, [(line, language, code, marker), ...])
EXTRACT_CASES: dict[str, tuple[tuple[str, ...], list[tuple[object, ...]]]] = {
    "top-level": (  # AC2
        ("# Title", "", "```python", "x = 1", "```"),
        [(4, "python", "x = 1\n", None)],
    ),
    "tab": (  # AC2
        ('=== "uv"', "", "    ```python", "    a = 1", "", "    b = 2", "    ```"),
        [(4, "python", "a = 1\n\nb = 2\n", None)],
    ),
    "tab-in-admonition": (  # AC2
        (
            "!!! note",
            "",
            '    === "pip"',
            "",
            "        ```python",
            "        print(1)",
            "        ```",
        ),
        [(6, "python", "print(1)\n", None)],
    ),
    "tilde": (("~~~text", "hello", "~~~"), [(2, "text", "hello\n", None)]),  # AC2
    "long-fence": (  # AC2
        ("````markdown", "```python", "x = 1", "```", "````", "after"),
        [(2, "markdown", "```python\nx = 1\n```\n", None)],
    ),
    "language-before-options": (  # AC2
        ('```Python title="x.py"', "x = 1", "```"),
        [(2, "python", "x = 1\n", None)],
    ),
    "tab-indented-fence-ignored": (("\t```python", "\tx = 1", "\t```"), []),  # AC2
    "skip-marker": (  # AC2, AC4
        (_SKIP, "", "```python", "x = 1", "```"),
        [(4, "python", "x = 1\n", "skip")],
    ),
    "live-marker": (  # AC2, AC4
        (_LIVE, "", "```python", "x = 1", "```"),
        [(4, "python", "x = 1\n", "live")],
    ),
    "marker-applies-to-next-block-only": (  # AC2
        (_SKIP, "```python", "a", "```", "```python", "b", "```"),
        [(3, "python", "a\n", "skip"), (6, "python", "b\n", None)],
    ),
    "snippet-outside-fence": (('--8<-- "CHANGELOG.md"',), []),  # AC5
    "non-python-languages": (  # AC5
        ("```bash", "ls", "```", "```", "plain", "```", "```mermaid", "A-->B", "```"),
        [
            (2, "bash", "ls\n", None),
            (5, "", "plain\n", None),
            (8, "mermaid", "A-->B\n", None),
        ],
    ),
}


@pytest.mark.parametrize(
    ("lines", "expected"), EXTRACT_CASES.values(), ids=list(EXTRACT_CASES)
)
def test_extract_code_blocks_reads_blocks(
    lines: tuple[str, ...], expected: list[tuple[object, ...]]
) -> None:
    blocks = extract_code_blocks(_md(*lines), "p.md")
    assert [(b.line, b.language, b.code, b.marker) for b in blocks] == expected


_ALIAS = r"p\.md:2: use ```python"
_ORPHAN = r"p\.md:1: docs-test marker is not followed by a code block"
# id -> (markdown lines, error regex)
REJECT_CASES: dict[str, tuple[tuple[str, ...], str]] = {
    "unclosed-fence": (("text", "```python", "x = 1"), r"p\.md:2: unclosed fence"),
    "unknown-marker": (
        ("<!-- docs-test: maybe -->", "```python", "x", "```"),
        r"p\.md:1: unknown docs-test marker 'maybe'",
    ),
    "orphan-text-between": ((_SKIP, "some text", "```python", "x", "```"), _ORPHAN),
    "orphan-two-markers": ((_SKIP, _LIVE, "```python", "x", "```"), _ORPHAN),
    "orphan-end-of-file": ((_SKIP,), _ORPHAN),
    "marker-on-non-python": (
        (_SKIP, "```bash", "ls", "```"),
        r"p\.md:1: docs-test marker on a non-python",
    ),
    "snippet-in-python-block": (
        ("```python", '--8<-- "CHANGELOG.md"', "```"),
        r"p\.md:2: snippet include in a python block",
    ),
    **{
        f"alias-{info}": (("", f"```{info}", "x", "```"), _ALIAS)
        for info in [
            *sorted(PYTHON_ALIASES),
            *(f"{{ .{name} }}" for name in ("python", "py", "pycon", "pyi")),
            *(f"{{ .{name} }}" for name in ("python3", "ipython")),
        ]
    },
}  # all AC5


@pytest.mark.parametrize(
    ("lines", "error"), REJECT_CASES.values(), ids=list(REJECT_CASES)
)
def test_extract_code_blocks_rejects_malformed_page(
    lines: tuple[str, ...], error: str
) -> None:
    with pytest.raises(DocsExampleError, match=error):
        extract_code_blocks(_md(*lines), "p.md")


# ---- self-tests: page and docstring runners ---------------------------------------


@pytest.mark.parametrize(
    ("lines", "ran"),
    [
        (("```python", "a = 21", "```", "x", "```python", "assert a == 21", "```"), 2),
        ((_SKIP, "```python", "def (:", "```", "```python", "b = 1", "```"), 1),
        (("```bash", "not python (", "```", "```mermaid", "A-->B", "```"), 0),
        (("```python", "```"), 1),
    ],
    ids=["shared-namespace", "skip-not-compiled", "non-python-ignored", "empty-block"],
)
def test_run_page_counts_python_blocks_run(lines: tuple[str, ...], ran: int) -> None:
    assert run_page(extract_code_blocks(_md(*lines), "p.md")) == ran  # AC3


def test_run_page_traceback_names_page_and_line() -> None:  # AC3
    text = _md("# T", "", "```python", "x = 1", "", "raise ValueError('boom')", "```")
    with pytest.raises(ValueError, match="boom") as info:
        run_page(extract_code_blocks(text, "pages/p.md"))
    frames = [
        (f.filename, f.lineno) for f in traceback.extract_tb(info.value.__traceback__)
    ]
    assert ("pages/p.md", 6) in frames


def test_docs_page_runs_in_tmp_path(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:  # AC3
    code = ("import pathlib", 'pathlib.Path("o.txt").write_text("x")')
    text = _md("```python", *code, "```")
    assert _execute_page(text, "p.md", request, monkeypatch, tmp_path) == 1
    assert (tmp_path / "o.txt").read_text() == "x"


def test_docs_page_blocks_network_unless_live(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:  # AC4, AC8
    code = ("import socket", 'socket.getaddrinfo("example.invalid", 80)')
    text = _md("```python", *code, "```")
    with pytest.raises(RuntimeError, match="docs-test: live"):
        _execute_page(text, "p.md", request, monkeypatch, tmp_path)


def test_live_page_keeps_network_unblocked(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:  # AC4
    code = ("import socket", 'assert socket.getaddrinfo.__name__ == "getaddrinfo"')
    text = _md(_LIVE, "```python", *code, "```")
    assert _execute_page(text, "p.md", request, monkeypatch, tmp_path) == 1


@pytest.mark.parametrize(
    ("lines", "live"),
    [
        (("```python", "a", "```", _LIVE, "```python", "b", "```"), True),
        ((_SKIP, "```python", "a", "```", "```python", "b", "```"), False),
    ],
    ids=["live-marker", "no-live-marker"],
)
def test_page_is_live_only_with_live_marker(lines: tuple[str, ...], live: bool) -> None:
    blocks = extract_code_blocks(_md(*lines), "p.md")
    assert page_is_live(blocks) is live  # AC4


def test_live_page_gets_live_mark(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:  # AC4
    (tmp_path / "sub").mkdir()
    (tmp_path / "plain.md").write_text("```python\nx = 1\n```\n", encoding="utf-8")
    live = f"{_LIVE}\n```python\nx = 1\n```\n"
    (tmp_path / "sub" / "live.md").write_text(live, encoding="utf-8")
    monkeypatch.setitem(globals(), "DOCS_DIR", tmp_path)
    got = [(p.values[0], [m.name for m in p.marks]) for p in _page_params()]
    assert got == [("plain.md", []), ("sub/live.md", ["live"])]


def test_docs_page_test_skips_without_docs_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:  # AC10
    monkeypatch.setitem(globals(), "DOCS_DIR", tmp_path / "missing")
    assert iter_pages() == []
    (param,) = _page_params()
    assert [m.name for m in param.marks] == ["skip"]
    assert param.marks[0].kwargs["reason"] == "docs/ not present"


def _add_module(example: str) -> types.ModuleType:
    doc = "Add.\n\n    Example:\n" + example
    return _module(f'def add(a, b):\n    """{doc}    """\n    return a + b\n')


@pytest.mark.parametrize(
    ("example", "attempted"),
    [
        ("        >>> add(1, 2)\n        3\n", 1),
        ("        >>> add(1, 2)  # doctest: +SKIP\n        99\n", 0),
        ("        >>> list(range(6))\n        [0, 1,\n         ..., 5]\n", 1),
    ],
    ids=["correct", "skip-directive", "ellipsis-and-whitespace-flags"],
)
def test_run_docstring_examples_counts_examples_run(
    example: str, attempted: int
) -> None:
    assert run_docstring_examples(_add_module(example)) == attempted  # AC6


def test_run_docstring_examples_fails_on_wrong_output() -> None:  # AC6
    module = _add_module("        >>> add(1, 2)\n        4\n")
    with pytest.raises(pytest.fail.Exception) as info:
        run_docstring_examples(module)
    assert "Expected:\n    4\nGot:\n    3" in str(info.value)


# ---- self-tests: example guard and network fixture --------------------------------

_DEF = 'def f():\n    """F.\n\n    Example:\n        {}\n    """\n'


@pytest.mark.parametrize(
    ("source", "problems"),
    [
        (_DEF.format("f()"), ["m:2: Example section without >>>"]),
        (
            'X = 1\n"""The value.\n\n>>> X\n1\n"""\n',
            ["m:2: example in an attribute docstring is not run"],
        ),
        (_DEF.format(">>> f()"), []),
    ],
    ids=["missing-doctest", "attribute-docstring", "doctest-accepted"],
)
def test_example_sections_without_doctest_reports(
    source: str, problems: list[str]
) -> None:
    assert example_sections_without_doctest(source, "m") == problems  # AC7


def test_no_network_blocks_dns_and_connect(no_network: None) -> None:  # AC8
    with pytest.raises(RuntimeError, match="docs-test: live"):
        socket.create_connection(("example.invalid", 80))
    with pytest.raises(RuntimeError, match="docs-test: live"):
        socket.getaddrinfo("example.invalid", 80)
    for call in (socket.gethostbyname, socket.gethostbyname_ex):
        with pytest.raises(RuntimeError, match="docs-test: live"):
            call("example.invalid")
    with (
        contextlib.closing(socket.socket()) as sock,
        pytest.raises(RuntimeError, match="docs-test: live"),
    ):
        sock.connect(("127.0.0.1", 9))
