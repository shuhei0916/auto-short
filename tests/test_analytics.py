from autoshort.analytics import build_report


def meta(seed, fmt, vid, publish_at=None, at="2026-11-11T17:00:00+00:00"):
    up = None if vid is None else {"id": vid, "at": at, "publish_at": publish_at}
    return {"seed": seed, "format": fmt, "title": f"t{seed}", "uploaded": up}


METAS = [
    meta(3, "ring_escape", "A"),
    meta(4, "ring_escape", "B", publish_at="2026-11-11T23:00:00Z"),
    meta(5, "ball_grow", "C", publish_at="2026-11-12T15:00:00Z"),
    meta(9, "ball_grow", None),  # rendered but never uploaded
]
STATS = {"A": {"views": 100, "likes": 5, "comments": 1}, "B": {"views": 300, "likes": 9, "comments": 0},
         "C": {"views": 50, "likes": 2, "comments": 0}}
RETENTION = {"A": {"avg_view_pct": 80.0, "avg_view_s": 20.0, "subs_gained": 1},
             "B": {"avg_view_pct": 60.0, "avg_view_s": 15.0, "subs_gained": 3}}


def test_only_uploaded_videos_are_reported_in_publish_order():
    r = build_report(METAS, STATS, RETENTION, today="2026-11-14")
    assert [v["id"] for v in r["videos"]] == ["A", "B", "C"]
    assert r["generated"] == "2026-11-14"


def test_video_rows_merge_stats_and_retention():
    v = build_report(METAS, STATS, RETENTION, today="2026-11-14")["videos"][1]
    assert v == {"id": "B", "seed": 4, "format": "ring_escape", "title": "t4",
                 "published": "2026-11-11T23:00:00Z", "url": "https://youtube.com/shorts/B",
                 "views": 300, "likes": 9, "comments": 0,
                 "avg_view_pct": 60.0, "avg_view_s": 15.0, "subs_gained": 3}


def test_retention_may_lag_behind():
    c = build_report(METAS, STATS, RETENTION, today="2026-11-14")["videos"][2]
    assert c["views"] == 50 and c["avg_view_pct"] is None and c["subs_gained"] is None


def test_per_format_totals_weight_retention_by_views():
    f = build_report(METAS, STATS, RETENTION, today="2026-11-14")["by_format"]
    assert f["ring_escape"] == {"videos": 2, "views": 400, "avg_view_pct": 65.0, "subs_gained": 4}
    assert f["ball_grow"] == {"videos": 1, "views": 50, "avg_view_pct": None, "subs_gained": 0}


def test_channel_totals_are_included():
    r = build_report(METAS, STATS, RETENTION, today="2026-11-14", channel={"subscribers": 12, "views": 450})
    assert r["channel"] == {"subscribers": 12, "views": 450}


def test_daily_channel_log_adds_or_replaces_todays_row():
    from autoshort.analytics import upsert_daily

    csv = upsert_daily("", "2026-11-13", 3, 100, 4)
    assert csv == "date,subscribers,views,videos\n2026-11-13,3,100,4\n"
    csv = upsert_daily(csv, "2026-11-14", 5, 300, 5)
    csv = upsert_daily(csv, "2026-11-14", 6, 320, 5)
    assert csv.splitlines()[1:] == ["2026-11-13,3,100,4", "2026-11-14,6,320,5"]
