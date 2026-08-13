"""Tests for AdbMediaPlayer entity attributes."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.media_player import MediaPlayerState

from custom_components.adb_media_session.media_player import AdbMediaPlayer
from custom_components.adb_media_session.parser import MediaSession, ParsedMediaSessionData


def test_adb_media_player_attributes():
    """Test entity properties and extra_state_attributes."""
    primary = MediaSession(
        name="Smarttube",
        package="org.smarttube.stable",
        active=True,
        state=MediaPlayerState.PLAYING,
        position_ms=198760,
        updated_ms=1000,
        speed=1.0,
        error=None,
    )
    mock_data = ParsedMediaSessionData(
        uptime_seconds=1000.0,
        media_button_session_pkg=None,
        primary_session=primary,
        sessions=[primary],
    )

    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = mock_data

    entry = MagicMock()
    entry.entry_id = "test_entry_id"

    player = AdbMediaPlayer(coordinator, entry, "ADB-Test")

    # Verify standard properties
    assert player.app_id == "org.smarttube.stable"
    assert player.app_name == "Smarttube"

    # Verify extra_state_attributes does NOT contain 'app' or 'sessions'
    extra_attrs = player.extra_state_attributes
    assert "app" not in extra_attrs
    assert "sessions" not in extra_attrs
    assert extra_attrs == {"playback_speed": 1.0}


def test_adb_media_player_state():
    """Test state reporting directly from MediaPlayerState."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    entry = MagicMock(entry_id="test_entry")
    player = AdbMediaPlayer(coordinator, entry, "Test")

    # None primary session -> IDLE and no extra_state_attributes
    coordinator.data = ParsedMediaSessionData(100.0, None, [], None)
    assert player.state == MediaPlayerState.IDLE
    assert player.extra_state_attributes is None

    # Update failed -> None
    coordinator.last_update_success = False
    assert player.state is None
    coordinator.last_update_success = True

    # Active session state return
    sess = MediaSession("App", "pkg", True, MediaPlayerState.PLAYING, 0, 0, 1.0, None)
    coordinator.data = ParsedMediaSessionData(100.0, None, [sess], sess)
    assert player.state == MediaPlayerState.PLAYING
    assert player.extra_state_attributes == {"playback_speed": 1.0}


