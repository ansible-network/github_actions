#!/usr/bin/env python3
"""Script to update boto* library constraints aws hard-coded variable."""

from __future__ import annotations

import logging
import os
import re

from functools import partial
from pathlib import PosixPath


FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("update_aws_user_agent")
logger.setLevel(logging.DEBUG)

MIN_BOTOCORE_RE = re.compile(r"MINIMUM_BOTOCORE_VERSION( *)=( *)[\"|'][0-9\.]+[\"|']")
MIN_BOTO3_RE = re.compile(r"MINIMUM_BOTO3_VERSION( *)=( *)[\"|'][0-9\.]+[\"|']")
INCLUDE_RE = re.compile(r"^[ \t]*(?:-r|--requirement)[= \t]+(\S+)", re.MULTILINE)


def replace_vars(values: dict[str, str], line: str) -> str:
    """Replace a variable from a string.

    :param values: A dictionary of values to search into string.
    :param line: The string to replace values in.
    :returns: The updated string.
    """
    res = None
    for var, value in values.items():
        match = re.match(rf"^{var}([ =\"']*)[0-9\.]+(.*)", line)
        if match:
            res = var + match.group(1) + value + match.group(2)
            break
    return line if res is None else res


def update_single_file(path: str, values: dict[str, str]) -> None:
    """Update requirement file with boto3 and botocore constraints.

    :param path: The path to the file to update.
    :param values: dictionary of boto3 and botocore constraints
    """
    with open(path, encoding="utf-8") as file_read:
        content = file_read.read().split("\n")
    new_content = list(map(partial(replace_vars, values), content))
    if new_content != content:
        with open(path, "w", encoding="utf-8") as file_write:
            file_write.write("\n".join(new_content))
        logger.info("%s => updated", path)


def update_tests_constraints(boto3_version: str, botocore_version: str) -> None:
    """Update boto3 and botocore constraints from requirement file.

    :param boto3_version: The boto3 version to define.
    :param botocore_version: The boto core version to define.
    """
    boto_values = {"boto3": boto3_version, "botocore": botocore_version}
    for file in ("tests/unit/constraints.txt", "tests/integration/constraints.txt"):
        if PosixPath(file).exists():
            update_single_file(file, boto_values)

    min_boto_values = {
        "MINIMUM_BOTO3_VERSION": boto3_version,
        "MINIMUM_BOTOCORE_VERSION": botocore_version,
    }
    for root, _, files in os.walk("plugins"):
        for name in files:
            if not name.endswith(".py"):
                continue
            update_single_file(os.path.join(root, name), min_boto_values)


def read_requirements(path: PosixPath, seen: set[PosixPath] | None = None) -> str:
    """Read a requirements file, inlining any file it pulls in with -r/--requirement.

    Collections do not always declare the boto floors directly in
    requirements.txt; some only carry "-r meta/ee-requirements.txt" and keep the
    pins there. pip resolves an include relative to the directory of the file
    that contains it, so the same rule is applied here.

    :param path: The requirements file to read.
    :param seen: Files already read, used to stop include cycles.
    :returns: The content of the file concatenated with everything it includes.
    """
    already_read = set() if seen is None else seen
    resolved = PosixPath(os.path.abspath(path))
    if resolved in already_read or not path.is_file():
        return ""
    already_read.add(resolved)

    content = path.read_text(encoding="utf-8")
    for include in INCLUDE_RE.findall(content):
        content += "\n" + read_requirements(path.parent / include, already_read)
    return content


def read_boto_version() -> tuple[str, str]:
    """Read boto version constraints from requirement file.

    :returns: Tuple of boto3 and botocore version constraints
    :raises ValueError: If either version cannot be determined.
    """
    botocore_regex = re.compile(r"^botocore[>=<]+([0-9\.]+)", re.MULTILINE | re.IGNORECASE)
    boto3_regex = re.compile(r"^boto3[>=<]+([0-9\.]+)", re.MULTILINE | re.IGNORECASE)

    content = read_requirements(PosixPath("requirements.txt"))
    m_boto3 = boto3_regex.search(content)
    m_botocore = botocore_regex.search(content)

    # Returning "" here used to be silent, and the caller would then write the
    # empty string over every pin it found -- blanking out the constraints files
    # and turning MINIMUM_BOTOCORE_VERSION into "". Fail loudly instead.
    missing = [
        name for name, match in (("boto3", m_boto3), ("botocore", m_botocore)) if match is None
    ]
    if missing:
        raise ValueError(
            f"Could not determine the minimum version of {' and '.join(missing)} from "
            "requirements.txt or the files it includes. Refusing to continue, because "
            "writing an empty version would erase the existing constraints."
        )

    return m_boto3.group(1), m_botocore.group(1)  # type: ignore[union-attr]


def main() -> None:
    """Read boto constraints and update variables accordingly."""
    boto3_version, botocore_version = read_boto_version()
    logger.info("boto3='%s' - botocore='%s'", boto3_version, botocore_version)
    update_tests_constraints(boto3_version, botocore_version)


if __name__ == "__main__":
    main()
