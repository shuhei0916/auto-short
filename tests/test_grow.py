import math

import pytest

from autoshort.sim import FORMATS, find_good_sim, quality_ok


@pytest.fixture(scope="module")
def sim():
    return find_good_sim(2, "ball_grow")


def test_formats_are_registered():
    assert FORMATS == ("ring_escape", "ball_grow", "plinko")


def test_grow_is_deterministic(sim):
    assert find_good_sim(2, "ball_grow").frames == sim.frames


def test_ball_grows_on_every_bounce_and_never_shrinks(sim):
    assert all(b >= a for a, b in zip(sim.radius, sim.radius[1:]))
    p = sim.params
    bounces = sum(e["kind"] == "bounce" for e in sim.events)
    assert sim.bounces[-1] == bounces
    assert bounces == math.ceil((p.radii[0] - p.thickness / 2 - 1 - p.ball_r) / p.growth)


def test_run_ends_with_the_ball_filling_the_ring(sim):
    p = sim.params
    assert sim.radius[-1] == pytest.approx(p.radii[0] - p.thickness / 2)
    assert sim.frames[-1] == (0.0, 0.0)
    assert sim.events[-1]["kind"] == "break"


def test_ball_stays_inside_the_ring(sim):
    p = sim.params
    for (x, y), r in zip(sim.frames, sim.radius):
        assert math.hypot(x, y) + r <= p.radii[0] + 1.0


def test_accepted_grow_run_passes_the_gate(sim):
    assert quality_ok(sim) == (True, "ok")
    assert 14.0 <= sim.finish_t <= 34.0


def test_ring_escape_records_per_frame_radius_and_bounces():
    s = find_good_sim(3)
    assert len(s.radius) == len(s.bounces) == len(s.frames)
    assert set(s.radius) == {s.params.ball_r}
    assert s.bounces[-1] == sum(e["kind"] == "bounce" for e in s.events)
