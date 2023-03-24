#!/usr/bin/python

import argparse
import logging
import re
import subprocess
import sys
from collections import defaultdict
from typing import Any, Dict, Tuple, Union

import yaml

FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("validate_changelog")
logger.setLevel(logging.DEBUG)


def is_changelog_file(ref: str) -> bool:
    match = re.match(r"^changelogs/fragments/(.*)\.(yaml|yml)$", ref)
    return bool(match)


def is_module_or_plugin(ref: str) -> bool:
    prefix_list = (
        "plugins/modules",
        "plugins/action",
        "plugins/inventory",
        "plugins/lookup",
        "plugins/filter",
        "plugins/connection",
        "plugins/become",
        "plugins/cache",
        "plugins/callback",
        "plugins/cliconf",
        "plugins/httpapi",
        "plugins/netconf",
        "plugins/shell",
        "plugins/strategy",
        "plugins/terminal",
        "plugins/test",
        "plugins/vars",
    )
    return ref.startswith(prefix_list)


def is_documentation_file(ref: str) -> bool:
    prefix_list = (
        "docs/",
        "plugins/doc_fragments",
    )
    return ref.startswith(prefix_list)


def should_skip_changelog(changes: Dict[Any, Any]) -> bool:
    # Validate Pull request add new modules and plugins
    if any(is_module_or_plugin(x) for x in changes["A"]):
        return True

    # Validate documentation changes only
    all_files = changes["A"] + changes["M"] + changes["D"]
    if all(is_documentation_file(x) for x in all_files):
        return True

    return False


def is_valid_changelog_format(path: str) -> bool:
    try:
        # https://github.com/ansible-community/antsibull-changelog/blob/main/docs/changelogs.rst#changelog-fragment-categories
        changes_type = (
            "release_summary",
            "breaking_changes",
            "major_changes",
            "minor_changes",
            "removed_features",
            "deprecated_features",
            "security_fixes",
            "bugfixes",
            "known_issues",
            "trivial",
        )
        with open(path, "rb") as file_desc:
            result = list(yaml.safe_load_all(file_desc))

        for section in result:
            for key in section.keys():
                if key not in changes_type:
                    msg = f"{key} from {path} is not a valid changelog type"
                    logger.error(msg)
                    return False
                if not isinstance(section[key], list):
                    logger.error(
                        "Changelog section %s from file %s must be a list,"
                        " '%s' found instead.",
                        key,
                        path,
                        type(section[key]),
                    )
                    return False
        return True
    except (IOError, yaml.YAMLError) as exc:
        msg = f"yaml loading error for file {path} -> {exc}"
        logger.error(msg)
        return False


def run_command(cmd: str) -> Tuple[Union[int, Any], str, str]:
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        encoding="utf-8",
    ) as proc:
        out, err = proc.communicate()
        return proc.returncode, out, err


def list_files(ref: str) -> Dict[Any, Any]:
    command = "git diff origin/" + ref + " --name-status"
    logger.info("Executing -> %s", command)
    ret_code, stdout, stderr = run_command(command)
    if ret_code != 0:
        raise ValueError(stderr)

    changes = defaultdict(list)
    for file in stdout.split("\n"):
        file_attr = file.split("\t")
        if len(file_attr) == 2:
            changes[file_attr[0]].append(file_attr[1])
    logger.info("changes -> %s", changes)
    return changes


def main(ref: str) -> None:
    changes = list_files(ref)
    if changes:
        changelog = [x for x in changes["A"] if is_changelog_file(x)]
        logger.info("changelog files -> %s", changelog)
        if not changelog:
            if not should_skip_changelog(changes):
                logger.error(
                    "Missing changelog fragment. This is not required"
                    " only if PR adds new modules and plugins or contain"
                    " only documentation changes."
                )
                sys.exit(1)
            logger.info(
                "Changelog not required as PR adds new modules and/or"
                " plugins or contain only documentation changes."
            )
        else:
            invalid_changelog_files = [
                x for x in changelog if not is_valid_changelog_format(x)
            ]
            if invalid_changelog_files:
                logger.error(
                    "The following changelog files are not valid -> %s",
                    invalid_changelog_files,
                )
                sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate changelog file from new commit"
    )
    parser.add_argument("--ref", required=True, help="Pull request base ref")

    args = parser.parse_args()
    main(args.ref)
