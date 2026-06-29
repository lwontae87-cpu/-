#!/usr/bin/env python3
"""YouTube 분석 결과를 Phase 2.5 UX 대시보드 HTML로 변환합니다.

사용 예시:
    python youtube_phase_2_5_dashboard.py --input youtube_results.json --output youtube_dashboard.html

.env.local이나 API 키는 읽거나 출력하지 않습니다. 이미 수집된 YouTube 결과 JSON만 사용합니다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import re
from pathlib import Path
from typing import Any

NUMBER_KEYS = {
    "views",
    "likes",
    "comments",
    "subscribers",
    "performance",
    "early_reaction",
}
TITLE_WORD_RE = re.compile(r"[0-9A-Za-z가-힣+#./-]{2,}")
MOCK_IMAGE_HINTS = ("rick", "astley", "never-gonna", "mock", "placeholder")
YOUTUBE_THUMBNAIL_HINTS = (
    "i.ytimg.com",
    "img.youtube.com",
    "yt3.ggpht.com",
    "googleusercontent.com",
)


def parse_number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        if math.isnan(value):
            return 0.0
        return float(value)
    cleaned = re.sub(r"[^0-9.-]", "", str(value))
    if cleaned in {"", "-", "."}:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def first_value(row: dict[str, Any], *keys: str, default: Any = "") -> Any:
    lowered = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
        lower_key = key.lower()
        if lower_key in lowered and lowered[lower_key] not in (None, ""):
            return lowered[lower_key]
    return default


def parse_date(value: Any) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else text


def detect_short(row: dict[str, Any], title: str, duration: str) -> bool:
    raw = first_value(row, "is_short", "isShort", "shorts", "is_shorts", default=None)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.strip().lower() in {"true", "yes", "y", "1", "shorts", "short"}:
        return True
    text = f"{title} {duration}".lower()
    return "#shorts" in text or "shorts" in text


def normalize_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("videos", "items", "results", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ValueError("JSON 최상위 값은 list이거나 videos/items/results/data 배열을 포함해야 합니다.")

    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            continue
        title = str(first_value(raw, "title", "video_title", "Video", default=f"Untitled #{idx}")).strip()
        duration = str(first_value(raw, "duration", "length", default="")).strip()
        source = str(first_value(raw, "source", default="youtube")).strip().lower() or "youtube"
        thumbnail_url = str(
            first_value(raw, "thumbnail_url", "thumbnail", "thumbnailUrl", "image", "image_url", default="")
        ).strip()

        row = {
            "rank": idx,
            "title": title,
            "channel": str(first_value(raw, "channel", "channel_title", "Channel", default="")).strip(),
            "upload_date": parse_date(first_value(raw, "upload_date", "published_at", "publishedAt", "date", "Date")),
            "views": parse_number(first_value(raw, "views", "view_count", "Views")),
            "likes": parse_number(first_value(raw, "likes", "like_count", "Likes")),
            "comments": parse_number(first_value(raw, "comments", "comment_count", "Comments")),
            "subscribers": parse_number(first_value(raw, "subscribers", "subscriber_count", "Subscribers")),
            "performance": parse_number(first_value(raw, "performance", "Performance")),
            "early_reaction": parse_number(first_value(raw, "early_reaction", "earlyReaction", "Early Reaction")),
            "duration": duration,
            "is_short": detect_short(raw, title, duration),
            "source": source,
            "thumbnail_url": thumbnail_url,
            "url": str(first_value(raw, "url", "video_url", "link", default="")).strip(),
        }
        rows.append(row)
    return rows


def safe_thumbnail(row: dict[str, Any]) -> str:
    url = str(row.get("thumbnail_url") or "").strip()
    if not url:
        return ""
    lower = url.lower()
    if any(hint in lower for hint in MOCK_IMAGE_HINTS):
        return ""
    if row.get("source") == "youtube":
        if not lower.startswith(("http://", "https://")):
            return ""
        if not any(hint in lower for hint in YOUTUBE_THUMBNAIL_HINTS):
            return ""
    return url


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    best_performance = max(rows, key=lambda r: r.get("performance", 0))
    best_early = max(rows, key=lambda r: r.get("early_reaction", 0))
    best_efficiency = max(
        rows,
        key=lambda r: (r.get("views", 0) / r.get("subscribers", 1)) if r.get("subscribers", 0) else 0,
    )
    shorts_count = sum(1 for r in rows if r.get("is_short"))
    total = len(rows)
    return {
        "best_performance": best_performance,
        "best_early": best_early,
        "best_efficiency": best_efficiency,
        "shorts_ratio": round(shorts_count / total * 100, 1),
        "longform_ratio": round((total - shorts_count) / total * 100, 1),
        "total": total,
    }


def generate_ideas(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, str]]:
    sorted_rows = sorted(rows, key=lambda r: (r.get("performance", 0), r.get("early_reaction", 0)), reverse=True)
    ideas: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in sorted_rows:
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        words = [w for w in TITLE_WORD_RE.findall(title) if len(w) >= 2]
        core = " ".join(words[:6]) or title
        is_short = bool(row.get("is_short"))
        performance = row.get("performance", 0)
        early = row.get("early_reaction", 0)
        if is_short or early >= performance:
            fmt = "Shorts"
            idea = f"{core} 핵심만 20초 안에 보여주기"
            reason = "초반 반응이 강하거나 숏폼 패턴이라 짧은 훅 중심 재가공에 적합합니다."
        elif performance >= 50:
            fmt = "YouTube"
            idea = f"{core} 실제 테스트와 비교 영상으로 확장"
            reason = "성과 지표가 높아 긴 영상에서 사례·비교·검증 구조로 확장할 가치가 있습니다."
        else:
            fmt = "Blog"
            idea = f"{core} 검색 의도형 정리 글 작성"
            reason = "제목 키워드가 검색형 콘텐츠로 전환하기 좋아 블로그 유입용으로 적합합니다."
        dedupe_key = idea.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        ideas.append({"idea": idea, "format": fmt, "reason": reason, "source_title": title})
        if len(ideas) >= limit:
            break
    return ideas


def render_dashboard(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        row["safe_thumbnail_url"] = safe_thumbnail(row)
    summary = build_summary(rows)
    ideas = generate_ideas(rows)
    data_json = json.dumps({"rows": rows, "summary": summary, "ideas": ideas}, ensure_ascii=False)
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>YouTube Phase 2.5 UX Dashboard</title>
  <style>
    :root {{ color-scheme: light; --bg:#f5f7fb; --card:#ffffff; --text:#151922; --muted:#667085; --line:#e6e8ef; --accent:#2563eb; --warn:#f59e0b; --mock:#7c3aed; --youtube:#ef4444; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); }}
    header {{ padding:32px 28px 18px; }}
    h1 {{ margin:0 0 8px; font-size:28px; letter-spacing:-0.03em; }}
    p {{ margin:0; color:var(--muted); }}
    main {{ padding:0 28px 40px; }}
    .cards {{ display:grid; grid-template-columns:repeat(5,minmax(150px,1fr)); gap:14px; margin:18px 0; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:18px; padding:16px; box-shadow:0 10px 30px rgba(15,23,42,.04); }}
    .label {{ color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }}
    .value {{ margin-top:9px; font-size:22px; font-weight:800; letter-spacing:-.02em; }}
    .sub {{ margin-top:7px; color:var(--muted); font-size:13px; line-height:1.35; }}
    .toolbar {{ display:flex; justify-content:space-between; align-items:center; gap:12px; margin:22px 0 12px; flex-wrap:wrap; }}
    .btns {{ display:flex; gap:8px; flex-wrap:wrap; }}
    button {{ border:1px solid var(--line); background:#fff; border-radius:999px; padding:9px 13px; font-weight:700; cursor:pointer; }}
    button.active {{ background:var(--text); color:#fff; border-color:var(--text); }}
    .panel {{ background:var(--card); border:1px solid var(--line); border-radius:20px; overflow:hidden; box-shadow:0 10px 30px rgba(15,23,42,.04); }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ padding:13px 14px; border-bottom:1px solid var(--line); text-align:left; vertical-align:middle; }}
    th {{ font-size:12px; color:var(--muted); background:#fafbff; position:sticky; top:0; z-index:1; }}
    tr:hover {{ background:#fbfdff; }}
    .video {{ display:flex; gap:12px; align-items:center; min-width:320px; }}
    .thumb {{ width:96px; height:54px; border-radius:10px; background:linear-gradient(135deg,#e5e7eb,#f8fafc); object-fit:cover; flex:none; border:1px solid var(--line); }}
    .title {{ font-weight:800; line-height:1.35; }}
    .meta {{ color:var(--muted); font-size:12px; margin-top:4px; }}
    .badge {{ display:inline-flex; align-items:center; gap:4px; border-radius:999px; padding:5px 8px; font-size:12px; font-weight:800; white-space:nowrap; }}
    .badge.youtube {{ background:#fee2e2; color:#991b1b; }}
    .badge.mock {{ background:#ede9fe; color:#4c1d95; }}
    .badge.short {{ background:#dcfce7; color:#166534; }}
    .badge.long {{ background:#e0f2fe; color:#075985; }}
    .badge.warn {{ background:#fef3c7; color:#92400e; margin-left:6px; }}
    .num {{ font-variant-numeric:tabular-nums; font-weight:750; }}
    .ideas {{ display:grid; grid-template-columns:repeat(2,minmax(260px,1fr)); gap:14px; margin-top:14px; }}
    .idea {{ background:#fff; border:1px solid var(--line); border-radius:16px; padding:15px; }}
    .idea h3 {{ margin:8px 0; font-size:16px; line-height:1.35; }}
    .format {{ display:inline-block; border-radius:999px; padding:5px 9px; background:#eef2ff; color:#3730a3; font-size:12px; font-weight:800; }}
    .source-title {{ color:var(--muted); font-size:12px; margin-top:10px; }}
    @media (max-width:1100px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} .ideas {{ grid-template-columns:1fr; }} }}
    @media (max-width:760px) {{ header, main {{ padding-left:16px; padding-right:16px; }} .cards {{ grid-template-columns:1fr; }} .panel {{ overflow-x:auto; }} }}
  </style>
</head>
<body>
  <header>
    <h1>YouTube 분석 대시보드 · Phase 2.5</h1>
    <p>생성 시각: {html.escape(generated_at)} · Performance 기본 내림차순 · API 키 비표시</p>
  </header>
  <main>
    <section class=\"cards\" id=\"summaryCards\"></section>

    <section class=\"toolbar\">
      <div>
        <h2 style=\"margin:0 0 6px;font-size:20px\">영상 결과</h2>
        <p>source, Shorts 여부, 미래 날짜 경고를 한눈에 확인합니다.</p>
      </div>
      <div class=\"btns\">
        <button id=\"sortPerformance\" class=\"active\">Performance순</button>
        <button id=\"sortEarly\">Early Reaction순</button>
      </div>
    </section>

    <section class=\"panel\">
      <table>
        <thead>
          <tr>
            <th>영상</th><th>Source</th><th>형식</th><th>업로드</th><th>조회수</th><th>구독자</th><th>Performance</th><th>Early Reaction</th>
          </tr>
        </thead>
        <tbody id=\"videoRows\"></tbody>
      </table>
    </section>

    <section class=\"toolbar\" style=\"margin-top:30px\">
      <div>
        <h2 style=\"margin:0 0 6px;font-size:20px\">추천 아이디어 10개</h2>
        <p>실제 검색 결과 제목을 기반으로 포맷과 추천 이유를 붙였습니다.</p>
      </div>
    </section>
    <section class=\"ideas\" id=\"ideas\"></section>
  </main>

  <script>
    const dashboard = {data_json};
    let currentSort = 'performance';

    const fmtNum = (value) => new Intl.NumberFormat('ko-KR', {{ maximumFractionDigits: 1 }}).format(value || 0);
    const shortTitle = (title) => title && title.length > 46 ? title.slice(0, 46) + '…' : title;
    const isFutureDate = (dateText) => {{
      if (!dateText) return false;
      const date = new Date(dateText + 'T00:00:00');
      if (Number.isNaN(date.getTime())) return false;
      const today = new Date();
      today.setHours(0,0,0,0);
      return date > today;
    }};

    function sourceBadge(source) {{
      const isYoutube = source === 'youtube';
      return `<span class=\"badge ${{isYoutube ? 'youtube' : 'mock'}}\">${{isYoutube ? 'YOUTUBE' : 'MOCK'}}</span>`;
    }}

    function formatBadge(row) {{
      return `<span class=\"badge ${{row.is_short ? 'short' : 'long'}}\">${{row.is_short ? 'Shorts' : 'Longform'}}</span>`;
    }}

    function renderSummary() {{
      const s = dashboard.summary || {{}};
      const cards = [
        ['최고 성과 영상', shortTitle(s.best_performance?.title || '-'), `Performance ${{fmtNum(s.best_performance?.performance)}}`],
        ['가장 빠른 초반 반응', shortTitle(s.best_early?.title || '-'), `Early Reaction ${{fmtNum(s.best_early?.early_reaction)}}`],
        ['구독자 대비 조회수', shortTitle(s.best_efficiency?.title || '-'), `${{fmtNum((s.best_efficiency?.views || 0) / Math.max(s.best_efficiency?.subscribers || 1, 1))}}배`],
        ['숏폼 비율', `${{fmtNum(s.shorts_ratio)}}%`, `총 ${{s.total || 0}}개 중 Shorts`],
        ['롱폼 비율', `${{fmtNum(s.longform_ratio)}}%`, `총 ${{s.total || 0}}개 중 Longform`],
      ];
      document.getElementById('summaryCards').innerHTML = cards.map(([label, value, sub]) => `
        <article class=\"card\"><div class=\"label\">${{label}}</div><div class=\"value\">${{value}}</div><div class=\"sub\">${{sub}}</div></article>
      `).join('');
    }}

    function renderRows() {{
      const rows = [...dashboard.rows].sort((a,b) => (b[currentSort] || 0) - (a[currentSort] || 0));
      document.getElementById('videoRows').innerHTML = rows.map(row => {{
        const future = isFutureDate(row.upload_date);
        const thumb = row.safe_thumbnail_url
          ? `<img class=\"thumb\" src=\"${{row.safe_thumbnail_url}}\" alt=\"thumbnail\" loading=\"lazy\" />`
          : `<div class=\"thumb\" aria-label=\"thumbnail removed\"></div>`;
        const linkedTitle = row.url ? `<a href=\"${{row.url}}\" target=\"_blank\" rel=\"noreferrer\">${{row.title}}</a>` : row.title;
        return `<tr>
          <td><div class=\"video\">${{thumb}}<div><div class=\"title\">${{linkedTitle}}</div><div class=\"meta\">${{row.channel || '채널 정보 없음'}}</div></div></div></td>
          <td>${{sourceBadge(row.source)}}</td>
          <td>${{formatBadge(row)}}</td>
          <td>${{row.upload_date || '-'}}${{future ? '<span class=\"badge warn\">미래 날짜 의심</span>' : ''}}</td>
          <td class=\"num\">${{fmtNum(row.views)}}</td>
          <td class=\"num\">${{fmtNum(row.subscribers)}}</td>
          <td class=\"num\">${{fmtNum(row.performance)}}</td>
          <td class=\"num\">${{fmtNum(row.early_reaction)}}</td>
        </tr>`;
      }}).join('');
    }}

    function renderIdeas() {{
      document.getElementById('ideas').innerHTML = dashboard.ideas.map((item, index) => `
        <article class=\"idea\">
          <span class=\"format\">${{item.format}}</span>
          <h3>${{index + 1}}. ${{item.idea}}</h3>
          <p>${{item.reason}}</p>
          <div class=\"source-title\">기반 제목: ${{item.source_title}}</div>
        </article>
      `).join('');
    }}

    document.getElementById('sortPerformance').addEventListener('click', () => {{
      currentSort = 'performance';
      document.getElementById('sortPerformance').classList.add('active');
      document.getElementById('sortEarly').classList.remove('active');
      renderRows();
    }});
    document.getElementById('sortEarly').addEventListener('click', () => {{
      currentSort = 'early_reaction';
      document.getElementById('sortEarly').classList.add('active');
      document.getElementById('sortPerformance').classList.remove('active');
      renderRows();
    }});

    renderSummary();
    renderRows();
    renderIdeas();
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YouTube Phase 2.5 UX 대시보드 생성기")
    parser.add_argument("--input", required=True, help="YouTube 검색 결과 JSON 파일")
    parser.add_argument("--output", default="youtube_dashboard.html", help="생성할 HTML 파일")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = normalize_rows(payload)
    output = render_dashboard(rows)
    Path(args.output).write_text(output, encoding="utf-8")
    print(f"Phase 2.5 dashboard written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
