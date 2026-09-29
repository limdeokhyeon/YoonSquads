# YoonSquads

텔레그램 → 인스타그램 자동 게시 봇.
텔레그램 봇에 사진(+캡션)을 보내면 확인 버튼이 나오고, `게시`를 누르면 인스타그램에 업로드됩니다.

## 준비물
1. **텔레그램 봇**: [@BotFather](https://t.me/BotFather)에서 봇을 만들고 토큰 발급
2. **인스타그램 비즈니스/크리에이터 계정** (페이스북 페이지 연결은 필요 없음)
3. **Meta 앱** ([developers.facebook.com](https://developers.facebook.com)): 이용 사례 `Instagram API` → `Instagram 로그인이 포함된 API 설정`
   - `권한 및 기능`에서 `instagram_business_basic`, `instagram_business_content_publish` 추가
   - `역할` 탭에서 인스타그램 계정을 Instagram 테스터로 등록하고, 인스타그램 앱에서 초대 수락
   - 설정 2번 `계정 추가`로 액세스 토큰과 IG User ID 발급
4. **외부에서 접근 가능한 주소**: 인스타그램 서버가 이미지를 URL로 가져가므로 `PUBLIC_BASE_URL`이 필요합니다 (서버 도메인, 또는 개발 중에는 ngrok/cloudflared 터널로 `MEDIA_PORT`를 노출)

## 실행
```bash
pip install -r requirements.txt
cp .env.example .env   # 값 채우기
python -m tg2ig
```
봇에 `/start`를 보내면 내 텔레그램 ID가 표시됩니다. 이를 `TELEGRAM_ALLOWED_USER_IDS`에 넣으세요.

## 참고
- 허용된 사용자 ID만 게시할 수 있습니다.
- 사진 1장 게시만 지원합니다 (JPEG). 캡션은 2,200자까지.
- 인스타그램 API는 하루 게시 횟수 제한(24시간당 약 100건)이 있습니다.
- 액세스 토큰은 `.env`에만 두고 커밋하지 마세요.
