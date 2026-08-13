"""Tests for primary media session selection logic."""

from __future__ import annotations

from homeassistant.components.media_player import MediaPlayerState

from custom_components.adb_media_session.parser import (
    MediaSession,
    select_primary_session,
)


def create_session(
    package: str,
    active: bool = True,
    state: MediaPlayerState = MediaPlayerState.PAUSED,
    error: str | None = None,
) -> MediaSession:
    """Helper to construct MediaSession instances for testing."""
    return MediaSession(
        name=f"{package} session",
        package=package,
        active=active,
        state=state,
        position_ms=1000,
        updated_ms=1000,
        speed=1.0,
        error=error,
    )


def test_select_media_button_session_priority():
    """Test that media button session takes highest priority if active."""
    s1 = create_session("com.netflix.ninja", active=True, state=MediaPlayerState.PAUSED)
    s2 = create_session("com.google.android.youtube.tv", active=True, state=MediaPlayerState.PLAYING)

    selected = select_primary_session([s1, s2], media_button_pkg="com.netflix.ninja")
    assert selected == s1


def test_select_playing_over_paused():
    """Test that active playing session takes priority over active paused session."""
    s1 = create_session("com.netflix.ninja", active=True, state=MediaPlayerState.PAUSED)
    s2 = create_session("com.google.android.youtube.tv", active=True, state=MediaPlayerState.PLAYING)

    selected = select_primary_session([s1, s2], media_button_pkg=None)
    assert selected == s2


def test_select_buffering_over_paused():
    """Test that buffering session takes priority over paused session."""
    s1 = create_session("com.netflix.ninja", active=True, state=MediaPlayerState.PAUSED)
    s2 = create_session("com.amazon.amazonvideo.livingroom", active=True, state=MediaPlayerState.BUFFERING)

    selected = select_primary_session([s1, s2], media_button_pkg=None)
    assert selected == s2


def test_select_ignore_inactive_error_session():
    """Test that inactive error-only sessions are ignored during selection."""
    s1 = create_session(
        "com.android.bluetooth",
        active=False,
        state=MediaPlayerState.IDLE,
        error="Bluetooth audio disconnected",
    )
    s2 = create_session("com.netflix.ninja", active=True, state=MediaPlayerState.PAUSED)

    selected = select_primary_session([s1, s2], media_button_pkg=None)
    assert selected == s2


def test_select_empty_session_list():
    """Test selection when no sessions exist."""
    assert select_primary_session([], media_button_pkg=None) is None
