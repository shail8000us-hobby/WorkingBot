import os
import sys
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _build_client():
    try:
        from openai import OpenAI
    except ImportError:
        print("Missing dependency: openai")
        print("Install it with: pip install openai")
        sys.exit(1)

    api_key = os.getenv("KIMI_API_KEY")
    base_url = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")

    if not api_key:
        print("KIMI_API_KEY not found. Put it in .env or environment variables.")
        sys.exit(1)

    return OpenAI(api_key=api_key, base_url=base_url)


def generate_code(prompt: str) -> str:
    client = _build_client()
    model = os.getenv("KIMI_MODEL", "kimi-2.6")

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You are a senior coding assistant. Return complete, runnable code."},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        message = str(exc)
        if "Authentication" in message or "401" in message:
            print("Authentication failed for Kimi API.")
            print("- Verify KIMI_API_KEY is valid and active")
            print("- Verify KIMI_BASE_URL and KIMI_MODEL are correct for your account")
            print("- If this key was exposed, rotate it and update .env")
            sys.exit(1)
        print("Kimi API request failed:", message)
        sys.exit(1)

    return (resp.choices[0].message.content or "").strip()


def main() -> None:
    _load_dotenv(Path(__file__).resolve().parent / ".env")

    if len(sys.argv) > 1:
        user_prompt = " ".join(sys.argv[1:])
    else:
        user_prompt = "Write a Python function for binary search and include simple tests."

    print("Using model:", os.getenv("KIMI_MODEL", "kimi-2.6"))
    print("\n--- Kimi response ---\n")
    print(generate_code(user_prompt))


if __name__ == "__main__":
    main()
