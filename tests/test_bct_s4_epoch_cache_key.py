"""Prevent literal cache-key shell variables from blocking CPU runtime restore."""
from pathlib import Path

def test_pinned_cpu_cache_key_shell_interpolation_is_not_escaped():
    data=(Path(__file__).resolve().parents[1]/
          ".github/workflows/bct-s4-epoch-cpu-manual.yml").read_text()
    line=next(x for x in data.splitlines() if 'echo "key=v4-cpu-runtime-' in x)
    assert 'key=v4-cpu-runtime-' in line
    for variable in ("RUNNER_OS","RUNNER_ARCH","PYTHON_VERSION","LOCK_SHA"):
        assert '+variable+' in line
        assert chr(92)+'+variable+' not in line
    assert "fail-on-cache-miss: true" in data
    assert "BCT_V4_PRIVATE_STATE_TOKEN" not in data.split("  research:",1)[1].split("  publish:",1)[0]
