#!/usr/bin/python

import argparse
import logging
import re
import subprocess
import sys
from collections import defaultdict

import yaml

FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("validate_changelog")
logger.setLevel(logging.DEBUG)


def is_valid_change_log(ref):
    return re.match(r"^changelogs/fragments/(.*)\.(yaml|yml)$", ref)



def is_module_or_plugin(ref):
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


def is_documentation_file(ref):
    prefix_list = (
        "docs/",
        "plugins/doc_fragments",
    )
    return ref.startswith(prefix_list)


def is_added_module_or_plugin_or_documentation_changes(changes):
    # Validate Pull request add new modules and plugins
    if any([is_module_or_plugin(x) for x in changes["A"]]):
        return True

    # Validate documentation changes only
    all_files = changes["A"] + changes["M"] + changes["D"]
    if all([is_documentation_file(x) for x in all_files]):
        return True

    return False


def validate_changelog(path):
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
        with open(path, "rb") as f:
            result = list(yaml.safe_load_all(f))

        for section in result:
            for key in section.keys():
                if key not in changes_type:
                    msg = f"{key} from {path} is not a valid changelog type"
                    logger.error(msg)
                    return False
                if not isinstance(section[key], list):
                    logger.error(
                        "Changelog section {0} from file {1} must be a list,"
                        " {2} found instead.".format(
                            key,
                            path,
                            type(section[key]),
                        )
                    )
                    return False
        return True
    except (IOError, yaml.YAMLError) as exc:
        msg = "yaml loading error for file {0} -> {1}".format(path, exc)
        logger.error(msg)
        return False


def run_command(cmd):
    params = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    proc = subprocess.Popen(cmd, **params)
    out, err = proc.communicate()
    return proc.returncode, out, err


def list_files(head_ref, base_ref):
    cmd = "git diff origin/{0} {1} --name-status".format(base_ref, head_ref)
    logger.info("Executing '{0}'".format(cmd))
    rc, stdout, stderr = run_command(cmd)
    if rc != 0:
        raise ValueError(stderr)

    changes = defaultdict(list)
    for file in stdout.decode("utf-8").split("\n"):
        v = file.split("\t")
        if len(v) == 2:
            changes[v[0]].append(v[1])
    return changes


def main(head_ref, base_ref):

def main(head_ref, base_ref):
    changes = list_files(head_ref, base_ref)
    if changes:
        changelog = [x for x in changes["A"] if is_valid_change_log(x)]
        if not changelog:
            if not is_added_module_or_plugin_or_documentation_changes(changes):
                print(
                    "Missing changelog fragment. This is not required"
                    " only if PR adds new modules and plugins or contain"
                    " only documentation changes."
                )
                sys.exit(1)
            print(
                "Changelog not required as PR adds new modules and/or"
                " plugins or contain only documentation changes."
            )
        elif any(not validate_changelog(f) for f in changelog):
            sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate changelog file from new commit"
    )
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)

    args = parser.parse_args()
    main(args.head_ref, args.base_ref)
