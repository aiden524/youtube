#!/usr/bin/env bash
# Stop 훅: 세션 대화록을 날짜별로 저장하고 커밋·푸시한다.
# 실패해도 세션을 막지 않도록 항상 0으로 끝난다.
set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$REPO" || exit 0

# stdin의 훅 JSON을 변환기로 넘긴다
python3 "$REPO/.claude/hooks/save-transcript.py" >/dev/null 2>&1 || exit 0

git add transcripts >/dev/null 2>&1 || exit 0
git diff --cached --quiet -- transcripts && exit 0   # 바뀐 게 없으면 끝

BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null)" || exit 0
[ -n "$BRANCH" ] || exit 0

git commit -q -m "Update transcript ($(TZ=Asia/Seoul date "+%Y-%m-%d %H:%M KST"))" \
  -m "Co-Authored-By: Claude <noreply@anthropic.com>" \
  -- transcripts >/dev/null 2>&1 || exit 0

for delay in 0 2 4 8; do
  [ "$delay" -gt 0 ] && sleep "$delay"
  if git push -q -u origin "$BRANCH" >/dev/null 2>&1; then
    echo "{\"systemMessage\": \"대화록 저장·푸시 완료 ($BRANCH)\"}"
    exit 0
  fi
done

echo '{"systemMessage": "대화록은 커밋했지만 푸시에 실패했습니다 (다음 턴에 다시 시도)"}'
exit 0
