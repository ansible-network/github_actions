#!/usr/bin/env python3
"""Executable used to add backport labels to Github issues."""

import argparse
import os
import re
import sys

import requests


class RequestError(Exception):
    """An exception class."""


def main() -> None:
    """Perform operations.

    :raises RequestError: In case an error occurs when calling requests API.
    """
    parser = argparse.ArgumentParser(description="Ensure an issue contains the backport labels.")
    parser.add_argument("--issue-id", type=int, required=True, help="The pull request number.")
    parser.add_argument(
        "--repository",
        type=str,
        required=True,
        help="The Github project name, e.g: 'ansible-collections/amazon.aws'.",
    )
    args = parser.parse_args(sys.argv[1:])
    # Get list of labels attached to the pull requests
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Get PR Labels
    response = requests.get(
        f"https://api.github.com/repos/{args.repository}/issues/{args.issue_id}/labels",
        headers=headers,
        timeout=30,
    )
    if not response.ok:
        raise RequestError(response.reason)
    issue_backport_labels = [
        i["name"] for i in response.json() if re.match("^backport-[0-9]*$", i["name"])
    ]

    # Get Repository Labels
    response = requests.get(
        f"https://api.github.com/repos/{args.repository}/labels",
        headers=headers,
        timeout=30,
    )
    if not response.ok:
        raise RequestError(response.reason)
    repository_backport_labels = [
        i["name"] for i in response.json() if re.match("^backport-[0-9]*$", i["name"])
    ]

    labels_to_add = list(set(repository_backport_labels) - set(issue_backport_labels))
    if labels_to_add:
        data = {"labels": labels_to_add}
        response = requests.post(
            f"https://api.github.com/repos/{args.repository}/issues/{args.issue_id}/labels",
            headers=headers,
            json=data,
            timeout=30,
        )
        if not response.ok:
            raise RequestError(response.reason)


if __name__ == "__main__":
    main()
