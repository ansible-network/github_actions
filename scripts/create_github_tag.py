#!/usr/bin/env python3
"""Script to create tag on github repository."""

import logging
import os

from argparse import ArgumentParser

from github import Github


FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("compute_release_version")
logger.setLevel(logging.DEBUG)


def main() -> None:
    """Create tag and publish to Github repository."""
    parser = ArgumentParser(
        description="Create tag to Github repository and pull request to default branch."
    )
    parser.add_argument("--repository", required=True, help="Repository name.")
    parser.add_argument("--tag", required=True, help="Name of the tag to create.")
    parser.add_argument("--branch", required=True, help="Name of the branch to create tag from.")

    args = parser.parse_args()

    access_token = os.environ.get("GITHUB_TOKEN")

    gh_instance = Github(access_token)
    gh_repository = gh_instance.get_repo(args.repository)

    commit_sha = gh_repository.get_branch(args.branch).commit.sha
    logger.info("Create tag [%s] from commit '%s'", args.tag, commit_sha)
    gh_repository.create_git_ref(f"refs/tags/{args.tag}", commit_sha)

    # create pull request to default branch
    if args.branch != gh_repository.default_branch:
        default_branch = gh_repository.default_branch
        pr_title = f"Release '{args.tag}' on '{default_branch}'"
        body = f"Push changes from Release {args.tag} into default repository branch."
        logger.info(
            "Create pull request from branch '%s' to default branch '%s'",
            args.branch,
            default_branch,
        )
        gh_repository.create_pull(title=pr_title, body=body, head=args.branch, base=default_branch)


if __name__ == "__main__":
    main()
