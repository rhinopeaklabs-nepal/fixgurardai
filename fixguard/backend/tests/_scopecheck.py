"""Find names a function reads that nothing in its scope ever binds.

This is the check that was missing when two handlers in routers/audits.py
shipped reading names that had been renamed out from under them: ``who`` in
the ``POST /audits`` alias, and ``bucket`` in the retry route. Both files
parsed, both imported cleanly, and both raised NameError only once a real
request arrived - so every test that did not happen to exercise that exact
route stayed green, and the retry button advertised by NFR 5.3 was a 500.

It follows Python's real scoping rules rather than approximating them:
comprehensions and lambdas are scopes, a class body is a scope that does not
enclose its own methods, and global/nonlocal/except-as all bind a name.
"""
from __future__ import annotations

import ast
import builtins
import pathlib

BUILTINS = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__all__"}
SCOPES = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
)


def _own_nodes(scope: ast.AST) -> list[ast.AST]:
    """Nodes inside `scope` that are not inside a nested scope of their own."""
    out: list[ast.AST] = []
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        n = stack.pop()
        out.append(n)
        if not isinstance(n, SCOPES):
            stack.extend(ast.iter_child_nodes(n))
    return out


def _params(fn: ast.AST) -> set[str]:
    a = fn.args
    names = {p.arg for p in [*a.posonlyargs, *a.args, *a.kwonlyargs]}
    if a.vararg:
        names.add(a.vararg.arg)
    if a.kwarg:
        names.add(a.kwarg.arg)
    return names


def _binds(scope: ast.AST, own: list[ast.AST]) -> set[str]:
    out: set[str] = set()
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        out |= _params(scope)
    for n in own:
        if isinstance(n, SCOPES) and not isinstance(n, ast.Lambda):
            out.add(getattr(n, "name", ""))
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {(a.asname or a.name.split(".")[0]) for a in n.names}
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            out |= set(n.names)
        elif isinstance(n, ast.comprehension):
            out |= {t.id for t in ast.walk(n.target) if isinstance(t, ast.Name)}
    return out - {""}


def _walk(scope, enclosing: set[str], where: str, out: list[str], file: str) -> None:
    own = _own_nodes(scope)
    here = enclosing | _binds(scope, own)
    for n in own:
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in here:
            out.append(f"{file}:{n.lineno} {where} reads undefined name {n.id!r}")

    # A class body sees the scope around it, but does not itself enclose the
    # scopes defined inside it - a method cannot read a class attribute by
    # bare name. So a nested scope inherits this scope's names unless this
    # scope is a class, in which case it skips straight past to the outside.
    passed = enclosing if isinstance(scope, ast.ClassDef) else here
    for n in own:
        if isinstance(n, SCOPES):
            name = getattr(n, "name", None)
            _walk(n, passed, f"{name}()" if name else f"<{type(n).__name__}>", out, file)


def undefined_in(path: pathlib.Path) -> list[str]:
    out: list[str] = []
    _walk(ast.parse(path.read_text(encoding="utf-8")), BUILTINS, "module", out, path.name)
    return out


def scan(root: str | pathlib.Path = "app") -> list[str]:
    out: list[str] = []
    for f in sorted(pathlib.Path(root).rglob("*.py")):
        out += undefined_in(f)
    return out


def scan_source(src: str, file: str = "<snippet>") -> list[str]:
    """The same check against a string, so the checker itself can be tested."""
    out: list[str] = []
    _walk(ast.parse(src), BUILTINS, "module", out, file)
    return out


if __name__ == "__main__":
    found = scan()
    print("\n".join(found) if found else "clean")
