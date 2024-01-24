#!/usr/bin/python
"""Script to request new azure session using ansible_core_ci_key."""

import json
import os
import secrets
import sys

from pathlib import PosixPath

import requests


def main() -> None:
    """Request new azure session credentials.

    :raises ValueError: when ANSIBLE_CORE_CI_KEY environment variable is missing or empty
    """
    try:
        ansible_core_ci_key = os.environ["ANSIBLE_CORE_CI_KEY"]
    except KeyError:
        sys.stderr.write("Missing mandatory environment variable ANSIBLE_CORE_CI_KEY.\n")
        sys.exit(1)
    ansible_core_ci_stage = os.environ.get("ANSIBLE_CORE_CI_STAGE") or "prod"
    headers = {"Content-Type": "application/json"}
    ansible_ssh_public_key_path = os.environ.get(
        "ANSIBLE_TEST_SSH_PUBLIC_KEY_PATH"
    ) or os.path.expanduser("~/.ssh/id_rsa.pub")

    data = {
        "config": {
            "platform": "azure",
            "version": "",
            "architecture": "",
            "public_key": PosixPath(ansible_ssh_public_key_path).read_text(encoding="utf-8"),
        },
        "auth": {
            "remote": {
                "key": ansible_core_ci_key,
                "nonce": None,
            }
        },
    }
    session_id = "".join(secrets.choice("0123456789abcdef") for i in range(32))
    endpoint_url = (
        f"https://ansible-core-ci.testing.ansible.com/{ansible_core_ci_stage}/azure/{session_id}"
    )
    response = requests.put(endpoint_url, data=json.dumps(data), headers=headers, timeout=30)
    if response.status_code != 200:
        sys.stderr.write("Unexpected http status code received from server. Expected (200) Received (%s)" % response.status_code)
        sys.exit(1)

    # create ansible-test credential file
    credentials = response.json().get("azure")
    cloud_config_file = os.environ.get("ANSIBLE_TEST_CLOUD_CONFIG_FILE") or "cloud-config-azure.ini"
    cloud_config_content = [
        "[default]",
        f"AZURE_CLIENT_ID: {credentials.get('clientId')}",
        f"AZURE_SECRET: {credentials.get('clientSecret')}",
        f"AZURE_SUBSCRIPTION_ID: {credentials.get('subscriptionId')}",
        f"AZURE_TENANT: {credentials.get('tenantId')}",
        f"RESOURCE_GROUP: {credentials.get('resourceGroupNames')[0]}",
        f"RESOURCE_GROUP_SECONDARY: {credentials.get('resourceGroupNames')[1]}",
    ]
    with open(cloud_config_file, mode="w", encoding="utf-8") as file_writer:
        file_writer.write("\n".join(cloud_config_content))


if __name__ == "__main__":
    main()
