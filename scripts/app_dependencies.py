"""Print a Mermaid chart of imports between geniza apps.

Run from any directory with ``python scripts/app_dependencies.py`` (using the
appropriate path to this script). Excludes tests and migrations; arrows point
from the importing app to the imported app. Dynamic imports and non-Python
dependencies are not included. Does not require Django or third-party packages.

Use ``--find entities`` to list imports of that app from other apps, with source paths and line numbers.
"""

import argparse
import ast
from importlib.util import resolve_name
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent / "geniza"
    apps = {path.parent.name for path in root.glob("*/apps.py")}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--find",
        dest="target",
        metavar="APP",
        help="show imports of APP from other apps instead of the Mermaid chart",
    )
    args = parser.parse_args()
    if args.target:
        args.target = args.target.removeprefix("geniza.")
        if args.target not in apps:
            parser.error(
                f"unknown app {args.target!r}; choose from {', '.join(sorted(apps))}"
            )
    edges = set()
    details = set()

    for app in sorted(apps):
        for path in (root / app).rglob("*.py"):
            relative = path.relative_to(root.parent)
            if (
                {"tests", "migrations"} & set(relative.parts)
                or path.name.startswith("test_")
                or path.name == "conftest.py"
            ):
                continue

            package = ".".join(relative.parent.parts)
            source_text = path.read_text(encoding="utf-8")
            tree = ast.parse(source_text, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if node.level:
                        module = resolve_name("." * node.level + module, package)
                    modules = [module]
                    # Also handle `from geniza import corpus`.
                    if module == "geniza":
                        modules += [f"geniza.{alias.name}" for alias in node.names]
                else:
                    continue

                for module in modules:
                    parts = module.split(".")
                    if (
                        len(parts) >= 2
                        and parts[0] == "geniza"
                        and parts[1] in apps
                        and parts[1] != app
                    ):
                        edges.add((app, parts[1]))
                        if parts[1] == args.target:
                            statement = ast.get_source_segment(source_text, node)
                            details.add(
                                (
                                    str(relative),
                                    node.lineno,
                                    app,
                                    " ".join(statement.split()),
                                )
                            )

    if args.target:
        for path, lineno, source, statement in sorted(details):
            print(f"{path}:{lineno}:\n\t{source} -> {args.target}: {statement}")
        return

    print("flowchart LR")
    for app in sorted(apps):
        print(f"    {app}")
    for source, target in sorted(edges):
        print(f"    {source} --> {target}")


if __name__ == "__main__":
    main()
