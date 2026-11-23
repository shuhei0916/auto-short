"""Weekly report: numbers are computed here, the weekly routine only adds notes.

`python -m autoshort weekly --notes notes.json` writes an HTML email body and a
plain-text fallback, so every week has the same layout and the numbers are
never computed by hand.
"""
from __future__ import annotations

import csv
import html
import io
import json
import subprocess
from datetime import date, timedelta
from pathlib import Path

ANALYTICS_DIR = Path("analytics")

# YouTube Partner Program (Shorts route): 1,000 subscribers and
# 10M public Shorts views in the last 90 days.
YPP_SUBS = 1000
YPP_VIEWS_90D = 10_000_000
# Assumed Shorts revenue per 1,000 views (yen). A rough band for a global,
# non-verbal channel; replace with real numbers once monetized.
RPM_YEN = (5, 10)
INCOME_GOALS_YEN = (30000, 50000)
MIN_AGE_DAYS = 2  # younger videos are left out of top/bottom lists
STALE_AFTER_DAYS = 2


def parse_channel_csv(text: str) -> list[dict]:
    rows = [{"date": r["date"], "subscribers": int(r["subscribers"]),
             "views": int(r["views"]), "videos": int(r["videos"])}
            for r in csv.DictReader(io.StringIO(text))]
    return sorted(rows, key=lambda r: r["date"])


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def _base_row(rows: list[dict], days: int) -> dict:
    """Latest row at least `days` before the newest row, else the first row."""
    cutoff = _d(rows[-1]["date"]) - timedelta(days=days)
    older = [r for r in rows if _d(r["date"]) <= cutoff]
    return older[-1] if older else rows[0]


def _format_rows(videos: list[dict]) -> list[dict]:
    by: dict[str, list[dict]] = {}
    for v in videos:
        by.setdefault(v["format"], []).append(v)
    rows = []
    for fmt, vs in by.items():
        views = sum(v["views"] or 0 for v in vs)
        pcts = [v["avg_view_pct"] for v in vs if v.get("avg_view_pct") is not None]
        rows.append({
            "format": fmt,
            "videos": len(vs),
            "views": views,
            "avg_views": round(views / len(vs)),
            "avg_view_pct": round(sum(pcts) / len(pcts), 1) if pcts else None,
            "subs_gained": sum(v.get("subs_gained") or 0 for v in vs),
        })
    return sorted(rows, key=lambda r: -r["avg_views"])


def build_weekly(daily: list[dict], videos: list[dict], today: str,
                 unmerged_branches: list[str]) -> dict:
    latest = daily[-1]
    data_date = _d(latest["date"])
    week = _base_row(daily, 7)
    b90 = _base_row(daily, 90)
    b30 = _base_row(daily, 30)
    stale_days = max(0, (_d(today) - data_date).days - 1)

    window = max(1, (data_date - _d(b30["date"])).days)
    monthly = round((latest["views"] - b30["views"]) * 30 / window)
    goals = []
    for yen in INCOME_GOALS_YEN:
        need = (yen * 1000 // RPM_YEN[1], yen * 1000 // RPM_YEN[0])
        goals.append({"yen": yen, "views_needed": need,
                      "progress_pct": round(100 * monthly / need[1], 1)})

    eligible = [v for v in videos
                if (data_date - _d(v["published"])).days >= MIN_AGE_DAYS]
    by_views = sorted(eligible, key=lambda v: -(v["views"] or 0))

    actions = []
    if stale_days >= STALE_AFTER_DAYS:
        actions.append(f"analytics が {stale_days} 日更新されていません（最新 {latest['date']}）。"
                       "GitHub Actions の daily が失敗していないか確認してください")
    for b in unmerged_branches:
        actions.append(f"未マージのブランチ {b} をレビュー")

    return {
        "today": today,
        "data_date": latest["date"],
        "stale_days": stale_days,
        "subscribers": latest["subscribers"],
        "total_views": latest["views"],
        "compare_date": week["date"],
        "subs_change": latest["subscribers"] - week["subscribers"],
        "views_change": latest["views"] - week["views"],
        "videos_change": latest["videos"] - week["videos"],
        "monetization": {
            "subs": latest["subscribers"], "subs_target": YPP_SUBS,
            "views_90d": latest["views"] - b90["views"], "views_90d_target": YPP_VIEWS_90D,
        },
        "income": {"window_days": window, "monthly_views": monthly, "rpm_yen": RPM_YEN,
                   "goals": goals},
        "formats": _format_rows(videos),
        "top": by_views[:3],
        "bottom": list(reversed(by_views[-3:])) if len(by_views) > 3 else [],
        "unmerged_branches": list(unmerged_branches),
        "owner_actions": actions,
    }


# ---------- rendering ----------

def _n(x) -> str:
    return "-" if x is None else f"{x:,}"


def _signed(x: int) -> str:
    return f"+{x:,}" if x >= 0 else f"{x:,}"


def _pct(x) -> str:
    return "-" if x is None else f"{x:.1f}%"


def _man(yen: int) -> str:
    return f"{yen // 10000}万円"


def _compare_url(repo: str, branch: str) -> str:
    return f"https://github.com/{repo}/compare/main...{branch}?expand=1"


def _review_branches(w: dict, notes: dict) -> list[str]:
    out = [notes["branch"]] if notes.get("branch") else []
    return out + [b for b in w["unmerged_branches"] if b not in out]


def _short_title(v: dict) -> str:
    return v["title"].replace(" #shorts", "")


def render_text(w: dict, notes: dict, repo: str) -> str:
    m, inc = w["monetization"], w["income"]
    L = [f"■ 今週の結論（データ {w['data_date']} 時点）"]
    L += [f"・{c}" for c in notes.get("conclusion", [])]
    L += ["", "■ あなたの作業"]
    reviews = _review_branches(w, notes)
    for b in reviews:
        L.append(f"・レビュー: {b}\n  {_compare_url(repo, b)}")
    if reviews:
        L.append("  PR を作成 → CI の Artifacts の preview 動画を確認 → 問題なければ Merge")
    L += [f"・{a}" for a in w["owner_actions"] if not a.startswith("未マージ")]
    if not reviews and not w["owner_actions"]:
        L.append("・なし")
    L += ["", "■ 目標までの進捗",
          f"・収益化条件: 登録者 {_n(m['subs'])} / {_n(m['subs_target'])}人、"
          f"90日再生 {_n(m['views_90d'])} / {_n(m['views_90d_target'])}回"]
    for g in inc["goals"]:
        lo, hi = g["views_needed"]
        L.append(f"・月{_man(g['yen'])}: 月間再生 {_n(inc['monthly_views'])} / 必要 {_n(lo)}〜{_n(hi)}回"
                 f"（{g['progress_pct']}%）")
    L += ["", f"■ 数字（{w['compare_date']} 比）",
          f"・登録者 {_n(w['subscribers'])}（{_signed(w['subs_change'])}）",
          f"・総再生 {_n(w['total_views'])}（{_signed(w['views_change'])}）",
          f"・動画数 +{w['videos_change']}本",
          "", "■ フォーマット別（1本あたり再生の多い順）"]
    for r in w["formats"]:
        L.append(f"・{r['format']}: {r['videos']}本 / 平均 {_n(r['avg_views'])}回 / "
                 f"視聴率 {_pct(r['avg_view_pct'])} / 登録 +{r['subs_gained']}")
    L += ["", "■ 伸びた動画"]
    L += [f"・{_n(v['views'])}回 {_short_title(v)} {v['url']}" for v in w["top"]]
    if w["bottom"]:
        L += ["", "■ 伸びなかった動画"]
        L += [f"・{_n(v['views'])}回 {_short_title(v)} {v['url']}" for v in w["bottom"]]
    for key, head in (("done", "今週やったこと"), ("next", "来週やること")):
        if notes.get(key):
            L += ["", f"■ {head}"] + [f"・{x}" for x in notes[key]]
    return "\n".join(L) + "\n"


_S = {
    "body": "font-family:-apple-system,'Hiragino Sans','Noto Sans JP',sans-serif;"
            "color:#1f2328;max-width:640px;margin:0 auto;padding:12px;line-height:1.6;",
    "h2": "font-size:16px;margin:20px 0 6px;padding-bottom:4px;border-bottom:2px solid #d0d7de;",
    "table": "border-collapse:collapse;width:100%;font-size:14px;",
    "th": "text-align:left;padding:6px 8px;background:#f6f8fa;border-bottom:1px solid #d0d7de;",
    "td": "padding:6px 8px;border-bottom:1px solid #eaeef2;",
    "num": "padding:6px 8px;border-bottom:1px solid #eaeef2;text-align:right;white-space:nowrap;",
    "box": "background:#fff8c5;border:1px solid #d4a72c;border-radius:6px;padding:8px 12px;",
    "ok": "background:#dafbe1;border:1px solid #4ac26b;border-radius:6px;padding:8px 12px;",
    "bar_bg": "background:#eaeef2;border-radius:4px;height:8px;width:100%;",
    "muted": "color:#656d76;font-size:12px;",
}


def _e(s) -> str:
    return html.escape(str(s))


def _ul(items: list[str]) -> str:
    return "<ul style='margin:4px 0;padding-left:20px;'>" + \
        "".join(f"<li>{x}</li>" for x in items) + "</ul>"


def _bar(pct: float) -> str:
    p = max(0.0, min(100.0, pct))
    return (f"<div style='{_S['bar_bg']}'><div style='background:#2da44e;border-radius:4px;"
            f"height:8px;width:{max(p, 1):.1f}%;'></div></div>")


def _table(head: list[str], rows: list[list[str]], num_cols: set[int]) -> str:
    h = "".join(f"<th style='{_S['th']}'>{_e(c)}</th>" for c in head)
    body = "".join("<tr>" + "".join(
        f"<td style='{_S['num'] if i in num_cols else _S['td']}'>{c}</td>"
        for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table style='{_S['table']}'><tr>{h}</tr>{body}</table>"


def _video_rows(vs: list[dict]) -> list[list[str]]:
    return [[f"<a href='{_e(v['url'])}'>{_e(_short_title(v))}</a>", _e(v["format"]),
             _n(v["views"]), _pct(v.get("avg_view_pct"))] for v in vs]


def render_html(w: dict, notes: dict, repo: str) -> str:
    m, inc = w["monetization"], w["income"]
    P = [f"<div style=\"{_S['body']}\">"]

    P.append(f"<h2 style='{_S['h2']}'>今週の結論</h2>")
    P.append(_ul([_e(c) for c in notes.get("conclusion", [])]))
    P.append(f"<div style='{_S['muted']}'>データ {_e(w['data_date'])} 時点"
             f"（比較対象 {_e(w['compare_date'])}）</div>")

    P.append(f"<h2 style='{_S['h2']}'>あなたの作業</h2>")
    items = []
    reviews = _review_branches(w, notes)
    for b in reviews:
        items.append(f"レビュー: <a href='{_e(_compare_url(repo, b))}'>{_e(b)}</a>")
    items += [_e(a) for a in w["owner_actions"] if not a.startswith("未マージ")]
    if items:
        tail = ("<div style='font-size:13px;'>PR を作成 → CI の Artifacts の preview 動画を確認 → "
                "問題なければ Merge</div>") if reviews else ""
        P.append(f"<div style='{_S['box']}'>{_ul(items)}{tail}</div>")
    else:
        P.append(f"<div style='{_S['ok']}'>なし</div>")

    P.append(f"<h2 style='{_S['h2']}'>目標までの進捗</h2>")
    sub_pct = 100 * m["subs"] / m["subs_target"]
    v_pct = 100 * m["views_90d"] / m["views_90d_target"]
    goals = [
        ("収益化条件: 登録者", f"{_n(m['subs'])} / {_n(m['subs_target'])}人", sub_pct),
        ("収益化条件: 90日の再生", f"{_n(m['views_90d'])} / {_n(m['views_90d_target'])}回", v_pct),
    ]
    for g in inc["goals"]:
        lo, hi = g["views_needed"]
        goals.append((f"月{_man(g['yen'])}: 月間再生", f"{_n(inc['monthly_views'])} / "
                      f"{_n(lo)}〜{_n(hi)}回", g["progress_pct"]))
    for label, value, pct in goals:
        P.append("<div style='margin:8px 0;'>"
                 f"<div style='font-size:14px;'><b>{_e(label)}</b>"
                 f"<span style='float:right;'>{pct:.1f}%</span></div>"
                 f"<div style='font-size:13px;color:#656d76;'>{_e(value)}</div>"
                 f"{_bar(pct)}</div>")
    P.append(f"<div style='{_S['muted']}'>月間再生は直近{min(inc['window_days'], 30)}日から30日換算。"
             f"必要再生は 1,000回あたり {inc['rpm_yen'][0]}〜{inc['rpm_yen'][1]}円 と仮定"
             "（達成率は保守的な方で計算）。収入は収益化条件を満たした後から。</div>")

    P.append(f"<h2 style='{_S['h2']}'>数字（{_e(w['compare_date'])} 比）</h2>")
    P.append(_table(["", "現在", "増減"], [
        ["登録者", _n(w["subscribers"]), _signed(w["subs_change"])],
        ["総再生", _n(w["total_views"]), _signed(w["views_change"])],
        ["公開本数", "", f"+{w['videos_change']}"],
    ], {1, 2}))

    P.append(f"<h2 style='{_S['h2']}'>フォーマット別（1本あたり再生の多い順）</h2>")
    P.append(_table(["フォーマット", "本数", "平均再生", "視聴率", "登録増"], [
        [_e(r["format"]), str(r["videos"]), _n(r["avg_views"]), _pct(r["avg_view_pct"]),
         f"+{r['subs_gained']}"] for r in w["formats"]], {1, 2, 3, 4}))

    P.append(f"<h2 style='{_S['h2']}'>伸びた動画</h2>")
    P.append(_table(["タイトル", "形式", "再生", "視聴率"], _video_rows(w["top"]), {2, 3}))
    if w["bottom"]:
        P.append(f"<h2 style='{_S['h2']}'>伸びなかった動画</h2>")
        P.append(_table(["タイトル", "形式", "再生", "視聴率"], _video_rows(w["bottom"]), {2, 3}))
    P.append(f"<div style='{_S['muted']}'>公開から{MIN_AGE_DAYS}日未満の動画は除外</div>")

    for key, head in (("done", "今週やったこと"), ("next", "来週やること")):
        if notes.get(key):
            P.append(f"<h2 style='{_S['h2']}'>{head}</h2>")
            P.append(_ul([_e(x) for x in notes[key]]))
    P.append("</div>")
    return "\n".join(P) + "\n"


# ---------- CLI ----------

def unmerged_weekly_branches(exclude: str | None = None) -> list[str]:
    out = subprocess.run(["git", "branch", "-r", "--no-merged", "origin/main"],
                         capture_output=True, text=True, check=True).stdout
    names = [b.strip().removeprefix("origin/") for b in out.splitlines()]
    return sorted(b for b in names if b.startswith("claude/weekly-") and b != exclude)


def run(notes_path: Path | None, out_dir: Path, today: str, repo: str) -> tuple[Path, Path]:
    notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path else {}
    daily = parse_channel_csv((ANALYTICS_DIR / "channel_daily.csv").read_text(encoding="utf-8"))
    videos = json.loads((ANALYTICS_DIR / "latest.json").read_text(encoding="utf-8"))["videos"]
    w = build_weekly(daily, videos, today, unmerged_weekly_branches(exclude=notes.get("branch")))
    out_dir.mkdir(parents=True, exist_ok=True)
    h, t = out_dir / "weekly.html", out_dir / "weekly.txt"
    h.write_text(render_html(w, notes, repo), encoding="utf-8")
    t.write_text(render_text(w, notes, repo), encoding="utf-8")
    return h, t
