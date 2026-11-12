"""Collects per-video performance into analytics/latest.json (read by the weekly routine)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .schedule import HISTORY_DIR

ANALYTICS_DIR = Path("analytics")


def build_report(metas: list[dict], stats: dict, retention: dict, today: str, channel: dict | None = None) -> dict:
    videos = []
    for m in metas:
        up = m.get("uploaded")
        if not up:
            continue
        vid = up["id"]
        s = stats.get(vid, {})
        r = retention.get(vid, {})
        videos.append({
            "id": vid,
            "seed": m["seed"],
            "format": m["format"],
            "title": m["title"],
            "published": up.get("publish_at") or up["at"],
            "url": f"https://youtube.com/shorts/{vid}",
            "views": s.get("views", 0),
            "likes": s.get("likes", 0),
            "comments": s.get("comments", 0),
            "avg_view_pct": r.get("avg_view_pct"),
            "avg_view_s": r.get("avg_view_s"),
            "subs_gained": r.get("subs_gained"),
        })
    videos.sort(key=lambda v: dt.datetime.fromisoformat(v["published"].replace("Z", "+00:00")))

    by_format: dict[str, dict] = {}
    for fmt in dict.fromkeys(v["format"] for v in videos):
        rows = [v for v in videos if v["format"] == fmt]
        rated = [v for v in rows if v["avg_view_pct"] is not None and v["views"]]
        weight = sum(v["views"] for v in rated)
        by_format[fmt] = {
            "videos": len(rows),
            "views": sum(v["views"] for v in rows),
            "avg_view_pct": round(sum(v["avg_view_pct"] * v["views"] for v in rated) / weight, 1) if weight else None,
            "subs_gained": sum(v["subs_gained"] or 0 for v in rows),
        }
    return {"generated": today, "channel": channel, "videos": videos, "by_format": by_format}


CSV_HEADER = "date,subscribers,views,videos"


def upsert_daily(csv_text: str, date: str, subscribers: int, views: int, videos: int) -> str:
    rows = [r for r in csv_text.splitlines()[1:] if r and not r.startswith(date + ",")]
    rows.append(f"{date},{subscribers},{views},{videos}")
    return "\n".join([CSV_HEADER, *sorted(rows)]) + "\n"


def _fetch_channel(youtube) -> dict:
    st = youtube.channels().list(part="statistics", mine=True).execute()["items"][0]["statistics"]
    return {"subscribers": int(st.get("subscriberCount", 0)), "views": int(st.get("viewCount", 0))}


def _fetch_stats(youtube, ids: list[str]) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        resp = youtube.videos().list(part="statistics", id=",".join(ids[i : i + 50])).execute()
        for item in resp.get("items", []):
            st = item["statistics"]
            out[item["id"]] = {name: int(st.get(key, 0)) for name, key in
                               (("views", "viewCount"), ("likes", "likeCount"), ("comments", "commentCount"))}
    return out


def _fetch_retention(analytics, start: str, end: str) -> dict:
    resp = analytics.reports().query(
        ids="channel==MINE", startDate=start, endDate=end, dimensions="video",
        metrics="views,averageViewDuration,averageViewPercentage,subscribersGained",
        sort="-views", maxResults=200,
    ).execute()
    cols = [h["name"] for h in resp.get("columnHeaders", [])]
    out = {}
    for row in resp.get("rows", []):
        r = dict(zip(cols, row))
        out[r["video"]] = {"avg_view_pct": round(float(r["averageViewPercentage"]), 1),
                           "avg_view_s": round(float(r["averageViewDuration"]), 1),
                           "subs_gained": int(r["subscribersGained"])}
    return out


def collect(history: Path = HISTORY_DIR, out_dir: Path = ANALYTICS_DIR) -> Path:
    from .upload import _analytics_service, _service

    metas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(history.glob("*.json"))]
    ids = [m["uploaded"]["id"] for m in metas if m.get("uploaded")]
    today = dt.date.today().isoformat()
    youtube = _service()
    stats = _fetch_stats(youtube, ids)
    channel = _fetch_channel(youtube)
    retention = _fetch_retention(_analytics_service(), "2026-11-01", today)
    report = build_report(metas, stats, retention, today, channel)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "latest.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    daily = out_dir / "channel_daily.csv"
    old = daily.read_text(encoding="utf-8") if daily.exists() else ""
    daily.write_text(upsert_daily(old, today, channel["subscribers"], channel["views"], len(ids)), encoding="utf-8")
    print(f"{path}: {len(report['videos'])} videos, {channel['subscribers']} subscribers")
    return path
