"""Print a Mermaid chart of imports between geniza apps.

Run from any directory with ``python scripts/app_dependencies.py`` (using the
appropriate path to this script). Excludes tests and migrations; arrows point
from the importing app to the imported app. Dynamic imports and non-Python
dependencies are not included. Does not require Django or third-party packages.
"""

import ast
from importlib.util import resolve_name
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent / "geniza"
    apps = {path.parent.name for path in root.glob("*/apps.py")}
    edges = set()

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
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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

    print("flowchart LR")
    for app in sorted(apps):
        print(f"    {app}")
    for source, target in sorted(edges):
        print(f"    {source} --> {target}")


if __name__ == "__main__":
    main()
