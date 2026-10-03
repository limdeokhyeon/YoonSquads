from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from .agent import run_due
from .config import Config
from .content import generate_draft
from .instagram import InstagramClient
from .queue import Queue

KST = timezone(timedelta(hours=9))


def parse_when(s: str) -> datetime:
    """'2026-10-05 18:30' 형식은 한국시간(KST)으로 해석."""
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=KST)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="insta-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("draft", help="Claude로 캡션 초안 생성")
    g.add_argument("topic")
    g.add_argument("--extra", default="")

    s = sub.add_parser("schedule", help="초안 생성 후 예약 등록")
    s.add_argument("topic")
    s.add_argument("--images", nargs="+", required=True, help="공개 이미지 URL (2장 이상이면 캐러셀)")
    s.add_argument("--at", required=True, help="예약 시각 (예: '2026-10-05 18:30', KST)")
    s.add_argument("--extra", default="")

    r = sub.add_parser("run", help="발행 시각이 된 게시물 발행")
    r.add_argument("--dry-run", action="store_true")

    sub.add_parser("list", help="큐 조회")
    sub.add_parser("ig-whoami", help="인스타 토큰이 유효한지, 어느 계정인지 확인")
    sub.add_parser("ig-refresh", help="인스타 장기 토큰 연장 후 .env에 저장")
    sub.add_parser("serve", help="텔레그램 봇 상시 실행 (뉴스 수집·승인·예약발행)")

    args = p.parse_args(argv)
    cfg = Config.load()

    if args.cmd == "draft":
        print(generate_draft(cfg, args.topic, args.extra).full_text())
    elif args.cmd == "schedule":
        draft = generate_draft(cfg, args.topic, args.extra)
        pid = Queue(cfg.db_path).add(draft.full_text(), args.images, parse_when(args.at))
        print(f"예약 완료 #{pid}\n\n{draft.full_text()}")
    elif args.cmd == "run":
        for pid, result in run_due(Queue(cfg.db_path), InstagramClient(cfg), args.dry_run):
            print(f"#{pid}: {result}")
    elif args.cmd == "ig-whoami":
        info = InstagramClient(cfg).whoami()
        print("연결 성공:", info)
    elif args.cmd == "ig-refresh":
        from .config import update_env
        token, expires = InstagramClient(cfg).refresh_token()
        update_env("IG_ACCESS_TOKEN", token)
        print(f"갱신 완료 (유효 {expires // 86400}일). .env에 저장했습니다.")
    elif args.cmd == "serve":
        from .bot import serve
        serve(cfg)
    elif args.cmd == "list":
        for post in Queue(cfg.db_path).list():
            when = post.scheduled_at.astimezone(KST).strftime("%Y-%m-%d %H:%M")
            print(f"#{post.id} [{post.status}] {when} 이미지 {len(post.image_urls)}장 | {post.caption[:30]!r}")


if __name__ == "__main__":
    main()
