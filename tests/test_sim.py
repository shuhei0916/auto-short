import math
import wave

import pytest

from autoshort.audio import SR, build_audio
from autoshort.sim import FPS, find_good_sim, make_params, quality_ok, simulate


@pytest.fixture(scope="module")
def sim():
    return find_good_sim(3)


def test_same_seed_gives_identical_run(sim):
    again = find_good_sim(3)
    assert again.frames == sim.frames
    assert again.events == sim.events


def test_retries_keep_the_look_but_change_the_start():
    a, b = make_params(5, 0), make_params(5, 1)
    assert (a.n_rings, a.gaps, a.omegas, a.hue0) == (b.n_rings, b.gaps, b.omegas, b.hue0)
    assert a.v0 != b.v0


def test_rings_break_in_order_and_all_break(sim):
    breaks = [e["ring"] for e in sim.events if e["kind"] == "break"]
    assert breaks == list(range(sim.params.n_rings))
    assert sim.broken[-1] == sim.params.n_rings


def test_ball_never_leaves_the_current_ring(sim):
    p = sim.params
    for (x, y), broken in zip(sim.frames, sim.broken):
        if broken < p.n_rings:
            assert math.hypot(x, y) + p.ball_r <= p.radii[broken] + 1.0


def test_accepted_run_passes_the_gate_and_fits_a_short(sim):
    assert quality_ok(sim) == (True, "ok")
    assert 16.0 <= sim.finish_t <= 34.0
    assert sim.duration < 60
    assert sim.duration == pytest.approx(sim.finish_t + 1.8, abs=2 / FPS)


def test_gate_rejects_a_run_that_ends_too_fast(sim):
    sim.finish_t, saved = 5.0, sim.finish_t
    try:
        ok, reason = quality_ok(sim)
    finally:
        sim.finish_t = saved
    assert not ok and "finish_t" in reason


def test_simulation_gives_up_when_time_runs_out():
    assert simulate(make_params(3, 0), max_seconds=0.5) is None


def test_audio_matches_video_length(sim, tmp_path):
    path = tmp_path / "a.wav"
    build_audio(sim, path)
    with wave.open(str(path)) as f:
        assert f.getframerate() == SR
        assert f.getnframes() / SR == pytest.approx(sim.duration, abs=0.01)
