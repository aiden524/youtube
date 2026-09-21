#!/usr/bin/env python3
"""세션 트랜스크립트를 날짜별 마크다운으로 레포에 저장한다.

Claude Code의 Stop 훅에서 호출된다. stdin으로 받은 훅 JSON에서
transcript_path를 읽어 대화를 날짜별 파일로 변환한다.

출력: transcripts/YYYY-MM-DD/session-<id8>.md   (읽기용 대화록)
      transcripts/YYYY-MM-DD/session-<id8>.raw.jsonl  (원본, SAVE_RAW=False로 끌 수 있음)
"""
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone, timedelta

SAVE_RAW = True          # 원본 jsonl도 함께 저장할지
TZ = timezone(timedelta(hours=9))   # 파일을 가를 기준 시간대 (KST)

SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)


def clean(text):
    return SYSTEM_REMINDER.sub("", text).strip()


def blocks_to_text(content):
    """메시지 content에서 사람이 읽을 부분만 뽑는다."""
    if isinstance(content, str):
        return clean(content), []
    if not isinstance(content, list):
        return "", []
    parts, tools = [], []
    for block in content:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            parts.append(clean(block.get("text", "")))
        elif kind == "tool_use":
            name = block.get("name", "tool")
            inp = block.get("input") or {}
            hint = inp.get("description") or inp.get("file_path") or inp.get("pattern") or ""
            tools.append(f"{name}: {hint}".strip().rstrip(":"))
    return "\n\n".join(p for p in parts if p), tools


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    path = payload.get("transcript_path")
    if not path or not os.path.isfile(path):
        return

    session = payload.get("session_id") or os.path.splitext(os.path.basename(path))[0]
    short = session[:8]

    # 날짜별로 메시지를 모은다
    by_date = {}
    first_date = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") not in ("user", "assistant"):
                continue
            if entry.get("isMeta"):
                continue

            message = entry.get("message") or {}
            text, tools = blocks_to_text(message.get("content"))
            if not text and not tools:
                continue

            stamp = entry.get("timestamp") or ""
            try:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(TZ)
            except ValueError:
                when = datetime.now(TZ)
            date = when.strftime("%Y-%m-%d")
            first_date = first_date or date

            speaker = "사용자" if entry["type"] == "user" else "Claude"
            chunk = [f"### {speaker} · {when.strftime('%H:%M')}", ""]
            if text:
                chunk.append(text)
            if tools:
                chunk.append("")
                chunk.append("<sub>도구: " + " / ".join(tools) + "</sub>")
            by_date.setdefault(date, []).append("\n".join(chunk))

    if not by_date:
        return

    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    written = []
    for date, chunks in by_date.items():
        out_dir = os.path.join(root, "transcripts", date)
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, f"session-{short}.md")
        header = (
            f"# 대화록 {date}\n\n"
            f"- 세션: `{session}`\n"
            f"- 갱신: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M')} KST\n\n"
            "---\n"
        )
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(header + "\n\n".join(chunks) + "\n")
        written.append(out)

    if SAVE_RAW and first_date:
        raw_dir = os.path.join(root, "transcripts", first_date)
        os.makedirs(raw_dir, exist_ok=True)
        raw = os.path.join(raw_dir, f"session-{short}.raw.jsonl")
        shutil.copyfile(path, raw)
        written.append(raw)

    print("\n".join(written))


if __name__ == "__main__":
    main()
