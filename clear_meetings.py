import json
import sys

cp_file = "/media/mihai/data/teams_chat_backup/checkpoint.json"
with open(cp_file) as f:
    cp = json.load(f)

before = len(cp)

if len(sys.argv) > 1:
    key = sys.argv[1]
    if key in cp:
        del cp[key]
        print(f"Removed: {key}")
    else:
        print(f"Key not found: {key}")
        print("Available meeting keys:")
        for k in cp:
            if "meeting" in k.lower():
                print(f"  {k}")
        sys.exit(1)
else:
    cp = {k: v for k, v in cp.items() if not k.startswith("19:meeting_")}
    print(f"Removed {before - len(cp)} meeting entries.")

with open(cp_file, "w") as f:
    json.dump(cp, f, indent=2)

print(f"{len(cp)} entries remain.")
