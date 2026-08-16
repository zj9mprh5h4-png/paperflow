from __future__ import annotations

import shutil
import tempfile
import zipfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

from . import __version__
from .commands import PaperflowError, git, run_command
from .config import PaperflowConfig
from .docx_package import read_docx_members, write_docx_members
from .manifest import git_commit

CUSTOM_PROPERTIES_MEMBER = "docProps/custom.xml"
CORE_PROPERTIES_MEMBER = "docProps/core.xml"
CONTENT_TYPES_MEMBER = "[Content_Types].xml"
ROOT_RELATIONSHIPS_MEMBER = "_rels/.rels"
CUSTOM_PROPERTIES_NAMESPACE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
)
CUSTOM_PROPERTY_TYPES_NAMESPACE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
)
DCTERMS_NAMESPACE = "http://purl.org/dc/terms/"
CONTENT_TYPES_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/content-types"
PACKAGE_RELATIONSHIPS_NAMESPACE = (
    "http://schemas.openxmlformats.org/package/2006/relationships"
)
CUSTOM_PROPERTIES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.custom-properties+xml"
)
CUSTOM_PROPERTIES_RELATIONSHIP_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    "custom-properties"
)
CUSTOM_PROPERTY_FMTID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"


def _build_time(now: datetime | None = None) -> datetime:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0)


def _build_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _build_label(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


def _parse_build_utc(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _xml_bytes(root: ElementTree.Element) -> bytes:
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def _custom_properties_root(xml: bytes | None) -> ElementTree.Element:
    if xml is not None:
        return ElementTree.fromstring(xml)
    return ElementTree.Element(f"{{{CUSTOM_PROPERTIES_NAMESPACE}}}Properties")


def _set_custom_string_properties(
    root: ElementTree.Element,
    values: Mapping[str, str],
) -> None:
    property_tag = f"{{{CUSTOM_PROPERTIES_NAMESPACE}}}property"
    value_tag = f"{{{CUSTOM_PROPERTY_TYPES_NAMESPACE}}}lpwstr"
    properties = {
        item.get("name"): item for item in root.findall(property_tag) if item.get("name")
    }
    used_pids = {
        int(item.get("pid", "0"))
        for item in root.findall(property_tag)
        if item.get("pid", "").isdigit()
    }
    next_pid = max(used_pids, default=1) + 1

    for name, value in values.items():
        prop = properties.get(name)
        if prop is None:
            while next_pid in used_pids:
                next_pid += 1
            prop = ElementTree.SubElement(
                root,
                property_tag,
                {"fmtid": CUSTOM_PROPERTY_FMTID, "pid": str(next_pid), "name": name},
            )
            used_pids.add(next_pid)
            next_pid += 1
        for child in list(prop):
            prop.remove(child)
        ElementTree.SubElement(prop, value_tag).text = value


def _ensure_custom_content_type(xml: bytes) -> bytes:
    root = ElementTree.fromstring(xml)
    override_tag = f"{{{CONTENT_TYPES_NAMESPACE}}}Override"
    for override in root.findall(override_tag):
        if override.get("PartName") == f"/{CUSTOM_PROPERTIES_MEMBER}":
            override.set("ContentType", CUSTOM_PROPERTIES_CONTENT_TYPE)
            return _xml_bytes(root)
    ElementTree.SubElement(
        root,
        override_tag,
        {
            "PartName": f"/{CUSTOM_PROPERTIES_MEMBER}",
            "ContentType": CUSTOM_PROPERTIES_CONTENT_TYPE,
        },
    )
    return _xml_bytes(root)


def _ensure_custom_relationship(xml: bytes) -> bytes:
    root = ElementTree.fromstring(xml)
    relationship_tag = f"{{{PACKAGE_RELATIONSHIPS_NAMESPACE}}}Relationship"
    relationships = root.findall(relationship_tag)
    for relationship in relationships:
        if relationship.get("Type") == CUSTOM_PROPERTIES_RELATIONSHIP_TYPE:
            relationship.set("Target", CUSTOM_PROPERTIES_MEMBER)
            return _xml_bytes(root)
    used_ids = {relationship.get("Id") for relationship in relationships}
    sequence = 1
    while f"rId{sequence}" in used_ids:
        sequence += 1
    ElementTree.SubElement(
        root,
        relationship_tag,
        {
            "Id": f"rId{sequence}",
            "Type": CUSTOM_PROPERTIES_RELATIONSHIP_TYPE,
            "Target": CUSTOM_PROPERTIES_MEMBER,
        },
    )
    return _xml_bytes(root)


def embed_docx_build_metadata(path: Path, values: Mapping[str, str]) -> None:
    """Embed Paperflow provenance without changing the generated document body."""
    members, infos = read_docx_members(path)

    if CONTENT_TYPES_MEMBER not in members or ROOT_RELATIONSHIPS_MEMBER not in members:
        raise PaperflowError(f"Generated DOCX package metadata is incomplete: {path}")

    try:
        custom_root = _custom_properties_root(members.get(CUSTOM_PROPERTIES_MEMBER))
        _set_custom_string_properties(custom_root, values)
        members[CUSTOM_PROPERTIES_MEMBER] = _xml_bytes(custom_root)
        members[CONTENT_TYPES_MEMBER] = _ensure_custom_content_type(
            members[CONTENT_TYPES_MEMBER]
        )
        members[ROOT_RELATIONSHIPS_MEMBER] = _ensure_custom_relationship(
            members[ROOT_RELATIONSHIPS_MEMBER]
        )
    except ElementTree.ParseError as exc:
        raise PaperflowError(f"Could not parse generated DOCX metadata: {path}") from exc

    write_docx_members(path, members, infos)


def _custom_docx_property(path: Path, name: str) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read(CUSTOM_PROPERTIES_MEMBER)
        root = ElementTree.fromstring(xml)
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
        return None
    property_tag = f"{{{CUSTOM_PROPERTIES_NAMESPACE}}}property"
    for prop in root.findall(property_tag):
        if prop.get("name") == name and len(prop):
            return prop[0].text or ""
    return None


def _core_created_time(path: Path) -> datetime | None:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read(CORE_PROPERTIES_MEMBER)
        root = ElementTree.fromstring(xml)
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
        return None
    created = root.find(f"{{{DCTERMS_NAMESPACE}}}created")
    return _parse_build_utc(created.text or "") if created is not None else None


def _archive_label(path: Path) -> str:
    embedded = _custom_docx_property(path, "PaperflowBuildUTC")
    embedded_time = _parse_build_utc(embedded or "")
    if embedded_time is not None:
        return _build_label(embedded_time)
    created = _core_created_time(path)
    if created is not None:
        return _build_label(created)
    return _build_label(datetime.fromtimestamp(path.stat().st_mtime, UTC))


def _archive_stem(path: Path) -> str:
    for suffix in ("_current", "-current"):
        if path.stem.lower().endswith(suffix):
            return path.stem[: -len(suffix)]
    return path.stem


def _legacy_current_path(path: Path) -> Path | None:
    archive_stem = _archive_stem(path)
    if archive_stem == path.stem:
        return None
    return path.with_name(archive_stem + path.suffix)


def _available_archive_path(path: Path, archive_dir: Path, reserved: set[Path]) -> Path:
    base = archive_dir / f"{_archive_stem(path)}_{_archive_label(path)}.docx"
    if not base.exists() and base not in reserved:
        return base
    sequence = 1
    while True:
        candidate = base.with_name(f"{base.stem}_{sequence:02d}.docx")
        if not candidate.exists() and candidate not in reserved:
            return candidate
        sequence += 1


def assert_archive_is_dedicated(archive_dir: Path) -> None:
    """Refuse to treat a directory as the archive when it holds anything else."""
    if not archive_dir.exists():
        return
    if not archive_dir.is_dir():
        raise PaperflowError(
            f"Configured build.archive_dir is not a directory: {archive_dir}",
            code="clean.archive_not_a_directory",
            remediation=(
                "Set build.archive_dir to a dedicated project-relative directory such as "
                "build/archived.",
            ),
        )
    unexpected = sorted(
        child.name
        for child in archive_dir.iterdir()
        if child.is_dir() or child.suffix.lower() != ".docx"
    )
    if not unexpected:
        return
    listed = ", ".join(unexpected[:5])
    if len(unexpected) > 5:
        listed += f", and {len(unexpected) - 5} more"
    raise PaperflowError(
        f"Refusing to delete {archive_dir} because it holds content Paperflow did not "
        f"archive: {listed}",
        code="clean.archive_not_dedicated",
        remediation=(
            "Check build.archive_dir in paperflow.yml; it must be a dedicated directory that "
            "holds only archived DOCX versions.",
            "Move the listed content elsewhere, or delete the directory manually after "
            "confirming what it contains.",
        ),
    )


def remove_archived_versions(archive_dir: Path) -> None:
    """Delete archived DOCX versions without touching unrelated content."""
    assert_archive_is_dedicated(archive_dir)
    if not archive_dir.exists():
        return
    for child in archive_dir.iterdir():
        child.unlink()
    archive_dir.rmdir()


def build_metadata(config: PaperflowConfig, build_time: datetime) -> dict[str, str]:
    try:
        commit = git_commit(config.root)
    except OSError:
        commit = None
    try:
        status = git(
            ["status", "--porcelain", "--untracked-files=normal"],
            cwd=config.root,
            check=False,
        )
        dirty = "unknown" if status.returncode != 0 else str(bool(status.stdout)).lower()
    except OSError:
        dirty = "unknown"
    try:
        quarto = run_command(["quarto", "--version"], cwd=config.root, check=False)
        quarto_version = (
            quarto.stdout.splitlines()[0]
            if quarto.returncode == 0 and quarto.stdout
            else "unknown"
        )
    except OSError:
        quarto_version = "unknown"
    return {
        "PaperflowBuildUTC": _build_utc(build_time),
        "PaperflowSourceCommit": commit or "unknown",
        "PaperflowSourceDirty": dirty,
        "PaperflowVersion": __version__,
        "PaperflowQuartoVersion": quarto_version,
    }


def _locked_output_error(path: Path, *, archive_previous: bool) -> PaperflowError:
    if archive_previous:
        outcome = (
            "After a successful rebuild, the existing document will be archived with its "
            "original build timestamp; it will not be deleted."
        )
    else:
        outcome = "After a successful rebuild, the existing document will be replaced."
    return PaperflowError(
        f"Could not update '{path.name}' because it appears to be open or locked. Close the "
        f"document in Microsoft Word and rerun the command. {outcome}"
    )


def _assert_outputs_replaceable(
    paths: list[Path],
    *,
    archive_previous: bool,
) -> None:
    for path in paths:
        try:
            with path.open("r+b"):
                pass
        except OSError as exc:
            raise _locked_output_error(path, archive_previous=archive_previous) from exc


def _temporary_publication_copy(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        delete=False,
    ) as temporary:
        prepared = Path(temporary.name)
        with source.open("rb") as staged:
            shutil.copyfileobj(staged, temporary)
    return prepared


def publish_docx_outputs(
    staged_outputs: Mapping[Path, Path],
    *,
    config: PaperflowConfig,
    now: datetime | None = None,
) -> None:
    """Publish validated DOCX files together, archiving or restoring all existing outputs."""
    if not staged_outputs:
        return
    destinations = list(staged_outputs)
    if len(set(destinations)) != len(destinations):
        raise PaperflowError("DOCX publication destinations must be unique.")
    for destination, staged in staged_outputs.items():
        if not staged.is_file():
            raise PaperflowError(f"Staged DOCX does not exist for {destination}: {staged}")

    build_time = _build_time(now)
    if config.build.embed_provenance:
        metadata = build_metadata(config, build_time)
        for staged in staged_outputs.values():
            embed_docx_build_metadata(staged, metadata)

    existing = [path for path in destinations if path.exists()]
    if config.build.archive_previous:
        for destination in destinations:
            legacy = _legacy_current_path(destination)
            if legacy is not None and legacy.exists() and legacy not in existing:
                existing.append(legacy)
    _assert_outputs_replaceable(
        existing,
        archive_previous=config.build.archive_previous,
    )

    archive_dir = config.build.archive_dir
    reserved: set[Path] = set()
    rotations: list[tuple[Path, Path]] = []
    temporary_backups: list[Path] = []
    if config.build.archive_previous and existing:
        archive_dir.mkdir(parents=True, exist_ok=True)
    for destination in existing:
        if config.build.archive_previous:
            backup = _available_archive_path(destination, archive_dir, reserved)
            reserved.add(backup)
        else:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.name}.backup-",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as handle:
                backup = Path(handle.name)
            backup.unlink()
            temporary_backups.append(backup)
        rotations.append((destination, backup))

    prepared: dict[Path, Path] = {}
    rotated: list[tuple[Path, Path]] = []
    promoted: list[Path] = []
    try:
        for destination, staged in staged_outputs.items():
            prepared[destination] = _temporary_publication_copy(staged, destination)
        for current, backup in rotations:
            current.rename(backup)
            rotated.append((current, backup))
        for destination in destinations:
            prepared[destination].replace(destination)
            promoted.append(destination)
    except OSError as exc:
        for destination in reversed(promoted):
            destination.unlink(missing_ok=True)
        for current, backup in reversed(rotated):
            if backup.exists() and not current.exists():
                backup.rename(current)
        locked = next((path for path in existing if path.exists()), destinations[0])
        raise _locked_output_error(
            locked,
            archive_previous=config.build.archive_previous,
        ) from exc
    finally:
        for prepared_copy in prepared.values():
            prepared_copy.unlink(missing_ok=True)
        if not config.build.archive_previous:
            for backup in temporary_backups:
                backup.unlink(missing_ok=True)
