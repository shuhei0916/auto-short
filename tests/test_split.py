import math

import pytest

from autoshort.sim import FORMATS, FPS, find_good_sim, quality_ok


@pytest.fixture(scope="module")
def sim():
    return find_good_sim(2, "split")


def test_format_registered():
    assert "split" in FORMATS


def test_deterministic(sim):
    again = find_good_sim(2, "split")
    assert again.counts == sim.counts
    assert again.finish_t == sim.finish_t
    assert again.frames[-1] == sim.frames[-1]


def test_count_starts_at_one_never_drops_and_reaches_target(sim):
    assert sim.counts[0] == 1
    assert all(b >= a for a, b in zip(sim.counts, sim.counts[1:]))
    assert sim.counts[-1] == sim.params.n_balls
    assert len(sim.frames[-1]) == sim.params.n_balls


def test_balls_stay_inside_arena(sim):
    p = sim.params
    for balls in sim.frames[:: FPS // 2]:
        for x, y, _gen in balls:
            assert math.hypot(x, y) + p.ball_r <= p.arena_r + 1.0


def test_gate_and_length(sim):
    assert quality_ok(sim) == (True, "ok")
    assert 15.0 <= sim.duration <= 40.0


def test_ending_has_clear_final_event(sim):
    assert sim.events[-1]["kind"] == "break"
    assert sim.events[-1]["t"] == pytest.approx(sim.finish_t)
    assert sim.duration > sim.finish_t + 1.5


def test_growth_is_visibly_progressing(sim):
    # count at 1/3 of the run is well below the final count, and above 1
    i = int(sim.finish_t * FPS / 3)
    assert 1 < sim.counts[i] < sim.params.n_balls * 0.6
