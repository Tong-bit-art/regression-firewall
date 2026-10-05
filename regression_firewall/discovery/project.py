from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FRAMEWORK_PATTERNS = (
    ("fastapi", "fastapi"),
    ("flask", "flask"),
    ("django", "django"),
    ("click", "click"),
    ("typer", "typer"),
)

_PYPROJECT_NAME_RE = re.compile(r'^name\s*=\s*["\']([^"\']+)["\']', re.M)


@dataclass
class ProjectInfo:
    name: str
    language: str = "unknown"
    frameworks: list = field(default_factory=list)
    package_name: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "language": self.language,
            "frameworks": list(self.frameworks),
            "package_name": self.package_name,
        }

    def summary(self) -> str:
        parts = [self.language]
        if self.frameworks:
            parts.append(", ".join(self.frameworks))
        return " / ".join(parts)


def detect_project(root: Path) -> ProjectInfo:
    root = Path(root)
    name = _detect_name(root)
    language = _detect_language(root)
    frameworks = _detect_frameworks(root) if language == "python" else []
    package_name = _detect_package_name(root, name) if language == "python" else None
    return ProjectInfo(name=name, language=language, frameworks=frameworks,
                       package_name=package_name)


def _detect_name(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        match = _PYPROJECT_NAME_RE.search(pyproject.read_text(encoding="utf-8", errors="replace"))
        if match:
            return match.group(1)
    package_json = root / "package.json"
    if package_json.is_file():
        import json

        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            if isinstance(data.get("name"), str):
                return data["name"]
        except json.JSONDecodeError:
            pass
    return root.resolve().name


def _detect_language(root: Path) -> str:
    markers_python = ("pyproject.toml", "setup.py", "setup.cfg")
    if any((root / m).is_file() for m in markers_python):
        return "python"
    if any(root.glob("requirements*.txt")) or any(root.glob("*.py")):
        return "python"
    if (root / "package.json").is_file():
        return "node"
    if (root / "go.mod").is_file():
        return "go"
    return "unknown"


def _dependency_text(root: Path) -> str:
    chunks = []
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        chunks.append(pyproject.read_text(encoding="utf-8", errors="replace"))
    for req in root.glob("requirements*.txt"):
        chunks.append(req.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks).lower()


def _detect_frameworks(root: Path) -> list:
    text = _dependency_text(root)
    found = []
    for needle, name in FRAMEWORK_PATTERNS:
        if re.search(rf"(?m)^\s*[-A-Za-z_]*{needle}\b", text) or f'"{needle}"' in text or f"'{needle}'" in text:
            found.append(name)
    return found


def _detect_package_name(root: Path, name: str) -> str | None:
    candidate = name.replace("-", "_").split("/")[-1]
    if (root / candidate).is_dir() or (root / "src" / candidate).is_dir():
        return candidate
    return None
