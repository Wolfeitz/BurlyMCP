from __future__ import annotations

import glob
import logging
import os
from typing import Any, Dict, Iterable, List, Tuple

import yaml

DEFAULT_POLICY_FILE = "/config/policy/tools.yaml"
DEFAULT_POLICY_DIR = "/config/tools.d"


def _read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            return {}
        return data


def collect_policy_sources(
    policy_file_override: str | None = None,
    policy_dir_override: str | None = None,
) -> Tuple[str, str, List[str]]:
    """Resolve the policy sources from environment or overrides."""

    policy_file = policy_file_override or os.getenv("POLICY_FILE", DEFAULT_POLICY_FILE)
    policy_dir = policy_dir_override or os.getenv("POLICY_DIR", DEFAULT_POLICY_DIR)

    dir_files: List[str] = []
    if os.path.isdir(policy_dir):
        dir_files = sorted(glob.glob(os.path.join(policy_dir, "*.yaml")))
    return policy_file, policy_dir, dir_files


def _extract_tools(
    data: Dict[str, Any],
    source: str,
    stats: Dict[str, Any],
) -> List[dict]:
    tools_raw = data.get("tools") if isinstance(data, dict) else None
    tools: List[dict] = []

    if isinstance(tools_raw, dict):
        iterable: Iterable[Tuple[str, Any]] = tools_raw.items()
        for name, cfg in iterable:
            if not isinstance(cfg, dict):
                stats.setdefault("invalid", []).append(
                    {"source": source, "reason": f"tool '{name}' must be a mapping"}
                )
                continue
            merged = {"name": name, **cfg}
            tools.append(merged)
    elif isinstance(tools_raw, list):
        for entry in tools_raw:
            if not isinstance(entry, dict):
                stats.setdefault("invalid", []).append(
                    {"source": source, "reason": "tool entry must be a mapping"}
                )
                continue
            if "name" not in entry:
                stats.setdefault("invalid", []).append(
                    {"source": source, "reason": "tool entry missing name"}
                )
                continue
            tools.append(dict(entry))
    elif tools_raw is not None:
        stats.setdefault("invalid", []).append(
            {"source": source, "reason": "tools section must be a mapping or list"}
        )

    return tools


def merge_tools(
    policy_file_tools: List[dict],
    dir_file_tools: List[Tuple[str, dict]],
    stats: Dict[str, Any] | None = None,
) -> Tuple[List[dict], Dict[str, Any]]:
    """Merge tool definitions by name."""

    merged: Dict[str, dict] = {}
    stats = stats or {"invalid": []}

    for tool in policy_file_tools or []:
        name = (tool or {}).get("name")
        if not name:
            stats.setdefault("invalid", []).append(
                {"source": "POLICY_FILE", "reason": "missing name"}
            )
            continue
        merged[name] = tool
        stats["from_file_count"] = stats.get("from_file_count", 0) + 1

    for path, tool in dir_file_tools:
        name = (tool or {}).get("name")
        if not name:
            stats.setdefault("invalid", []).append(
                {"source": path, "reason": "missing name"}
            )
            continue
        merged[name] = tool
        stats["from_dir_tools"] = stats.get("from_dir_tools", 0) + 1

    return list(merged.values()), stats


def load_tools_from_sources(
    logger: logging.Logger | None = None,
    policy_file_override: str | None = None,
    policy_dir_override: str | None = None,
) -> Tuple[List[dict], Dict[str, Any]]:
    """Load tool policies from the legacy file and optional directory."""

    policy_file, policy_dir, dir_files = collect_policy_sources(
        policy_file_override=policy_file_override,
        policy_dir_override=policy_dir_override,
    )
    stats: Dict[str, Any] = {
        "invalid": [],
        "from_file_count": 0,
        "from_dir_files": len(dir_files),
        "from_dir_tools": 0,
        "skipped_files": [],
    }

    file_tools: List[dict] = []
    if os.path.isfile(policy_file):
        try:
            data = _read_yaml(policy_file)
        except Exception as exc:  # pragma: no cover - defensive
            stats.setdefault("invalid", []).append(
                {"source": policy_file, "reason": str(exc)}
            )
            if logger:
                logger.warning("Skipping invalid policy file %s: %s", policy_file, exc)
            data = {}
        file_tools = _extract_tools(data, "POLICY_FILE", stats)
    else:
        if logger:
            logger.info("Legacy policy file not found at %s", policy_file)

    dir_tools: List[Tuple[str, dict]] = []
    for path in dir_files:
        try:
            data = _read_yaml(path)
        except Exception as exc:  # pragma: no cover - defensive
            stats.setdefault("invalid", []).append({"source": path, "reason": str(exc)})
            stats.setdefault("skipped_files", []).append(path)
            if logger:
                logger.warning("Skipping invalid policy file %s: %s", path, exc)
            continue
        tools = _extract_tools(data, path, stats)
        for tool in tools:
            dir_tools.append((path, tool))

    merged, stats = merge_tools(file_tools, dir_tools, stats=stats)

    if logger:
        logger.info(
            "Policy load summary: file=%s (%d tools), dir=%s (%d files, %d tools), merged=%d, invalid=%d",
            policy_file,
            stats.get("from_file_count", 0),
            policy_dir,
            stats.get("from_dir_files", 0),
            stats.get("from_dir_tools", 0),
            len(merged),
            len(stats.get("invalid", [])),
        )
    return merged, stats
