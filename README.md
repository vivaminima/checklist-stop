# checklist-stop
Unlike Claude Code's built-in Tasks, this enforces completion against your existing Markdown checklist at Stop time.

A Claude Code **Stop hook** in one Python file. When Claude tries to finish while your checklist still has a `- [ ]` item, the hook blocks the stop and hands the next open item back, with the file path and line number.

```
Checklist not finished: 2 open item(s) in PROGRESS.md.
Next: PROGRESS.md:4: - [ ] write the tests
Do that item, change it to "- [x]", then finish.
If it needs a person or cannot be done now, make the first line of PROGRESS.md "PAUSED: <reason> / human must do <what>" and finish.
```

- Python 3.8 or newer, standard library only.
- Makes no network requests. Reads one file. Writes nothing.
- MIT licence.

## Install

1. Copy `checklist_stop.py` into your project, for example to `.claude/hooks/checklist_stop.py`.
2. Add the hook to `.claude/settings.json` (see [examples/settings.json](examples/settings.json)):

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/checklist_stop.py\" --file PROGRESS.md"
          }
        ]
      }
    ]
  }
}
```

On Windows use `python` in place of `python3`. If your shell does not expand `$CLAUDE_PROJECT_DIR`, write the full path to the script.

3. Keep your checklist in `PROGRESS.md` at the project root, or name another file with `--file` or the `CHECKLIST_STOP_FILE` environment variable.

## What counts

| In the checklist file | Result |
| --- | --- |
| At least one `- [ ]` | Stop is blocked. The first open item is returned with `file:line`. |
| Every box is `- [x]` (or there are no boxes) | Stop goes through. |
| First non-blank line is `PAUSED: <reason>` | Stop goes through, open items stay as they are. |
| `PAUSED:` with nothing after the colon | Does not count. The hook says so and blocks. |
| The file does not exist | Stop goes through, with one warning line on stderr. |

Details:

- Bullets `-`, `*`, `+` and numbered items (`1.`, `1)`) all count, nested or inside a block quote.
- Boxes inside fenced code blocks (```` ``` ```` or `~~~`) and inside HTML comments are not counted.
- A UTF-8 BOM, CRLF line endings and UTF-16 files are read correctly.
- The hook's answer is ASCII-only JSON, so it survives any console code page.
- If the hook itself fails, it lets the session stop. A broken hook should never trap you.

## The way out of a loop

A stale checkbox can keep blocking the stop for ever. Two things prevent that:

- Every block message names the exact `file:line`, so the stale item is easy to find.
- Every block message tells Claude how to pause: put `PAUSED: <reason> / human must do <what>` on the first line of the file. Remove that line when work resumes.

This free version does not count blocks. If you want the hook to give up by itself after N blocks on the same item, that is in the Pro version.

## Check from the terminal

```
python3 checklist_stop.py --check --file PROGRESS.md
```

Prints every open item as `file:line` and exits 1 if there are any, 0 if not.

## Tests

```
python3 -m unittest discover -s tests -v
```

31 tests. They cover: open item blocks, all ticked passes, PAUSED passes, code blocks are skipped, BOM and CRLF, missing file passes with one warning, Korean text and paths with spaces, a cp949 console.

## Known limits

- The hook was tested by feeding it the Stop hook's JSON on standard input, on Windows with Python 3.10. Hook input fields it relies on: `cwd` (optional). Everything else is ignored.
- Indented (4-space) code blocks are not recognised as code, because nested list items use the same indent.
- One checklist file per hook. For several files, patterns and a TOML config, see Pro.

## Pro version

**Checklist Stop Pro** by Vivaminima adds: several checklist files and patterns, a TOML config, a repeat guard that suggests `PAUSED` after N blocks on the same item, headings to ignore, a larger edge-case test suite, and install guides for Windows and macOS.

## Not affiliated

This tool works with Claude Code. It is not affiliated with, endorsed by or sponsored by Anthropic.

## Licence

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 Vivaminima.

## More from Vivaminima

- **Token Audit Kit ($19)** — see how many tokens your CLAUDE.md and its @imports cost before your first prompt, and a step-by-step guide to split it. Free script: https://github.com/vivaminima/context-file-audit · Paid kit: https://vivaminima.lemonsqueezy.com/checkout/buy/57973270-94ea-4cc7-bcb4-294693714087
- Free tools: [skill-audit-kit](https://github.com/vivaminima/skill-audit-kit) · [secret-map](https://github.com/vivaminima/secret-map) · [inbox-ledger](https://github.com/vivaminima/inbox-ledger) · [release-gate](https://github.com/vivaminima/release-gate) · [skill-install-gate](https://github.com/vivaminima/skill-install-gate) · [console-safe](https://github.com/vivaminima/console-safe) · [checklist-stop](https://github.com/vivaminima/checklist-stop) · [handoff-check](https://github.com/vivaminima/handoff-check) · [llm-budget-router-lite](https://github.com/vivaminima/llm-budget-router-lite) · [go-no-go-verdict-skill](https://github.com/vivaminima/go-no-go-verdict-skill) · [ai-company-starter-kit](https://github.com/vivaminima/ai-company-starter-kit) · [beginner-readme-section](https://github.com/vivaminima/beginner-readme-section)

Vivaminima is not affiliated with, endorsed by or sponsored by Anthropic.
