from autoshort.weekly import (
    build_weekly,
    parse_channel_csv,
    render_html,
    render_text,
)

CSV = """date,subscribers,views,videos
2026-11-10,1,1000,5
2026-11-12,5,3000,7
2026-11-17,27,32697,17
2026-11-19,40,52697,21
"""


def video(vid, fmt, views, pct=None, subs=None, published="2026-11-12T15:00:00Z"):
    return {"id": vid, "seed": 1, "format": fmt, "title": f"title {vid} #shorts",
            "published": published, "url": f"https://youtube.com/shorts/{vid}",
            "views": views, "likes": 0, "comments": 0,
            "avg_view_pct": pct, "avg_view_s": None, "subs_gained": subs}


VIDEOS = [
    video("A", "ball_grow", 14000, 90.0, 20),
    video("B", "ball_grow", 2000, 80.0, 1),
    video("C", "ring_escape", 5000, 100.0, 2),
    video("D", "ring_escape", 10, None, None, published="2026-11-18T15:00:00Z"),
    video("E", "plinko", 300, 110.0, 0),
]


def weekly(**kw):
    args = dict(daily=parse_channel_csv(CSV), videos=VIDEOS, today="2026-11-23",
                unmerged_branches=[])
    args.update(kw)
    return build_weekly(**args)


def test_parse_channel_csv_reads_ints_in_date_order():
    rows = parse_channel_csv(CSV)
    assert rows[0] == {"date": "2026-11-10", "subscribers": 1, "views": 1000, "videos": 5}
    assert [r["date"] for r in rows] == sorted(r["date"] for r in rows)


def test_channel_numbers_compare_with_the_row_seven_days_before_latest():
    w = weekly()
    assert w["data_date"] == "2026-11-19"
    assert w["subscribers"] == 40
    # 7 days before 11-19 is 11-12 -> 5 subscribers, 3000 views
    assert w["subs_change"] == 35
    assert w["views_change"] == 49697
    assert w["compare_date"] == "2026-11-12"


def test_compare_falls_back_to_first_row_when_history_is_short():
    rows = parse_channel_csv("date,subscribers,views,videos\n2026-11-17,27,100,1\n2026-11-19,40,300,2\n")
    w = weekly(daily=rows)
    assert w["compare_date"] == "2026-11-17"
    assert w["subs_change"] == 13


def test_stale_data_is_flagged():
    assert weekly(today="2026-11-20")["stale_days"] == 0
    # daily writes a row each day, so data from yesterday is normal (0)
    assert weekly(today="2026-11-23")["stale_days"] == 3


def test_monetization_progress_uses_views_over_the_last_90_days():
    m = weekly()["monetization"]
    assert m["subs"] == 40 and m["subs_target"] == 1000
    # all history is inside 90 days: views since the first row
    assert m["views_90d"] == 52697 - 1000
    assert m["views_90d_target"] == 10_000_000


def test_income_goals_show_monthly_views_needed():
    inc = weekly()["income"]
    # 30-day window covers the whole history (9 days) -> scaled to 30 days
    assert inc["window_days"] == 9
    assert inc["monthly_views"] == round((52697 - 1000) * 30 / 9)
    goals = {g["yen"]: g for g in inc["goals"]}
    assert set(goals) == {30000, 50000}
    lo, hi = goals[30000]["views_needed"]
    assert lo < hi  # range from an assumed RPM band
    assert 0 < goals[30000]["progress_pct"] < 100


def test_formats_are_ranked_by_average_views_per_video():
    rows = weekly()["formats"]
    assert [r["format"] for r in rows] == ["ball_grow", "ring_escape", "plinko"]
    bg = rows[0]
    assert bg["videos"] == 2 and bg["views"] == 16000 and bg["avg_views"] == 8000
    assert bg["avg_view_pct"] == 85.0 and bg["subs_gained"] == 21
    ring = rows[1]
    assert ring["avg_view_pct"] == 100.0  # missing retention is ignored, not counted as 0


def test_top_and_bottom_skip_videos_younger_than_two_days():
    w = weekly()
    assert [v["id"] for v in w["top"]] == ["A", "C", "B"]
    assert "D" not in [v["id"] for v in w["bottom"]]  # published 1 day before data date
    assert w["bottom"][0]["id"] == "E"


def test_unmerged_branches_create_an_owner_action():
    w = weekly(unmerged_branches=["claude/weekly-2026-11-16"])
    assert w["unmerged_branches"] == ["claude/weekly-2026-11-16"]
    assert any("weekly-2026-11-16" in a for a in w["owner_actions"])


def test_no_owner_action_when_everything_is_merged_and_fresh():
    assert weekly(today="2026-11-20")["owner_actions"] == []


def test_renders_include_numbers_links_and_notes():
    w = weekly(unmerged_branches=["claude/weekly-2026-11-16"])
    notes = {"conclusion": ["ball_grow が最強"], "done": ["swarm を追加"], "next": ["比較する"],
             "branch": "claude/weekly-2026-11-23"}
    html = render_html(w, notes, repo="shuhei0916/auto-short")
    text = render_text(w, notes, repo="shuhei0916/auto-short")
    for out in (html, text):
        assert "ball_grow が最強" in out and "swarm を追加" in out and "比較する" in out
        assert "40" in out and "+35" in out
        assert "https://youtube.com/shorts/A" in out
        assert "compare/main...claude/weekly-2026-11-23" in out
        assert "compare/main...claude/weekly-2026-11-16" in out
        assert "3万円" in out and "5万円" in out
    assert "<table" in html
    assert "<script" not in html


def test_html_escapes_titles_and_notes():
    vids = [video("X", "plinko", 999, 90.0, 0)]
    vids[0]["title"] = "<b>bad</b>"
    w = weekly(videos=vids)
    html = render_html(w, {"conclusion": ["a < b"]}, repo="o/r")
    assert "<b>bad</b>" not in html and "&lt;b&gt;bad" in html
    assert "a &lt; b" in html
