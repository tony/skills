"""Opt-in cross-run memoization via pytest's ``config.cache``.

Use when an expensive artifact (a built dataset, a compiled schema, a downloaded
corpus) is recomputed every run but rarely changes. ``config.cache`` persists
JSON under ``.pytest_cache/`` across runs.

Two correctness rules this snippet enforces:

1. **Invalidation** -- the artifact is cached under a token hashed from its
   inputs, so a stale entry is never served. With no inputs the token cannot
   invalidate, so the fixture raises instead of caching forever.
2. **xdist write-guard** -- the cache is written only on a *serial* run. Under
   pytest-xdist the fixture runs inside workers (which carry
   ``config.workerinput``), so every worker skips the write: the entry is never
   populated in parallel, a safe read-only no-op rather than a concurrent-write
   race. To populate it under xdist, replace the guard with a single-writer
   ``FileLock`` over a shared file in ``tmp_path_factory.getbasetemp().parent``.

``config.cache`` values must be JSON-serializable. For a binary or large
artifact, cache a *path* to an on-disk file (plus the token) instead.

Set ``INPUTS`` and implement ``_build_expensive_artifact``, then drop this into a
``conftest.py``.
"""

from __future__ import annotations

import hashlib
import pathlib
import typing as t

import pytest

CACHE_KEY = "pytest_optimizer/expensive_artifact"

# Bump when the build code changes but the input files do not.
BUILD_VERSION = "1"

# Files the artifact derives from; any content change invalidates the cache.
INPUTS: tuple[pathlib.Path, ...] = ()


def _invalidation_token(inputs: t.Sequence[pathlib.Path]) -> str:
    """Return a token that changes whenever the cached artifact must be rebuilt."""
    if not inputs:
        msg = "set INPUTS: with no inputs the cache token can never invalidate"
        raise ValueError(msg)
    h = hashlib.sha256(BUILD_VERSION.encode())
    for p in sorted(inputs):
        h.update(str(p).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _build_expensive_artifact() -> dict[str, t.Any]:
    """Produce the artifact as a JSON-serializable value."""
    raise NotImplementedError


@pytest.fixture(scope="session")
def expensive_artifact(request: pytest.FixtureRequest) -> dict[str, t.Any]:
    """Build the artifact once, reuse across runs while its inputs are unchanged."""
    token = _invalidation_token(INPUTS)
    # None when cacheprovider is disabled (`-p no:cacheprovider`): build uncached.
    cache = getattr(request.config, "cache", None)

    if cache is not None:
        stored = cache.get(CACHE_KEY, None)
        if stored is not None and stored.get("token") == token:
            return stored["value"]

    value = _build_expensive_artifact()

    if cache is not None and not hasattr(request.config, "workerinput"):
        cache.set(CACHE_KEY, {"token": token, "value": value})

    return value
