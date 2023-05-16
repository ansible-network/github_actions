#!/usr/bin/env python3
"""Script to update galaxy file with release version."""

import logging
import os

from pathlib import PosixPath

import yaml


FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)


def main() -> None:
    """Update galaxy.yml file with release version."""
    release_version = os.environ.get("RELEASE_VERSION")
    collection_path = PosixPath(os.environ.get("COLLECTION_PATH") or ".")

    for extension in ("yml", "yaml"):
        file_name = "galaxy." + extension
        logger.info("checking file <%s> from directory <%s>", file_name, collection_path)
        if PosixPath(collection_path / file_name).exists():
            info = {}
            with PosixPath(collection_path / file_name).open(encoding="utf-8") as file_desc:
                info = yaml.safe_load(file_desc)
            if "version" in info and info.get("version") != release_version:
                info["version"] = release_version
                with PosixPath(collection_path / file_name).open(
                    "w", encoding="utf-8"
                ) as file_write:
                    file_write.write(yaml.dump(info, default_flow_style=False))
                logger.info("galaxy file <%s> updated.", file_name)
            else:
                logger.info(
                    "version match (or undefined) galaxy file version <%s>, expected <%s>",
                    info.get("version", ""),
                    release_version,
                )
            break
    else:
        logger.info("No galaxy.[yml|yaml] file was found / galaxy file has already been updated.")


if __name__ == "__main__":
    main()
