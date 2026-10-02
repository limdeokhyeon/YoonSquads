# YoonSquads — 인스타그램 자동화 에이전트

Claude가 캡션·해시태그를 만들고, 예약 큐에 넣고, Instagram Graph API로 발행합니다.

## 준비
1. 인스타그램 **비즈니스/크리에이터 계정** + Facebook 페이지 연결, Meta 개발자 앱에서 `instagram_content_publish` 권한의 장기 토큰 발급
2. `cp .env.example .env` 후 `ANTHROPIC_API_KEY`, `IG_USER_ID`, `IG_ACCESS_TOKEN` 입력
3. `pip install -r requirements.txt`

## 사용
```bash
python -m insta_agent.cli draft "가을 제철 과일 소개"
python -m insta_agent.cli schedule "가을 제철 과일 소개" --images https://.../1.jpg --at "2026-10-05 18:30"
python -m insta_agent.cli list
python -m insta_agent.cli run --dry-run   # 발행 대상 확인
python -m insta_agent.cli run             # 실제 발행
```
`--at` 은 한국시간(KST) 기준. 이미지 2장 이상이면 캐러셀로 발행됩니다.

## 자동 실행
`run` 을 5~10분마다 돌리면 예약 발행됩니다. 예: `*/10 * * * * cd /path && python -m insta_agent.cli run`

## 주의
- 이미지는 **공개 URL**이어야 합니다(Graph API 제약). 하루 API 발행 한도(약 50건)가 있습니다.
- 비공식 로그인/스크래핑 방식은 계정 정지 위험이 있어 사용하지 않았습니다.
- `.env`(토큰)는 커밋하지 마세요.

## 테스트
`python -m pytest`
