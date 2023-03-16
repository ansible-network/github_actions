#!/usr/bin/python

import re
import os
import sys
from github import Github
import logging


FORMAT = '[%(asctime)s] - %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('resolve_dependency')
logger.setLevel(logging.DEBUG)

"""
    While trying to checkout a repository, this script will check if there is an override into the
    Pull request body.
    Example: 
        assuming we are going to checkout 'ansible-collections/community.aws' on 'main' branch,
        if the pull request body contains 'Depends-On: https://github.com/ansible-collections/community.aws/pull/1542'
        we will checkout 'ansible-collections/community.aws' on 'merge_commit_sha' instead
"""

def get_pr_merge_commit_sha(repository, pr_number):
    access_token = os.environ.get("GITHUB_TOKEN")
    gh = Github(access_token)
    repo = gh.get_repo(repository)

    pr = repo.get_pull(pr_number)
    if not pr.mergeable:
        # raise an error when the pull request is not mergeable
        sys.tracebacklimit = -1
        raise ValueError("Pull request %d from %s is not mergeable" % (pr_number, repository))

    return pr.merge_commit_sha


def resolve_ref(pr_body, repository):
    pr_regx = re.compile(rf"^Depends-On:[ ]*https://github.com/{repository}/pull/(\d+)\s*$", re.MULTILINE | re.IGNORECASE)
    # Search for expression starting with depends-on not case-sensitive
    m = pr_regx.findall(pr_body)
    return int(m[0]) if m else None


def main():

    pr_body = os.environ.get("RESOLVE_REF_PR_BODY")
    repository = os.environ.get("RESOLVE_REF_REPOSITORY")

    pr_number = resolve_ref(pr_body, repository)
    if pr_number is None:
        return
    logger.info("Override checkout with pr number: %d" % pr_number)

    # get pull request merge commit sha
    merge_commit_sha = get_pr_merge_commit_sha(repository, pr_number)
    logger.info("merge commit sha for pull request %d => '%s'" % (pr_number, merge_commit_sha))
    with open(os.environ.get("GITHUB_OUTPUT"), "a") as fw:
        fw.write("merge_commit_sha={0}\n".format(merge_commit_sha))

if __name__ == "__main__":

    main()
