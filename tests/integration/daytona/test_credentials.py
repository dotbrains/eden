"""Daytona provider credential checks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from eden.providers._types import CreateOptions
from eden.sandboxes.daytona import provider as daytona_provider
from eden.sandboxes.errors import ProviderUnavailable

pytestmark = pytest.mark.integration


def test_missing_credentials_raises_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    daytona_options: Callable[[Path, str], CreateOptions],
) -> None:
    """The credential check raises lazily at create() time, not factory time."""
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    # Construct the provider WITHOUT calling _require_credentials — we are
    # exercising the unconfigured path on purpose.
    p = daytona_provider(api_key=None)
    seed = tmp_path / "seed"
    seed.mkdir()
    with pytest.raises(ProviderUnavailable) as exc:
        p.create(daytona_options(seed, "eden-it-noauth"))
    assert exc.value.provider == "daytona"
