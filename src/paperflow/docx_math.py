from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from xml.dom import Node, minidom
from xml.dom.minidom import Element

MATH_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _element_children(node: Node) -> list[Element]:
    return [child for child in node.childNodes if child.nodeType == Node.ELEMENT_NODE]


def _has_ancestor(node: Node, *, namespace: str, local_name: str) -> bool:
    parent = node.parentNode
    while parent is not None:
        if parent.namespaceURI == namespace and parent.localName == local_name:
            return True
        parent = parent.parentNode
    return False


def _is_protected_inline_math(node: Element) -> bool:
    children = _element_children(node)
    if len(children) != 1:
        return False
    box = children[0]
    if box.namespaceURI != MATH_NAMESPACE or box.localName != "box":
        return False

    box_properties = next(
        (
            child
            for child in _element_children(box)
            if child.namespaceURI == MATH_NAMESPACE and child.localName == "boxPr"
        ),
        None,
    )
    if box_properties is None:
        return False
    no_break = next(
        (
            child
            for child in _element_children(box_properties)
            if child.namespaceURI == MATH_NAMESPACE and child.localName == "noBreak"
        ),
        None,
    )
    if no_break is None:
        return False

    value = no_break.getAttributeNS(MATH_NAMESPACE, "val").strip().lower()
    return value not in {"0", "false", "off", "no"}


def _inline_math_nodes(document: minidom.Document) -> list[Element]:
    return [
        node
        for node in document.getElementsByTagNameNS(MATH_NAMESPACE, "oMath")
        if not _has_ancestor(node, namespace=MATH_NAMESPACE, local_name="oMathPara")
    ]


def _protect_xml_inline_math(xml: bytes) -> tuple[bytes, int]:
    document = minidom.parseString(xml)
    changed = 0
    for math in _inline_math_nodes(document):
        if _is_protected_inline_math(math):
            continue

        box = document.createElementNS(MATH_NAMESPACE, "m:box")
        box_properties = document.createElementNS(MATH_NAMESPACE, "m:boxPr")
        no_break = document.createElementNS(MATH_NAMESPACE, "m:noBreak")
        no_break.setAttributeNS(MATH_NAMESPACE, "m:val", "1")
        expression = document.createElementNS(MATH_NAMESPACE, "m:e")

        box_properties.appendChild(no_break)
        box.appendChild(box_properties)
        while math.firstChild is not None:
            expression.appendChild(math.firstChild)
        box.appendChild(expression)
        math.appendChild(box)
        changed += 1

    if not changed:
        return xml, 0
    return document.toxml(encoding="UTF-8"), changed


def _math_xml_members(archive: zipfile.ZipFile) -> list[str]:
    return [
        name
        for name in archive.namelist()
        if name.startswith("word/") and name.endswith(".xml") and b"oMath" in archive.read(name)
    ]


def docx_inline_math_protection(path: Path) -> tuple[int, int]:
    total = 0
    protected = 0
    with zipfile.ZipFile(path) as archive:
        for name in _math_xml_members(archive):
            document = minidom.parseString(archive.read(name))
            inline_math = _inline_math_nodes(document)
            total += len(inline_math)
            protected += sum(_is_protected_inline_math(node) for node in inline_math)
    return total, protected


def protect_docx_inline_math(path: Path) -> int:
    modified_members: dict[str, bytes] = {}
    changed = 0
    with zipfile.ZipFile(path) as archive:
        for name in _math_xml_members(archive):
            transformed, member_changes = _protect_xml_inline_math(archive.read(name))
            if member_changes:
                modified_members[name] = transformed
                changed += member_changes

    if not changed:
        return 0

    with tempfile.NamedTemporaryFile(
        prefix=f".{path.stem}-",
        suffix=".docx",
        dir=path.parent,
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)

    try:
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(
            temporary_path, "w", zipfile.ZIP_DEFLATED
        ) as target:
            for item in source.infolist():
                data = modified_members.get(item.filename)
                if data is None:
                    data = source.read(item.filename)
                target.writestr(item, data)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise

    return changed
