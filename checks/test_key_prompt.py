"""Verify the optional hidden-input launcher without credentials or network access."""
from contextlib import redirect_stdout
from io import StringIO
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import start_with_ai as launcher


class KeyPromptTests(unittest.TestCase):
    def test_no_terminal_never_prompts_or_starts(self):
        with patch('sys.stdin.isatty', return_value=False), patch('getpass.getpass') as prompt:
            with self.assertRaises(SystemExit):
                launcher.main()
            prompt.assert_not_called()

    def test_keys_are_process_only_and_never_printed(self):
        fake = SimpleNamespace(run=Mock())
        output = StringIO()
        with (patch('sys.stdin.isatty', return_value=True), patch('os.chdir'),
              patch('pathlib.Path.is_file', return_value=True), patch.dict('sys.modules', uvicorn=fake),
              patch.dict('os.environ', {'OPENAI_API_KEY': 'existing-demo-only'}, clear=True),
              patch('getpass.getpass', side_effect=['', ' fictitious-example-value ']), redirect_stdout(output)):
            launcher.main()
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'existing-demo-only')
            self.assertEqual(os.environ['ANTHROPIC_API_KEY'], 'fictitious-example-value')
            fake.run.assert_called_once_with('backend.app:app', host='127.0.0.1', port=8000, proxy_headers=False)
        self.assertNotIn('existing-demo-only', output.getvalue())
        self.assertNotIn('fictitious-example-value', output.getvalue())

    def test_unavailable_hidden_prompt_aborts(self):
        import getpass
        fake = SimpleNamespace(run=Mock())
        with (patch('sys.stdin.isatty', return_value=True), patch('os.chdir'),
              patch('pathlib.Path.is_file', return_value=True), patch.dict('sys.modules', uvicorn=fake),
              patch('getpass.getpass', side_effect=getpass.GetPassWarning), redirect_stdout(StringIO())):
            with self.assertRaises(SystemExit):
                launcher.main()
            fake.run.assert_not_called()
