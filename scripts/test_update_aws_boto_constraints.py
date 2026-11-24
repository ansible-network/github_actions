#!/usr/bin/env python3
"""Module used to test update_aws_boto_constraints.py script."""

from pathlib import Path
from pathlib import PosixPath

import pytest

from update_aws_boto_constraints import read_boto_version
from update_aws_boto_constraints import read_requirements


def test_read_boto_version_direct_pins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Read the floors when requirements.txt declares them itself.

    :param tmp_path: Temporary directory provided by pytest.
    :param monkeypatch: Fixture used to change the working directory.
    """
    (tmp_path / "requirements.txt").write_text("botocore>=1.31.0\nboto3>=1.28.0\n")
    monkeypatch.chdir(tmp_path)

    assert read_boto_version() == ("1.28.0", "1.31.0")


def test_read_boto_version_follows_include(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Read the floors from a file pulled in with -r.

    amazon.aws keeps only "-r meta/ee-requirements.txt" in requirements.txt and
    declares the pins in that included file.

    :param tmp_path: Temporary directory provided by pytest.
    :param monkeypatch: Fixture used to change the working directory.
    """
    (tmp_path / "meta").mkdir()
    (tmp_path / "meta" / "ee-requirements.txt").write_text("botocore>=1.38.23\nboto3>=1.38.23\n")
    (tmp_path / "requirements.txt").write_text("-r meta/ee-requirements.txt\n")
    monkeypatch.chdir(tmp_path)

    assert read_boto_version() == ("1.38.23", "1.38.23")


def test_read_requirements_resolves_nested_includes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolve an include relative to the file that declares it, as pip does.

    :param tmp_path: Temporary directory provided by pytest.
    :param monkeypatch: Fixture used to change the working directory.
    """
    (tmp_path / "meta").mkdir()
    (tmp_path / "meta" / "base.txt").write_text("botocore>=1.38.23\n")
    (tmp_path / "meta" / "ee-requirements.txt").write_text("-r base.txt\nboto3>=1.38.23\n")
    (tmp_path / "requirements.txt").write_text("-r meta/ee-requirements.txt\n")
    monkeypatch.chdir(tmp_path)

    content = read_requirements(PosixPath("requirements.txt"))

    assert "botocore>=1.38.23" in content
    assert "boto3>=1.38.23" in content


def test_read_requirements_stops_on_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return instead of recursing forever when two files include each other.

    :param tmp_path: Temporary directory provided by pytest.
    :param monkeypatch: Fixture used to change the working directory.
    """
    (tmp_path / "requirements.txt").write_text("-r other.txt\nboto3>=1.28.0\n")
    (tmp_path / "other.txt").write_text("-r requirements.txt\nbotocore>=1.31.0\n")
    monkeypatch.chdir(tmp_path)

    assert read_boto_version() == ("1.28.0", "1.31.0")


@pytest.mark.parametrize(
    "content",
    [
        "",
        "# no pins here\n",
        "boto3>=1.28.0\n",
        "botocore>=1.31.0\n",
        "-r meta/ee-requirements.txt\n",
    ],
)
def test_read_boto_version_raises_when_missing(
    content: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail loudly rather than reporting an empty version.

    Returning "" made the caller overwrite every pin it could find with the
    empty string, blanking out the constraints files and turning
    MINIMUM_BOTOCORE_VERSION into "".

    :param content: requirements.txt content missing at least one floor.
    :param tmp_path: Temporary directory provided by pytest.
    :param monkeypatch: Fixture used to change the working directory.
    """
    (tmp_path / "requirements.txt").write_text(content)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="Could not determine the minimum version"):
        read_boto_version()
