# Microsoft Teams Chat Backup

Exports all your Microsoft Teams chats (1:1, group, channels) to local Markdown files — no admin access, no app registration, no Azure setup required.

---

## How It Works

The script uses the same internal API that the Teams web client uses. You extract a short-lived authentication token directly from your browser session and pass it to the script. It then paginates through all your conversations and messages, saving each chat as a `.md` file.

---

## Requirements

- Python **3.11** recommended (`3.8+` should work, but `3.14` has known issues)
- `requests` library

```bash
pip install requests
```

---

## Scripts

| Script | Purpose |
|---|---|
| `scraper.py` | Main backup script — exports all chats to `.md` files |
| `search.py` | Search across exported chats by keyword/token |
| `clear_meetings.py` | Remove meeting entries from checkpoint to force re-export |
| `list_meetings.py` | List all meeting thread IDs currently in the checkpoint |

---

## Step-by-Step Usage

### 1. Log into Teams in Chrome

Go to [https://teams.cloud.microsoft](https://teams.cloud.microsoft) and sign in normally.

### 2. Open DevTools and find your token

1. Press **F12** to open Chrome DevTools
2. Click the **Network** tab
3. Click **Fetch/XHR** filter in the toolbar
4. In Teams, click on any chat or send a message to trigger network activity
5. Look for a request named **`messages`** with type **fetch** and status **201**
6. Click on it → go to the **Headers** tab → scroll down to **Request Headers**
7. Find the `authorization` header — it starts with `Bearer eyJ...`
8. Right-click the value → **Copy value**

> **Tip:** If you don't see a `messages` request, send yourself a message in Teams to trigger one.
> **Tip:** Avoid clicking image/script/XHR requests — only the `fetch` type `messages` rows contain the auth token.

### 3. Run the script

```bash
python3 scraper.py
```

When prompted, paste your token (with or without the `Bearer ` prefix — both work).

### 4. Wait for it to finish

The script will print progress for each conversation:

```
Fetching conversation list...
  Got 146 conversations (total: 146)

[1/146] Processing: Team Chat Name
  Fetched 1273 messages
  Wrote 1217 messages -> /path/to/chats/Team Chat Name_2025-03-14_1032.md
...
```

All files are saved to the `chats/` subfolder.

---

## Output Format

Each conversation becomes a single `.md` file. Chats with a topic name use that as the filename. Recurring meetings with the same name get a timestamp suffix derived from the first message in that thread:

```
Meeting with John_2025-03-14_1032.md
Meeting with John_2025-04-02_0915.md
```

File contents:

```markdown
# Team Chat Name

_Thread ID: 19:abc123@thread.tacv2_

---

**[2025-03-14 10:32:01 UTC] john.smith**
Hey, can you review the PR?

---

**[2025-03-14 10:45:22 UTC] jane.doe**
Sure, looking at it now.

---
```

---

## Searching Exported Chats

Use `search.py` to search across all exported `.md` files by one or more keywords:

```bash
# Single keyword
python3 search.py scanalyzer

# Multiple keywords
python3 search.py scanalyzer "edge computing" protocol

# Exact phrase
python3 search.py "SBIR phase I"
```

Results are grouped and sorted:

1. **ALL TOKENS MATCHED** — chats containing every keyword, sorted by most recent activity
2. **PARTIAL MATCHES** — chats containing some keywords, showing which are missing

Example output:

```
Searching for: 'scanalyzer', 'protocol'
Found 4 chat(s) with at least one match.

============================================================
  ALL TOKENS MATCHED (2 chat(s))
============================================================

  task in Scanalyzer
    Tokens matched : 'scanalyzer', 'protocol'
    Messages       : 1217
    First message  : 2024-01-10 09:15 UTC
    Last message   : 2025-06-20 14:32 UTC
    File           : /path/to/chats/task in Scanalyzer.md
```

---

## Resuming After Interruption

The script saves a `checkpoint.json` file after each conversation. If it stops (token expiry, network error, etc.):

1. Grab a fresh token from the browser (same steps as above)
2. Re-run `python3 scraper.py` with the new token
3. Already-completed conversations are skipped automatically

---

## Managing the Checkpoint

### List all meeting entries in checkpoint

```bash
python3 list_meetings.py
```

### Remove all meeting entries (force re-export with timestamps)

```bash
python3 clear_meetings.py
```

### Remove a specific thread by ID

```bash
python3 clear_meetings.py "19:meeting_abc123@thread.v2"
```

### Clear the entire checkpoint (re-export everything)

```bash
echo '{}' > checkpoint.json
```

---

## Token Expiry

Browser tokens expire in approximately **1 hour**. If you see:

```
ERROR: Token expired or invalid. Please refresh your token.
```

Go back to Teams in Chrome, find a new `messages` request in the Network tab, copy the new `authorization` header value, and re-run the script. The checkpoint ensures already-exported chats are not re-downloaded.

---

## Troubleshooting

### "Wrote 0 messages" for some chats
Normal — these are system-only threads (meeting join/leave events, call logs, file shares with no text). No actual user text was present.

### Rate limiting (`Rate limited, waiting Xs...`)
Normal — the script handles this automatically and retries. Do not interrupt it.

### Script crashes after rate limiting with `Failed after 10 retries`
The token expired during a long rate-limit wait. Grab a fresh token and re-run — the checkpoint will resume where it left off.

### Token works in browser but script says "Token expired"
- Make sure you copied the **full** token — it is ~1300-1500 characters long and starts with `eyJ`
- Avoid copying from requests marked **"Provisional headers are shown"** in DevTools — those may be cached/stale
- Test your token manually:
  ```bash
  curl -H "Authorization: Bearer YOUR_TOKEN" "https://teams.cloud.microsoft/api/chatsvc/amer/v1/users/ME/conversations?view=msnp24Equivalent&pageSize=5"
  ```
  If this returns JSON, the token is valid. If it returns `401`, the token is bad.

### No conversations found
- Check your region — look at the `Request URL` of the `messages` request in DevTools. It will contain `amer`, `emea`, or `apac`. Edit line 12 of `scraper.py` to match:
  ```python
  BASE = "https://teams.cloud.microsoft/api/chatsvc/emea/v1/users/ME"   # Europe
  BASE = "https://teams.cloud.microsoft/api/chatsvc/apac/v1/users/ME"   # Asia-Pacific
  ```

### Duplicate meeting filenames overwriting each other
Run `clear_meetings.py` with no arguments, delete the existing meeting `.md` files, then re-run `scraper.py`. Each meeting will get a unique timestamp suffix.

### Windows-specific: token paste gets truncated
In the DevTools Headers panel, right-click the `authorization` value → **Copy value** (not "Copy all"). Then verify the token length:
```python
python -c "t = input('Paste token: '); print(len(t))"
```
A valid token is 1300–1500 characters.

Alternatively, hardcode the token directly in `scraper.py` line 8 to avoid paste issues:
```python
TOKEN = "eyJ0eXAiOi..."  # paste full token here
```

### Windows-specific: "Token expired" immediately on first request
Three things that fixed this for a confirmed working setup:
1. Use **Python 3.11** — Python 3.14 has known compatibility issues with this script
2. **Close all other Teams clients** — the Teams desktop app or other browser tabs with Teams open can invalidate the token
3. **Hardcode the token** in `scraper.py` instead of pasting at the prompt to rule out truncation

---

## Known Limitations

| Limitation | Detail |
|---|---|
| **Token expires in ~1 hour** | Must refresh manually for large exports |
| **Text only** | Attached files, images, and videos are noted but not downloaded |
| **No reactions** | Emoji reactions are not captured |
| **No reply threads** | Threaded replies in channels are fetched as flat messages |
| **System messages skipped** | Meeting join/leave events, call logs, and other non-text messages are filtered out |
| **AMER region hardcoded** | Users in Europe/Asia may need to change the region in `scraper.py` line 12 |

---

## Privacy & Security

- Your token is **never stored to disk** — it is only held in memory for the duration of the script
- Treat your bearer token like a password — it grants full access to your Teams account for ~1 hour
- Do not share your token with anyone
- The `checkpoint.json` file contains only conversation thread IDs, no message content

---

## File Structure

```
teams_chat_backup/
├── scraper.py          # Main backup script
├── search.py           # Search across exported chats
├── clear_meetings.py   # Remove meeting entries from checkpoint
├── list_meetings.py    # List meeting thread IDs in checkpoint
├── checkpoint.json     # Auto-generated, tracks progress
├── README.md           # This file
└── chats/              # Auto-generated output folder
    ├── Chat Name_2025-01-10_0915.md
    ├── Meeting with John_2025-03-14_1032.md
    └── ...
```
