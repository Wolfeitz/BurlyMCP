"""Runtime metadata utilities for response envelopes.

This module centralizes construction of the metadata block that accompanies
all HTTP bridge responses. The metadata ensures downstream consumers can
determine which API contract produced the payload as well as the running
container build and git revision.

The helpers are intentionally lightweight and memoized because they are used
for every response emitted by the bridge and MCP engine.
"""

from __future__ import annotations

import functools
import os
import subprocess
from typing import Dict


def _detect_package_version() -> str:
    """Best-effort detection of the installed package version."""

    try:
        from burly_mcp import __version__  # type: ignore import-not-found

        return str(__version__)
    except Exception:
        return "dev"


def _detect_git_sha() -> str:
    """Detect the git SHA for the current checkout if available."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        sha = result.stdout.strip()
        if sha:
            return sha
    except Exception:
        pass

    return "unknown"


@functools.lru_cache(maxsize=1)
def get_response_metadata() -> Dict[str, str]:
    """Return the canonical metadata block for response envelopes."""

    api_version = os.environ.get("BURLYMCP_API_VERSION") or "v1"
    container_version = (
        os.environ.get("BURLYMCP_CONTAINER_VERSION")
        or os.environ.get("SERVER_VERSION")
        or _detect_package_version()
    )
    git_sha = os.environ.get("BURLYMCP_GIT_SHA") or _detect_git_sha()

    return {
        "api_version": api_version,
        "container_version": container_version,
        "git_sha": git_sha,
    }


__all__ = ["get_response_metadata"]

