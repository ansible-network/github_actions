#!/usr/bin/env python3
"""Script to create tag on github repository."""

import logging
import os

from github import Github
from packaging import version


FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("compute_release_version")
logger.setLevel(logging.DEBUG)


def is_release_patch(release_tag: str) -> bool:
    """Check if the release tag is a patch release.

    :param release_tag: the release tag to test.
    :returns: Whether the release tag is a patch release.
    """
    return version.Version(release_tag).micro == 0


def main() -> None:
    """Create tag and publish to Github repository."""
    access_token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("REPOSITORY_NAME") or ""
    tag = os.environ.get("RELEASE_TAG") or ""
    commit_sha = os.environ.get("COMMIT_SHA") or ""

    logger.info("Release tag -> '%s'", tag)
    logger.info("Repository -> '%s'", repository)
    logger.info("Commit sha -> '%s'", commit_sha)

    gh_instance = Github(access_token)
    gh_repository = gh_instance.get_repo(repository)

    tag_message = f"tag created from commit {commit_sha}"
    gh_tag = gh_repository.create_git_tag(
        tag=tag, message=tag_message, type="commit", object=commit_sha
    )
    gh_repository.create_git_ref(f"refs/tags/{gh_tag.tag}", gh_tag.sha)

    # create pull request to default branch
    if is_release_patch(release_tag=tag):
        default_branch = gh_repository.default_branch
        release_branch = "stable-" + ".".join(tag.split(".")[0:2])
        pr_title = f"Push release {tag} on branch {default_branch}"
        body = f"Push changes from Release {tag} into default repository branch."
        logger.info(
            "Create pull request from branch '%s' to default branch '%s'",
            release_branch,
            default_branch,
        )
        gh_repository.create_pull(
            title=pr_title, body=body, head=release_branch, base=default_branch
        )


if __name__ == "__main__":
    main()
