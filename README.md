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

## 뉴스 → 텔레그램 검토 → 자동 발행
```bash
python -m insta_agent.cli serve
```
상시 실행하면 다음을 처리합니다.
1. 매일 `COLLECT_HOUR`시(KST)에 네이버 뉴스 API로 `NEWS_KEYWORDS` 기사 `DAILY_COUNT`건 수집 (텔레그램 `/collect`로 즉시 수집도 가능)
2. Claude가 제목·검색요약만 보고 카드뉴스 문구와 캡션을 새로 작성 (본문 복사 없음, 출처 링크 자동 첨부)
3. 텔레그램으로 카드 이미지 + 캡션 미리보기 전송 → ✅승인 / 🔄다시 쓰기 / ❌폐기
   - 수정 요청은 `수정 3 더 짧게` 처럼 답장
4. 승인하면 카드를 imgbb에 올려 공개 URL을 만들고 `POST_HOURS` 중 비어 있는 다음 시각에 예약 → 시각이 되면 자동 발행, 결과를 텔레그램으로 알림

본인 chat id(`TELEGRAM_CHAT_ID`)가 아닌 사용자의 메시지·버튼은 무시합니다.
추가 필요 키: `NAVER_CLIENT_ID/SECRET`, `IMGBB_API_KEY` (`.env.example` 참고).
