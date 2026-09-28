# YoonSquads

YoonSquads 텔레그램 봇입니다.

## 설정

1. `.env.example`을 `.env`로 복사하고 값을 채웁니다.
   - `TELEGRAM_BOT_TOKEN`: BotFather에서 발급받은 봇 토큰
   - `TELEGRAM_CHAT_ID`: 뉴스 알림을 받을 채팅/채널 ID (비워두면 정기 알림은 비활성화되고 `/news` 명령만 동작합니다)
   - `NEWS_SOURCE`: `rss` 또는 `naver` (기본값: `rss`)
   - RSS 사용 시: `RSS_FEED_URL` (기본값: 구글 뉴스 한국)
   - 네이버 검색 API 사용 시:
     - [네이버 개발자센터](https://developers.naver.com/apps)에서 애플리케이션 등록 후 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 발급
     - `NAVER_NEWS_KEYWORDS`: 검색할 키워드를 콤마로 구분 (예: `정치,경제,시사`)
2. `npm install`
3. `npm start`

## 기능

- `/start`, `/help`: 기본 안내
- `/news`: 최신 뉴스 5건을 즉시 조회
- 30분마다 뉴스 소스를 확인해 새 기사를 `TELEGRAM_CHAT_ID`로 자동 전송 (중복 전송 방지)

## 뉴스 소스

- **RSS** (`NEWS_SOURCE=rss`): 지정한 RSS 피드에서 최신 기사를 가져옵니다.
- **네이버 검색 API** (`NEWS_SOURCE=naver`): `NAVER_NEWS_KEYWORDS`에 지정한 키워드로 네이버 뉴스를 검색해 최신순으로 가져옵니다. 네이버는 전체 실시간 뉴스 RSS를 공식 제공하지 않기 때문에, 키워드 기반 검색 API로 대체한 방식입니다. 무료 API이며 일일 호출 한도가 있습니다.
