# auto-short

Code-generated YouTube Shorts for the channel **Bounce Theory**
(https://www.youtube.com/@bouncetheory-x7k). Goal: 1M subscribers. Global,
non-verbal audience: on-screen text and titles are English.

## How it runs

- `.github/workflows/daily.yml`: every day 12:00 UTC renders the next seed,
  schedules it on YouTube, refreshes `analytics/`, commits `history/` + `analytics/`.
- `analytics/latest.json`: per-video views, likes, retention and per-format totals.
  `analytics/channel_daily.csv`: subscribers per day. Retention lags 2-3 days.
- Formats live in `autoshort/sim.py` (`FORMATS`), rendering in `render.py`,
  sound in `audio.py`, titles/hooks in `__main__.py`. Formats alternate by seed.
- A weekly Claude routine improves the generator on a `claude/weekly-*` branch.
  The owner reviews the PR (CI attaches preview videos) and merges it.
  Weekly reports are kept in `reports/YYYY-MM-DD.md`.

## Rules for changes

- TDD for logic (simulation, quality gates, metadata, scheduling). Visuals are
  judged by rendering a sample and looking at frames, not by tests.
- Never weaken or delete existing tests to make a change pass.
- Do not edit `.github/`, `autoshort/upload.py`, `autoshort/schedule.py`,
  `history/`, `analytics/` or `secrets/`.
- Every format must stay deterministic per seed, 15-40 s long, 1080x1920 60 fps,
  with a clear ending, and must look different from the existing formats.
- Keep each weekly change small enough to review in one sitting.

## Commands

```
python -m pytest -q
python -m autoshort make --seed 90001 --format <name> --out preview
```

Extract frames to inspect a render: ffmpeg path is
`python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"`, then
`ffmpeg -i preview/X.mp4 -vf "select='eq(n,60)+eq(n,600)+eq(n,1200)',scale=360:-1,tile=3x1" -frames:v 1 sheet.png`.
