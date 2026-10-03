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

## 뉴스 → 텔레그램 검토 → 자동 발행 (한 장짜리 뉴스 카드)
```bash
python -m insta_agent.cli serve
```
상시 실행하면 다음을 처리합니다.
1. 매일 `COLLECT_HOUR`시(KST)에 네이버 API HUB 뉴스 검색으로 `NEWS_KEYWORDS`(기본 정치,경제,시사) 기사 `DAILY_COUNT`건 수집 (텔레그램 `/collect`로 즉시 수집도 가능)
2. Claude가 제목·검색요약만 보고 카드뉴스 문구와 캡션을 새로 작성 (본문 복사 없음, 출처 링크 자동 첨부)
3. 텔레그램으로 카드 이미지 + 캡션 미리보기 전송 → ✅승인 / 🔄다시 쓰기 / ❌폐기
   - 수정 요청은 `수정 3 더 짧게` 처럼 답장
4. 승인하면 카드를 imgbb에 올려 공개 URL을 만들고 `POST_HOURS` 중 비어 있는 다음 시각에 예약 → 시각이 되면 자동 발행, 결과를 텔레그램으로 알림

본인 chat id(`TELEGRAM_CHAT_ID`)가 아닌 사용자의 메시지·버튼은 무시합니다.
추가 필요 키: `NAVER_CLIENT_ID/SECRET`(NAVER API HUB의 Client ID/Secret), `IMGBB_API_KEY` (`.env.example` 참고).

## API 키 없이 쓰기 (Claude 구독)
`ANTHROPIC_API_KEY`를 비워 두면 서버에 설치·로그인된 Claude Code(`claude -p`)로 문구를 생성합니다.
`.env`가 있는 프로젝트 폴더가 아닌 빈 임시 폴더에서 실행해 키가 노출되지 않게 했습니다.
구독 사용량 한도를 공유하므로 하루 건수가 많으면 API 키 방식이 안정적입니다.

## 기사 본문 참고 (선택)
`.env`에 `FETCH_BODY=true`를 넣으면 기사 링크를 열어 본문 앞 2,000자를 **사실 파악용으로만** Claude에게 보여 줍니다.
- `robots.txt`가 막은 사이트·접속 실패 시 자동으로 제목·요약만 사용
- 결과물이 원문과 연속 25자 이상 같으면 자동으로 한 번 더 다시 씀
- 본문은 텔레그램·인스타에 올라가지 않으며 로컬 DB(`queue.db`)에만 저장됨
언론사 약관·저작권은 본인 책임이며, 승인 전에 원문 링크로 사실관계를 확인하세요.

## 인스타 토큰 종류와 갱신
- `IGAA...`로 시작(Instagram 로그인): `graph.instagram.com` 사용, `IG_USER_ID`는 비워 둬도 됨(`me`), 60일 토큰을 30일마다 자동 연장 후 `.env`에 저장
- `EAA...`로 시작(Facebook 로그인): `graph.facebook.com` 사용, `IG_USER_ID` 필요, 자동 갱신 없음
- 확인: `python3 -m insta_agent.cli ig-whoami` / 수동 갱신: `python3 -m insta_agent.cli ig-refresh`
- Meta **앱 시크릿은 이 에이전트에 필요 없습니다.** 어디에도 저장하지 마세요.

## 서버 업데이트
서버 맥북에서는 `git pull` 대신 아래를 쓰세요. 로컬 변경 충돌 없이 GitHub 최신 코드로 맞추고 패키지도 설치합니다.
```bash
bash update.sh
```

## 카드 형식
사진 한 장을 꽉 채우고 아래쪽에 `[배지] 작은 문구 / 큰 제목 / 부제 / 출처: 언론사 | 날짜`를 얹은 4:5 한 장 카드입니다.
- 사진은 `AI_IMAGES=true` + `OPENAI_API_KEY`일 때 GPT 이미지로 만들고, 없으면 남색 그라데이션
- 실존 인물 얼굴은 생성하지 않고 연단·마이크·건물 같은 상징 장면으로 대신함, 기사 사진은 쓰지 않음
- AI 배경에는 우측 상단에 `AI 생성 이미지` 표시(`AI_LABEL=false`로 끌 수 있음)
- 캡션에는 핵심 3줄과 출처 링크가 들어갑니다

## 배경 사진 선택 (`PHOTO_SOURCE`)
- `none`: 남색 그라데이션 (기본, 비용·키 없음)
- `ai`: GPT 이미지로 생성 (`OPENAI_API_KEY`, 유료, 카드에 `AI 생성 이미지` 표시)
- `unsplash`: Unsplash 무료 사진 검색 (`UNSPLASH_ACCESS_KEY`, 데모 한도 시간당 50회). 촬영자·Unsplash 출처가 캡션에 자동으로 들어가고 승인(실제 사용) 시 다운로드 집계 호출을 함
검토 때 받은 배경은 승인 때 그대로 재사용합니다(사진이 바뀌거나 비용이 두 번 나가지 않음).

## 캡션·해시태그 중복 방지
- 최근 후보 12개의 해시태그와 캡션 첫 줄을 Claude에게 알려 주고 "같은 태그·비슷한 시작·같은 행동 유도 문구 금지"로 쓰게 함
- 코드에서도 최근에 쓴 태그를 걸러 냄(새 태그가 3개 미만일 때만 겹치는 태그로 채움)
- 해시태그는 5~8개(분야 1 + 기사 주제 3~4 + 좁은 키워드 1~2), `BRAND_HASHTAG`로 계정 고유 태그 1개는 항상 포함
- 첫 줄 후크(40자 이내), 짧은 문장, 검색 키워드 포함, 행동 유도 한 줄 구성
