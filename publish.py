#!/usr/bin/env python3
"""더블클릭용 발행 도구.

build.py 로 글을 확인하고, 문제 없으면 저장소에 올린다.
배치 파일은 한글 출력이 깨져서 안내까지 여기서 한다.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SITE = "https://moon-cardone.github.io/moonz-lab/"

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def run(*args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def wait():
    """더블클릭으로 열린 창이 바로 닫히지 않게 붙잡아 둔다."""
    try:
        input("  엔터를 누르면 창이 닫힙니다...")
    except EOFError:
        pass  # 자동 실행 등 입력이 없는 경우


def stop(msg):
    print(f"\n{'=' * 52}\n  {msg}\n{'=' * 52}\n")
    wait()
    sys.exit(1)


print("\n  [1/3] 글 확인하는 중...\n")

check = run(sys.executable, "build.py")
print(check.stdout, end="")
if check.returncode != 0:
    print(check.stderr, end="")
    stop("올리지 않았습니다. 위에 적힌 파일을 고쳐주세요.")

print("\n  [2/3] 저장소에 올리는 중...\n")

run("git", "add", "-A")
if run("git", "diff", "--cached", "--quiet").returncode == 0:
    print("  바뀐 게 없습니다.\n")
    wait()
    sys.exit(0)

commit = run("git", "commit", "-m", "발행")
if commit.returncode != 0:
    print(commit.stdout + commit.stderr, end="")
    stop("커밋 실패.")

push = run("git", "push")
if push.returncode != 0:
    print(push.stdout + push.stderr, end="")
    stop("올리기 실패. 인터넷 연결을 확인해주세요.")

print(f"\n  [3/3] 끝났습니다.\n\n  2~3분 뒤 여기서 확인:\n  {SITE}\n")
wait()
