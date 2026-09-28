# YoonSquads

YoonSquads 텔레그램 봇입니다.

## 설정

1. `.env.example`을 `.env`로 복사하고 값을 채웁니다.
   - `TELEGRAM_BOT_TOKEN`: BotFather에서 발급받은 봇 토큰
   - `TELEGRAM_CHAT_ID`: 뉴스 알림을 받을 채팅/채널 ID (비워두면 정기 알림은 비활성화되고 `/news` 명령만 동작합니다)
   - `ANTHROPIC_API_KEY`: [Anthropic 콘솔](https://console.anthropic.com/)에서 발급받은 API 키. 설정하면 명령어가 아닌 일반 메시지를 Claude가 대화형으로 응답합니다. 비워두면 이 기능은 비활성화됩니다.
   - `ANTHROPIC_MODEL`: 사용할 Claude 모델 (기본값: `claude-sonnet-4-5`)
   - `NEWS_SOURCE`: `google`(기본값, 키 불필요) / `rss` / `naver`
   - 구글 뉴스 키워드 검색 사용 시 (기본값): `NEWS_KEYWORDS` — 검색할 키워드를 콤마로 구분 (예: `정치,경제,시사`)
   - RSS 피드 그대로 사용 시: `RSS_FEED_URL` (기본값: 구글 뉴스 한국 전체 피드)
   - 네이버 검색 API 사용 시:
     - [네이버 개발자센터](https://developers.naver.com/apps)에서 애플리케이션 등록 후 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 발급
     - `NAVER_NEWS_KEYWORDS`: 검색할 키워드를 콤마로 구분
2. `npm install`
3. `npm start`

## 기능

- `/start`, `/help`: 기본 안내
- `/news`: 최신 뉴스 5건을 즉시 조회
- 10분마다 뉴스 소스를 확인해 새 기사를 `TELEGRAM_CHAT_ID`로 자동 전송 (중복 전송 방지)
- `ANTHROPIC_API_KEY` 설정 시: 명령어가 아닌 일반 메시지를 보내면 Claude가 대화형으로 응답 (`/reset`으로 대화 기록 초기화)

## 뉴스 소스

- **구글 뉴스 키워드 검색** (`NEWS_SOURCE=google`, 기본값): API 키 없이 `NEWS_KEYWORDS`에 지정한 키워드로 구글 뉴스를 검색해 최신순으로 가져옵니다. 가입/등록 절차가 필요 없어 바로 사용 가능합니다.
- **RSS** (`NEWS_SOURCE=rss`): 지정한 RSS 피드 전체에서 최신 기사를 가져옵니다.
- **네이버 검색 API** (`NEWS_SOURCE=naver`): `NAVER_NEWS_KEYWORDS`에 지정한 키워드로 네이버 뉴스를 검색합니다. 네이버 개발자센터에서 앱 등록/API 키 발급이 필요합니다.

## 참고: 뉴스 반영 속도

구글/네이버 뉴스 모두 언론사 기사를 색인하는 방식이라 발행 후 반영까지 다소 지연(수 분~수십 분)이 있을 수 있습니다. 봇은 10분마다 확인하므로 평균 5분, 최대 10분 정도의 추가 지연이 생깁니다. 필요하면 `src/bot.js`의 cron 주기(`*/10 * * * *`)를 더 짧게 조정할 수 있습니다.
