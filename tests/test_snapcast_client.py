"""Tests for SnapcastClient.set_volume mute preservation (Bug 2)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.snapcast_client import SnapcastClient


def _make_status(client_id: str, volume: int, muted: bool) -> dict:
    return {
        "server": {
            "groups": [
                {
                    "clients": [
                        {
                            "id": client_id,
                            "config": {"volume": {"percent": volume, "muted": muted}},
                        }
                    ]
                }
            ]
        }
    }


async def test_set_volume_preserves_mute_state():
    """set_volume with no muted arg must not change a muted client's mute state."""
    client = SnapcastClient()
    status = _make_status("client-1", 60, muted=True)

    client.get_status = AsyncMock(return_value=status)
    captured = {}

    async def fake_call(method, params=None):
        captured["method"] = method
        captured["params"] = params

    client._call = fake_call

    await client.set_volume("client-1", 80)

    assert captured["params"]["volume"]["muted"] is True
    assert captured["params"]["volume"]["percent"] == 80


async def test_set_volume_preserves_unmuted_state():
    """set_volume with no muted arg must not mute an unmuted client."""
    client = SnapcastClient()
    status = _make_status("client-1", 40, muted=False)

    client.get_status = AsyncMock(return_value=status)
    captured = {}

    async def fake_call(method, params=None):
        captured["method"] = method
        captured["params"] = params

    client._call = fake_call

    await client.set_volume("client-1", 70)

    assert captured["params"]["volume"]["muted"] is False


async def test_set_volume_explicit_muted_overrides():
    """When muted is passed explicitly, it must be used regardless of current state."""
    client = SnapcastClient()

    captured = {}

    async def fake_call(method, params=None):
        captured["params"] = params

    client._call = fake_call
    # get_status should NOT be called when muted is explicit
    client.get_status = AsyncMock()

    await client.set_volume("client-1", 50, muted=False)

    assert captured["params"]["volume"]["muted"] is False
    client.get_status.assert_not_called()


async def test_find_client_muted_returns_correct_value():
    """_find_client_muted must locate the right client and return its mute state."""
    client = SnapcastClient()
    status = _make_status("client-2", 75, muted=True)

    assert client._find_client_muted(status, "client-2") is True


async def test_find_client_muted_missing_returns_false():
    """_find_client_muted must return False when client ID is not found."""
    client = SnapcastClient()
    status = _make_status("client-1", 75, muted=True)

    assert client._find_client_muted(status, "unknown-id") is False
