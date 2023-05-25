#!/usr/bin/env python3
"""Script to update boto* library constraints aws hard-coded variable."""

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


def replace_vars(values: dict[str, str], line: str) -> str:
    """Replace a variable from a string.

    :param values: A dictionary of values to search into strin.
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


def read_boto_version() -> tuple[str, str]:
    """Read boto version constraints from requirement file.

    :returns: Tuple of boto3 and botocore version constraints
    """
    botocore_regex = re.compile(r"^botocore[>=<]+([0-9\.]+)", re.MULTILINE | re.IGNORECASE)
    boto3_regex = re.compile(r"^boto3[>=<]+([0-9\.]+)", re.MULTILINE | re.IGNORECASE)

    with PosixPath("requirements.txt").open(encoding="utf-8") as file_desc:
        content = file_desc.read()
        m_boto3 = boto3_regex.search(content)
        m_botocore = botocore_regex.search(content)
        return m_boto3.group(1) if m_boto3 else "", m_botocore.group(1) if m_botocore else ""


def main() -> None:
    """Read boto constraints and update variables accordingly."""
    boto3_version, botocore_version = read_boto_version()
    logger.info("boto3='%s' - botocore='%s'", boto3_version, botocore_version)
    update_tests_constraints(boto3_version, botocore_version)


if __name__ == "__main__":
    main()
