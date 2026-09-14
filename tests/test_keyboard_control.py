"""Tests for windows keyboard_control virtual key mappings and error handling."""

from __future__ import annotations

from hadj_no_touch.windows.keyboard_control import _vk, tap, press


def test_vk_standard_keys() -> None:
    assert _vk("ENTER") == 0x0D
    assert _vk("SPACE") == 0x20
    assert _vk("BACKSPACE") == 0x08
    assert _vk("TAB") == 0x09
    assert _vk("ESC") == 0x1B


def test_vk_letters_and_digits() -> None:
    assert _vk("A") == ord("A")
    assert _vk("a") == ord("A")
    assert _vk("Z") == ord("Z")
    assert _vk("5") == ord("5")


def test_vk_page_navigation_aliases() -> None:
    assert _vk("PGDN") == 0x22
    assert _vk("PGUP") == 0x21
    assert _vk("PAGEDOWN") == 0x22
    assert _vk("PAGEUP") == 0x21
    assert _vk("PAGE_DOWN") == 0x22
    assert _vk("PAGE_UP") == 0x21
    assert _vk("NEXT") == 0x22
    assert _vk("PRIOR") == 0x21


def test_vk_symbols() -> None:
    assert _vk("=") == 0xBB
    assert _vk("+") == 0xBB
    assert _vk("-") == 0xBD
    assert _vk("_") == 0xBD


def test_vk_unknown_multi_char_does_not_raise() -> None:
    # Must log warning and return 0 instead of raising TypeError: ord() expected a character...
    assert _vk("INVALID_KEY_NAME") == 0
    assert _vk("UNKNOWN123") == 0


def test_tap_and_press_unknown_keys_safely() -> None:
    # Should not raise any exception when tapping/pressing unknown multi-char keys
    tap("INVALID_KEY_NAME")
    press("INVALID_KEY_NAME", hold_ms=10)
