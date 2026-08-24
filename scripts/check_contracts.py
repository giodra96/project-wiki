#!/usr/bin/env python3
"""Check documentation and templates for drift from the schema manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from .schema_contract import (
        DEFAULT_MANIFEST_PATH,
        SchemaContract,
        SchemaContractDependencyError,
        SchemaContractError,
        load_schema_contract,
        strict_yaml_load,
    )
except ImportError:
    from schema_contract import (  # type: ignore[no-redef]
        DEFAULT_MANIFEST_PATH,
        SchemaContract,
        SchemaContractDependencyError,
        SchemaContractError,
        load_schema_contract,
        strict_yaml_load,
    )


SEMVER_PATTERN = re.compile(r"(?<![\d.])(\d+\.\d+\.\d+)(?!\d|\.\d)")


@dataclass(frozen=True)
class DriftFinding:
    code: str
    path: str
    message: str
    line: int | None = None

    def sort_key(self) -> tuple[str, int, str, str]:
        return (self.path.casefold(), self.line or 0, self.code, self.message)


@dataclass(frozen=True)
class ContractReport:
    manifest: str
    schema_version: str
    findings: tuple[DriftFinding, ...]

    @property
    def valid(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "manifest": self.manifest,
            "schema_version": self.schema_version,
            "valid": self.valid,
            "summary": {"findings": len(self.findings)},
            "findings": [asdict(finding) for finding in self.findings],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check project-wiki documentation and templates against schema/project-wiki.yml."
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Project Wiki repository root. Defaults to the skill root.",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Schema manifest path. Defaults to schema/project-wiki.yml.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Defaults to text.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()
    try:
        contract = load_schema_contract(manifest_path)
        report = check_contracts(repo_root, contract)
    except SchemaContractDependencyError as error:
        print_contract_error(args.format, manifest_path, "contract-dependency-error", str(error))
        return 2
    except SchemaContractError as error:
        print_contract_error(args.format, manifest_path, "contract-manifest-invalid", str(error))
        return 2
    except (OSError, ValueError) as error:
        print_contract_error(args.format, manifest_path, "contract-check-error", str(error))
        return 2

    if args.format == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0 if report.valid else 1


def check_contracts(repo_root: Path, contract: SchemaContract) -> ContractReport:
    findings: list[DriftFinding] = []
    check_version_references(repo_root, contract, findings)
    check_public_tree(repo_root, contract, findings)
    check_required_path_references(repo_root, contract, findings)
    check_forbidden_root_paths(repo_root, contract, findings)
    check_intake_artifact_references(repo_root, contract, findings)
    check_template_contracts(repo_root, contract, findings)
    return ContractReport(
        manifest=contract.manifest_path.as_posix(),
        schema_version=contract.schema_version,
        findings=tuple(sorted(findings, key=DriftFinding.sort_key)),
    )


def check_version_references(
    repo_root: Path,
    contract: SchemaContract,
    findings: list[DriftFinding],
) -> None:
    schema_minor = ".".join(contract.schema_version.split(".")[:2])
    for relative, references in contract.documentation.version_references.items():
        path = repo_root / relative
        if not path.is_file():
            findings.append(DriftFinding("contract-file-missing", relative, "Version-bound file is missing."))
            continue
        text = path.read_text(encoding="utf-8")
        for reference in references:
            expected = reference.format(
                schema_version=contract.schema_version,
                schema_minor=schema_minor,
            )
            if expected not in text:
                findings.append(
                    DriftFinding(
                        "schema-version-reference-missing",
                        relative,
                        f"Missing expected schema declaration: {expected!r}.",
                    )
                )
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "schema" not in line.casefold():
                continue
            for match in SEMVER_PATTERN.finditer(line):
                if match.group(1) != contract.schema_version:
                    findings.append(
                        DriftFinding(
                            "schema-version-drift",
                            relative,
                            f"Schema-context version {match.group(1)} differs from {contract.schema_version}.",
                            line_number,
                        )
                    )


def check_public_tree(
    repo_root: Path,
    contract: SchemaContract,
    findings: list[DriftFinding],
) -> None:
    relative = contract.documentation.public_tree_file
    path = repo_root / relative
    if not path.is_file():
        findings.append(DriftFinding("contract-file-missing", relative, "Public tree document is missing."))
        return
    text = path.read_text(encoding="utf-8")
    if not require_unique_heading(text, "Generated Wiki", 2, relative, "public-tree-heading", findings):
        return
    block = fenced_block_after_heading(text, "Generated Wiki")
    if block is None:
        findings.append(DriftFinding("public-tree-block-missing", relative, "Generated Wiki fenced block is missing."))
        return
    actual = parse_ascii_tree(block)
    allowed = expected_tree_nodes(contract)
    for entry in sorted(actual):
        if entry not in allowed:
            findings.append(DriftFinding("public-tree-entry-extra", relative, f"Public tree contains undeclared path '{entry}'."))
        elif actual[entry] != allowed[entry]:
            findings.append(DriftFinding("public-tree-entry-kind-drift", relative, f"Public tree declares '{entry}' as {actual[entry]}, expected {allowed[entry]}."))
    for required in contract.documentation.public_required_paths:
        normalized = required.rstrip("/")
        if normalized not in actual:
            findings.append(DriftFinding("public-tree-entry-missing", relative, f"Public tree omits required path '{required}'."))
        elif actual[normalized] != "directory":
            findings.append(DriftFinding("public-tree-entry-kind-drift", relative, f"Public tree required path '{required}' must be a directory."))


def check_template_contracts(
    repo_root: Path,
    contract: SchemaContract,
    findings: list[DriftFinding],
) -> None:
    catalog_texts: dict[str, str] = {}
    owner_by_heading = {
        heading: owner
        for owner, headings in contract.template_section_inventory.items()
        for heading in headings
    }
    for owner, expected_headings in sorted(contract.template_section_inventory.items()):
        path = repo_root / owner
        if not path.is_file():
            findings.append(DriftFinding("contract-file-missing", owner, "Template catalog file is missing."))
            continue
        owner_text = path.read_text(encoding="utf-8")
        catalog_texts[owner] = owner_text
        owner_headings = headings_at_level(owner_text, level=2)
        duplicate_owner_headings = {
            heading
            for heading in owner_headings
            if owner_headings.count(heading) > 1
        }
        for heading in sorted(duplicate_owner_headings):
            findings.append(DriftFinding("template-heading-duplicate", owner, f"Template section heading {heading!r} appears more than once."))
        actual_owner_headings = set(owner_headings)
        expected_owner_headings = set(expected_headings)
        for heading in sorted(expected_owner_headings - actual_owner_headings):
            findings.append(DriftFinding("template-section-missing", owner, f"Template section {heading!r} is missing."))
        for heading in sorted(actual_owner_headings - expected_owner_headings):
            findings.append(DriftFinding("template-section-extra", owner, f"Undeclared template section {heading!r}."))

    if not catalog_texts:
        return
    wiki_version_heading = PurePosixPath(contract.semantic_paths.wiki_version_file).name
    relative = owner_by_heading[wiki_version_heading]
    wiki_version = load_named_yaml_block(
        catalog_texts.get(relative, ""),
        wiki_version_heading,
        relative,
        findings,
    )
    if wiki_version is not None:
        check_exact_mapping_keys(
            wiki_version,
            {"schema", "schema_version", "schema_updated", "last_migrated", "maintained_by_skill", "notes"},
            relative,
            "WIKI_VERSION",
            findings,
        )
        expected = {
            "schema": contract.schema_name,
            "schema_version": contract.schema_version,
            "schema_updated": contract.schema_updated,
        }
        for field, value in expected.items():
            if str(wiki_version.get(field)) != value:
                findings.append(DriftFinding("template-wiki-version-drift", relative, f"WIKI_VERSION {field} must be {value!r}."))
        if wiki_version.get("last_migrated") != "YYYY-MM-DD":
            findings.append(DriftFinding("template-wiki-version-drift", relative, "WIKI_VERSION last_migrated must be 'YYYY-MM-DD'."))
    document_registry_heading = PurePosixPath(contract.semantic_paths.document_registry_file).name
    relative = owner_by_heading[document_registry_heading]
    document_registry = load_named_yaml_block(
        catalog_texts.get(relative, ""),
        document_registry_heading,
        relative,
        findings,
    )
    if document_registry is not None:
        check_exact_mapping_keys(document_registry, {"version", "updated", "documents"}, relative, "REGISTRY", findings)
        if document_registry.get("version") != contract.document_registry_version:
            findings.append(DriftFinding("template-registry-version-drift", relative, f"REGISTRY version must be {contract.document_registry_version}."))
        if document_registry.get("updated") != "YYYY-MM-DD" or not isinstance(document_registry.get("documents"), list):
            findings.append(DriftFinding("template-registry-shape-drift", relative, "REGISTRY updated/documents shape is invalid."))
    source_registry_heading = PurePosixPath(contract.semantic_paths.source_registry_file).name
    relative = owner_by_heading[source_registry_heading]
    source_registry = load_named_yaml_block(
        catalog_texts.get(relative, ""),
        source_registry_heading,
        relative,
        findings,
    )
    if source_registry is not None:
        check_exact_mapping_keys(source_registry, {"version", "updated", "sources"}, relative, "SOURCE_REGISTRY", findings)
        if source_registry.get("version") != contract.source_registry_version:
            findings.append(DriftFinding("template-source-registry-version-drift", relative, f"SOURCE_REGISTRY version must be {contract.source_registry_version}."))
        if source_registry.get("updated") != "YYYY-MM-DD" or not isinstance(source_registry.get("sources"), list):
            findings.append(DriftFinding("template-source-registry-shape-drift", relative, "SOURCE_REGISTRY updated/sources shape is invalid."))

    sections: dict[str, str] = {}
    section_owners: dict[str, str] = {}
    actual_frontmatter_headings: set[str] = set()
    for owner, owner_text in catalog_texts.items():
        for heading, section in h2_sections(owner_text).items():
            sections[heading] = section
            section_owners[heading] = owner
            block = exact_fenced_block(section, "markdown")
            if block is not None and block.startswith("---\n"):
                actual_frontmatter_headings.add(heading)
    expected_headings = set(contract.template_contracts)
    for heading in sorted(expected_headings - actual_frontmatter_headings):
        relative = owner_by_heading[heading]
        findings.append(DriftFinding("template-inventory-missing", relative, f"Template section {heading!r} is missing or has no exact markdown frontmatter fence."))
    for heading in sorted(actual_frontmatter_headings - expected_headings):
        relative = section_owners[heading]
        findings.append(DriftFinding("template-inventory-extra", relative, f"Undeclared frontmatter template section {heading!r}."))

    for heading in sorted(expected_headings & actual_frontmatter_headings):
        relative = owner_by_heading[heading]
        block = exact_fenced_block(sections[heading], "markdown")
        assert block is not None
        end = block.find("\n---", 4)
        if end < 0:
            findings.append(DriftFinding("template-frontmatter-unclosed", relative, f"Template {heading!r} has unclosed frontmatter."))
            continue
        try:
            payload = strict_yaml_load(block[4:end], "template frontmatter")
        except SchemaContractError as error:
            findings.append(DriftFinding("template-frontmatter-yaml-invalid", relative, str(error)))
            continue
        if not isinstance(payload, dict):
            findings.append(DriftFinding("template-frontmatter-invalid", relative, "Template frontmatter must be a mapping."))
            continue
        expected_template = contract.template_contracts[heading]
        type_contract = contract.document_type_contracts[expected_template.document_type]
        missing_fields = (
            set(contract.frontmatter_fields)
            | set(type_contract.required_fields)
        ) - set(payload)
        if missing_fields:
            findings.append(DriftFinding("template-frontmatter-fields-drift", relative, f"Template frontmatter is missing {sorted(missing_fields)}."))
        document_type = payload.get("type")
        if document_type != expected_template.document_type:
            findings.append(DriftFinding("template-type-drift", relative, f"Template {heading!r} type must be {expected_template.document_type!r}."))
        status = payload.get("status")
        if not isinstance(status, str) or status not in contract.statuses_for_type(document_type):
            findings.append(DriftFinding("template-status-drift", relative, f"Template status {status!r} is invalid for type {document_type!r}."))
        if isinstance(document_type, str):
            generated_status = contract.generated_status_for_type(document_type)
            if generated_status is not None and status != generated_status:
                findings.append(DriftFinding("template-generated-status-drift", relative, f"Template status for {document_type!r} must be {generated_status!r}."))
        confidence = payload.get("confidence")
        if confidence not in contract.confidence_values:
            findings.append(DriftFinding("template-confidence-drift", relative, f"Template confidence {confidence!r} is not declared."))
        severity = payload.get("severity")
        if severity is not None and severity not in contract.alert_severities:
            findings.append(DriftFinding("template-severity-drift", relative, f"Template severity {severity!r} is not declared."))
        template_id = payload.get("id")
        if template_id != expected_template.template_id:
            findings.append(DriftFinding("template-id-drift", relative, f"Template {heading!r} ID must be {expected_template.template_id!r}."))
        pattern = contract.type_id_patterns.get(document_type) if isinstance(document_type, str) else None
        sample_id = sample_template_id(template_id) if isinstance(template_id, str) else None
        if pattern is not None and sample_id is not None and pattern.fullmatch(sample_id) is None:
            findings.append(DriftFinding("template-id-pattern-drift", relative, f"Template ID {template_id!r} does not match type {document_type!r}."))
        for field in ("title",):
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                findings.append(DriftFinding("template-frontmatter-shape-drift", relative, f"Template {heading!r} {field} must be a non-empty string."))
        for field in ("created", "updated"):
            if payload.get(field) != "YYYY-MM-DD":
                findings.append(DriftFinding("template-frontmatter-shape-drift", relative, f"Template {heading!r} {field} must be 'YYYY-MM-DD'."))
        for field in ("tags", "related", "source_paths"):
            value = payload.get(field)
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                findings.append(DriftFinding("template-frontmatter-shape-drift", relative, f"Template {heading!r} {field} must be a list of strings."))


def check_required_path_references(
    repo_root: Path,
    contract: SchemaContract,
    findings: list[DriftFinding],
) -> None:
    public_tree_paths: set[str] = set()
    public_tree_path = repo_root / contract.documentation.public_tree_file
    if public_tree_path.is_file():
        block = fenced_block_after_heading(public_tree_path.read_text(encoding="utf-8"), "Generated Wiki")
        if block is not None:
            public_tree_paths = set(parse_ascii_tree(block))
    for required_path, relative_files in sorted(contract.documentation.required_path_references.items()):
        for relative in relative_files:
            path = repo_root / relative
            if not path.is_file():
                findings.append(DriftFinding("contract-file-missing", relative, "Path-bound documentation file is missing."))
                continue
            text = path.read_text(encoding="utf-8")
            represented_in_public_tree = (
                relative == contract.documentation.public_tree_file
                and required_path.rstrip("/") in public_tree_paths
            )
            if required_path not in text and not represented_in_public_tree:
                findings.append(
                    DriftFinding(
                        "required-path-reference-missing",
                        relative,
                        f"Documentation must reference canonical path '{required_path}'.",
                    )
                )


def check_forbidden_root_paths(
    repo_root: Path,
    contract: SchemaContract,
    findings: list[DriftFinding],
) -> None:
    for forbidden_path, relative_files in sorted(contract.documentation.forbidden_root_paths.items()):
        canonical_matches = [
            path
            for path in contract.documentation.required_path_references
            if path.endswith(forbidden_path.rstrip("/"))
        ]
        if len(canonical_matches) != 1:
            raise ValueError(f"forbidden alias {forbidden_path!r} must map to one canonical required path")
        canonical_prefix = canonical_matches[0][: -len(forbidden_path.rstrip("/"))]
        pattern = re.compile(
            rf"(?<!{re.escape(canonical_prefix)})(?<![A-Za-z0-9_-]){re.escape(forbidden_path)}"
        )
        for relative in relative_files:
            path = repo_root / relative
            if not path.is_file():
                findings.append(DriftFinding("contract-file-missing", relative, "Alias-bound documentation file is missing."))
                continue
            text = path.read_text(encoding="utf-8")
            searchable_text = text
            if relative == contract.documentation.public_tree_file:
                public_tree = fenced_block_after_heading(text, "Generated Wiki")
                if public_tree is not None:
                    searchable_text = searchable_text.replace(
                        public_tree,
                        "\n" * public_tree.count("\n"),
                        1,
                    )
            for match in pattern.finditer(searchable_text):
                findings.append(
                    DriftFinding(
                        "forbidden-root-path-reference",
                        relative,
                        f"Found forbidden root alias '{forbidden_path}'; use the canonical nested path.",
                        line_for_offset(text, match.start()),
                    )
                )


def check_intake_artifact_references(
    repo_root: Path,
    contract: SchemaContract,
    findings: list[DriftFinding],
) -> None:
    for artifact_key, relative_files in sorted(contract.documentation.intake_artifact_references.items()):
        artifact_value = getattr(contract.intake_artifacts, artifact_key)
        for relative in relative_files:
            path = repo_root / relative
            if not path.is_file():
                findings.append(DriftFinding("contract-file-missing", relative, "Artifact-bound documentation file is missing."))
                continue
            if artifact_value not in path.read_text(encoding="utf-8"):
                findings.append(
                    DriftFinding(
                        "intake-artifact-reference-missing",
                        relative,
                        f"Documentation must reference {artifact_key} value {artifact_value!r}.",
                    )
                )


def expected_tree_nodes(contract: SchemaContract) -> dict[str, str]:
    nodes: dict[str, str] = {
        value.rstrip("/"): "directory"
        for value in contract.required_directories
    }
    nodes.update({value: "file" for value in contract.required_files})
    for value in contract.example_files:
        nodes[value.rstrip("/")] = "directory" if value.endswith("/") else "file"
    for value in tuple(nodes):
        parent = PurePosixPath(value).parent
        while parent.as_posix() not in {"", "."}:
            existing = nodes.get(parent.as_posix())
            if existing == "file":
                raise ValueError(f"schema tree path is both file and directory: {parent.as_posix()}")
            nodes[parent.as_posix()] = "directory"
            parent = parent.parent
    return nodes


def fenced_block_after_heading(text: str, heading: str) -> str | None:
    section = h2_sections(text).get(heading)
    if section is None:
        return None
    blocks = fenced_blocks(section)
    return blocks[0][1] if blocks else None


def h2_sections(text: str) -> dict[str, str]:
    return heading_sections(text, level=2)


def headings_at_level(text: str, level: int) -> list[str]:
    lines = text.splitlines()
    headings: list[str] = []
    in_fence = False
    fence_character = ""
    fence_length = 0
    marker_text = "#" * level
    for line in lines:
        fence = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length and not fence.group(2).strip():
                in_fence = False
            continue
        if in_fence:
            continue
        heading_match = re.match(rf"^{re.escape(marker_text)}\s+(?!#)(.+?)\s*$", line)
        if heading_match:
            headings.append(heading_match.group(1))
    return headings


def require_unique_heading(
    text: str,
    heading: str,
    level: int,
    relative: str,
    code_prefix: str,
    findings: list[DriftFinding],
) -> bool:
    count = headings_at_level(text, level).count(heading)
    if count == 1:
        return True
    code = f"{code_prefix}-missing" if count == 0 else f"{code_prefix}-duplicate"
    findings.append(
        DriftFinding(
            code,
            relative,
            f"Expected exactly one level-{level} heading {heading!r}, found {count}.",
        )
    )
    return False


def heading_sections(text: str, level: int) -> dict[str, str]:
    lines = text.splitlines()
    headings: list[tuple[str, int]] = []
    in_fence = False
    fence_character = ""
    fence_length = 0
    for index, line in enumerate(lines):
        fence = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length and not fence.group(2).strip():
                in_fence = False
            continue
        if in_fence:
            continue
        marker = "#" * level
        heading_match = re.match(rf"^{re.escape(marker)}\s+(?!#)(.+?)\s*$", line)
        if heading_match:
            headings.append((heading_match.group(1), index))
    sections: dict[str, str] = {}
    for position, (heading, line_index) in enumerate(headings):
        end = headings[position + 1][1] if position + 1 < len(headings) else len(lines)
        sections[heading] = "\n".join(lines[line_index + 1 : end])
    return sections


def fenced_blocks(section: str) -> list[tuple[str, str]]:
    lines = section.splitlines()
    blocks: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        opening = re.match(r"^\s*(`{3,}|~{3,})\s*([^\s]*)\s*$", lines[index])
        if opening is None:
            index += 1
            continue
        marker = opening.group(1)
        info = opening.group(2)
        content_start = index + 1
        index += 1
        while index < len(lines):
            closing = re.match(r"^\s*(`{3,}|~{3,})\s*$", lines[index])
            if closing and closing.group(1)[0] == marker[0] and len(closing.group(1)) >= len(marker):
                blocks.append((info, "\n".join(lines[content_start:index])))
                break
            index += 1
        index += 1
    return blocks


def exact_fenced_block(section: str, info: str) -> str | None:
    matches = [content for block_info, content in fenced_blocks(section) if block_info == info]
    return matches[0] if len(matches) == 1 else None


def load_named_yaml_block(
    text: str,
    heading: str,
    relative: str,
    findings: list[DriftFinding],
) -> dict[str, Any] | None:
    block = fenced_block_after_heading(text, heading)
    if block is None:
        findings.append(DriftFinding("template-yaml-block-missing", relative, f"Template section {heading!r} has no fenced YAML block."))
        return None
    try:
        payload = strict_yaml_load(block, f"template section {heading}")
    except SchemaContractError as error:
        findings.append(DriftFinding("template-yaml-block-invalid", relative, str(error)))
        return None
    if not isinstance(payload, dict):
        findings.append(DriftFinding("template-yaml-block-invalid", relative, f"Template section {heading!r} must contain a YAML mapping."))
        return None
    return payload


def check_exact_mapping_keys(
    payload: dict[str, Any],
    expected: set[str],
    relative: str,
    label: str,
    findings: list[DriftFinding],
) -> None:
    if set(payload) != expected:
        missing = sorted(expected - set(payload))
        extra = sorted(set(payload) - expected)
        findings.append(
            DriftFinding(
                "template-yaml-shape-drift",
                relative,
                f"{label} keys mismatch; missing={missing}, extra={extra}.",
            )
        )


def sample_template_id(value: str) -> str | None:
    if " or " in value or "<" in value or ">" in value:
        return None
    return (
        value.replace("YYYYMMDD", "20260820")
        .replace("YYYY-MM-DD", "2026-08-20")
        .replace("NNN", "001")
    )


def parse_ascii_tree(block: str) -> dict[str, str]:
    paths: dict[str, str] = {}
    stack: list[str] = []
    root_seen = False
    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue
        if not root_seen:
            if raw_line.strip() != ".project-wiki/":
                raise ValueError("public tree must start with .project-wiki/")
            root_seen = True
            continue
        connector = re.search(r"(?:\|--|`--)\s+", raw_line)
        if connector is None:
            raise ValueError(f"invalid public tree entry: {raw_line!r}")
        depth = connector.start() // 4
        name = raw_line[connector.end() :].split("  #", 1)[0].rstrip()
        is_directory = name.endswith("/")
        name = name.rstrip("/")
        stack = stack[:depth]
        path = "/".join((*stack, name))
        paths[path] = "directory" if is_directory else "file"
        if is_directory:
            stack.append(name)
    if not root_seen:
        raise ValueError("public tree root is missing")
    return paths


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def print_text_report(report: ContractReport) -> None:
    status = "passed" if report.valid else "failed"
    print(f"Project Wiki contract check {status}")
    print(f"schema_version={report.schema_version} findings={len(report.findings)}")
    for finding in report.findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        print(f"ERROR {finding.code} {location} - {finding.message}")


def print_contract_error(output_format: str, manifest: Path, code: str, message: str) -> None:
    finding = DriftFinding(code=code, path=manifest.as_posix(), message=message)
    report = ContractReport(manifest=manifest.as_posix(), schema_version="unknown", findings=(finding,))
    if output_format == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"error: {message}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())