# YoonSquads

YoonSquads 텔레그램 봇입니다.

## 설정

1. `.env.example`을 `.env`로 복사하고 값을 채웁니다.
   - `TELEGRAM_BOT_TOKEN`: BotFather에서 발급받은 봇 토큰
   - `TELEGRAM_CHAT_ID`: 뉴스 알림을 받을 채팅/채널 ID (비워두면 정기 알림은 비활성화되고 `/news` 명령만 동작합니다)
   - `RSS_FEED_URL`: 뉴스 RSS 피드 URL (기본값: 구글 뉴스 한국)
2. `npm install`
3. `npm start`

## 기능

- `/start`, `/help`: 기본 안내
- `/news`: 최신 뉴스 5건을 즉시 조회
- 30분마다 RSS 피드를 확인해 새 기사를 `TELEGRAM_CHAT_ID`로 자동 전송 (중복 전송 방지)
