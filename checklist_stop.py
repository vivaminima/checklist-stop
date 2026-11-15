#!/usr/bin/env python3
"""checklist-stop

A Claude Code Stop hook. While a Markdown checklist still has an open
"- [ ]" item, the hook blocks the stop and hands the next open item back,
with the file path and line number.

Standard library only. Makes no network requests. Reads one file, writes none.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

__version__ = "1.0.1"

DEFAULT_FILE = "PROGRESS.md"
ENV_FILE = "CHECKLIST_STOP_FILE"

_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_ITEM_RE = re.compile(
    r"^\s*(?:>\s?)*\s*(?:[-*+]|\d{1,9}[.)])\s+\[([ xX])\](?=\s|$)\s*(.*)$"
)
_PAUSED_RE = re.compile(r"^\s*(?:#+\s*)?PAUSED\s*:\s*(.*?)\s*$", re.IGNORECASE)


class Item(object):
    """One checkbox line."""

    __slots__ = ("line", "checked", "text")

    def __init__(self, line, checked, text):
        self.line = line
        self.checked = checked
        self.text = text

    def as_markdown(self):
        return "- [%s] %s" % ("x" if self.checked else " ", self.text)


class Parsed(object):
    """Result of reading one checklist file."""

    __slots__ = ("pause_line", "pause_reason", "items")

    def __init__(self, pause_line, pause_reason, items):
        self.pause_line = pause_line      # 0 when the file has no PAUSED line
        self.pause_reason = pause_reason  # "" when the PAUSED line gives no reason
        self.items = items

    @property
    def open_items(self):
        return [item for item in self.items if not item.checked]


def read_text(path):
    """Read a text file as UTF-8, accepting a BOM and UTF-16 files."""
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8-sig", errors="replace")


def parse_checklist(text, ignore_headings=()):
    """Find the PAUSED line and every checkbox outside code and comments."""
    lines = text.splitlines()

    pause_line = 0
    pause_reason = ""
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        match = _PAUSED_RE.match(line)
        if match:
            pause_line = number
            pause_reason = match.group(1)
        break

    ignored = set(title.strip().lower() for title in ignore_headings)
    items = []
    fence = ""
    in_comment = False
    skip_level = 0

    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if fence:
            if (
                stripped
                and stripped[0] == fence[0]
                and len(stripped) >= len(fence)
                and stripped == stripped[0] * len(stripped)
            ):
                fence = ""
            continue
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        match = _FENCE_RE.match(line)
        if match:
            fence = match.group(1)
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped[4:]:
                in_comment = True
            continue
        match = _HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            if skip_level and level <= skip_level:
                skip_level = 0
            if match.group(2).strip().lower() in ignored:
                skip_level = level
            continue
        if skip_level:
            continue
        match = _ITEM_RE.match(line)
        if match:
            items.append(Item(number, match.group(1) != " ", match.group(2).strip()))

    return Parsed(pause_line, pause_reason, items)


def harden_streams():
    """Never crash on a console that cannot print a character (cp949, cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except Exception:
            pass


def warn(message):
    sys.stderr.write(message + "\n")


def read_hook_input():
    """Read the JSON object Claude Code sends on stdin. Empty dict if none."""
    stream = sys.stdin
    if stream is None:
        return {}
    try:
        if stream.isatty():
            return {}
        raw = stream.buffer.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw.decode("utf-8-sig", errors="replace"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def resolve_root(hook_input, explicit=None):
    """The folder relative checklist paths are read from."""
    if explicit:
        return os.path.abspath(explicit)
    for candidate in (os.environ.get("CLAUDE_PROJECT_DIR"), hook_input.get("cwd")):
        if candidate and os.path.isdir(candidate):
            return os.path.abspath(candidate)
    return os.getcwd()


def show_path(path):
    return path.replace("\\", "/")


def evaluate(path, display, ignore_headings=(), require_reason=True):
    """Read one checklist and say what it means for stopping.

    Returns a dict with "state" set to one of:
    missing, unreadable, paused, pause_without_reason, open, done.
    """
    result = {"display": display, "state": "done", "open": [], "total": 0,
              "pause_line": 0, "pause_reason": "", "error": ""}
    if not os.path.isfile(path):
        result["state"] = "missing"
        return result
    try:
        parsed = parse_checklist(read_text(path), ignore_headings)
    except OSError as exc:
        result["state"] = "unreadable"
        result["error"] = exc.__class__.__name__
        return result
    result["total"] = len(parsed.items)
    result["open"] = parsed.open_items
    result["pause_line"] = parsed.pause_line
    result["pause_reason"] = parsed.pause_reason
    if parsed.pause_line and (parsed.pause_reason or not require_reason):
        result["state"] = "paused"
    elif parsed.open_items:
        result["state"] = "pause_without_reason" if parsed.pause_line else "open"
    return result


def block_reason(result, extra_lines=()):
    """The text Claude reads when the stop is blocked."""
    display = result["display"]
    item = result["open"][0]
    lines = [
        "Checklist not finished: %d open item(s) in %s." % (len(result["open"]), display),
        "Next: %s:%d: %s" % (display, item.line, item.as_markdown()),
    ]
    if result["state"] == "pause_without_reason":
        lines.append(
            "%s:%d has a PAUSED line with no reason, so it does not count. "
            "Write the reason after the colon." % (display, result["pause_line"])
        )
    lines.extend(extra_lines)
    lines.append('Do that item, change it to "- [x]", then finish.')
    lines.append(
        'If it needs a person or cannot be done now, make the first line of %s '
        '"PAUSED: <reason> / human must do <what>" and finish.' % display
    )
    return "\n".join(lines)


def emit(payload):
    """Print a hook decision as ASCII-only JSON."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def print_check(results):
    """Human-readable report for --check. Returns the exit code."""
    failing = 0
    for result in results:
        state = result["state"]
        display = result["display"]
        if state == "missing":
            print("%s: not found" % display)
        elif state == "unreadable":
            print("%s: cannot be read (%s)" % (display, result["error"]))
        elif state == "paused":
            print("%s: PAUSED (%s), %d open item(s) left as they are"
                  % (display, result["pause_reason"] or "no reason given", len(result["open"])))
        elif state == "done":
            print("%s: done, %d of %d ticked" % (display, result["total"], result["total"]))
        else:
            failing += 1
            print("%s: %d open of %d" % (display, len(result["open"]), result["total"]))
            if state == "pause_without_reason":
                print("  %s:%d: PAUSED line has no reason" % (display, result["pause_line"]))
            for item in result["open"]:
                print("  %s:%d: %s" % (display, item.line, item.as_markdown()))
    return 1 if failing else 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="checklist_stop.py",
        description="Claude Code Stop hook: block the stop while a Markdown "
                    "checklist has open items.",
    )
    parser.add_argument("--file", help="checklist file (default: %s, or the %s "
                        "environment variable)" % (DEFAULT_FILE, ENV_FILE))
    parser.add_argument("--root", help="folder a relative --file is read from "
                        "(default: the project folder)")
    parser.add_argument("--check", action="store_true",
                        help="print the open items and exit 1 if any; for use "
                             "outside a hook")
    parser.add_argument("--version", action="version",
                        version="checklist-stop " + __version__)
    return parser


def run(args):
    hook_input = {} if args.check else read_hook_input()
    root = resolve_root(hook_input, args.root)
    configured = args.file or os.environ.get(ENV_FILE) or DEFAULT_FILE
    path = configured if os.path.isabs(configured) else os.path.join(root, configured)
    result = evaluate(path, show_path(configured))

    if args.check:
        return print_check([result])

    state = result["state"]
    if state == "missing":
        warn("checklist-stop: %s not found, nothing to enforce." % result["display"])
    elif state == "unreadable":
        warn("checklist-stop: %s cannot be read (%s), nothing to enforce."
             % (result["display"], result["error"]))
    elif state in ("open", "pause_without_reason"):
        emit({"decision": "block", "reason": block_reason(result)})
    return 0


def main(argv=None):
    harden_streams()
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except Exception as exc:  # a broken hook must never trap the session
        warn("checklist-stop: internal error (%s), letting the session stop."
             % exc.__class__.__name__)
        return 0


if __name__ == "__main__":
    sys.exit(main())
