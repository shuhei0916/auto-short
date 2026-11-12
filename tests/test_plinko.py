import math

import pytest

from autoshort.sim import FORMATS, FPS, find_good_sim, quality_ok


@pytest.fixture(scope="module")
def sim():
    return find_good_sim(2, "plinko")


def test_format_registered():
    assert "plinko" in FORMATS


def test_deterministic(sim):
    again = find_good_sim(2, "plinko")
    assert again.balls == sim.balls
    assert again.finish_t == sim.finish_t


def test_every_ball_lands_in_a_bin_and_counts_add_up(sim):
    p = sim.params
    assert len(sim.balls) == p.n_balls
    assert sum(sim.final_counts) == p.n_balls
    assert len(sim.final_counts) == p.rows + 1
    assert all(b["bin"] in range(p.rows + 1) for b in sim.balls)


def test_distribution_is_bell_shaped(sim):
    c = sim.final_counts
    mid = len(c) // 2
    assert max(c) in (c[mid - 1], c[mid], c[mid + 1] if mid + 1 < len(c) else c[mid])
    assert c[0] + c[-1] < 0.1 * sim.params.n_balls


def test_ball_stays_on_screen_and_in_board(sim):
    for b in sim.balls:
        for x, y in b["pts"]:
            assert 0 < x < 1080 and 0 < y < 1920


def test_gate_and_length(sim):
    assert quality_ok(sim) == (True, "ok")
    assert 15.0 <= sim.duration <= 40.0
    assert sim.n_frames / FPS == sim.duration


def test_ending_has_clear_final_event(sim):
    assert sim.events[-1]["kind"] == "break"
    assert sim.events[-1]["t"] == pytest.approx(sim.finish_t)


def test_ball_drops_get_faster(sim):
    starts = [b["start"] for b in sim.balls]
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert gaps[0] > gaps[-1]
