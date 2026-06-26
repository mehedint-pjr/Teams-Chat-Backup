import os
import re
import sys
from datetime import datetime

CHATS_DIR = "/media/mihai/data/teams_chat_backup/chats"

TIMESTAMP_RE = re.compile(r'\*\*\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)\]')


def parse_chat(filepath):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    timestamps = TIMESTAMP_RE.findall(content)
    first_ts = None
    last_ts = None
    if timestamps:
        parsed = []
        for t in timestamps:
            try:
                parsed.append(datetime.strptime(t, "%Y-%m-%d %H:%M:%S UTC"))
            except Exception:
                pass
        if parsed:
            first_ts = min(parsed)
            last_ts = max(parsed)

    return {
        "file": filepath,
        "name": os.path.splitext(os.path.basename(filepath))[0],
        "content": content.lower(),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "message_count": len(timestamps),
    }


def search(tokens, chats_dir=CHATS_DIR):
    tokens_lower = [t.lower() for t in tokens]

    files = [
        os.path.join(chats_dir, f)
        for f in os.listdir(chats_dir)
        if f.endswith(".md")
    ]

    results = []
    for filepath in files:
        try:
            chat = parse_chat(filepath)
        except Exception as e:
            print(f"  Warning: could not read {filepath}: {e}")
            continue

        matched = [t for t in tokens_lower if t in chat["content"]]
        if not matched:
            continue

        results.append({
            "name": chat["name"],
            "file": chat["file"],
            "matched_tokens": matched,
            "match_count": len(matched),
            "all_matched": len(matched) == len(tokens_lower),
            "first_ts": chat["first_ts"],
            "last_ts": chat["last_ts"],
            "message_count": chat["message_count"],
        })

    results.sort(key=lambda r: (
        -r["match_count"],
        -(r["last_ts"].timestamp() if r["last_ts"] else 0),
    ))

    return results


def format_ts(dt):
    if not dt:
        return "unknown"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def print_results(results, tokens):
    if not results:
        print(f"\nNo chats found containing any of: {', '.join(tokens)}")
        return

    all_match = [r for r in results if r["all_matched"]]
    partial_match = [r for r in results if not r["all_matched"]]

    print(f"\nSearching for: {', '.join(repr(t) for t in tokens)}")
    print(f"Found {len(results)} chat(s) with at least one match.\n")

    if all_match:
        print(f"{'='*60}")
        print(f"  ALL TOKENS MATCHED ({len(all_match)} chat(s))")
        print(f"{'='*60}")
        for r in all_match:
            print(f"\n  {r['name']}")
            print(f"    Tokens matched : {', '.join(repr(t) for t in r['matched_tokens'])}")
            print(f"    Messages       : {r['message_count']}")
            print(f"    First message  : {format_ts(r['first_ts'])}")
            print(f"    Last message   : {format_ts(r['last_ts'])}")
            print(f"    File           : {r['file']}")

    if partial_match:
        print(f"\n{'='*60}")
        print(f"  PARTIAL MATCHES ({len(partial_match)} chat(s))")
        print(f"{'='*60}")
        for r in partial_match:
            print(f"\n  {r['name']}")
            print(f"    Tokens matched : {', '.join(repr(t) for t in r['matched_tokens'])}")
            print(f"    Missing        : {', '.join(repr(t) for t in tokens if t.lower() not in r['matched_tokens'])}")
            print(f"    Messages       : {r['message_count']}")
            print(f"    First message  : {format_ts(r['first_ts'])}")
            print(f"    Last message   : {format_ts(r['last_ts'])}")
            print(f"    File           : {r['file']}")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 search.py token1 [token2 token3 ...]")
        print('       python3 search.py "exact phrase" word1 word2')
        sys.exit(1)

    tokens = sys.argv[1:]
    results = search(tokens)
    print_results(results, tokens)
