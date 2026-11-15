"""Tests for checklist_stop.py. Run: python -m unittest discover -s tests -v"""
import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
SCRIPT = os.path.join(PACKAGE, "checklist_stop.py")
sys.path.insert(0, PACKAGE)

import checklist_stop as cs  # noqa: E402


class HookCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cls test ")
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, name, text, encoding="utf-8", newline="\n"):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding=encoding, newline=newline) as handle:
            handle.write(text)
        return path

    def run_script(self, args=(), payload=None, env=None, raw_input=None, cwd=None):
        if raw_input is None:
            if payload is None:
                payload = {"hook_event_name": "Stop", "cwd": self.root,
                           "session_id": "s1", "stop_hook_active": False}
            raw_input = json.dumps(payload).encode("utf-8")
        environ = dict(os.environ)
        for name in ("CLAUDE_PROJECT_DIR", "CHECKLIST_STOP_FILE", "PYTHONIOENCODING",
                     "PYTHONUTF8"):
            environ.pop(name, None)
        if sys.flags.utf8_mode:  # keep the child in the same mode as this process
            environ["PYTHONUTF8"] = "1"
        environ.update(env or {})
        proc = subprocess.run([sys.executable, SCRIPT] + list(args), input=raw_input,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=cwd or self.root, env=environ)
        encoding = environ.get("PYTHONIOENCODING") or locale.getpreferredencoding(False)
        return (proc.returncode, proc.stdout.decode(encoding, "replace"),
                proc.stderr.decode(encoding, "replace"))

    def decision(self, stdout):
        self.assertTrue(stdout.strip(), "expected a hook decision on stdout")
        return json.loads(stdout)


class BlockAndPass(HookCase):
    def test_open_item_blocks_with_path_and_line(self):
        self.write("PROGRESS.md", "# Plan\n\n- [x] one\n- [ ] two\n- [ ] three\n")
        code, out, err = self.run_script()
        self.assertEqual(code, 0)
        data = self.decision(out)
        self.assertEqual(data["decision"], "block")
        self.assertIn("PROGRESS.md:4: - [ ] two", data["reason"])
        self.assertIn("2 open item(s) in PROGRESS.md", data["reason"])
        self.assertNotIn("three", data["reason"])

    def test_all_ticked_passes_silently(self):
        self.write("PROGRESS.md", "- [x] one\n- [X] two\n")
        code, out, err = self.run_script()
        self.assertEqual((code, out, err), (0, "", ""))

    def test_no_checkboxes_passes(self):
        self.write("PROGRESS.md", "# Notes\n\nNothing to do.\n")
        self.assertEqual(self.run_script()[:2], (0, ""))

    def test_empty_file_passes(self):
        self.write("PROGRESS.md", "")
        self.assertEqual(self.run_script()[:2], (0, ""))

    def test_missing_file_passes_with_one_warning_line(self):
        code, out, err = self.run_script()
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("PROGRESS.md not found", err)

    def test_stop_hook_active_still_blocks(self):
        self.write("PROGRESS.md", "- [ ] one\n")
        payload = {"cwd": self.root, "stop_hook_active": True}
        self.assertEqual(self.decision(self.run_script(payload=payload)[1])["decision"],
                         "block")

    def test_reason_tells_how_to_pause(self):
        self.write("PROGRESS.md", "- [ ] one\n")
        reason = self.decision(self.run_script()[1])["reason"]
        self.assertIn("PAUSED: <reason>", reason)


class Paused(HookCase):
    def test_paused_with_reason_passes(self):
        self.write("PROGRESS.md", "PAUSED: waiting for the API key / human must add it\n\n- [ ] one\n")
        self.assertEqual(self.run_script(), (0, "", ""))

    def test_paused_after_blank_lines_and_as_heading(self):
        self.write("PROGRESS.md", "\n\n# paused: blocked on review\n- [ ] one\n")
        self.assertEqual(self.run_script()[:2], (0, ""))

    def test_paused_without_reason_does_not_count(self):
        self.write("PROGRESS.md", "PAUSED:\n- [ ] one\n")
        reason = self.decision(self.run_script()[1])["reason"]
        self.assertIn("PROGRESS.md:1 has a PAUSED line with no reason", reason)
        self.assertIn("PROGRESS.md:2: - [ ] one", reason)

    def test_paused_lower_in_the_file_does_not_count(self):
        self.write("PROGRESS.md", "# Plan\nPAUSED: nope\n- [ ] one\n")
        self.assertEqual(self.decision(self.run_script()[1])["decision"], "block")

    def test_paused_word_inside_a_sentence_does_not_count(self):
        self.write("PROGRESS.md", "This was PAUSED: yesterday\n- [ ] one\n")
        self.assertEqual(self.decision(self.run_script()[1])["decision"], "block")


class Parsing(HookCase):
    def test_boxes_in_code_fences_are_not_counted(self):
        self.write("PROGRESS.md", "\n".join([
            "- [x] real",
            "```markdown",
            "- [ ] example in backticks",
            "```",
            "~~~",
            "- [ ] example in tildes",
            "~~~",
            "````",
            "```",
            "- [ ] nested example",
            "```",
            "````",
            "  ```",
            "  - [ ] indented fence",
            "  ```",
            "",
        ]))
        self.assertEqual(self.run_script()[:2], (0, ""))

    def test_unclosed_fence_hides_the_rest(self):
        parsed = cs.parse_checklist("- [ ] a\n```\n- [ ] b\n- [ ] c\n")
        self.assertEqual([item.line for item in parsed.open_items], [1])

    def test_box_after_a_closed_fence_counts(self):
        self.write("PROGRESS.md", "```\n- [ ] example\n```\n- [ ] real\n")
        self.assertIn("PROGRESS.md:4:", self.decision(self.run_script()[1])["reason"])

    def test_html_comments_are_not_counted(self):
        self.write("PROGRESS.md", "<!-- - [ ] one line -->\n<!--\n- [ ] hidden\n-->\n- [x] done\n")
        self.assertEqual(self.run_script()[:2], (0, ""))

    def test_bom_and_crlf(self):
        self.write("PROGRESS.md", "﻿# Plan\r\n- [x] one\r\n- [ ] two\r\n", newline="")
        reason = self.decision(self.run_script()[1])["reason"]
        self.assertIn("PROGRESS.md:3: - [ ] two", reason)
        self.assertNotIn("\r", reason)

    def test_bom_before_paused(self):
        self.write("PROGRESS.md", "﻿PAUSED: on hold\r\n- [ ] one\r\n", newline="")
        self.assertEqual(self.run_script()[:2], (0, ""))

    def test_utf16_file(self):
        self.write("PROGRESS.md", "- [x] one\n- [ ] two\n", encoding="utf-16")
        self.assertIn("PROGRESS.md:2:", self.decision(self.run_script()[1])["reason"])

    def test_list_styles(self):
        text = "\n".join([
            "* [ ] star", "+ [ ] plus", "1. [ ] numbered", "2) [ ] paren",
            "    - [ ] nested", "> - [ ] quoted", "- [ ]", "- [x] done",
        ])
        parsed = cs.parse_checklist(text)
        self.assertEqual([item.line for item in parsed.open_items], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(parsed.open_items[6].text, "")

    def test_things_that_are_not_checkboxes(self):
        text = "\n".join([
            "- [] no space", "- [ ]glued", "[ ] no bullet", "- [?] other mark",
            "text - [ ] mid line", "-[ ] no gap", "- [ x] wide",
        ])
        self.assertEqual(cs.parse_checklist(text).items, [])

    def test_ignore_headings(self):
        text = "# Plan\n- [x] a\n## Later\n- [ ] b\n### Sub\n- [ ] c\n## Now\n- [ ] d\n"
        parsed = cs.parse_checklist(text, ["later"])
        self.assertEqual([item.line for item in parsed.open_items], [8])

    def test_korean_text_is_ascii_json(self):
        self.write("PROGRESS.md", "- [ ] 시험을 작성한다 ✅\n")
        code, out, err = self.run_script()
        out.encode("ascii")
        self.assertIn("시험을 작성한다 ✅", json.loads(out)["reason"])


class Options(HookCase):
    def test_file_option_with_spaces_and_korean(self):
        self.write("할 일/진행 목록.md", "- [ ] 하나\n")
        reason = self.decision(self.run_script(["--file", "할 일/진행 목록.md"])[1])["reason"]
        self.assertIn("할 일/진행 목록.md:1:", reason)

    def test_environment_variable(self):
        self.write("TODO.md", "- [ ] one\n")
        out = self.run_script(env={"CHECKLIST_STOP_FILE": "TODO.md"})[1]
        self.assertIn("TODO.md:1:", self.decision(out)["reason"])

    def test_project_dir_wins_over_cwd(self):
        self.write("PROGRESS.md", "- [ ] root item\n")
        sub = os.path.join(self.root, "sub")
        os.makedirs(sub)
        payload = {"cwd": sub}
        out = self.run_script(payload=payload, env={"CLAUDE_PROJECT_DIR": self.root},
                              cwd=sub)[1]
        self.assertIn("root item", self.decision(out)["reason"])

    def test_garbage_input_falls_back_to_current_folder(self):
        self.write("PROGRESS.md", "- [ ] one\n")
        out = self.run_script(raw_input=b"not json at all")[1]
        self.assertEqual(self.decision(out)["decision"], "block")

    def test_empty_input(self):
        self.write("PROGRESS.md", "- [ ] one\n")
        self.assertEqual(self.decision(self.run_script(raw_input=b"")[1])["decision"], "block")

    def test_check_mode(self):
        self.write("PROGRESS.md", "- [x] one\n- [ ] two\n")
        code, out, err = self.run_script(["--check"])
        self.assertEqual(code, 1)
        self.assertIn("PROGRESS.md: 1 open of 2", out)
        self.assertIn("PROGRESS.md:2: - [ ] two", out)
        self.write("PROGRESS.md", "- [x] one\n- [x] two\n")
        code, out, err = self.run_script(["--check"])
        self.assertEqual(code, 0)
        self.assertIn("done, 2 of 2 ticked", out)

    def test_check_mode_on_a_cp949_console(self):
        self.write("PROGRESS.md", "- [ ] café ✅ 한글\n")
        code, out, err = self.run_script(["--check"], env={"PYTHONIOENCODING": "cp949"})
        self.assertEqual(code, 1)
        self.assertIn("한글", out)
        self.assertNotIn("Traceback", err)

    def test_version(self):
        code, out, err = self.run_script(["--version"])
        self.assertEqual(code, 0)
        self.assertIn(cs.__version__, out)


if __name__ == "__main__":
    unittest.main()
