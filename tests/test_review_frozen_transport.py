"""Only byte-preserving formatting drift may use the activated transport."""
import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location('frozen_review',
    Path('.github/scripts/review_shadow_frozen.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_ast_accepts_semicolon_and_line_break_formatting():
    assert module.executable_ast(b'a=None;b=None\n') == module.executable_ast(b'a=None\nb=None\n')


def test_ast_accepts_only_the_known_unused_transport_import():
    assert module.executable_ast(b'from datetime import datetime, timezone\na=1\n', transport=True) == module.executable_ast(b'a=1\n', transport=True)
    assert module.executable_ast(b'from datetime import date\na=1\n', transport=True) != module.executable_ast(b'a=1\n', transport=True)


def test_ast_rejects_actual_judgment_or_literal_changes():
    assert module.executable_ast(b'if good: status="HOLD"\n') != module.executable_ast(b'if good: status="PASS"\n')
