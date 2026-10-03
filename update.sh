#!/bin/bash
# 서버 맥북용: GitHub의 최신 코드로 맞춘다. `git pull`이 divergent branches로 막히는 문제를 피한다.
# 이 맥북에만 있던 커밋은 backup-<시각> 브랜치로 남기고, .env·queue.db 는 건드리지 않는다.
set -e
BRANCH=claude/pensive-mayer-dkbvkp
git fetch origin "$BRANCH"
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/$BRANCH)" ]; then
  git branch "backup-$(date +%s)" HEAD 2>/dev/null || true
fi
git reset --hard "origin/$BRANCH"
python3 -m pip install -q -r requirements.txt
echo "✅ 최신 코드로 업데이트했습니다: $(git log --oneline -1)"
