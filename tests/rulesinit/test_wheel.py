import subprocess
import typing
import zipfile

import auditor.rulesinit

if typing.TYPE_CHECKING:
    import pathlib


def test_the_wheel_holds_the_catalogue(tmp_path: pathlib.Path) -> None:
    root = auditor.rulesinit.catalogue_root().parents[2]
    subprocess.run(['uv', 'build', '--wheel', '--out-dir', str(tmp_path)], cwd=root, check=True, capture_output=True)  # noqa: S607
    wheels = sorted(tmp_path.glob('*.whl'))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())
    assert 'auditor/catalogue/packs.toml' in names
    for directory in sorted((auditor.rulesinit.catalogue_root() / 'rules').iterdir()):
        if directory.is_dir():
            assert f'auditor/catalogue/rules/{directory.name}/rule.toml' in names
