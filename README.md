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
     - `NAVER_API_PROVIDER`: 키를 발급받은 곳. `developers`(기본값, [네이버 개발자센터](https://developers.naver.com/apps)) 또는 `ncp`(네이버 클라우드 플랫폼 NAVER API HUB)
     - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 발급받은 Client ID / Secret
     - `NAVER_NEWS_KEYWORDS`: 검색할 키워드를 콤마로 구분
   - 인스타그램 게시(선택): 아래 "인스타그램 게시" 항목 참고
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

## 인스타그램 게시

허용된 사용자가 봇에 사진(+캡션)을 보내면 확인 버튼이 나오고, `게시`를 누르면 인스타그램(비즈니스/크리에이터 계정)에 업로드됩니다.

1. [Meta 앱](https://developers.facebook.com)에서 `Instagram API` → `Instagram 로그인이 포함된 API 설정`
   - `권한 및 기능`에서 `instagram_business_basic`, `instagram_business_content_publish` 추가
   - `역할` 탭에서 인스타그램 계정을 **Instagram 테스터**로 등록하고, 인스타그램에서 초대 수락 (`instagram.com/accounts/manage_access` → 테스터 초대)
   - 설정 2번 `계정 추가`로 액세스 토큰과 IG User ID 발급
2. `.env`에 `INSTAGRAM_USER_ID`, `INSTAGRAM_ACCESS_TOKEN`, `TELEGRAM_ALLOWED_USER_IDS`(내 텔레그램 ID), `PUBLIC_BASE_URL` 입력
3. `PUBLIC_BASE_URL`은 인스타그램 서버가 이미지를 가져갈 외부 주소입니다. 봇이 `MEDIA_PORT`(기본 8080)로 사진을 잠깐 공개하고 게시 후 삭제합니다. 개발 중에는 ngrok/cloudflared 터널로 해당 포트를 열어 주소를 넣으세요.

사진 1장(JPEG), 캡션 2,200자까지 지원하며 인스타그램 API는 24시간당 약 100건까지 게시할 수 있습니다. 토큰은 `.env`에만 두고 커밋하지 마세요.
