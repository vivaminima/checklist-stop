# Changelog

## 1.0.1 - 2026-11-13

- README: added the line that this tool is not affiliated with, endorsed by or sponsored by Anthropic.
- The package is now named `checklist-stop`.
- No change to behaviour. Same tests.

## 1.0.0 - 2026-11-12

First release.

- Stop hook that blocks while the checklist file has an open `- [ ]` item and returns the next one as `file:line`.
- `PAUSED: <reason>` on the first non-blank line lets the stop through. A PAUSED line with no reason does not count.
- Boxes inside fenced code blocks and HTML comments are not counted.
- Reads UTF-8 with or without a BOM, CRLF line endings and UTF-16.
- A missing checklist file lets the stop through with one warning line.
- `--file`, `--root`, `--check`, and the `CHECKLIST_STOP_FILE` environment variable.
- 31 unit tests.
