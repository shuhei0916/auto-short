import math

import pytest

from autoshort.sim import FORMATS, FPS, find_good_sim, quality_ok


@pytest.fixture(scope="module")
def sim():
    return find_good_sim(2, "swarm")


def test_registered():
    assert "swarm" in FORMATS


def test_deterministic(sim):
    again = find_good_sim(2, "swarm")
    assert again.counts == sim.counts
    assert again.finish_t == sim.finish_t


def test_population_grows_to_target(sim):
    assert sim.counts[0] == 1
    assert all(b >= a for a, b in zip(sim.counts, sim.counts[1:]))
    assert sim.counts[-1] == sim.params.target


def test_balls_stay_inside_ring(sim):
    for frame in sim.frames:
        for x, y in frame:
            assert math.hypot(x, y) <= sim.params.wall + 1


def test_gate_and_length(sim):
    assert quality_ok(sim) == (True, "ok")
    assert 15.0 <= sim.duration <= 40.0
    assert sim.n_frames / FPS == sim.duration


def test_ends_with_break_event(sim):
    last = sim.events[-1]
    assert last["kind"] == "break" and abs(last["t"] - sim.finish_t) < 1e-6
