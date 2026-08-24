from __future__ import annotations

from pathlib import Path, PurePosixPath

import yaml  # type: ignore[import-untyped]

from scripts.schema_contract import SchemaContract, load_schema_contract


TEST_CONTRACT = load_schema_contract()


def create_valid_wiki(root: Path, contract: SchemaContract = TEST_CONTRACT) -> dict[str, str]:
    for relative in contract.required_directories:
        (root / relative).mkdir(parents=True, exist_ok=True)

    frontmatter_ids: dict[str, str] = {}
    next_id = 1
    for relative in contract.required_files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == contract.semantic_paths.wiki_version_file:
            path.write_text(
                "\n".join(
                    [
                        "schema: project-wiki",
                        f"schema_version: {contract.schema_version}",
                        f"schema_updated: {contract.schema_updated}",
                        "last_migrated: 2026-08-20",
                        "maintained_by_skill: project-wiki",
                        "notes: Current schema applied.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
        elif relative == contract.semantic_paths.document_registry_file:
            continue
        elif relative == contract.semantic_paths.source_registry_file:
            path.write_text(
                f"version: {contract.source_registry_version}\nupdated: 2026-08-20\nsources: []\n",
                encoding="utf-8",
            )
        elif relative.startswith("templates/"):
            path.write_text("Template placeholder.\n", encoding="utf-8")
        elif frontmatter_is_exempt(relative, contract):
            path.write_text(f"# {path.stem.replace('-', ' ').title()}\n", encoding="utf-8")
        elif path.suffix == ".md":
            document_id = f"DOC-{next_id:03d}"
            next_id += 1
            frontmatter_ids[relative] = document_id
            path.write_text(
                "\n".join(
                    [
                        "---",
                        f"id: {document_id}",
                        "type: note",
                        "status: placeholder",
                        f"title: {path.stem.replace('-', ' ').title()}",
                        "created: 2026-08-20",
                        "updated: 2026-08-20",
                        "tags: []",
                        "related: []",
                        "source_paths: []",
                        "confidence: unknown",
                        "---",
                        "",
                        f"# {path.stem.replace('-', ' ').title()}",
                        "",
                        "No project-specific information has been captured yet.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

    registry = {
        "version": 1,
        "updated": "2026-08-20",
        "documents": [
            {
                "id": document_id,
                "type": "note",
                "title": Path(relative).stem.replace("-", " ").title(),
                "path": relative,
                "status": "placeholder",
                "tags": [],
                "related": [],
                "source_paths": [],
                "confidence": "unknown",
            }
            for relative, document_id in sorted(frontmatter_ids.items())
        ],
    }
    (root / contract.semantic_paths.document_registry_file).write_text(
        yaml.safe_dump(registry, sort_keys=False),
        encoding="utf-8",
    )
    return frontmatter_ids


def frontmatter_is_exempt(relative: str, contract: SchemaContract = TEST_CONTRACT) -> bool:
    return (
        PurePosixPath(relative).name == "INDEX.md"
        or relative in contract.frontmatter_exempt_paths
        or relative.startswith("logs/wiki-log-")
    )