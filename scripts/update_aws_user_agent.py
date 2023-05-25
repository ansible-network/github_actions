#!/usr/bin/env python3
"""Script to update aws hard-coded user agent variable with value from galaxy.yml."""

import logging
import re

from pathlib import PosixPath

import yaml


FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("update_aws_user_agent")
logger.setLevel(logging.DEBUG)


def update_user_agent(src: PosixPath, var_name: str, galaxy_version: str) -> bool:
    """Update aws user agent variable from file passed in input.

    :param src: The path to the file to search variable in.
    :param var_name: The name of the variable to update
    :param galaxy_version: The collection version stored into galaxy.yml
    :returns: Whether the variable has been updated
    """
    variable_regex = rf"^{var_name} = [\"|'](.*)[\"|']"
    new_content = []
    updated = False
    logger.info("********** Parsing file => %s *************", src)
    with src.open() as file_handler:
        for line in file_handler.read().split("\n"):
            match = re.match(variable_regex, line)
            if match and match.group(1) != galaxy_version:
                logger.info("Match variable [%s] with value [%s]", var_name, match.group(1))
                updated = True
                new_content.append(f'{var_name} = "{galaxy_version}"')
            else:
                new_content.append(line)

    if updated:
        src.write_text("\n".join(new_content))
    return updated


def update_collection_user_agent(var_name: str, galaxy_version: str) -> bool:
    """Update aws variable name with value provided as input.

    :param var_name: The name of the variable to update
    :param galaxy_version: The collection version stored into galaxy.yml
    :returns: Whether the variable has been updated somewhere
    """

    def _get_files_from_directory(path: PosixPath) -> list[PosixPath]:
        if not path.is_dir():
            return [path]
        result = []
        for child in path.iterdir():
            result.extend(_get_files_from_directory(child))
        return result

    return any(
        update_user_agent(src, var_name, galaxy_version)
        for src in _get_files_from_directory(PosixPath("plugins"))
        if str(src).endswith(".py")
    )


def main() -> None:
    """Read collection info and update aws user agent if needed."""
    # Read collection information from galaxy.yml
    collection_info = {}
    with PosixPath("galaxy.yml").open(encoding="utf-8") as file_desc:
        collection_info = yaml.safe_load(file_desc)
    logger.info("collection information from galaxy.yml: %s", collection_info)
    variable_name = (
        collection_info["namespace"].upper()
        + "_"
        + collection_info["name"].upper()
        + "_COLLECTION_VERSION"
    )
    logger.info("Expecting collection user-agent variable => '%s'", variable_name)

    galaxy_version = collection_info["version"]
    update_collection_user_agent(variable_name, galaxy_version)


if __name__ == "__main__":
    main()
