"""Only the public, pure byte-count parser is tested. No private token."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location("cpu_storage_cap_audit",
    Path(__file__).resolve().parents[1]/"tools/bct_s4_private_storage_capacity.py")
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_exact_git_object_raw_bytes_including_history():
    ids=["a"*40,"b"*40,"c"*40,"d"*40]
    raw="\n".join([ids[0]+" commit 340",ids[1]+" tree 200",
                   ids[2]+" blob 5900000",ids[3]+" blob 5900000"])
    answer=audit.parse_object_sizes(raw,expected=4)
    assert answer["history_unique_object_bytes"]==11800540
    assert answer["objects"]=={"commit":1,"tree":1,"blob":2}
    assert answer["type_bytes"]["blob"]==11800000


@pytest.mark.parametrize("value,expected",[
    ("a"*40+" blob 19\n"+"a"*40+" blob 19",2),
    ("b"*40+" blob 19",2),
    ("a"*40+" blob -5",1),
    ("a"*40+" secret 100",1),
    ("malformed size here",1),
])
def test_reject_corrupt_incomplete_or_duplicated_git_size_report(value,expected):
    with pytest.raises(ValueError):
        audit.parse_object_sizes(value,expected)


def test_history_limit_not_redefined_or_disabled():
    assert audit.CAP==64*1024*1024
    assert audit.EXPECTED_HEAD=="8493ce906aea1c4ef14693873ba016e708d30245"
    assert audit.ARCHIVE_REF.startswith("refs/heads/archive/")
    assert audit.CURRENT_REF!=audit.ARCHIVE_REF
