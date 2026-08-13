"""Tests for the dumpsys media_session and uptime parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from homeassistant.components.media_player import MediaPlayerState

from custom_components.adb_media_session.parser import (
    parse_media_session_output,
    parse_playback_state,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def read_fixture(filename: str) -> str:
    """Read a test fixture file."""
    with open(FIXTURES_DIR / filename, "r", encoding="utf-8") as f:
        return f.read()


def test_parse_netflix_paused():
    """Test parsing Netflix paused fixture."""
    output = read_fixture("netflix_paused.txt")
    data = parse_media_session_output(output)

    assert data.uptime_seconds == 123456.78
    assert data.media_button_session_pkg == "com.netflix.ninja"
    assert len(data.sessions) == 1

    primary = data.primary_session
    assert primary is not None
    assert primary.package == "com.netflix.ninja"
    assert primary.name == "Netflix"
    assert primary.active is True
    assert primary.state == MediaPlayerState.PAUSED
    assert primary.position_ms == 107708
    assert primary.updated_ms == 123400000
    assert primary.speed == 1.0

    # Since state is PAUSED, position should not extrapolate uptime
    current_pos = primary.calculate_current_position(data.uptime_seconds)
    assert current_pos == pytest.approx(107.708)


def test_parse_youtube_playing_position_calculation():
    """Test position extrapolation while playing."""
    output = read_fixture("youtube_playing.txt")
    data = parse_media_session_output(output)

    assert data.uptime_seconds == 500000.00
    assert data.media_button_session_pkg == "com.google.android.youtube.tv"

    primary = data.primary_session
    assert primary is not None
    assert primary.package == "com.google.android.youtube.tv"
    assert primary.state == MediaPlayerState.PLAYING

    # reported: 45000ms = 45.0s, updated: 495000000ms = 495000s, uptime: 500000s
    # elapsed: 5.0s -> total corrected position: 45.0 + 5.0 = 50.0s
    calculated_pos = primary.calculate_current_position(data.uptime_seconds)
    assert calculated_pos == pytest.approx(50.0)


def test_parse_multiple_sessions():
    """Test parsing multiple sessions and identifying inactive error sessions."""
    output = read_fixture("multiple_sessions.txt")
    data = parse_media_session_output(output)

    assert data.uptime_seconds == 123456.78
    assert data.media_button_session_pkg is None
    assert len(data.sessions) == 3

    # Primary should be YouTube TV because it is in PLAYING state vs Netflix PAUSED
    primary = data.primary_session
    assert primary is not None
    assert primary.package == "com.google.android.youtube.tv"
    assert primary.state == MediaPlayerState.PLAYING

    # Verify bluetooth error session was parsed correctly in session list
    bt_session = next(s for s in data.sessions if s.package == "com.android.bluetooth")
    assert bt_session.active is False
    assert bt_session.state == MediaPlayerState.IDLE
    assert bt_session.error == "Bluetooth audio disconnected"


def test_playback_state_parser():
    """Test state integer and string conversion helper."""
    assert parse_playback_state(3) == MediaPlayerState.PLAYING
    assert parse_playback_state("2") == MediaPlayerState.PAUSED
    assert parse_playback_state("PLAYING") == MediaPlayerState.PLAYING
    assert parse_playback_state("BUFFERING") == MediaPlayerState.BUFFERING
    assert parse_playback_state("ERROR") == MediaPlayerState.IDLE
    assert parse_playback_state(None) == MediaPlayerState.IDLE


def test_friendly_app_name_resolution():
    """Test dynamic session tag parsing and app name cleaning."""
    from custom_components.adb_media_session.parser import clean_session_tag

    assert clean_session_tag("Netflix media session", "com.netflix.ninja") == "Netflix"
    assert clean_session_tag("YouTube", "com.google.android.youtube.tv") == "YouTube"
    assert clean_session_tag("org.smarttube.stable", "org.smarttube.stable") == "Smarttube"
    assert clean_session_tag("Spotify", "com.spotify.tv.android") == "Spotify"

