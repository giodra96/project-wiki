#!/usr/bin/env python3
"""Read, validate, and edit per-project wiki configuration."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from .schema_contract import SchemaContractError, strict_yaml_load
except ImportError:
    from schema_contract import SchemaContractError, strict_yaml_load


CONFIG_FILE = "config.yml"
CONFIG_VERSION = 1


class WikiConfigError(ValueError):
    pass


def default_config() -> dict[str, Any]:
    return {"config_version": CONFIG_VERSION, "automation": {"auto_sync": True}}


def validate_config(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"config_version", "automation"}:
        raise WikiConfigError("config must contain exactly config_version and automation")
    if type(payload["config_version"]) is not int or payload["config_version"] != CONFIG_VERSION:
        raise WikiConfigError(f"unsupported config_version; expected {CONFIG_VERSION}")
    automation = payload["automation"]
    if not isinstance(automation, dict) or set(automation) != {"auto_sync"}:
        raise WikiConfigError("automation must contain exactly auto_sync")
    if type(automation["auto_sync"]) is not bool:
        raise WikiConfigError("automation.auto_sync must be a boolean")
    return payload


def read_config(wiki_root: Path) -> dict[str, Any]:
    path = wiki_root / CONFIG_FILE
    if path.is_symlink():
        raise WikiConfigError("config.yml must not be a symlink")
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default_config()
    try:
        return validate_config(strict_yaml_load(content, "wiki configuration"))
    except SchemaContractError as error:
        raise WikiConfigError(str(error)) from error


def render_config(payload: dict[str, Any]) -> str:
    validate_config(payload)
    enabled = str(payload["automation"]["auto_sync"]).lower()
    return (
        "# Project Wiki configuration. Explicit wiki commands remain available.\n"
        f"config_version: {CONFIG_VERSION}\n\nautomation:\n"
        f"  auto_sync: {enabled}\n"
    )


def set_auto_sync(wiki_root: Path, enabled: bool) -> bool:
    if not wiki_root.is_dir():
        raise WikiConfigError("wiki root must already exist; run init or scan first")
    payload = read_config(wiki_root)
    path = wiki_root / CONFIG_FILE
    if path.is_file() and payload["automation"]["auto_sync"] == enabled:
        return False
    payload["automation"]["auto_sync"] = enabled
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=wiki_root,
                                         prefix=".config-", delete=False) as handle:
            temporary = handle.name
            handle.write(render_config(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", type=Path, default=Path(".project-wiki"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("show", help="Show effective configuration and its source as JSON")
    setter = subparsers.add_parser("set", help="Set a supported option (normalizes config formatting)")
    setter.add_argument("key", choices=("automation.auto_sync",))
    setter.add_argument("value", choices=("true", "false"))
    args = parser.parse_args()
    try:
        changed = None
        if args.command == "set":
            changed = set_auto_sync(args.wiki_root, args.value == "true")
        payload = read_config(args.wiki_root)
        result = {"config": payload,
                  "source": "file" if (args.wiki_root / CONFIG_FILE).is_file() else "defaults"}
        if changed is not None:
            result["changed"] = changed
        print(json.dumps(result, indent=2))
        return 0
    except (WikiConfigError, OSError, UnicodeError, RuntimeError) as error:
        print(f"error: {error}; automatic wiki writes must be suspended until configuration is valid",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
