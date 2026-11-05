"""Docs must not advertise deleted Python modules (#215).

Guards:
  - Every ``from llmwiki…`` / ``import llmwiki…`` in tracked ``docs/`` Python
    fences (`` ```python `` or `` ```py ``) resolves (``docs/adapter-authoring.md``
    excluded — placeholder adapters).
  - Every relative path linked from a tracked README names a path on disk.
  - Every AWOS context-gate armed prefix is a real directory.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import re
from pathlib import Path

from llmwiki import REPO_ROOT
from tests.awos_context_gate import ARMED_PREFIXES
from tests.tracked_files import tracked_files

_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_IMPORT_SCAN_SKIP = frozenset({"docs/adapter-authoring.md"})


def _tracked_docs_markdown(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in tracked_files(repo_root):
        if path.suffix != ".md" or not path.is_file():
            continue
        rel = path.relative_to(repo_root).as_posix()
        if not rel.startswith("docs/"):
            continue
        if rel in _IMPORT_SCAN_SKIP:
            continue
        paths.append(path)
    return paths


def _python_fences(text: str) -> list[str]:
    blocks: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line.startswith("```python") or line.startswith("```py"):
            index += 1
            chunk: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                chunk.append(lines[index])
                index += 1
            blocks.append("\n".join(chunk))
        index += 1
    return blocks


def _imports_from_block(source: str) -> list[tuple[str | None, list[str]]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[tuple[str | None, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if not node.module or not node.module.startswith("llmwiki"):
                continue
            module_suffix: str | None
            if node.module == "llmwiki":
                module_suffix = None
            else:
                module_suffix = node.module.removeprefix("llmwiki.")
            names = [alias.name for alias in node.names if alias.name != "*"]
            found.append((module_suffix, names))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "llmwiki" or alias.name.startswith("llmwiki."):
                    suffix = None if alias.name == "llmwiki" else alias.name.removeprefix("llmwiki.")
                    found.append((suffix, []))
    return found


def _name_resolves(module_name: str, name: str) -> bool:
    module = importlib.import_module(module_name)
    if hasattr(module, name):
        return True
    submodule = f"{module_name}.{name}"
    try:
        return importlib.util.find_spec(submodule) is not None
    except (ModuleNotFoundError, AttributeError, ValueError):
        return False


def _resolve_llmwiki_import(module_suffix: str | None, names: list[str]) -> None:
    module_name = f"llmwiki.{module_suffix}" if module_suffix else "llmwiki"
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, f"module {module_name!r} does not resolve"
    for name in names:
        assert _name_resolves(module_name, name), (
            f"{module_name!r} has no attribute or submodule {name!r}"
        )


def _collect_documented_llmwiki_imports(text: str) -> list[tuple[str | None, list[str]]]:
    found: list[tuple[str | None, list[str]]] = []
    for block in _python_fences(text):
        found.extend(_imports_from_block(block))
    return found


def _is_skipped_link_target(target: str) -> bool:
    lowered = target.lower()
    if not target or target.startswith("#"):
        return True
    return lowered.startswith(("http://", "https://", "mailto:"))


def _linked_paths_from_readme(readme: Path) -> list[Path]:
    if not readme.is_file():
        return []
    text = readme.read_text(encoding="utf-8")
    base = readme.parent
    linked: list[Path] = []
    for match in _MD_LINK.finditer(text):
        target = match.group(1).strip().split(" ", 1)[0]
        target = target.split("#", 1)[0]
        if _is_skipped_link_target(target):
            continue
        if not target:
            continue
        resolved = (base / target).resolve()
        try:
            resolved.relative_to(REPO_ROOT.resolve())
        except ValueError:
            continue
        linked.append(resolved)
    return linked


def test_documented_llmwiki_imports_resolve() -> None:
    """Python examples under ``docs/`` must import real ``llmwiki`` symbols (#215)."""  # @regression
    failures: list[str] = []
    for md_path in _tracked_docs_markdown(REPO_ROOT):
        text = md_path.read_text(encoding="utf-8")
        rel = md_path.relative_to(REPO_ROOT)
        for module_suffix, names in _collect_documented_llmwiki_imports(text):
            try:
                _resolve_llmwiki_import(module_suffix, names)
            except AssertionError as exc:
                failures.append(f"{rel}: {exc}")
    assert not failures, "broken documented imports:\n  " + "\n  ".join(failures)


def test_readme_linked_paths_exist_on_disk() -> None:
    """Relative links in tracked README files must point at real paths (#215)."""  # @regression
    missing: list[str] = []
    for path in tracked_files(REPO_ROOT):
        if path.name != "README.md":
            continue
        for linked in _linked_paths_from_readme(path):
            if linked.exists():
                continue
            missing.append(
                f"{path.relative_to(REPO_ROOT)} → {linked.relative_to(REPO_ROOT)}"
            )
    assert not missing, "README links to missing paths:\n  " + "\n  ".join(missing)


def test_awos_context_gate_armed_prefixes_exist() -> None:
    """Armed gate prefixes must be real directories (#215)."""  # @regression
    missing = [
        prefix
        for prefix in ARMED_PREFIXES
        if not (REPO_ROOT / prefix.rstrip("/")).is_dir()
    ]
    assert not missing, f"armed prefixes with no directory: {missing}"
