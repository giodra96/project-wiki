#!/usr/bin/env python3
"""Create a validated project-wiki scaffold at a previously absent target."""

from __future__ import annotations

import argparse
import ctypes
import errno
import json
import os
import platform
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

import yaml  # type: ignore[import-untyped]

try:
    from .check_contracts import fenced_block_after_heading
    from .schema_contract import (
        ScaffoldFileRecipe,
        SchemaContract,
        SchemaContractDependencyError,
        SchemaContractError,
        load_schema_contract,
        strict_yaml_load,
    )
    from .validate_wiki import validate_wiki
except ImportError:
    from check_contracts import fenced_block_after_heading
    from schema_contract import (  # type: ignore[no-redef]
        ScaffoldFileRecipe,
        SchemaContract,
        SchemaContractDependencyError,
        SchemaContractError,
        load_schema_contract,
        strict_yaml_load,
    )
    from validate_wiki import validate_wiki


class ScaffoldError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a complete project-wiki scaffold without modifying existing targets."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--wiki-root", default=".project-wiki")
    create.add_argument("--dry-run", action="store_true")
    create.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = load_schema_contract()
        scaffold_date = date.today().isoformat()
        target = resolve_target(Path(args.wiki_root))
        validate_target_absent(target)
        validate_template_sources(contract)
        report = scaffold_report(contract, target, scaffold_date, args.dry_run)
        if args.dry_run:
            print_report(report, args.format)
            return 0
        ensure_exclusive_publish_supported()
        create_scaffold(target, scaffold_date, contract)
        report["scaffold_created"] = True
        report["validation"] = {"scaffold_contract": "passed", "wiki": "passed"}
        print_report(report, args.format)
        return 0
    except (
        OSError,
        ScaffoldError,
        SchemaContractDependencyError,
        SchemaContractError,
        UnicodeError,
        yaml.YAMLError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def resolve_target(requested: Path) -> Path:
    expanded = requested.expanduser()
    if expanded.name in {"", ".", ".."}:
        raise ScaffoldError("--wiki-root must name a target directory")
    parent = expanded.parent if expanded.is_absolute() else Path.cwd() / expanded.parent
    try:
        resolved_parent = parent.resolve(strict=True)
    except FileNotFoundError as error:
        raise ScaffoldError(f"wiki root parent does not exist: {parent}") from error
    if not resolved_parent.is_dir():
        raise ScaffoldError(f"wiki root parent is not a directory: {resolved_parent}")
    return resolved_parent / expanded.name


def validate_target_absent(target: Path) -> None:
    try:
        children = tuple(target.parent.iterdir())
    except OSError as error:
        raise ScaffoldError(f"cannot inspect wiki root parent: {error}") from error
    collision = next(
        (child for child in children if child.name.casefold() == target.name.casefold()),
        None,
    )
    if collision is not None or os.path.lexists(target):
        existing = collision or target
        raise ScaffoldError(
            f"wiki root target already exists or collides by case: {existing}; "
            "use the maintain workflow for existing wikis"
        )


def scaffold_report(
    contract: SchemaContract,
    target: Path,
    scaffold_date: str,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "version": 1,
        "action": "dry-run" if dry_run else "create-new",
        "target": target.as_posix(),
        "schema_version": contract.schema_version,
        "date": scaffold_date,
        "schema_declared_directories": len(contract.required_directories),
        "actual_directories": len(expected_directories(contract)),
        "files": len(contract.required_files),
        "scaffold_created": False,
        "project_initialization_complete": False,
        "semantic_content_captured": False,
        "validation": {
            "scaffold_contract": "planned" if dry_run else "pending",
            "wiki": "planned" if dry_run else "pending",
        },
    }


def expected_directories(contract: SchemaContract) -> set[str]:
    directories = set(contract.required_directories)
    for relative in (*contract.required_directories, *contract.required_files):
        parent = PurePosixPath(relative).parent
        while parent.as_posix() not in {"", "."}:
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def validate_template_sources(contract: SchemaContract) -> None:
    for relative, recipe in contract.scaffold.files.items():
        if recipe.recipe not in {"rendered-template", "local-template"}:
            continue
        extract_template(contract, recipe, relative)


def create_scaffold(target: Path, scaffold_date: str, contract: SchemaContract) -> None:
    staging: Path | None = None
    try:
        validate_target_absent(target)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f"{target.name}.stage-",
                dir=target.parent,
            )
        )
        if os.stat(staging).st_dev != os.stat(target.parent).st_dev:
            raise ScaffoldError("staging and wiki target are not on the same filesystem")
        contents = build_scaffold_contents(contract, scaffold_date)
        write_scaffold(staging, contract, contents)
        validate_scaffold_stage(staging, contract, contents, scaffold_date)
        report = validate_wiki(staging, contract.manifest_path)
        if report.findings:
            summary = "; ".join(
                f"{finding.code}:{finding.path}"
                for finding in report.findings[:10]
            )
            raise ScaffoldError(f"generated scaffold failed wiki validation: {summary}")
        validate_target_absent(target)
        publish_exclusive(staging, target)
        staging = None
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def build_scaffold_contents(contract: SchemaContract, scaffold_date: str) -> dict[str, str]:
    contents: dict[str, str] = {}
    for relative in contract.required_files:
        recipe = contract.scaffold.files[relative]
        if recipe.recipe == "document-registry":
            continue
        contents[relative] = render_recipe(relative, recipe, contract, scaffold_date)
    registry_path = contract.semantic_paths.document_registry_file
    contents[registry_path] = render_document_registry(contents, contract, scaffold_date)
    return contents


def render_recipe(
    relative: str,
    recipe: ScaffoldFileRecipe,
    contract: SchemaContract,
    scaffold_date: str,
) -> str:
    if recipe.recipe == "placeholder-document":
        return render_placeholder_document(recipe, scaffold_date)
    if recipe.recipe == "rendered-template":
        content = extract_template(contract, recipe, relative)
        if "date" in recipe.replacements:
            content = content.replace("YYYY-MM-DD", scaffold_date)
        return content.rstrip() + "\n"
    if recipe.recipe == "local-template":
        return extract_template(contract, recipe, relative).rstrip() + "\n"
    if recipe.recipe == "section-index":
        return render_section_index(recipe)
    if recipe.recipe == "plain-placeholder":
        return f"# {recipe.title}\n\n{recipe.message}\n"
    if recipe.recipe == "status":
        return render_status(scaffold_date)
    if recipe.recipe == "wiki-version":
        return render_wiki_version(contract, scaffold_date)
    if recipe.recipe == "source-registry":
        payload = {
            "version": contract.source_registry_version,
            "updated": scaffold_date,
            "sources": [],
        }
        return yaml.safe_dump(payload, sort_keys=False)
    if recipe.recipe == "requirement-evidence":
        return yaml.safe_dump({"version": 1, "records": {}}, sort_keys=False)
    raise ScaffoldError(f"unsupported scaffold recipe while rendering {relative}: {recipe.recipe}")


def render_placeholder_document(recipe: ScaffoldFileRecipe, scaffold_date: str) -> str:
    metadata = {
        "id": recipe.document_id,
        "type": recipe.document_type,
        "status": "placeholder",
        "title": recipe.title,
        "created": scaffold_date,
        "updated": scaffold_date,
        "tags": list(recipe.tags),
        "related": [],
        "source_paths": [],
        "confidence": "unknown",
    }
    return (
        "---\n"
        + yaml.safe_dump(metadata, sort_keys=False)
        + "---\n\n"
        + f"# {recipe.title}\n\n{recipe.message}\n"
    )


def render_section_index(recipe: ScaffoldFileRecipe) -> str:
    lines = [
        f"# {recipe.title}",
        "",
        recipe.description or "",
        "",
        "## When To Read",
        "",
        *(f"- {item}" for item in recipe.when_to_read),
        "",
        "## Key Files",
        "",
        *(f"- {item}" for item in recipe.key_files),
        "" if recipe.key_files else "- None yet.",
        "## Placeholders Or Stale Areas",
        "",
        *(f"- {item}" for item in recipe.placeholders),
        "",
    ]
    return "\n".join(lines)


def render_status(scaffold_date: str) -> str:
    return "\n".join(
        [
            "# Project Status",
            "",
            f"Last updated: {scaffold_date}",
            "",
            "## Scaffold State",
            "",
            "- Canonical scaffold created: yes",
            "- Project initialization complete: no",
            "- Semantic project content captured: no",
            "",
            "## Next Step",
            "",
            "- Complete the project-wiki init or scan workflow.",
            "",
            "## Active Alerts",
            "",
            "- None captured yet.",
            "",
            "## Blockers And Open Questions",
            "",
            "- No project-specific review has been performed yet.",
            "",
        ]
    )


def render_wiki_version(contract: SchemaContract, scaffold_date: str) -> str:
    payload = {
        "schema": contract.schema_name,
        "schema_version": contract.schema_version,
        "schema_updated": contract.schema_updated,
        "last_migrated": scaffold_date,
        "maintained_by_skill": "project-wiki",
        "notes": "Current schema applied.",
    }
    return yaml.safe_dump(payload, sort_keys=False)


def extract_template(
    contract: SchemaContract,
    recipe: ScaffoldFileRecipe,
    relative: str,
) -> str:
    if recipe.asset is None or recipe.template is None:
        raise ScaffoldError(f"template recipe is incomplete for {relative}")
    asset = contract.manifest_path.parent.parent / recipe.asset
    if not asset.is_file():
        raise ScaffoldError(f"scaffold template asset is missing: {recipe.asset}")
    block = fenced_block_after_heading(
        asset.read_text(encoding="utf-8"),
        recipe.template,
    )
    if block is None:
        raise ScaffoldError(
            f"scaffold template block is missing: {recipe.asset}#{recipe.template}"
        )
    return block


def render_document_registry(
    contents: dict[str, str],
    contract: SchemaContract,
    scaffold_date: str,
) -> str:
    documents: list[dict[str, Any]] = []
    for relative, recipe in sorted(contract.scaffold.files.items()):
        if recipe.recipe != "placeholder-document":
            continue
        metadata = parse_frontmatter(contents[relative], relative)
        documents.append(
            {
                "id": metadata["id"],
                "type": metadata["type"],
                "title": metadata["title"],
                "path": relative,
                "status": metadata["status"],
                "tags": metadata["tags"],
                "related": metadata["related"],
                "source_paths": metadata["source_paths"],
                "confidence": metadata["confidence"],
            }
        )
    payload = {
        "version": contract.document_registry_version,
        "updated": scaffold_date,
        "documents": documents,
    }
    return yaml.safe_dump(payload, sort_keys=False)


def parse_frontmatter(content: str, relative: str) -> dict[str, Any]:
    if not content.startswith("---\n"):
        raise ScaffoldError(f"generated document has no frontmatter: {relative}")
    parts = content.split("---", 2)
    if len(parts) != 3:
        raise ScaffoldError(f"generated document has invalid frontmatter: {relative}")
    payload = strict_yaml_load(parts[1], f"generated frontmatter in {relative}")
    if not isinstance(payload, dict):
        raise ScaffoldError(f"generated frontmatter is not a mapping: {relative}")
    return payload


def write_scaffold(
    staging: Path,
    contract: SchemaContract,
    contents: dict[str, str],
) -> None:
    for relative in sorted(expected_directories(contract), key=lambda value: (value.count("/"), value)):
        (staging / relative).mkdir(parents=True, exist_ok=True)
    for relative in contract.required_files:
        path = staging / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents[relative], encoding="utf-8")


def validate_scaffold_stage(
    staging: Path,
    contract: SchemaContract,
    contents: dict[str, str],
    scaffold_date: str,
) -> None:
    actual_files = {
        path.relative_to(staging).as_posix()
        for path in staging.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    actual_directories = {
        path.relative_to(staging).as_posix()
        for path in staging.rglob("*")
        if path.is_dir() and not path.is_symlink()
    }
    if actual_files != set(contract.required_files):
        raise ScaffoldError("generated scaffold file set does not match the canonical contract")
    if actual_directories != expected_directories(contract):
        raise ScaffoldError("generated scaffold directory set does not match the canonical contract")
    if any(path.is_symlink() for path in staging.rglob("*")):
        raise ScaffoldError("generated scaffold contains a symlink")
    for relative, expected in contents.items():
        if (staging / relative).read_text(encoding="utf-8") != expected:
            raise ScaffoldError(f"generated scaffold content changed unexpectedly: {relative}")
    for relative, recipe in contract.scaffold.files.items():
        if recipe.recipe != "placeholder-document":
            continue
        metadata = parse_frontmatter((staging / relative).read_text(encoding="utf-8"), relative)
        expected_metadata = {
            "id": recipe.document_id,
            "type": recipe.document_type,
            "status": "placeholder",
            "title": recipe.title,
            "created": scaffold_date,
            "updated": scaffold_date,
            "tags": list(recipe.tags),
            "related": [],
            "source_paths": [],
            "confidence": "unknown",
        }
        if metadata != expected_metadata:
            raise ScaffoldError(f"generated document does not match its scaffold recipe: {relative}")
    registry = strict_yaml_load(
        (staging / contract.semantic_paths.document_registry_file).read_text(encoding="utf-8"),
        "generated document registry",
    )
    expected_registry = strict_yaml_load(
        contents[contract.semantic_paths.document_registry_file],
        "expected document registry",
    )
    if registry != expected_registry:
        raise ScaffoldError("generated document registry does not match generated frontmatter")


def ensure_exclusive_publish_supported() -> None:
    system = platform.system()
    libc = ctypes.CDLL(None, use_errno=True)
    if system == "Darwin" and getattr(libc, "renamex_np", None) is not None:
        return
    if system == "Linux" and getattr(libc, "renameat2", None) is not None:
        return
    if system == "Windows":
        return
    raise ScaffoldError(
        f"exclusive directory publication is unavailable on {system}; refusing unsafe fallback"
    )


def publish_exclusive(staging: Path, target: Path) -> None:
    system = platform.system()
    if system == "Darwin":
        publish_darwin(staging, target)
        return
    if system == "Linux":
        publish_linux(staging, target)
        return
    if system == "Windows":
        try:
            os.rename(staging, target)
        except FileExistsError as error:
            raise ScaffoldError(f"wiki root target appeared during publication: {target}") from error
        return
    raise ScaffoldError(
        f"exclusive directory publication is unavailable on {system}; refusing unsafe fallback"
    )


def publish_darwin(staging: Path, target: Path) -> None:
    rename_exclusive = ctypes.CDLL(None, use_errno=True).renamex_np
    rename_exclusive.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    rename_exclusive.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = rename_exclusive(os.fsencode(staging), os.fsencode(target), 0x00000004)
    if result == 0:
        return
    raise_publish_error(target, ctypes.get_errno())


def publish_linux(staging: Path, target: Path) -> None:
    rename_no_replace = ctypes.CDLL(None, use_errno=True).renameat2
    rename_no_replace.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename_no_replace.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = rename_no_replace(
        -100,
        os.fsencode(staging),
        -100,
        os.fsencode(target),
        0x00000001,
    )
    if result == 0:
        return
    raise_publish_error(target, ctypes.get_errno())


def raise_publish_error(target: Path, error_number: int) -> None:
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise ScaffoldError(f"wiki root target appeared during publication: {target}")
    raise ScaffoldError(
        f"exclusive scaffold publication failed: "
        f"{os.strerror(error_number) if error_number else 'unknown error'}"
    )


def print_report(report: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"action: {report['action']}")
    print(f"target: {report['target']}")
    print(f"schema_version: {report['schema_version']}")
    print(
        "planned: "
        f"{report['actual_directories']} directories, {report['files']} files"
    )
    print(f"scaffold_created: {str(report['scaffold_created']).lower()}")
    print("project_initialization_complete: false")
    print("semantic_content_captured: false")
    print(
        "validation: "
        f"scaffold_contract={report['validation']['scaffold_contract']}, "
        f"wiki={report['validation']['wiki']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())