import pytest
from types import SimpleNamespace
from unittest.mock import Mock
from threading import Event, get_ident

from whatcable_linux.altmode import CableAltModeCompatibility
from whatcable_linux.app import BASE_APP_ID, _altmode_verdict_presentation, _application_id
from whatcable_linux.app import WhatCableApplication
from whatcable_linux.models import SystemReport


def refresh_state(**overrides):
    state = dict(scan_running=True, scan_pending=False, stopping=False,
                 last_report=None, status_label=Mock(), _apply_report=Mock(), refresh=Mock())
    state.update(overrides)
    return SimpleNamespace(**state)


def test_unchanged_poll_preserves_widgets():
    state = refresh_state(last_report=SystemReport())
    WhatCableApplication._scan_finished(state, SystemReport(), None)
    state._apply_report.assert_not_called()
    assert not state.scan_running


def test_changed_report_is_applied():
    state = refresh_state()
    report = SystemReport()
    WhatCableApplication._scan_finished(state, report, None)
    state._apply_report.assert_called_once_with(report)
    assert state.last_report == report


def test_refresh_burst_coalesces_into_one_followup():
    state = refresh_state()
    for _ in range(20):
        WhatCableApplication.refresh(state)
    assert state.scan_pending
    WhatCableApplication._scan_finished(state, SystemReport(), None)
    state.refresh.assert_called_once()
    assert not state.scan_pending


def test_scan_failure_retains_content_and_allows_retry():
    state = refresh_state(last_report=SystemReport())
    WhatCableApplication._scan_finished(state, None, "Device unavailable")
    state._apply_report.assert_not_called()
    state.status_label.set_label.assert_called_with("Refresh failed")
    WhatCableApplication._scan_finished(state, SystemReport(), None)
    state._apply_report.assert_called_once()


def test_late_result_after_shutdown_does_not_touch_widgets():
    state = refresh_state(stopping=True, scan_pending=True)
    WhatCableApplication._scan_finished(state, SystemReport(), None)
    state._apply_report.assert_not_called()
    state.refresh.assert_not_called()


def test_scan_runs_off_caller_thread_and_marshals_result(monkeypatch):
    from whatcable_linux import app

    completed = Event()
    worker_threads = []
    deliveries = []
    report = SystemReport()

    def scan():
        worker_threads.append(get_ident())
        return report

    def idle_add(callback, *args):
        deliveries.append((callback, args))
        completed.set()

    state = refresh_state(scan_running=False)
    state._scan_finished = Mock()
    state._scan = lambda: WhatCableApplication._scan(state)
    monkeypatch.setattr(app, "scan_system", scan)
    monkeypatch.setattr(app.GLib, "idle_add", idle_add)
    WhatCableApplication.refresh(state)
    assert completed.wait(2)
    assert worker_threads[0] != get_ident()
    assert deliveries == [(state._scan_finished, (report, None))]
    state._scan_finished.assert_not_called()


def test_hardware_text_disables_markup_before_setting_labels(monkeypatch):
    from whatcable_linux import app

    row = Mock()

    def check_literal(_text):
        row.set_use_markup.assert_called_once_with(False)

    row.set_title.side_effect = check_literal
    row.set_subtitle.side_effect = check_literal
    monkeypatch.setattr(app.Adw, "ActionRow", lambda: row)
    assert app._plain_row("A & B", "<b>literal</b>") is row
    row.set_title.assert_called_once_with("A & B")
    row.set_subtitle.assert_called_once_with("<b>literal</b>")


def test_application_id_uses_development_flatpak_identity() -> None:
    assert _application_id(f"{BASE_APP_ID}.Devel") == f"{BASE_APP_ID}.Devel"


def test_application_id_ignores_unexpected_environment_value() -> None:
    assert _application_id("com.example.Unrelated") == BASE_APP_ID
    assert _application_id(None) == BASE_APP_ID


@pytest.mark.parametrize(
    ("compatibility", "label"),
    [
        (CableAltModeCompatibility.SUPPORTED, "Not blocked"),
        (CableAltModeCompatibility.UNSUPPORTED, "Blocked"),
        (CableAltModeCompatibility.UNKNOWN, "Unknown"),
    ],
)
def test_altmode_verdict_describes_cable_restriction_without_overclaiming(
    compatibility: CableAltModeCompatibility,
    label: str,
) -> None:
    verdict, _css_class, _icon_name = _altmode_verdict_presentation(compatibility)

    assert verdict == label
