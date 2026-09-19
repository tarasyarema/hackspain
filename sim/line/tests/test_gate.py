"""Gate: command strings per channel, non-blocking pulse timing, coalescing, dry_run, selftest."""
import threading
import time

import pytest

from line.arduino_link import FakeArduino, LinkError
from line.config import LineConfig
from line.contracts import GateDriver
from line.gate import Gate


@pytest.fixture
def env():
    cfg = LineConfig()  # base=D9, flush 90, open 65, hold (90, 75)
    fake = FakeArduino()
    gates = []

    def make(**kw):
        g = Gate(fake, cfg, **kw)
        gates.append(g)
        return g

    yield cfg, fake, make
    for g in gates:
        g.close()


def wait_state(g, state, timeout=2.0):
    t0 = time.monotonic()
    while g.state != state and time.monotonic() - t0 < timeout:
        time.sleep(0.005)
    return g.state == state


def test_command_strings_per_channel(env):
    cfg, fake, make = env
    g = make()
    assert isinstance(g, GateDriver)
    assert g.command(65) == "S 65 90 75" and g.command(90) == "S 90 90 75"
    cfg.gate.channel = "shoulder"
    assert g.command(65) == "S 90 65 75"
    cfg.gate.channel = "elbow"
    assert g.command(65) == "S 90 75 65"
    cfg.gate.channel = "wrist"
    with pytest.raises(ValueError):
        g.command(65)
    assert not g.selftest()[0].ok


def test_flush_and_open_send_immediately(env):
    cfg, fake, make = env
    g = make()
    g.open()
    assert fake.sent[-1] == "S 65 90 75" and g.state == "open"
    g.flush()
    assert fake.sent[-1] == "S 90 90 75" and g.state == "flush"
    assert [e["action"] for e in g.log] == ["open", "flush"] and all(e["sent"] for e in g.log)


def test_pulse_is_non_blocking_and_on_time(env):
    cfg, fake, make = env
    g = make()
    t0 = time.monotonic()
    g.pulse(0.10, 0.20)
    assert time.monotonic() - t0 < 0.02, "pulse() must return immediately"
    assert g.state == "scheduled" and fake.sent == []
    assert wait_state(g, "open") and fake.sent[-1] == "S 65 90 75"
    assert wait_state(g, "flush") and fake.sent[-1] == "S 90 90 75"
    opens = [e for e in g.log if e["action"] == "open"]
    flushes = [e for e in g.log if e["action"] == "flush"]
    assert len(opens) == 1 and len(flushes) == 1
    assert abs((opens[0]["t"] - t0) - 0.10) <= 0.020
    assert abs((flushes[0]["t"] - t0) - 0.30) <= 0.020
    assert g.n_pulses == 1 and g.n_coalesced == 0


def test_overlapping_pulses_coalesce_into_one_open_and_extended_flush(env):
    cfg, fake, make = env
    g = make()
    t0 = time.monotonic()
    g.pulse(0.10, 0.10)  # open 0.10, flush 0.20
    time.sleep(0.03)
    g.pulse(0.15, 0.30)  # would open 0.18, flush 0.48 → open stays 0.10, flush extends to 0.48
    time.sleep(0.15)  # door is now open
    g.pulse(0.00, 0.10)  # while open: flush at 0.28 < 0.48 → no change
    assert wait_state(g, "flush", timeout=1.5)
    actions = [e["action"] for e in g.log]
    assert actions == ["open", "flush"], actions
    t_open, t_flush = g.log[0]["t"] - t0, g.log[1]["t"] - t0
    assert abs(t_open - 0.10) <= 0.02
    assert abs(t_flush - 0.48) <= 0.03
    assert g.n_pulses == 3 and g.n_coalesced == 2


def test_pulse_while_manually_open_only_schedules_the_flush(env):
    cfg, fake, make = env
    g = make()
    g.open()
    g.pulse(0.0, 0.10)
    assert g.state == "open"
    assert wait_state(g, "flush")
    assert [e["action"] for e in g.log] == ["open", "flush"]


def test_earlier_second_pulse_moves_open_forward(env):
    cfg, fake, make = env
    g = make()
    t0 = time.monotonic()
    g.pulse(0.30, 0.10)
    g.pulse(0.05, 0.10)  # earlier: open at 0.05, flush stays at 0.40
    assert wait_state(g, "flush", timeout=1.0)
    assert abs((g.log[0]["t"] - t0) - 0.05) <= 0.02
    assert abs((g.log[1]["t"] - t0) - 0.40) <= 0.02


def test_flush_cancels_a_scheduled_pulse(env):
    cfg, fake, make = env
    g = make()
    g.pulse(0.2, 0.2)
    g.flush()
    time.sleep(0.5)
    assert [e["action"] for e in g.log] == ["flush"] and fake.sent == ["S 90 90 75"]


def test_flush_cannot_be_followed_by_a_stale_worker_open():
    class BlockingLink:
        def __init__(self):
            self.open_started = threading.Event()
            self.release_open = threading.Event()
            self.completed = []

        def cmd(self, line):
            if line == "S 65 90 75":
                self.open_started.set()
                assert self.release_open.wait(1.0)
            self.completed.append(line)
            return "ok"

    cfg = LineConfig()
    link = BlockingLink()
    g = Gate(link, cfg)
    g.pulse(0.0, 10.0)
    assert link.open_started.wait(1.0)
    flush_done = threading.Event()
    flush_thread = threading.Thread(target=lambda: (g.flush(), flush_done.set()))
    flush_thread.start()
    assert not flush_done.wait(0.05), "flush must wait behind the selected OPEN command"
    link.release_open.set()
    assert flush_done.wait(1.0)
    flush_thread.join()
    assert link.completed == ["S 65 90 75", "S 90 90 75"]
    assert g.state == "flush"
    g.close()


def test_pulse_does_not_wait_for_an_inflight_serial_command():
    class BlockingLink:
        def __init__(self):
            self.open_started = threading.Event()
            self.release_open = threading.Event()

        def cmd(self, line):
            if line == "S 65 90 75":
                self.open_started.set()
                assert self.release_open.wait(1.0)
            return "ok"

    link = BlockingLink()
    g = Gate(link, LineConfig())
    open_thread = threading.Thread(target=g.open)
    open_thread.start()
    assert link.open_started.wait(1.0)
    t0 = time.monotonic()
    g.pulse(0.1, 0.1)
    assert time.monotonic() - t0 < 0.02
    link.release_open.set()
    open_thread.join(1.0)
    g.flush()
    g.close()


def test_pulses_during_inflight_flush_coalesce_into_a_new_schedule():
    class BlockingFlushLink:
        def __init__(self):
            self.flush_started = threading.Event()
            self.release_flush = threading.Event()

        def cmd(self, line):
            if line == "S 90 90 75":
                self.flush_started.set()
                assert self.release_flush.wait(1.0)
            return "ok"

    link = BlockingFlushLink()
    g = Gate(link, LineConfig())
    g.open()
    g.pulse(0.0, 0.02)
    assert link.flush_started.wait(1.0)
    g.pulse(0.30, 0.10)
    g.pulse(0.10, 0.50)
    link.release_flush.set()
    t0 = time.monotonic()
    while g.status()["inflight_action"] is not None and time.monotonic() - t0 < 1.0:
        time.sleep(0.005)
    status = g.status()
    assert status["state"] == "scheduled" and 0 < status["open_in_s"] <= 0.10
    assert 0.45 <= status["flush_in_s"] <= 0.60 and status["n_coalesced"] == 2
    g.flush()
    g.close()


def test_dry_run_records_but_sends_nothing(env):
    cfg, fake, make = env
    g = make(dry_run=True)
    g.open()
    g.pulse(0.02, 0.05)
    assert wait_state(g, "flush")
    assert fake.sent == []
    assert [e["action"] for e in g.log] == ["open", "flush"]  # pulse while open only schedules the flush
    assert all(e["sent"] is False for e in g.log)
    assert g.status()["dry_run"] is True


def test_default_dwell_and_status(env):
    cfg, fake, make = env
    cfg.gate.default_dwell_s = 0.05
    g = make()
    g.pulse(0.05)
    s = g.status()
    assert s["state"] == "scheduled" and 0 < s["open_in_s"] <= 0.05 and 0 < s["flush_in_s"] <= 0.10
    assert wait_state(g, "flush")
    s = g.status()
    assert s["open_in_s"] is None and s["flush_in_s"] is None and s["n_pulses"] == 1 and len(s["log"]) == 2


def test_link_error_is_logged_not_raised(env):
    cfg, fake, make = env
    g = make()
    fake.close()  # every cmd now raises LinkError
    g.open()
    assert g.state == "error"
    assert g.n_errors == 1 and g.log[-1]["reply"].startswith("ERROR") and "closed" in g.last_error


def test_non_ok_reply_is_an_error_not_a_success():
    class RefusingLink:
        def cmd(self, _line):
            return "err"

    g = Gate(RefusingLink(), LineConfig())
    g.open()
    assert g.state == "error" and g.n_errors == 1
    assert g.log[-1]["reply"] == "err" and "refused" in g.last_error
    g.close()


@pytest.mark.parametrize("delay,dwell", [(-0.1, 0.1), (float("nan"), 0.1), (float("inf"), 0.1), (0.1, -0.1), (0.1, float("nan")), (0.1, float("inf"))])
def test_pulse_rejects_negative_and_nonfinite_timing(env, delay, dwell):
    _, fake, make = env
    g = make()
    with pytest.raises(ValueError):
        g.pulse(delay, dwell)
    assert g.state == "flush" and fake.sent == [] and g.n_pulses == 0


def test_close_flushes_attempted_open_and_rejects_later_commands():
    class LostOpenReplyLink:
        def __init__(self):
            self.sent = []

        def cmd(self, line):
            self.sent.append(line)
            if line == "S 65 90 75":
                raise LinkError("open acknowledgement lost")
            return "ok"

    link = LostOpenReplyLink()
    g = Gate(link, LineConfig())
    g.open()
    assert g.state == "error"
    g.close()
    assert link.sent == ["S 65 90 75", "S 90 90 75"] and g.state == "flush"
    with pytest.raises(RuntimeError, match="closed"):
        g.pulse(0.0, 0.1)


def test_lost_open_ack_keeps_the_scheduled_compensating_flush():
    class LostOpenReplyLink:
        def __init__(self):
            self.sent = []

        def cmd(self, line):
            self.sent.append(line)
            if line == "S 65 90 75":
                raise LinkError("open acknowledgement lost")
            return "ok"

    link = LostOpenReplyLink()
    g = Gate(link, LineConfig())
    g.pulse(0.0, 0.15)
    assert wait_state(g, "error")
    with pytest.raises(RuntimeError, match="waiting.*flush"):
        g.pulse(0.0, 0.1)
    assert wait_state(g, "flush")
    assert link.sent == ["S 65 90 75", "S 90 90 75"]
    assert g.n_errors == 1 and "acknowledgement lost" in g.last_error
    g.close()


def test_close_cancels_a_pending_pulse_before_it_opens(env):
    _, fake, make = env
    g = make()
    g.pulse(0.2, 0.2)
    g.close()
    time.sleep(0.3)
    assert fake.sent == [] and g.state == "flush"


def test_selftest_uses_a_fake_and_never_moves_the_real_link(env):
    cfg, fake, make = env
    g = make()
    checks = g.selftest()
    assert all(c.ok for c in checks), [(c.name, c.detail) for c in checks if not c.ok]
    assert all(not s.startswith("S") for s in fake.sent), "selftest must not send S to the real link"
    assert fake.sent == ["?"]


def test_ramp_override_is_sent_once_at_start_when_enabled(env):
    cfg, fake, make = env
    g = make()
    assert not any(s.startswith("R") for s in fake.sent), "off by default"
    cfg.gate.ramp_override = True
    g2 = make()
    assert fake.sent[-1] == "R 0 400 8000" and g2.log[-1]["action"] == "ramp" and g2.log[-1]["reply"] == "ok"
    assert fake.vmax[0] == 400.0 and fake.amax[0] == 8000.0
    assert g2.status()["ramp_override"] is True
    cfg.gate.channel = "elbow"
    assert g2.ramp_command() == "R 2 400 8000"


def test_ramp_override_dry_run_and_old_firmware(env):
    cfg, fake, make = env
    cfg.gate.ramp_override = True
    g = make(dry_run=True)
    assert fake.sent == [] and g.log[-1]["action"] == "ramp" and g.log[-1]["sent"] is False
    fake._handle_orig = fake._handle
    fake._handle = lambda line: "err" if line.startswith("R") else fake._handle_orig(line)  # firmware without R
    g2 = make()
    assert g2.n_errors == 1 and "refused" in g2.last_error and g2.state == "flush"
