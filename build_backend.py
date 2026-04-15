"""Minimal PEP 517 backend for the local project.

This backend avoids external build-time dependencies, so editable installs
work in a restricted/offline environment.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import re
import tarfile
from pathlib import Path
import zipfile

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 not supported here.
    import tomli as tomllib  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parent
PYPROJECT = ROOT / "pyproject.toml"
PROJECT = None
WHEEL_TAG = "py3-none-any"


def _project_data() -> dict:
    global PROJECT
    if PROJECT is not None:
        return PROJECT
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)["project"]
    PROJECT = data
    return data


def _dist_name() -> str:
    return re.sub(r"[-.]+", "_", _project_data()["name"])


def _dist_info_dirname() -> str:
    return f"{_dist_name()}-{_project_data()['version']}.dist-info"


def _metadata_text() -> str:
    project = _project_data()
    lines = [
        "Metadata-Version: 2.3",
        f"Name: {project['name']}",
        f"Version: {project['version']}",
    ]
    description = project.get("description")
    if description:
        lines.append(f"Summary: {description}")
    requires_python = project.get("requires-python")
    if requires_python:
        lines.append(f"Requires-Python: {requires_python}")
    for dependency in project.get("dependencies", []):
        lines.append(f"Requires-Dist: {dependency}")
    for extra_name, extra_deps in project.get("optional-dependencies", {}).items():
        lines.append(f"Provides-Extra: {extra_name}")
        for dependency in extra_deps:
            lines.append(f'Requires-Dist: {dependency} ; extra == "{extra_name}"')
    return "\n".join(lines) + "\n"


def _wheel_text() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: build_backend",
            "Root-Is-Purelib: true",
            f"Tag: {WHEEL_TAG}",
            "",
        ]
    )


def _top_level_text() -> str:
    return "app\n"


def _write_metadata_tree(metadata_directory: str) -> str:
    dist_info = Path(metadata_directory) / _dist_info_dirname()
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(_metadata_text(), encoding="utf-8")
    (dist_info / "WHEEL").write_text(_wheel_text(), encoding="utf-8")
    (dist_info / "top_level.txt").write_text(_top_level_text(), encoding="utf-8")
    return dist_info.name


def _wheel_name() -> str:
    return f"{_dist_name()}-{_project_data()['version']}-{WHEEL_TAG}.whl"


def _hashed_record(path: str, content: bytes) -> list[str]:
    digest = hashlib.sha256(content).digest()
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return [path, f"sha256={encoded}", str(len(content))]


def _build_wheel_file(wheel_directory: str) -> str:
    wheel_path = Path(wheel_directory) / _wheel_name()
    dist_info = _dist_info_dirname()
    pth_name = f"{_dist_name()}.pth"
    pth_text = f"{ROOT.as_posix()}\n"

    files: list[tuple[str, bytes]] = [
        (pth_name, pth_text.encode("utf-8")),
        (f"{dist_info}/METADATA", _metadata_text().encode("utf-8")),
        (f"{dist_info}/WHEEL", _wheel_text().encode("utf-8")),
        (f"{dist_info}/top_level.txt", _top_level_text().encode("utf-8")),
    ]

    record_rows = [_hashed_record(path, content) for path, content in files]
    record_rows.append([f"{dist_info}/RECORD", "", ""])
    record_buffer = io.StringIO()
    writer = csv.writer(record_buffer, lineterminator="\n")
    writer.writerows(record_rows)
    files.append((f"{dist_info}/RECORD", record_buffer.getvalue().encode("utf-8")))

    wheel_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, content in files:
            zf.writestr(path, content)
    return wheel_path.name


def _build_sdist_file(sdist_directory: str) -> str:
    archive_name = f"{_dist_name()}-{_project_data()['version']}.tar.gz"
    archive_path = Path(sdist_directory) / archive_name
    root_prefix = f"{_dist_name()}-{_project_data()['version']}"
    include_paths = [
        "app",
        "alembic",
        "tests",
        "README.md",
        "pyproject.toml",
        ".env.example",
        "infra",
        "docs",
        "alembic.ini",
    ]

    with tarfile.open(archive_path, "w:gz") as tf:
        for rel_path in include_paths:
            src = ROOT / rel_path
            if not src.exists():
                continue
            tf.add(src, arcname=f"{root_prefix}/{rel_path}")
    return archive_path.name


def get_requires_for_build_wheel(config_settings=None):  # noqa: D401
    return []


def get_requires_for_build_editable(config_settings=None):  # noqa: D401
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):  # noqa: D401
    return _write_metadata_tree(metadata_directory)


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None):  # noqa: D401
    return _write_metadata_tree(metadata_directory)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):  # noqa: D401
    return _build_wheel_file(wheel_directory)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):  # noqa: D401
    return _build_wheel_file(wheel_directory)


def build_sdist(sdist_directory, config_settings=None):  # noqa: D401
    return _build_sdist_file(sdist_directory)
