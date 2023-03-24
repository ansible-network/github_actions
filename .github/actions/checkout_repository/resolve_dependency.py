#!/usr/bin/python

import logging
import os
import re
import sys
from typing import Any

from github import Github

FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("resolve_dependency")
logger.setLevel(logging.DEBUG)


def get_pr_merge_commit_sha(repository: str, pr_number: int) -> Any:
    access_token = os.environ.get("GITHUB_TOKEN")
    gh_obj = Github(access_token)
    repo = gh_obj.get_repo(repository)

    pr_obj = repo.get_pull(pr_number)
    if not pr_obj.mergeable:
        # raise an error when the pull request is not mergeable
        sys.tracebacklimit = -1
        raise ValueError(f"Pull request {pr_number} from {repository} is not mergeable")

    return pr_obj.merge_commit_sha


def resolve_ref(pr_body: str, repository: str) -> int:
    pr_regx = re.compile(
        rf"^Depends-On:[ ]*https://github.com/{repository}/pull/(\d+)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    # Search for expression starting with depends-on not case-sensitive
    match = pr_regx.findall(pr_body)
    return int(match[0]) if match else 0


def main() -> None:
    pr_body = os.environ.get("RESOLVE_REF_PR_BODY") or ""
    repository = os.environ.get("RESOLVE_REF_REPOSITORY") or ""

    if not repository:
        return

    pr_number = resolve_ref(pr_body, repository)
    if not pr_number:
        return
    logger.info("Override checkout with pr number: %d", pr_number)

    # get pull request merge commit sha
    merge_commit_sha = get_pr_merge_commit_sha(repository, pr_number)
    logger.info(
        "merge commit sha for pull request %d => '%s'", pr_number, merge_commit_sha
    )
    gh_output = str(os.environ.get("GITHUB_OUTPUT"))
    with open(gh_output, "a", encoding="utf-8") as file_handler:
        file_handler.write(f"merge_commit_sha={merge_commit_sha}\n")


if __name__ == "__main__":
    main()
