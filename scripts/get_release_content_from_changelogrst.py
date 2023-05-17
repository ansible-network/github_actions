#!/usr/bin/env python3
"""Script to read release content from CHANGELOG.rst file."""

import logging
import re

from argparse import ArgumentParser
from pathlib import PosixPath


FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)


def main() -> None:
    """Read release content from CHANGELOG.rst for a specific version."""
    parser = ArgumentParser(
        description="Read release content from CHANGELOG.rst for a specific version."
    )
    parser.add_argument("-r", "--release-version", required=True, help="Release version to parse.")

    args = parser.parse_args()
    if not PosixPath("CHANGELOG.rst").exists():
        logger.error("CHANGELOG.rst does not exist.")
        return

    release_version = args.release_version
    with PosixPath("CHANGELOG.rst").open(encoding="utf-8") as file_write:
        data = file_write.read().splitlines()
        idx = 0
        start, end = -1, 0
        while idx < len(data):
            if data[idx].startswith(f"v{release_version}") and data[idx + 1] == "======":
                start = idx + 2
                idx += 2
            elif (
                start > 0
                and re.match(r"^v[0-9]+\.[0-9]+\.[0-9]+$", data[idx])
                and data[idx + 1] == "======"
            ):
                end = idx
                break
            idx += 1
        if start != -1:
            release_content = "\n".join(data[start:]) if not end else "\n".join(data[start:end])
            logger.info(
                "[%s] ******** Release content ********\n%s", release_version, release_content
            )
            release_content = "\n".join(data[start:end])
            with open("release_content.txt", "w", encoding="utf-8") as file_write:
                file_write.write(release_content)


if __name__ == "__main__":
    main()
