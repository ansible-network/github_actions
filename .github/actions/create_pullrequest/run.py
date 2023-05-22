#!/usr/bin/env python3
"""Script to read release content from CHANGELOG.rst file."""

import logging
import os
import sys

from argparse import ArgumentParser

from github import Github
from github import GithubException


FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)


def main() -> None:
    """Read release content from CHANGELOG.rst for a specific version."""
    parser = ArgumentParser(
        description="Read release content from CHANGELOG.rst for a specific version."
    )
    parser.add_argument("--repository", required=True, help="Repository name.")
    parser.add_argument("--head", required=True, help="Pull request head branch.")
    parser.add_argument("--base", required=True, help="Pull request base branch.")
    parser.add_argument("--title", required=True, help="Pull request title.")
    parser.add_argument("--body", required=True, help="Pull request body.")

    args = parser.parse_args()

    access_token = os.environ.get("GITHUB_TOKEN")

    client = Github(access_token)
    repo = client.get_repo(args.repository)
    try:
        pr_obj = repo.create_pull(title=args.title, body=args.body, head=args.head, base=args.base)
    except GithubException as err:
        logger.error("Failed to create pull request due to: %s", err)
        sys.exit(1)

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as file_handler:
            file_handler.write(f"url={pr_obj.html_url}\n")
            file_handler.write(f"number={pr_obj.number}\n")


if __name__ == "__main__":
    main()
