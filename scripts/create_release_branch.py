#!/usr/bin/env python3
"""Script to compute release version based on release branch."""

import logging
import os

import semver

from github import Github
from github import Repository


FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("compute_release_version")
logger.setLevel(logging.DEBUG)


def compute_next_release_version(release_tags: list[str], release_branch: str) -> str:
    """Bump minor or patch version depending on target branch and existing tags.

    :param release_tags: list of existing tags from github repository
    :param release_branch: Release base branch
    :returns: a release version as string
    """
    release_version = release_branch.replace("stable-", "") + ".0"
    myversion = semver.Version.parse(release_version)

    minor_found = False
    for item in release_tags:
        version_obj = semver.Version.parse(item)
        if version_obj.major == myversion.major and version_obj.minor == myversion.minor:
            minor_found = True
            if semver.compare(str(myversion), str(version_obj)) == -1:
                myversion = version_obj

    return str(myversion.bump_patch()) if minor_found else str(myversion)


def create_repository_branch(gh_repository: Repository.Repository, release_branch: str) -> None:
    """Create a branch on github repository.

    :param gh_repository: Github repository object.
    :param release_branch: Name of the branch to create.
    """
    repository_branches = [branch.name for branch in gh_repository.get_branches()]
    logger.info("Repository branches: %s", repository_branches)
    if release_branch not in repository_branches:
        default_branch = gh_repository.default_branch
        logger.info("Repository default branch: %s", default_branch)
        default_branch_obj = gh_repository.get_branch(default_branch)
        logger.info("Creating release branch: %s", release_branch)
        gh_repository.create_git_ref(
            ref="refs/heads/" + release_branch, sha=default_branch_obj.commit.sha
        )


def main() -> None:
    """Read boto constraints and update variables accordingly."""
    repository = os.environ.get("REPOSITORY_NAME") or ""
    access_token = os.environ.get("GITHUB_TOKEN")
    release_branch = os.environ.get("RELEASE_BRANCH", "")

    logger.info("Repository name -> '%s'", repository)
    logger.info("Github token -> '%s'", access_token)
    logger.info("Release branch -> '%s'", release_branch)

    gh_client = Github(access_token)
    gh_repository = gh_client.get_repo(repository)

    if release_branch:
        repository_tags = [tag.name for tag in gh_repository.get_tags()]
        logger.info("Repository tags => %s", repository_tags)

        release_version = compute_next_release_version(repository_tags, release_branch)
        if release_version:
            create_repository_branch(gh_repository, release_branch)
            github_output_file = os.environ.get("GITHUB_OUTPUT") or ""
            if github_output_file:
                with open(github_output_file, "a", encoding="utf-8") as file_write:
                    file_write.write(f"release_version={release_version}\n")


if __name__ == "__main__":
    main()
