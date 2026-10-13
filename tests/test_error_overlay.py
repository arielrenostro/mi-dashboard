"""Spec: openspec/specs/screen-navigation (Connection error overlay)."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from app.ui.components.error_overlay import ErrorOverlay


@pytest.fixture
def parent(qapp):
    widget = QWidget()
    widget.resize(1000, 600)
    widget.show()
    yield widget
    widget.close()


@pytest.fixture
def overlay(parent):
    return ErrorOverlay(parent)


def labels(overlay):
    return [label.text() for label in overlay.findChildren(QLabel)]


def test_overlay_is_hidden_until_an_error_is_shown(overlay):
    assert not overlay.isVisible()


def test_overlay_shows_a_title_and_the_message(overlay):
    """Scenario: Error shown and closed."""
    overlay.show_message("Falha ao conectar em COM3: porta ocupada")

    assert overlay.isVisible()
    assert "Erro de conexão" in labels(overlay)
    assert "Falha ao conectar em COM3: porta ocupada" in labels(overlay)


def test_overlay_is_square(overlay):
    """Requirement: Connection error overlay (square, dialog-like)."""
    overlay.show_message("erro")

    assert overlay.width() == overlay.height() > 0


def test_overlay_is_centered_over_its_parent(overlay, parent):
    overlay.show_message("erro")

    assert overlay.geometry().center().x() == pytest.approx(parent.rect().center().x(), abs=1)
    assert overlay.geometry().center().y() == pytest.approx(parent.rect().center().y(), abs=1)


def test_overlay_stays_centered_when_the_parent_size_changes(overlay, parent):
    parent.resize(1600, 900)

    overlay.show_message("erro")

    assert overlay.geometry().center().x() == pytest.approx(800, abs=1)
    assert overlay.geometry().center().y() == pytest.approx(450, abs=1)


def test_overlay_closes_by_itself_after_two_seconds(overlay):
    """Scenario: Error shown and closed."""
    overlay.show_message("erro")

    assert overlay._timer.isSingleShot()
    assert overlay._timer.interval() == 2000
    assert overlay._timer.isActive()

    overlay._timer.timeout.emit()  # the two seconds elapse

    assert not overlay.isVisible()


def test_a_new_message_replaces_the_text_and_restarts_the_two_seconds(overlay):
    """Scenario: New error while visible (QTimer.start restarts a running timer, so every message must call it)."""
    overlay.show_message("primeiro erro")
    starts = []
    real_start = overlay._timer.start
    overlay._timer.start = lambda *args: (starts.append(1), real_start(*args))[1]

    overlay.show_message("segundo erro")

    assert "segundo erro" in labels(overlay)
    assert "primeiro erro" not in labels(overlay)
    assert starts == [1]
    assert overlay._timer.isActive() and overlay._timer.interval() == 2000
    assert overlay.isVisible()


def test_only_one_overlay_exists_however_many_errors_arrive(overlay, parent):
    for n in range(5):
        overlay.show_message(f"erro {n}")

    assert len(parent.findChildren(ErrorOverlay)) == 1


def test_overlay_never_takes_keyboard_focus(overlay):
    """Requirement: Connection error overlay (does not consume keyboard input)."""
    overlay.show_message("erro")

    assert overlay.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert all(label.focusPolicy() == Qt.FocusPolicy.NoFocus for label in overlay.findChildren(QLabel))
    assert not overlay.hasFocus()


def test_overlay_is_transparent_to_the_mouse(overlay):
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert all(label.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) for label in overlay.findChildren(QLabel))


def test_a_very_long_message_is_capped(overlay):
    """Risk: error text may be long."""
    overlay.show_message("x" * 5000)

    shown = max(labels(overlay), key=len)
    assert len(shown) <= 260
    assert shown.endswith("…")


def test_overlay_is_raised_above_its_siblings(parent, qapp):
    sibling_overlay = ErrorOverlay(parent)
    cover = QWidget(parent)
    cover.resize(1000, 600)
    cover.show()

    sibling_overlay.show_message("erro")

    assert parent.children()[-1] is sibling_overlay
