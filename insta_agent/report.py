"""발행 성과 요약(/report)과, 다음 글을 쓸 때 참고할 반응 좋은/낮은 글 목록."""

from __future__ import annotations

from collections import defaultdict


def _views(row: dict) -> float:
    m = row["metrics"]
    return m.get("views") or m.get("reach") or 0


def performance_hint(rows: list[dict], min_posts: int = 5) -> dict | None:
    """성과가 충분히 쌓였을 때만(기본 5건 이상) 잘 나온 글 3개와 낮았던 글 2개를 돌려준다."""
    rows = [r for r in rows if r["headline"] and _views(r) > 0]
    if len(rows) < min_posts:
        return None
    ranked = sorted(rows, key=_views, reverse=True)
    return {
        "best": [(r["headline"], int(_views(r))) for r in ranked[:3]],
        "worst": [(r["headline"], int(_views(r))) for r in ranked[-2:]],
    }


def build_report(rows: list[dict], days: int = 7) -> str:
    rows = [r for r in rows if r["metrics"]]
    if not rows:
        return "아직 성과가 수집된 글이 없어요. 발행 후 24시간이 지나면 조회·도달·저장·공유를 자동으로 가져옵니다."
    ranked = sorted(rows, key=_views, reverse=True)
    n = len(rows)
    avg = lambda key: sum(r["metrics"].get(key, 0) for r in rows) / n
    lines = [
        f"📊 최근 {days}일 성과 ({n}건)",
        f"평균 조회 {avg('views'):,.0f} · 도달 {avg('reach'):,.0f} · 좋아요 {avg('likes'):,.0f} · 저장 {avg('saved'):,.0f} · 공유 {avg('shares'):,.0f}",
        "",
        "🔥 반응 좋았던 글",
    ]
    for r in ranked[:3]:
        lines.append(f"· {r['headline'][:28]} — 조회 {int(_views(r)):,} / 저장 {int(r['metrics'].get('saved', 0))} / 공유 {int(r['metrics'].get('shares', 0))}")
    if n > 3:
        lines.append("")
        lines.append("🧊 반응 낮았던 글")
        for r in ranked[-2:]:
            lines.append(f"· {r['headline'][:28]} — 조회 {int(_views(r)):,}")
    by_kind = defaultdict(list)
    for r in rows:
        by_kind["속보" if r["kind"] == "breaking" else "일반"].append(_views(r))
    if len(by_kind) == 2:
        lines += ["", "속보 vs 일반 평균 조회: " + " / ".join(f"{k} {sum(v) / len(v):,.0f}" for k, v in by_kind.items())]
    tag_views = defaultdict(list)
    for r in rows:
        for t in r["tags"]:
            tag_views[t].append(_views(r))
    tags = sorted(((sum(v) / len(v), t, len(v)) for t, v in tag_views.items() if len(v) >= 2), reverse=True)[:3]
    if tags:
        lines += ["", "자주 쓴 태그 중 평균 조회가 높은 것: " + ", ".join(f"#{t}({a:,.0f})" for a, t, _ in tags)]
    lines += ["", "※ 표본이 적을 때는 우연일 수 있어요. 글이 쌓일수록 정확해집니다."]
    return "\n".join(lines)
