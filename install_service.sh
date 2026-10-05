#!/bin/bash
# 서버 맥북용: 뉴스 서버를 "로그인하면 자동으로 켜지고, 꺼지거나 오류가 나면 다시 켜지는" 서비스로 등록한다.
#   등록:  bash install_service.sh
#   해제:  bash install_service.sh remove
#   로그:  tail -f logs/serve.log
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
LABEL=com.yoonsquads.news
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [ "$1" = "remove" ]; then
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "서비스를 해제했습니다. 이제 터미널에서 직접 켜세요: caffeinate -s python3 -m insta_agent.cli serve"
  exit 0
fi

PY="$(command -v python3)"
[ -n "$PY" ] || { echo "python3를 찾지 못했습니다"; exit 1; }
[ -f .env ] || { echo ".env가 없습니다. 먼저 설정하세요"; exit 1; }
if pgrep -f "insta_agent.cli serve" >/dev/null 2>&1; then
  echo "⚠️ 터미널에서 직접 켜 둔 서버가 있습니다. 그 탭에서 Control + C 로 끈 뒤 다시 실행하세요 (두 곳에서 돌면 텔레그램 메시지가 꼬입니다)."
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/caffeinate</string><string>-s</string>
    <string>$PY</string><string>-m</string><string>insta_agent.cli</string><string>serve</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$DIR/logs/serve.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/serve.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin:$HOME/.bun/bin</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
</dict>
</plist>
PLISTEOF

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl kickstart -k "$DOMAIN/$LABEL"
echo "✅ 서비스로 등록하고 시작했습니다. 텔레그램에 '봇이 시작되었습니다'가 오는지 확인하세요."
echo "   로그 보기: tail -f $DIR/logs/serve.log   (나가려면 Control + C)"
