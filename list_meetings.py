import json
with open("/media/mihai/data/teams_chat_backup/checkpoint.json") as f:
    cp = json.load(f)
for k in cp:
    if "meeting" in k.lower():
        print(k)
