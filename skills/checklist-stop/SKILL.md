---
name: checklist-stop
description: Checks a Markdown checklist (PROGRESS.md) and reports the items still open, so a session does not stop with work left. Use when the user asks, for example, "what is still open in PROGRESS.md", "can I stop now", "checklist stop", "남은 체크 항목 보여 줘".
---

# checklist-stop

Checks a Markdown checklist (PROGRESS.md) and reports the items still open, so a session does not stop with work left. A small Python tool shipped in this plugin: standard library only, nothing to install, runs locally.

## Run

Use `python` (Windows: `py -3` also works; macOS/Linux: `python3`). On Windows add `-X utf8` if the console shows broken characters.

    python "${CLAUDE_PLUGIN_ROOT}/checklist_stop.py" --check --file PROGRESS.md

Run it from the user's project folder and pass the path they mean. If no path is given, ask which folder or file to check.

## Read the result

List the open items. Setting it up as a Stop hook is optional and described in the repository README; do not edit the user's settings without asking.

Show the tool's own output (shortened if long) and then a two- or three-line summary. Do not change the user's files unless they ask.
