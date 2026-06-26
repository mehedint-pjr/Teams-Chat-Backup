import requests
import json
import time
import os
import re
from datetime import datetime

TOKEN = input("Paste your Bearer token (without 'Bearer '): ").strip()
if TOKEN.startswith("Bearer "):
    TOKEN = TOKEN[7:]

BASE = "https://teams.cloud.microsoft/api/chatsvc/amer/v1/users/ME"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "x-ms-migration": "True",
    "x-ms-test-user": "False",
    "behavioroverride": "redirectAs404",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Referer": "https://teams.cloud.microsoft/",
    "Origin": "https://teams.cloud.microsoft",
}

OUT_DIR = "/media/mihai/data/teams_chat_backup/chats"
os.makedirs(OUT_DIR, exist_ok=True)

CHECKPOINT_FILE = "/media/mihai/data/teams_chat_backup/checkpoint.json"


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}


def save_checkpoint(data):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def safe_filename(name):
    return re.sub(r'[^\w\s-]', '_', name).strip()[:80]


def get_with_retry(url, params=None, retries=10):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=40)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 60))
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code == 401:
                print("ERROR: Token expired or invalid. Please refresh your token.")
                raise SystemExit(1)
            if r.status_code >= 500:
                print(f"  Server error {r.status_code}, retrying in {2**attempt}s...")
                time.sleep(2 ** attempt)
                continue
            return r
        except requests.exceptions.ConnectionError:
            print(f"  Connection error, retrying in {2**attempt}s...")
            time.sleep(2 ** attempt)
    raise Exception(f"Failed after {retries} retries: {url}")


def parse_timestamp(ts):
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return ts


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&quot;', '"', text)
    return text.strip()


def get_all_conversations():
    print("Fetching conversation list...")
    url = f"{BASE}/conversations"
    params = {"view": "msnp24Equivalent", "pageSize": 200}
    conversations = []
    page = 0
    while url:
        r = get_with_retry(url, params=params if page == 0 else None)
        if r.status_code != 200:
            print(f"  Error fetching conversations: {r.status_code} {r.text[:200]}")
            break
        data = r.json()
        batch = data.get("conversations", []) or data.get("value", [])
        conversations.extend(batch)
        print(f"  Got {len(batch)} conversations (total: {len(conversations)})")
        next_link = data.get("_metadata", {}).get("syncToken") or data.get("@odata.nextLink")
        if next_link and next_link != url:
            url = next_link
            page += 1
            time.sleep(0.5)
        else:
            break
    return conversations


def get_all_messages(thread_id):
    encoded = requests.utils.quote(thread_id, safe='')
    url = f"{BASE}/conversations/{encoded}/messages"
    params = {"view": "msnp24Equivalent&pageSize=200", "startTime": "1"}
    messages = []
    page = 0
    while url:
        r = get_with_retry(url, params=params if page == 0 else None)
        if r.status_code == 404:
            return []
        if r.status_code != 200:
            print(f"    Error fetching messages: {r.status_code}")
            break
        data = r.json()
        batch = data.get("messages", []) or data.get("value", [])
        messages.extend(batch)
        next_link = (data.get("_metadata", {}) or {}).get("backwardLink") or data.get("@odata.nextLink")
        if next_link and next_link != url and page < 500:
            url = next_link
            page += 1
            time.sleep(0.3)
        else:
            break
    return messages


def get_display_name(conv):
    topic = conv.get("threadProperties", {}).get("topic", "")
    if topic:
        return topic
    members = conv.get("members", [])
    names = []
    for m in members:
        dn = m.get("userPrincipalName") or m.get("displayName") or m.get("mri", "")
        if dn and "mmehedint" not in dn.lower():
            names.append(dn)
    if names:
        return ", ".join(names[:3])
    return conv.get("id", "unknown")


def format_message(msg):
    sender = ""
    creator = msg.get("creator", "")
    if ":" in creator:
        sender = creator.split(":")[-1]
    if "@" in sender:
        sender = sender.split("@")[0]

    ts = parse_timestamp(msg.get("originalarrivaltime") or msg.get("composetime", ""))
    msg_type = msg.get("messagetype", "")

    if msg_type not in ("Text", "RichText/Html", "RichText/Media_GenericFile", "RichText/Media_Video", ""):
        if not msg_type.startswith("RichText"):
            return None

    content = msg.get("content", "") or ""
    content = strip_html(content)

    if not content.strip():
        return None

    lines = [f"**[{ts}] {sender}**", content]

    attachments = msg.get("amsreferences", []) or []
    if attachments:
        lines.append(f"_(attachments: {len(attachments)} file(s) — not downloaded)_")

    return "\n".join(lines)


def first_timestamp(messages):
    timestamps = [
        m.get("originalarrivaltime") or m.get("composetime", "")
        for m in messages
        if m.get("originalarrivaltime") or m.get("composetime")
    ]
    if not timestamps:
        return None
    earliest = min(timestamps)
    try:
        dt = datetime.fromisoformat(earliest.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d_%H%M")
    except Exception:
        return None


def write_chat_md(conv, messages):
    name = get_display_name(conv)
    thread_id = conv.get("id", "unknown")
    base_filename = safe_filename(name)
    ts = first_timestamp(messages)
    if ts:
        filename = f"{base_filename}_{ts}.md"
    else:
        filename = base_filename + ".md"
    filepath = os.path.join(OUT_DIR, filename)

    messages_sorted = sorted(messages, key=lambda m: m.get("originalarrivaltime") or m.get("composetime") or "")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {name}\n\n")
        f.write(f"_Thread ID: {thread_id}_\n\n")
        f.write("---\n\n")

        written = 0
        for msg in messages_sorted:
            formatted = format_message(msg)
            if formatted:
                f.write(formatted + "\n\n---\n\n")
                written += 1

    return filepath, written


def main():
    checkpoint = load_checkpoint()
    conversations = get_all_conversations()

    if not conversations:
        print("No conversations found. The token may lack permissions or the API endpoint differs.")
        print("Try refreshing the page in Teams and grabbing a new token.")
        return

    print(f"\nFound {len(conversations)} conversations total.\n")

    for i, conv in enumerate(conversations):
        thread_id = conv.get("id", "")
        name = get_display_name(conv)

        if checkpoint.get(thread_id) == "done":
            print(f"[{i+1}/{len(conversations)}] Skipping (already done): {name}")
            continue

        print(f"[{i+1}/{len(conversations)}] Processing: {name}")

        messages = get_all_messages(thread_id)
        print(f"  Fetched {len(messages)} messages")

        if messages:
            filepath, written = write_chat_md(conv, messages)
            print(f"  Wrote {written} messages -> {filepath}")
        else:
            print(f"  No messages or inaccessible, skipping.")

        checkpoint[thread_id] = "done"
        save_checkpoint(checkpoint)
        time.sleep(0.5)

    print("\nDone! All chats saved to:", OUT_DIR)


if __name__ == "__main__":
    main()
