import importlib.util
from pathlib import Path
import stat
import zipfile
import pytest

spec = importlib.util.spec_from_file_location('operating_restore',
    Path(__file__).parents[1]/'.github/scripts/bct_restore_operating_state.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('name', ['../old-checkpoint.json', '/absolute', 'a\\b'])
def test_archive_cannot_escape_or_alias_the_restore_directory(tmp_path, name):
    archive = tmp_path/'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr(name, b'bytes')
    with pytest.raises(ValueError, match='unsafe'):
        module.unpack(archive, tmp_path/'restored')
    assert not (tmp_path/'restored').exists()


def test_normalized_alias_and_symlink_are_rejected_before_writing(tmp_path):
    archive = tmp_path/'aliases.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr('safe/file.txt', b'original')
        stream.writestr('safe/./file.txt', b'overwrite')
    with pytest.raises(ValueError, match='duplicate'):
        module.unpack(archive, tmp_path/'restored')
    with zipfile.ZipFile(archive, 'w') as stream:
        entry = zipfile.ZipInfo('link')
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        stream.writestr(entry, b'/existing/cache')
    with pytest.raises(ValueError, match='unsafe'):
        module.unpack(archive, tmp_path/'restored')


def test_restore_never_overwrites_an_existing_checkpoint(tmp_path):
    archive = tmp_path/'valid.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr('checkpoint.json', b'new')
    target = tmp_path/'restored'
    target.mkdir()
    (target/'checkpoint.json').write_bytes(b'preserved')
    with pytest.raises(ValueError, match='empty'):
        module.unpack(archive, target)
    assert (target/'checkpoint.json').read_bytes() == b'preserved'


def test_signed_download_redirect_does_not_forward_authenticated_request():
    assert module.NoRedirect().redirect_request(None, None, 302, '', {},
        'https://storage.blob.core.windows.net/signed') is None
