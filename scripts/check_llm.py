"""One real model call to confirm credentials, region and network. Prints no secrets.

Usage (from the repository root):  python scripts/check_llm.py
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from familyagent.agent.llm import get_llm  # noqa: E402
from familyagent.config import config  # noqa: E402


def main() -> int:
    print(f"model: {config.LLM_MODEL}")
    print(f"host:  {urlparse(config.DASHSCOPE_BASE_URL).netloc}")
    proxies = [k for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
               if os.environ.get(k) or os.environ.get(k.lower())]
    print(f"proxy env vars set: {proxies or 'none'}")
    try:
        reply = get_llm().invoke("Reply with exactly: pong")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {exc}")
        cause = exc.__cause__ or exc.__context__
        while cause is not None:
            print(f"  caused by: {type(cause).__name__}: {cause}")
            cause = cause.__cause__ or cause.__context__
        return 1
    print(f"reply: {reply.content!r}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
