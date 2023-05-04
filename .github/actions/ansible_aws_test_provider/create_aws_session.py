#!/usr/bin/python
"""Script to request new aws session using ansible_core_ci_key."""

import json
import logging
import os
import random
import sys

import requests


FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("create_aws_session")
logger.setLevel(logging.DEBUG)


def main() -> None:
    """Request new aws session credentials.

    :raises ValueError: when ANSIBLE_CORE_CI_KEY environment variable is missing or empty
    """
    ansible_core_ci_key = os.environ.get("ANSIBLE_CORE_CI_KEY") or ""
    ansible_core_ci_stage = os.environ.get("ANSIBLE_CORE_CI_STAGE") or "prod"
    headers = {"Content-Type": "application/json"}
    data = {
        "config": {"platform": "aws", "version": "sts"},
        "auth": {
            "remote": {
                "key": ansible_core_ci_key,
                "nonce": None,
            }
        },
        "threshold": 1,
    }
    if ansible_core_ci_key == "":
        logger.error("Empty or missing environment variable 'ANSIBLE_CORE_CI_KEY'")
        raise ValueError("ANSIBLE_CORE_CI_KEY environment variable is empty or missing")
    logger.info("data -> %s", json.dumps(data).replace(ansible_core_ci_key, "*******"))
    session_id = "".join(random.choice("0123456789abcdef") for _ in range(32))
    endpoint_url = (
        f"https://ansible-core-ci.testing.ansible.com/{ansible_core_ci_stage}/aws/{session_id}"
    )
    logger.info("Endpoint URL -> '%s'", endpoint_url)
    response = requests.put(endpoint_url, data=json.dumps(data), headers=headers, timeout=10)
    logger.info("Status: [%d]", response.status_code)
    if response.status_code != 200:
        logger.info("Response: %s", response.json())
        logger.error("Request failed with [%s]", response.json().get("errorMessage"))
        sys.exit(1)

    # create ansible-test credential file
    credentials = response.json().get("aws").get("credentials")
    cloud_config_file = os.environ.get("ANSIBLE_TEST_CLOUD_CONFIG_FILE") or "cloud-config-aws.ini"
    access_key = credentials.get("access_key")
    secret_key = credentials.get("secret_key")
    session_token = credentials.get("session_token")
    aws_credentials = [
        "[default]",
        f"aws_access_key: {access_key}",
        f"aws_secret_key: {secret_key}",
        f"security_token: {session_token}",
        "aws_region: us-east-1",
        "ec2_access_key: {{ aws_access_key }}",
        "ec2_secret_key: {{ aws_secret_key }}",
        "ec2_region: {{ aws_region }}",
    ]
    logger.info("writing aws credentials into file => %s", cloud_config_file)
    with open(cloud_config_file, mode="w", encoding="utf-8") as file_writer:
        file_writer.write("\n".join(aws_credentials))


if __name__ == "__main__":
    main()
