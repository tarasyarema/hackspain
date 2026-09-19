"""Closed loop on synthetic frames: one bean → one verdict; a burnt bean → one dry-run gate pulse; never twice per bean."""
import threading
import time

import cv2
import numpy as np
import pytest

from line import _stubs, config, panel as panel_module
from line.contracts import Frame, Verdict, now
from line.pipeline import SortingLine, flow_fraction, fallback_gate_schedule
from line.contracts import Blob, ROI
from line.gate import Gate


def make(cfg, t, u=None, dark=False):
    img = np.full((cfg.camera.height, cfg.camera.width, 3), 235, np.uint8)
    if u is not None:
        ppm = cfg.camera.px_per_mm
        cv2.ellipse(img, (int(u), (cfg.camera.zone[1] + cfg.camera.zone[3]) // 2), (int(6 * ppm), int(4 * ppm)), 0, 0, 360, (35, 30, 30) if dark else (70, 95, 140), -1)
    return Frame(img, t, int(t * 1000), "test")


def build(cfg):
    ard = _stubs.StubArduino()
    gate = _stubs.StubGate(ard, cfg, dry_run=True)
    line = SortingLine(cfg, _stubs.StubCamera(cfg), _stubs.StubDetector(cfg), _stubs.StubClassifier(cfg), gate, ard)
    line.enabled = True
    return line, gate


def roll(line, cfg, dark, dt=0.02):
    x0, _, x1, _ = cfg.camera.zone
    t = now()
    verdicts = []
    for u in range(x0 - 60, x1 + 60, 12):  # enters partial, crosses, leaves
        v = line.step(make(cfg, t, u, dark))
        if v:
            verdicts.append(v)
        t += dt
    for _ in range(30):  # empty frames → back to armed
        line.step(make(cfg, t))
        t += dt
    return verdicts


def test_good_bean_one_verdict_no_gate():
    cfg = config.LineConfig()
    cfg.act_on = "suspect"
    line, gate = build(cfg)
    verdicts = roll(line, cfg, dark=False)
    assert len(verdicts) == 1 and not verdicts[0].suspect, [v.reason for v in verdicts]
    assert line.counters["beans"] == 1 and line.counters["good"] == 1 and line.counters["gate_pulses"] == 0
    assert line.state == "armed"


def test_burnt_bean_schedules_one_dry_pulse():
    cfg = config.LineConfig()
    cfg.timing.bean_speed_cm_s = 1000.0  # make the scheduled pulse fire within the test
    line, gate = build(cfg)
    verdicts = roll(line, cfg, dark=True)
    assert len(verdicts) == 1 and verdicts[0].suspect, [v.reason for v in verdicts]
    assert line.counters["gate_pulses"] == 1
    time.sleep(cfg.gate.default_dwell_s + 0.3)
    kinds = [e.split()[0] for _, e in gate.events]
    assert kinds == ["open", "flush"], gate.events
    assert all("(dry)" in e for _, e in gate.events)
    assert line.arduino.log == []  # dry run never touched the Arduino


def test_two_beans_two_verdicts():
    cfg = config.LineConfig()
    line, gate = build(cfg)
    roll(line, cfg, dark=False)
    roll(line, cfg, dark=True)
    assert line.counters["beans"] == 2 and line.counters["good"] == 1 and line.counters["suspect"] == 1


def test_disabled_line_only_previews():
    cfg = config.LineConfig()
    line, gate = build(cfg)
    line.enabled = False
    assert roll(line, cfg, dark=True) == []
    assert line.counters["beans"] == 1 and line.counters["gate_pulses"] == 0
    assert line.latest_jpeg() is not None


def test_disabling_during_classification_flushes_and_prevents_a_late_pulse():
    class BlockingClassifier:
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()

        def classify(self, _frame, _blob):
            self.started.set()
            assert self.release.wait(1.0)
            return Verdict("burnt", 1.0, True, "test", 0.0, "blocking")

    class RecordingGate:
        dry_run = False

        def __init__(self):
            self.actions = []

        def pulse(self, _delay, _dwell):
            self.actions.append("pulse")

        def flush(self):
            self.actions.append("flush")

    cfg = config.LineConfig()
    classifier = BlockingClassifier()
    gate = RecordingGate()
    line = SortingLine(cfg, None, None, classifier, gate, None)
    line.set_enabled(True)
    frame = Frame(np.zeros((10, 10, 3), np.uint8), now(), 1, "test")
    blob = Blob(5, 5, (2, 2, 6, 6), 36, False)
    decision = threading.Thread(target=line._decide, args=(frame, blob, ROI(0, 0, 10, 10)))
    decision.start()
    assert classifier.started.wait(1.0)
    line.set_enabled(False, flush=True)
    classifier.release.set()
    decision.join(1.0)
    assert not decision.is_alive()
    assert gate.actions == ["flush"] and line.counters["gate_pulses"] == 0


def test_panel_stop_and_dry_disable_then_flush(monkeypatch):
    class Gate:
        dry_run = False

    class Line:
        enabled = True

        def __init__(self, gate):
            self.gate = gate
            self.calls = []

        def set_enabled(self, enabled, *, flush=False):
            self.calls.append((enabled, flush, self.gate.dry_run))
            self.enabled = enabled

        def status(self):
            return {"enabled": self.enabled}

    p = panel_module.Panel.__new__(panel_module.Panel)
    p.cfg = config.LineConfig()
    p.cfg.dry_run = False
    gate = Gate()
    gate.state = "flush"
    p.modules = {"gate": gate}
    p.line = Line(gate)
    p._action_lock = threading.Lock()
    monkeypatch.setattr(panel_module, "save", lambda _cfg: None)
    p.line_action("stop")
    p.line_action("start")
    p.line_action("dry")
    assert p.line.calls == [(False, True, False), (True, False, False), (False, True, False)]
    assert gate.dry_run is True and p.cfg.dry_run is True


def test_panel_rejects_dry_transition_when_live_flush_fails(monkeypatch):
    class Gate:
        dry_run = False
        state = "open"

        def flush(self):
            self.state = "error"

    class Line:
        enabled = True

        def __init__(self, gate):
            self.gate = gate

        def set_enabled(self, enabled, *, flush=False):
            self.enabled = enabled
            if flush:
                self.gate.flush()

    p = panel_module.Panel.__new__(panel_module.Panel)
    p.cfg = config.LineConfig()
    p.cfg.dry_run = False
    gate = Gate()
    p.modules = {"gate": gate}
    p.line = Line(gate)
    p._action_lock = threading.Lock()
    monkeypatch.setattr(panel_module, "save", lambda _cfg: None)
    with pytest.raises(RuntimeError, match="flush was not acknowledged"):
        p.line_action("dry")
    assert gate.dry_run is False and p.cfg.dry_run is False


def test_panel_serializes_manual_open_with_dry_transition(monkeypatch):
    class BlockingLink:
        def __init__(self):
            self.open_started = threading.Event()
            self.release_open = threading.Event()
            self.sent = []

        def cmd(self, line):
            self.sent.append(line)
            if line == "S 65 90 75":
                self.open_started.set()
                assert self.release_open.wait(1.0)
            return "ok"

    class Line:
        enabled = True

        def __init__(self, gate):
            self.gate = gate

        def set_enabled(self, enabled, *, flush=False):
            self.enabled = enabled
            if flush:
                self.gate.flush()

        def status(self):
            return {"enabled": self.enabled}

    p = panel_module.Panel.__new__(panel_module.Panel)
    p.cfg = config.LineConfig()
    link = BlockingLink()
    gate = Gate(link, p.cfg)
    p.modules = {"gate": gate}
    p.line = Line(gate)
    p._action_lock = threading.Lock()
    monkeypatch.setattr(panel_module, "save", lambda _cfg: None)
    open_thread = threading.Thread(target=p.gate, args=("open",))
    open_thread.start()
    assert link.open_started.wait(1.0)
    dry_done = threading.Event()
    dry_thread = threading.Thread(target=lambda: (p.line_action("dry"), dry_done.set()))
    dry_thread.start()
    assert not dry_done.wait(0.05)
    link.release_open.set()
    open_thread.join(1.0)
    assert dry_done.wait(1.0)
    dry_thread.join(1.0)
    assert link.sent == ["S 65 90 75", "S 90 90 75"]
    assert gate.state == "flush" and gate.dry_run is True
    gate.close()


def test_panel_closes_gate_before_arduino_link():
    order = []

    class Closeable:
        def __init__(self, name):
            self.name = name

        def close(self):
            order.append(self.name)

    class Line:
        def stop(self):
            order.append("line")

    p = panel_module.Panel.__new__(panel_module.Panel)
    p.line = Line()
    p.modules = {"arduino": Closeable("arduino"), "gate": Closeable("gate"), "camera": Closeable("camera")}
    p.close()
    assert order == ["line", "gate", "arduino", "camera"]


def test_flow_fraction_and_schedule():
    cfg = config.LineConfig()
    roi = ROI(100, 0, 300, 100)
    b = Blob(150, 50, (0, 0, 1, 1), 1, False)
    assert abs(flow_fraction(b, roi, "x") - 0.25) < 1e-9
    assert abs(flow_fraction(b, roi, "-x") - 0.75) < 1e-9
    delay, dwell = fallback_gate_schedule(0.5, cfg)  # bean at 12 cm, door at 30 cm, 35 cm/s, lead from cfg (derived by timing.py)
    assert abs(delay - max(0.0, (30 - 12) / 35 - cfg.timing.door_lead_s)) < 1e-6 and dwell == cfg.gate.default_dwell_s


def test_back_to_back_beans_each_get_a_verdict():
    """Second bean enters the zone while the first is still leaving it: two beans, two verdicts."""
    cfg = config.LineConfig()
    line, gate = build(cfg)
    x0, y0, x1, y1 = cfg.camera.zone
    ppm = cfg.camera.px_per_mm
    vmid = (y0 + y1) // 2
    t = now()
    verdicts = []
    for k in range(0, 60):
        u1 = x0 - 60 + k * 12
        u2 = u1 - 220  # trailing bean 220 px behind
        img = np.full((cfg.camera.height, cfg.camera.width, 3), 235, np.uint8)
        for u, dark in ((u1, False), (u2, True)):
            cv2.ellipse(img, (int(u), vmid), (int(6 * ppm), int(4 * ppm)), 0, 0, 360, (35, 30, 30) if dark else (70, 95, 140), -1)
        v = line.step(Frame(img, t, k, "test"))
        if v:
            verdicts.append(v)
        t += 0.02
    assert [v.suspect for v in verdicts] == [False, True], [v.reason for v in verdicts]
    assert line.counters["beans"] == 2
