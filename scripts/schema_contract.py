"""Load the canonical project-wiki schema contract."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "schema" / "project-wiki.yml"


class SchemaContractError(RuntimeError):
    pass


class SchemaContractDependencyError(SchemaContractError):
    pass


@dataclass(frozen=True)
class DocumentationContract:
    version_references: dict[str, tuple[str, ...]]
    public_tree_file: str
    public_required_paths: tuple[str, ...]
    required_path_references: dict[str, tuple[str, ...]]
    forbidden_root_paths: dict[str, tuple[str, ...]]
    intake_artifact_references: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class DocumentTypeContract:
    id_pattern: str
    status_domain: str
    generated_status: str | None
    required_fields: tuple[str, ...]


@dataclass(frozen=True)
class IdGenerationContract:
    intake_document_prefix: str
    intake_date_format: str
    intake_sequence_width: int
    intake_chunk_label: str
    intake_chunk_sequence_width: int


@dataclass(frozen=True)
class IntakeArtifactContract:
    source_info: str
    extraction_index: str
    chunks_manifest: str
    chunk_directory: str
    intake_report: str
    review_progress: str
    review: str
    copied_source_stem: str


@dataclass(frozen=True)
class ReviewProgressContract:
    workflow_statuses: frozenset[str]
    entry_statuses: frozenset[str]
    complete_entry_statuses: frozenset[str]
    classifications: frozenset[str]


@dataclass(frozen=True)
class SemanticPathContract:
    wiki_version_file: str
    document_registry_file: str
    source_registry_file: str
    source_inbox_directory: str
    source_processed_directory: str
    source_rejected_directory: str
    source_ignored_directory: str
    intake_root_directory: str
    intake_documents_directory: str
    intake_index_file: str


@dataclass(frozen=True)
class TemplateContract:
    document_type: str
    template_id: str


@dataclass(frozen=True)
class SchemaContract:
    manifest_path: Path
    manifest_version: int
    schema_name: str
    schema_version: str
    schema_updated: str
    document_registry_version: int
    source_registry_version: int
    intake_source_info_version: int
    intake_chunks_manifest_version: int
    intake_review_progress_version: int
    intake_artifacts: IntakeArtifactContract
    review_progress: ReviewProgressContract
    semantic_paths: SemanticPathContract
    required_directories: tuple[str, ...]
    required_files: tuple[str, ...]
    example_files: tuple[str, ...]
    frontmatter_fields: tuple[str, ...]
    frontmatter_exempt_paths: frozenset[str]
    statuses: dict[str, frozenset[str]]
    confidence_values: frozenset[str]
    alert_severities: frozenset[str]
    id_pattern_strings: dict[str, str]
    id_examples: dict[str, str]
    embedded_id_pattern_keys: tuple[str, ...]
    document_type_contracts: dict[str, DocumentTypeContract]
    embedded_id_status_domains: dict[str, str]
    generated_values: dict[str, str]
    id_generation: IdGenerationContract
    source_processable_statuses: frozenset[str]
    source_terminal_statuses: frozenset[str]
    source_status_priority: tuple[str, ...]
    source_reason_actions: dict[str, str]
    standalone_record_directories: frozenset[str]
    template_contracts: dict[str, TemplateContract]
    template_section_inventory: dict[str, tuple[str, ...]]
    documentation: DocumentationContract

    @property
    def type_id_patterns(self) -> dict[str, re.Pattern[str]]:
        return {
            document_type: re.compile(self.id_pattern_strings[contract.id_pattern])
            for document_type, contract in self.document_type_contracts.items()
        }

    @property
    def generic_id_pattern(self) -> re.Pattern[str]:
        return re.compile(self.id_pattern_strings["generic"])

    @property
    def canonical_id_pattern(self) -> re.Pattern[str]:
        alternatives = sorted(
            (
                self.id_pattern_strings[key]
                for key in self.embedded_id_pattern_keys
            ),
            key=len,
            reverse=True,
        )
        return re.compile(rf"(?:{'|'.join(alternatives)})(?=$|\s|[-–—:])")

    @property
    def document_statuses(self) -> frozenset[str]:
        return frozenset().union(
            self.statuses["default"],
            self.statuses["alert"],
            self.statuses["open-question"],
            self.statuses["intake"],
        )

    def statuses_for_type(self, document_type: object) -> frozenset[str]:
        contract = self.document_type_contracts.get(document_type) if isinstance(document_type, str) else None
        return self.statuses[contract.status_domain] if contract else self.statuses["default"]

    def statuses_for_embedded_id(self, document_id: str) -> frozenset[str]:
        for prefix, domain in self.embedded_id_status_domains.items():
            if document_id.startswith(prefix):
                return self.statuses[domain]
        return self.statuses["default"]

    def generated_status_for_type(self, document_type: str) -> str | None:
        contract = self.document_type_contracts.get(document_type)
        return contract.generated_status if contract else None


def load_schema_contract(path: Path | None = None) -> SchemaContract:
    manifest_path = (path or DEFAULT_MANIFEST_PATH).expanduser().resolve()
    if not manifest_path.is_file():
        raise SchemaContractError(f"schema manifest not found: {manifest_path}")
    payload = strict_yaml_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SchemaContractError("schema manifest must be a YAML mapping")
    require_exact_keys(
        payload,
        {
            "manifest_version",
            "schema",
            "registries",
            "artifact_versions",
            "intake_artifacts",
            "review_progress",
            "semantic_paths",
            "canonical_tree",
            "frontmatter",
            "statuses",
            "confidence_values",
            "alert_severities",
            "id_patterns",
            "id_examples",
            "embedded_id_pattern_keys",
            "document_type_contracts",
            "embedded_id_status_domains",
            "generated_values",
            "id_generation",
            "source_workflow",
            "standalone_record_directories",
            "template_contracts",
            "template_section_inventory",
            "documentation_contract",
        },
        "manifest",
    )

    schema = require_mapping(payload, "schema")
    registries = require_mapping(payload, "registries")
    artifact_versions = require_mapping(payload, "artifact_versions")
    intake_artifacts_payload = require_mapping(payload, "intake_artifacts")
    review_progress_payload = require_mapping(payload, "review_progress")
    semantic_paths_payload = require_mapping(payload, "semantic_paths")
    tree = require_mapping(payload, "canonical_tree")
    frontmatter = require_mapping(payload, "frontmatter")
    statuses_payload = require_mapping(payload, "statuses")
    id_patterns = require_mapping(payload, "id_patterns")
    id_examples_payload = require_mapping(payload, "id_examples")
    embedded_id_pattern_keys = tuple(require_string_list(payload, "embedded_id_pattern_keys"))
    document_types_payload = require_mapping(payload, "document_type_contracts")
    embedded_domains_payload = require_mapping(payload, "embedded_id_status_domains")
    generated_values_payload = require_mapping(payload, "generated_values")
    id_generation_payload = require_mapping(payload, "id_generation")
    source_workflow_payload = require_mapping(payload, "source_workflow")
    template_contracts_payload = require_mapping(payload, "template_contracts")
    template_inventory_payload = require_mapping(payload, "template_section_inventory")
    template_section_inventory = require_string_list_mapping(
        template_inventory_payload,
        "template_section_inventory",
    )
    for relative in template_section_inventory:
        normalized = require_relative_contract_path({"path": relative}, "path")
        if normalized != relative:
            raise SchemaContractError(
                f"template_section_inventory owner {relative!r} must be a normalized relative path"
            )
        require_extension(normalized, {".md"}, f"template_section_inventory.{relative}")
    inventory_headings = [
        heading
        for headings in template_section_inventory.values()
        for heading in headings
    ]
    if len(inventory_headings) != len(set(inventory_headings)):
        raise SchemaContractError("template_section_inventory headings must have exactly one owner file")
    documentation_payload = require_mapping(payload, "documentation_contract")
    path_references_payload = require_mapping(documentation_payload, "required_path_references")
    forbidden_paths_payload = require_mapping(documentation_payload, "forbidden_root_paths")
    artifact_references_payload = require_mapping(documentation_payload, "intake_artifact_references")
    require_exact_keys(schema, {"name", "version", "updated"}, "schema")
    require_exact_keys(registries, {"document_version", "source_version"}, "registries")
    require_exact_keys(
        artifact_versions,
        {"intake_source_info", "intake_chunks_manifest", "intake_review_progress"},
        "artifact_versions",
    )
    artifact_fields = {
        "source_info",
        "extraction_index",
        "chunks_manifest",
        "chunk_directory",
        "intake_report",
        "review_progress",
        "review",
        "copied_source_stem",
    }
    require_exact_keys(intake_artifacts_payload, artifact_fields, "intake_artifacts")
    require_exact_keys(
        review_progress_payload,
        {"workflow_statuses", "entry_statuses", "complete_entry_statuses", "classifications"},
        "review_progress",
    )
    semantic_path_fields = {
        "wiki_version_file",
        "document_registry_file",
        "source_registry_file",
        "source_inbox_directory",
        "source_processed_directory",
        "source_rejected_directory",
        "source_ignored_directory",
        "intake_root_directory",
        "intake_documents_directory",
        "intake_index_file",
    }
    require_exact_keys(semantic_paths_payload, semantic_path_fields, "semantic_paths")
    require_exact_keys(tree, {"required_directories", "required_files", "example_files"}, "canonical_tree")
    require_exact_keys(frontmatter, {"required_fields", "exempt_paths"}, "frontmatter")
    require_exact_keys(
        id_generation_payload,
        {
            "intake_document_prefix",
            "intake_date_format",
            "intake_sequence_width",
            "intake_chunk_label",
            "intake_chunk_sequence_width",
        },
        "id_generation",
    )
    require_exact_keys(
        source_workflow_payload,
        {"processable_statuses", "terminal_statuses", "status_priority", "reason_actions"},
        "source_workflow",
    )
    require_exact_keys(
        documentation_payload,
        {
            "version_references",
            "public_tree_file",
            "public_required_paths",
            "required_path_references",
            "forbidden_root_paths",
            "intake_artifact_references",
        },
        "documentation_contract",
    )

    schema_version = require_string(schema, "version")
    if re.fullmatch(r"\d+\.\d+\.\d+", schema_version) is None:
        raise SchemaContractError("schema.version must use semantic version format X.Y.Z")
    schema_updated = require_string(schema, "updated")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", schema_updated) is None:
        raise SchemaContractError("schema.updated must use YYYY-MM-DD")
    artifact_values = {
        field: require_simple_name(intake_artifacts_payload, field)
        for field in artifact_fields
    }
    if len(set(artifact_values.values())) != len(artifact_values):
        raise SchemaContractError("intake_artifacts values must be unique")
    intake_artifacts = IntakeArtifactContract(**artifact_values)
    require_extension(artifact_values["source_info"], {".yml", ".yaml"}, "source_info")
    require_extension(artifact_values["chunks_manifest"], {".json"}, "chunks_manifest")
    require_extension(artifact_values["review_progress"], {".yml", ".yaml"}, "review_progress")
    for field in ("extraction_index", "intake_report", "review"):
        require_extension(artifact_values[field], {".md"}, field)
    if "." in artifact_values["chunk_directory"] or "." in artifact_values["copied_source_stem"]:
        raise SchemaContractError("chunk_directory and copied_source_stem must not contain dots")
    workflow_statuses = frozenset(require_string_list(review_progress_payload, "workflow_statuses"))
    entry_statuses = frozenset(require_string_list(review_progress_payload, "entry_statuses"))
    complete_entry_statuses = frozenset(require_string_list(review_progress_payload, "complete_entry_statuses"))
    classifications = frozenset(require_string_list(review_progress_payload, "classifications"))
    if workflow_statuses != {"in-progress", "complete"}:
        raise SchemaContractError("review_progress.workflow_statuses must contain in-progress and complete")
    if not {"pending", "reviewed", "classified", "skipped"}.issubset(entry_statuses):
        raise SchemaContractError("review_progress.entry_statuses must include pending, reviewed, classified, and skipped")
    if not complete_entry_statuses or not complete_entry_statuses.issubset(entry_statuses):
        raise SchemaContractError("review_progress.complete_entry_statuses must be a non-empty subset of entry_statuses")
    if not classifications:
        raise SchemaContractError("review_progress.classifications must not be empty")
    review_progress = ReviewProgressContract(
        workflow_statuses=workflow_statuses,
        entry_statuses=entry_statuses,
        complete_entry_statuses=complete_entry_statuses,
        classifications=classifications,
    )
    semantic_path_values = {
        field: require_relative_contract_path(semantic_paths_payload, field)
        for field in semantic_path_fields
    }
    semantic_paths = SemanticPathContract(**semantic_path_values)
    required_directories = tuple(require_string_list(tree, "required_directories"))
    required_files = tuple(require_string_list(tree, "required_files"))
    canonical_directories = set(required_directories)
    for tree_path in (*required_directories, *required_files):
        parent = Path(tree_path).parent
        while parent.as_posix() not in {"", "."}:
            canonical_directories.add(parent.as_posix())
            parent = parent.parent
    directory_fields = {field for field in semantic_path_fields if field.endswith("_directory")}
    for field, value in semantic_path_values.items():
        if field in directory_fields and value not in canonical_directories:
            raise SchemaContractError(f"semantic path {field}={value!r} is not a canonical directory")
        if field not in directory_fields and value not in required_files:
            raise SchemaContractError(f"semantic path {field}={value!r} is not a required file")
    artifact_references = require_string_list_mapping(
        artifact_references_payload,
        "intake_artifact_references",
    )
    if not set(artifact_references).issubset(artifact_fields):
        raise SchemaContractError("intake_artifact_references contain unknown artifact keys")

    status_domains = {
        key: frozenset(require_string_list(statuses_payload, key))
        for key in ("default", "alert", "open-question", "intake", "source")
    }
    require_exact_keys(statuses_payload, {"default", "alert", "open-question", "intake", "source"}, "statuses")
    pattern_strings = {
        key: value
        for key, value in id_patterns.items()
        if isinstance(key, str) and isinstance(value, str)
    }
    if set(pattern_strings) != set(id_patterns) or "generic" not in pattern_strings:
        raise SchemaContractError("id_patterns must be a mapping of strings and include generic")
    for key, pattern in pattern_strings.items():
        try:
            re.compile(pattern)
        except re.error as error:
            raise SchemaContractError(f"invalid id pattern {key!r}: {error}") from error

    document_type_contracts: dict[str, DocumentTypeContract] = {}
    for document_type, value in document_types_payload.items():
        if not isinstance(document_type, str) or not isinstance(value, dict):
            raise SchemaContractError("document_type_contracts must map string types to mappings")
        id_pattern = require_string(value, "id_pattern")
        status_domain = require_string(value, "status_domain")
        allowed_keys = {"id_pattern", "status_domain", "generated_status", "required_fields"}
        unknown_keys = set(value) - allowed_keys
        if unknown_keys:
            raise SchemaContractError(f"document type {document_type!r} has unknown keys {sorted(unknown_keys)}")
        if id_pattern not in pattern_strings:
            raise SchemaContractError(f"document type {document_type!r} references unknown ID pattern {id_pattern!r}")
        if status_domain not in status_domains:
            raise SchemaContractError(f"document type {document_type!r} references unknown status domain {status_domain!r}")
        generated_status = value.get("generated_status")
        if generated_status is not None:
            if not isinstance(generated_status, str) or generated_status not in status_domains[status_domain]:
                raise SchemaContractError(f"document type {document_type!r} has invalid generated_status")
        required_fields = tuple(require_string_list(value, "required_fields")) if "required_fields" in value else ()
        document_type_contracts[document_type] = DocumentTypeContract(
            id_pattern=id_pattern,
            status_domain=status_domain,
            generated_status=generated_status,
            required_fields=required_fields,
        )
    if not document_type_contracts:
        raise SchemaContractError("document_type_contracts must not be empty")
    required_pattern_keys = {
        "generic",
        "source-record",
        "wiki-log",
        *(contract.id_pattern for contract in document_type_contracts.values()),
    }
    if set(pattern_strings) != required_pattern_keys:
        missing = sorted(required_pattern_keys - set(pattern_strings))
        extra = sorted(set(pattern_strings) - required_pattern_keys)
        raise SchemaContractError(f"id_patterns mismatch; missing={missing}, extra={extra}")
    id_examples = {
        key: value
        for key, value in id_examples_payload.items()
        if isinstance(key, str) and isinstance(value, str)
    }
    required_example_keys = set(pattern_strings) - {"generic"}
    if set(id_examples) != required_example_keys:
        missing = sorted(required_example_keys - set(id_examples))
        extra = sorted(set(id_examples) - required_example_keys)
        raise SchemaContractError(f"id_examples mismatch; missing={missing}, extra={extra}")
    for key, example in id_examples.items():
        if re.fullmatch(pattern_strings[key], example) is None:
            raise SchemaContractError(f"ID example {example!r} does not match pattern {key!r}")
    if not set(embedded_id_pattern_keys).issubset(pattern_strings):
        raise SchemaContractError("embedded_id_pattern_keys reference unknown ID patterns")
    if "generic" in embedded_id_pattern_keys:
        raise SchemaContractError("generic ID pattern cannot define embedded records")

    embedded_domains: dict[str, str] = {}
    for prefix, domain in embedded_domains_payload.items():
        if not isinstance(prefix, str) or not isinstance(domain, str):
            raise SchemaContractError("embedded_id_status_domains must map strings to strings")
        if domain not in status_domains:
            raise SchemaContractError(f"embedded prefix {prefix!r} references unknown status domain {domain!r}")
        embedded_domains[prefix] = domain
    if not embedded_domains:
        raise SchemaContractError("embedded_id_status_domains must not be empty")

    generated_values = {
        key: value
        for key, value in generated_values_payload.items()
        if isinstance(key, str) and isinstance(value, str)
    }
    if len(generated_values) != len(generated_values_payload):
        raise SchemaContractError("generated_values must map strings to strings")
    required_generated_values = {
        "source_initial_status",
        "source_processed_status",
        "intake_confidence",
    }
    if set(generated_values) != required_generated_values:
        raise SchemaContractError("generated_values does not match the required key set")
    if generated_values["source_initial_status"] not in status_domains["source"]:
        raise SchemaContractError("generated source_initial_status is outside the source domain")
    if generated_values["source_processed_status"] not in status_domains["source"]:
        raise SchemaContractError("generated source_processed_status is outside the source domain")
    if generated_values["intake_confidence"] not in require_string_list(payload, "confidence_values"):
        raise SchemaContractError("generated intake_confidence is outside confidence_values")
    id_generation = IdGenerationContract(
        intake_document_prefix=require_string(id_generation_payload, "intake_document_prefix"),
        intake_date_format=require_string(id_generation_payload, "intake_date_format"),
        intake_sequence_width=require_positive_int(id_generation_payload, "intake_sequence_width"),
        intake_chunk_label=require_string(id_generation_payload, "intake_chunk_label"),
        intake_chunk_sequence_width=require_positive_int(id_generation_payload, "intake_chunk_sequence_width"),
    )
    sample_date = date(2026, 8, 20).strftime(id_generation.intake_date_format)
    generated_intake_id = (
        f"{id_generation.intake_document_prefix}-{sample_date}-"
        f"{1:0{id_generation.intake_sequence_width}d}"
    )
    if re.fullmatch(pattern_strings["intake-document"], generated_intake_id) is None:
        raise SchemaContractError("id_generation intake document settings do not match intake-document pattern")
    generated_chunk_id = (
        f"{generated_intake_id}-{id_generation.intake_chunk_label}-"
        f"{1:0{id_generation.intake_chunk_sequence_width}d}"
    )
    if re.fullmatch(pattern_strings["intake-chunk"], generated_chunk_id) is None:
        raise SchemaContractError("id_generation chunk settings do not match intake-chunk pattern")
    if re.fullmatch(pattern_strings["intake-review"], f"{generated_intake_id}-REVIEW") is None:
        raise SchemaContractError("intake-review pattern does not derive from generated intake document IDs")
    if re.fullmatch(pattern_strings["intake-extraction-index"], f"{generated_intake_id}-EXTRACTED") is None:
        raise SchemaContractError("intake-extraction-index pattern does not derive from generated intake document IDs")
    expected_artifact_suffixes = {
        intake_artifacts.source_info,
        intake_artifacts.extraction_index,
        intake_artifacts.chunks_manifest,
        intake_artifacts.intake_report,
        intake_artifacts.review_progress,
        intake_artifacts.review,
        (
            f"{intake_artifacts.chunk_directory}/"
            f"{id_generation.intake_chunk_label}-"
            f"{1:0{id_generation.intake_chunk_sequence_width}d}.md"
        ),
    }
    intake_documents_parts = tuple(semantic_paths.intake_documents_directory.split("/"))
    actual_artifact_suffixes = {
        "/".join(parts[len(intake_documents_parts) + 1 :])
        for value in require_string_list(tree, "example_files")
        if len((parts := value.rstrip("/").split("/"))) >= len(intake_documents_parts) + 2
        and tuple(parts[: len(intake_documents_parts)]) == intake_documents_parts
    }
    if actual_artifact_suffixes != expected_artifact_suffixes:
        missing = sorted(expected_artifact_suffixes - actual_artifact_suffixes)
        extra = sorted(actual_artifact_suffixes - expected_artifact_suffixes)
        raise SchemaContractError(f"intake artifact example paths mismatch; missing={missing}, extra={extra}")
    processable_statuses = frozenset(require_string_list(source_workflow_payload, "processable_statuses"))
    terminal_statuses = frozenset(require_string_list(source_workflow_payload, "terminal_statuses"))
    status_priority = tuple(require_string_list(source_workflow_payload, "status_priority"))
    reason_actions_payload = require_mapping(source_workflow_payload, "reason_actions")
    reason_actions = {
        reason: action
        for reason, action in reason_actions_payload.items()
        if isinstance(reason, str) and isinstance(action, str)
    }
    if len(reason_actions) != len(reason_actions_payload):
        raise SchemaContractError("source reason_actions must map strings to strings")
    if set(reason_actions.values()) - {"process", "skip", "review"}:
        raise SchemaContractError("source reason_actions contain unsupported actions")
    required_reasons = {
        "new-unique",
        "inbox-duplicate",
        "intake-history-match",
        "historical-path-with-new-content",
        "ambiguous-processable-history",
        *(f"registered-{status}" for status in status_domains["source"]),
    }
    if set(reason_actions) != required_reasons:
        missing = sorted(required_reasons - set(reason_actions))
        extra = sorted(set(reason_actions) - required_reasons)
        raise SchemaContractError(f"source reason_actions mismatch; missing={missing}, extra={extra}")
    if processable_statuses & terminal_statuses:
        raise SchemaContractError("source workflow processable and terminal statuses overlap")
    if processable_statuses | terminal_statuses != status_domains["source"]:
        raise SchemaContractError("source workflow statuses do not cover the source status domain")
    if set(status_priority) != status_domains["source"]:
        raise SchemaContractError("source workflow priority does not cover the source status domain")
    if generated_values["source_initial_status"] not in processable_statuses:
        raise SchemaContractError("source_initial_status must be processable")
    if generated_values["source_processed_status"] not in terminal_statuses:
        raise SchemaContractError("source_processed_status must be terminal")

    template_contracts: dict[str, TemplateContract] = {}
    for heading, value in template_contracts_payload.items():
        if not isinstance(heading, str) or not heading or not isinstance(value, dict):
            raise SchemaContractError("template_contracts must map headings to mappings")
        require_exact_keys(value, {"type", "id"}, f"template_contracts.{heading}")
        document_type = require_string(value, "type")
        template_id = require_string(value, "id")
        if document_type not in document_type_contracts:
            raise SchemaContractError(f"template {heading!r} references unknown type {document_type!r}")
        sample_id = sample_placeholder_id(template_id)
        pattern = re.compile(pattern_strings[document_type_contracts[document_type].id_pattern])
        if pattern.fullmatch(sample_id) is None:
            raise SchemaContractError(f"template {heading!r} ID {template_id!r} does not match type {document_type!r}")
        template_contracts[heading] = TemplateContract(document_type=document_type, template_id=template_id)
    if not set(template_contracts).issubset(inventory_headings):
        raise SchemaContractError("template_contracts headings must be present in template_section_inventory")

    return SchemaContract(
        manifest_path=manifest_path,
        manifest_version=require_supported_manifest_version(payload),
        schema_name=require_string(schema, "name"),
        schema_version=schema_version,
        schema_updated=schema_updated,
        document_registry_version=require_int(registries, "document_version"),
        source_registry_version=require_int(registries, "source_version"),
        intake_source_info_version=require_int(artifact_versions, "intake_source_info"),
        intake_chunks_manifest_version=require_int(artifact_versions, "intake_chunks_manifest"),
        intake_review_progress_version=require_int(artifact_versions, "intake_review_progress"),
        intake_artifacts=intake_artifacts,
        review_progress=review_progress,
        semantic_paths=semantic_paths,
        required_directories=required_directories,
        required_files=required_files,
        example_files=tuple(require_string_list(tree, "example_files")),
        frontmatter_fields=tuple(require_string_list(frontmatter, "required_fields")),
        frontmatter_exempt_paths=frozenset(require_string_list(frontmatter, "exempt_paths")),
        statuses=status_domains,
        confidence_values=frozenset(require_string_list(payload, "confidence_values")),
        alert_severities=frozenset(require_string_list(payload, "alert_severities")),
        id_pattern_strings=pattern_strings,
        id_examples=id_examples,
        embedded_id_pattern_keys=embedded_id_pattern_keys,
        document_type_contracts=document_type_contracts,
        embedded_id_status_domains=embedded_domains,
        generated_values=generated_values,
        id_generation=id_generation,
        source_processable_statuses=processable_statuses,
        source_terminal_statuses=terminal_statuses,
        source_status_priority=status_priority,
        source_reason_actions=reason_actions,
        standalone_record_directories=frozenset(require_string_list(payload, "standalone_record_directories")),
        template_contracts=template_contracts,
        template_section_inventory=template_section_inventory,
        documentation=DocumentationContract(
            version_references=require_string_list_mapping(
                require_mapping(documentation_payload, "version_references"),
                "version_references",
            ),
            public_tree_file=require_string(documentation_payload, "public_tree_file"),
            public_required_paths=tuple(require_string_list(documentation_payload, "public_required_paths")),
            required_path_references=require_string_list_mapping(path_references_payload, "required_path_references"),
            forbidden_root_paths=require_string_list_mapping(forbidden_paths_payload, "forbidden_root_paths"),
            intake_artifact_references=artifact_references,
        ),
    )


def require_mapping(payload: dict[str, Any], field: str) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        raise SchemaContractError(f"{field} must be a mapping")
    return value


def require_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SchemaContractError(f"{field} must be a non-empty string")
    return value


def require_simple_name(payload: dict[str, Any], field: str) -> str:
    value = require_string(payload, field)
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise SchemaContractError(f"{field} must be a simple file or directory name")
    return value


def require_relative_contract_path(payload: dict[str, Any], field: str) -> str:
    value = require_string(payload, field).replace("\\", "/")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("./"):
        raise SchemaContractError(f"{field} must be a normalized relative path")
    return value


def require_extension(value: str, allowed: set[str], field: str) -> None:
    if Path(value).suffix.lower() not in allowed:
        raise SchemaContractError(f"{field} must use one of extensions {sorted(allowed)}")


def require_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if type(value) is not int:
        raise SchemaContractError(f"{field} must be an integer")
    return value


def require_positive_int(payload: dict[str, Any], field: str) -> int:
    value = require_int(payload, field)
    if value < 1:
        raise SchemaContractError(f"{field} must be positive")
    return value


def require_supported_manifest_version(payload: dict[str, Any]) -> int:
    version = require_int(payload, "manifest_version")
    if version != 1:
        raise SchemaContractError(f"unsupported manifest_version: {version}")
    return version


def sample_placeholder_id(value: str) -> str:
    return (
        value.replace("YYYY-MM-DD", "2026-08-20")
        .replace("YYYYMMDD", "20260820")
        .replace("NNN", "001")
    )


def require_string_list(payload: dict[str, Any], field: str) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise SchemaContractError(f"{field} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise SchemaContractError(f"{field} contains duplicate values")
    return value


def require_string_list_mapping(payload: dict[Any, Any], label: str) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for key in payload:
        if not isinstance(key, str) or not key:
            raise SchemaContractError(f"{label} keys must be non-empty strings")
        result[key] = tuple(require_string_list(payload, key))
    return result


def require_exact_keys(payload: dict[Any, Any], expected: set[str], label: str) -> None:
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(str(value) for value in actual - expected)
        raise SchemaContractError(f"{label} keys mismatch; missing={missing}, extra={extra}")


def strict_yaml_load(text: str, label: str = "schema manifest") -> Any:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as error:
        raise SchemaContractDependencyError(
            "schema contract loading requires PyYAML; install scripts/requirements.txt"
        ) from error

    class UniqueKeyLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
        loader.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as error:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found an unhashable key",
                    key_node.start_mark,
                ) from error
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    UniqueKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping,
    )
    try:
        return yaml.load(text, Loader=UniqueKeyLoader)
    except (yaml.YAMLError, UnicodeError) as error:
        raise SchemaContractError(f"invalid {label} YAML: {error}") from error