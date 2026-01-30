#!/usr/bin/env python3
"""Contains tests cases for list_changed_common and list_changed_targets modules."""

import io

from pathlib import PosixPath
from typing import Any
from unittest.mock import ANY
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from list_changed_common import Collection
from list_changed_common import ElGrandeSeparator
from list_changed_common import WhatHaveChanged
from list_changed_common import list_pyimport
from list_changed_common import make_unique
from list_changed_common import read_collection_name
from list_changed_common import read_collections_to_test
from list_changed_common import read_targets_to_test
from list_changed_common import read_test_all_the_targets
from list_changed_common import read_total_jobs


MY_MODULE = """
from ..module_utils.core import AnsibleAWSModule
from ipaddress import ipaddress
import time
import botocore.exceptions
"""

MY_MODULE_2 = """
import ansible_collections.kubernetes.core.plugins.module_utils.k8sdynamicclient

def main():
    mutually_exclusive = [
        ("resource_definition", "src"),
    ]
    module = AnsibleModule(
        argument_spec=argspec(),
    )
    from ansible_collections.kubernetes.core.plugins.module_utils.common import (
        K8sAnsibleMixin,
        get_api_client,
    )

    k8s_ansible_mixin = K8sAnsibleMixin(module)
"""

MY_MODULE_3 = """
from .modules import AnsibleAWSModule
from ipaddress import ipaddress
import time
import botocore.exceptions
"""


def test_read_collection_name() -> None:
    """Test read_collection_name method."""
    m_galaxy_file = MagicMock()
    m_galaxy_file.open = lambda: io.BytesIO(b"name: b\nnamespace: a\n")
    m_path = MagicMock()
    m_path.__truediv__.return_value = m_galaxy_file
    assert read_collection_name(m_path) == "a.b"


def test_list_pyimport() -> None:
    """Test list_pyimport."""
    assert list(list_pyimport("ansible_collections.amazon.aws.plugins.", "modules", MY_MODULE)) == [
        "ansible_collections.amazon.aws.plugins.module_utils.core",
        "ipaddress",
        "time",
        "botocore.exceptions",
    ]

    assert list(
        list_pyimport("ansible_collections.kubernetes.core.plugins.", "modules", MY_MODULE_2)
    ) == [
        "ansible_collections.kubernetes.core.plugins.module_utils.k8sdynamicclient",
        "ansible_collections.kubernetes.core.plugins.module_utils.common",
    ]

    assert list(
        list_pyimport("ansible_collections.amazon.aws.plugins.", "module_utils", MY_MODULE_3)
    ) == [
        "ansible_collections.amazon.aws.plugins.module_utils.modules",
        "ipaddress",
        "time",
        "botocore.exceptions",
    ]


@patch("list_changed_common.read_collection_name")
def test_what_changed_files(m_read_collection_name: MagicMock) -> None:
    """Test changes from WhatHaveChanged class.

    :param m_read_collection_name: read_collection mock method
    """
    m_read_collection_name.return_value = "a.b"
    whc = WhatHaveChanged(PosixPath("a"), "b")
    whc.files = [
        PosixPath("tests/something"),
        PosixPath("plugins/module_utils/core.py"),
        PosixPath("plugins/plugin_utils/base.py"),
        PosixPath("plugins/connection/aws_ssm.py"),
        PosixPath("plugins/modules/ec2.py"),
        PosixPath("plugins/lookup/aws_test.py"),
        PosixPath("tests/integration/targets/k8s_target_1/action.yaml"),
        PosixPath("tests/integration/targets/k8s_target_2/file.txt"),
        PosixPath("tests/integration/targets/k8s_target_3/tasks/main.yaml"),
    ]
    assert list(whc.modules()) == [PosixPath("plugins/modules/ec2.py")]
    assert list(whc.plugin_utils()) == [
        (
            PosixPath("plugins/plugin_utils/base.py"),
            "ansible_collections.a.b.plugins.plugin_utils.base",
        )
    ]
    assert list(whc.module_utils()) == [
        (
            PosixPath("plugins/module_utils/core.py"),
            "ansible_collections.a.b.plugins.module_utils.core",
        )
    ]
    assert list(whc.lookup()) == [PosixPath("plugins/lookup/aws_test.py")]
    assert list(whc.targets()) == [
        "k8s_target_1",
        "k8s_target_2",
        "k8s_target_3",
    ]
    assert list(whc.connection()) == [PosixPath("plugins/connection/aws_ssm.py")]


def build_collection(aliases: list[Any]) -> Collection:
    """Build Collection.

    :param aliases: aliases
    :returns: Mock collection
    """
    with patch("list_changed_common.read_collection_name") as m_read_collection_name:
        m_read_collection_name.return_value = "some.collection"
        mycollection = Collection(PosixPath("nowhere"))
        m_c_path = MagicMock()
        mycollection.collection_path = m_c_path
        m_c_path.glob.return_value = aliases
        return mycollection


def create_test_content(path: PosixPath, aliases: str = "") -> PosixPath:
    """Create integration test target.

    :param path: The path to the target
    :param aliases: the content of the aliases file
    :returns: the path to the target.
    """
    path.mkdir()
    if aliases:
        file = path / "aliases"
        file.write_text(aliases)
    return path


def test_c_targets(tmp_path: PosixPath) -> None:
    """Test add targets method from Collection class.

    :param tmp_path: python temporary path fixture
    """
    mycollection = build_collection([])
    assert not list(mycollection.targets())

    a = tmp_path / "a"
    mycollection = build_collection([create_test_content(a, "ec2\n")])
    assert len(list(mycollection.targets())) == 1
    assert list(mycollection.targets())[0].name == "a"
    assert list(mycollection.targets())[0].is_alias_of("ec2")

    b = tmp_path / "b"
    mycollection = build_collection([create_test_content(b, "#ec2\n")])
    assert len(list(mycollection.targets())) == 1
    assert list(mycollection.targets())[0].name == "b"
    assert list(mycollection.targets())[0].execution_time() == 180

    c = tmp_path / "c"
    mycollection = build_collection([create_test_content(c, "time=30\n")])
    assert len(list(mycollection.targets())) == 1
    assert list(mycollection.targets())[0].name == "c"
    assert list(mycollection.targets())[0].execution_time() == 30


def test_2_targets_for_one_module(tmp_path: PosixPath) -> None:
    """Test 2 targets.

    :param tmp_path: python temporary path fixture
    """
    a = tmp_path / "a"
    b = tmp_path / "b"
    collection = build_collection(
        [create_test_content(a, "ec2_instance\n"), create_test_content(b, "ec2_instance\n")]
    )
    assert collection.regular_targets_to_test() == []
    collection.add_target_to_plan("ec2_instance")
    assert collection.regular_targets_to_test() == ["a", "b"]


@patch("list_changed_common.read_collection_name")
def test_c_disabled_unstable(tmp_path: PosixPath) -> None:
    """Test disable/unstable targets.

    :param tmp_path: python temporary path fixture
    """
    a = tmp_path / "a"
    b = tmp_path / "b"
    collection = build_collection(
        [create_test_content(a, "disabled\n"), create_test_content(b, "unstable\n")]
    )
    collection.collection_path = tmp_path

    # all, we should ignore the disabled,unstable jobs
    collection.cover_all()
    assert len(collection.regular_targets_to_test()) == 0
    # if the module is targets, we continue to ignore the disabled
    collection.add_target_to_plan("modules_a")
    assert len(collection.regular_targets_to_test()) == 0
    collection.add_target_to_plan("modules_b")
    assert len(collection.regular_targets_to_test()) == 0


@patch("list_changed_common.read_collection_name")
def test_c_slow_regular_targets(m_read_collection_name: MagicMock, tmp_path: PosixPath) -> None:
    """Test targets* methods from Collection class.

    :param m_read_collection_name: read_collection_name patched method
    :param tmp_path: python temporary path fixture
    """
    m_read_collection_name.return_value = "some.collection"
    tortue = tmp_path / "inventory_tortue"
    lapin = tmp_path / "lapin"
    collection = build_collection(
        [
            create_test_content(tortue, "slow\nec2\n#s3\n"),
            create_test_content(lapin, "notslow\ncarrot\n\n"),
        ]
    )

    collection.cover_all()
    assert len(list(collection.targets())) == 2
    assert list(collection.targets())[0].is_slow()
    assert not list(collection.targets())[1].is_slow()
    assert len(collection.slow_targets_to_test()) == 1


def test_c_inventory_targets(tmp_path: PosixPath) -> None:
    """Test targets methods from Collection class.

    :param tmp_path: python temporary path fixture
    """
    inventory_tortue = tmp_path / "inventory_tortue"
    lapin = tmp_path / "lapin"
    col = build_collection(
        [
            create_test_content(inventory_tortue, "slow\nec2\n#s3\n"),
            create_test_content(lapin, "notslow\ninventory_carrot\n\n"),
        ]
    )
    col.cover_all()
    assert len(list(col.targets())) == 2
    assert list(col.targets())[0].is_slow()
    assert not list(col.targets())[1].is_slow()
    assert len(col.slow_targets_to_test()) == 1


@patch("list_changed_common.read_collection_name")
def test_c_with_cover(m_read_collection_name: MagicMock, tmp_path: PosixPath) -> None:
    """Test add_target_to_plan method from Collection class.

    :param m_read_collection_name: read_collection_name patched method
    :param tmp_path: python temporary path fixture
    """
    m_read_collection_name.return_value = "some.collection"
    collection = Collection(PosixPath("nowhere"))
    m_c_path = MagicMock()
    collection.collection_path = m_c_path

    tortue = tmp_path / "tortue"
    lapin = tmp_path / "lapin"
    m_c_path.glob.return_value = [
        create_test_content(tortue, "slow\nec2\n#s3\n"),
        create_test_content(lapin, "carrot\n\n"),
    ]
    collection.add_target_to_plan("ec2")
    assert len(collection.slow_targets_to_test()) == 1
    assert collection.regular_targets_to_test() == []


def test_splitter_with_time(tmp_path: PosixPath) -> None:
    """Test splitter method from class ElGrandeSeparator.

    :param tmp_path: python temporary path fixture
    """
    a = tmp_path / "a"
    b = tmp_path / "b"
    c = tmp_path / "c"
    d = tmp_path / "d"
    e = tmp_path / "e"
    collection_1 = build_collection(
        [
            create_test_content(a, "time=50m\n"),
            create_test_content(b, "time=10m\n"),
            create_test_content(c, "time=180\n"),
            create_test_content(d, "time=140s  \n"),
            create_test_content(e, "time=70\n"),
        ]
    )
    collection_1.cover_all()
    egs = ElGrandeSeparator([collection_1], ANY)
    result = list(egs.build_up_batches([f"slot{i}" for i in range(2)], collection_1))
    assert result == [
        ("slot0", ["a"]),
        ("slot1", ["b", "c", "d", "e"]),
    ]

    a0 = tmp_path / "a0"
    b0 = tmp_path / "b0"
    c0 = tmp_path / "c0"
    d0 = tmp_path / "d0"
    collection_2 = build_collection(
        [
            create_test_content(a0, "time=50m\n"),
            create_test_content(b0, "time=50m\n"),
            create_test_content(c0, "time=18\n"),
            create_test_content(d0, "time=5m\n"),
        ]
    )
    collection_2.cover_all()
    egs = ElGrandeSeparator([collection_2], ANY)
    result = list(egs.build_up_batches([f"slot{i}" for i in range(3)], collection_2))
    assert result == [("slot0", ["a0"]), ("slot1", ["b0"]), ("slot2", ["d0", "c0"])]


@patch("list_changed_common.read_collection_name")
@patch("list_changed_common.run_command")
def test_what_changed_git_call(m_run_command: MagicMock, m_read_collection_name: MagicMock) -> None:
    """Test changed_files method from WhatHaveChanged class.

    :param m_run_command: run_command patched method
    :param m_read_collection_name: read_collection_name patched method
    """
    m_run_command.return_value = "plugins/modules/foo.py\n"
    m_read_collection_name.return_value = "a.b"

    whc = WhatHaveChanged(PosixPath("a"), "stable-2.1")
    assert whc.changed_files() == [PosixPath("plugins/modules/foo.py")]

    m_run_command.assert_called_with(
        command="git diff origin/stable-2.1 --name-only",
        chdir=PosixPath("a"),
    )


def test_make_unique() -> None:
    """Test test_make_unique function."""
    assert make_unique(["a", "b", "a"]) == ["a", "b"]
    assert make_unique(["a", "b"]) == ["a", "b"]


def test_read_test_all_the_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test read_test_all_the_targets function.

    :param monkeypatch: monkey patch
    """
    # default value when environment variable is not defined
    assert read_test_all_the_targets() is False

    # ANSIBLE_TEST_ALL_THE_TARGETS -> 'any'
    monkeypatch.setenv("ANSIBLE_TEST_ALL_THE_TARGETS", "any")
    assert read_test_all_the_targets() is False

    # ANSIBLE_TEST_ALL_THE_TARGETS -> 'TRUE'
    monkeypatch.setenv("ANSIBLE_TEST_ALL_THE_TARGETS", "TRUE")
    assert read_test_all_the_targets() is True

    # ANSIBLE_TEST_ALL_THE_TARGETS -> 'True'
    monkeypatch.setenv("ANSIBLE_TEST_ALL_THE_TARGETS", "True")
    assert read_test_all_the_targets() is True


def test_read_total_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test read_total_jobs function.

    :param monkeypatch: monkey patch
    """
    # default value when environment variable is not defined
    assert read_total_jobs() == 3

    # TOTAL_JOBS -> 'any'
    monkeypatch.setenv("TOTAL_JOBS", "any")
    assert read_total_jobs() == 3

    # TOTAL_JOBS -> '07'
    monkeypatch.setenv("TOTAL_JOBS", "07")
    assert read_total_jobs() == 7

    # TOTAL_JOBS -> '5'
    monkeypatch.setenv("TOTAL_JOBS", "5")
    assert read_total_jobs() == 5


def test_read_targets_to_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test read_targets_to_test function.

    :param monkeypatch: monkey patch
    """
    # default value when environment variable is not defined
    assert not read_targets_to_test()

    body = "No target to test set here"
    monkeypatch.setenv("PULL_REQUEST_BODY", body)
    assert not read_targets_to_test()

    body = (
        "This is the first line of my pull request description\n"
        "TargetsToTest=collection1:target_01,target_02;collection2:target_2"
    )
    monkeypatch.setenv("PULL_REQUEST_BODY", body)
    print(body)
    assert read_targets_to_test() == {
        "collection1": ["target_01", "target_02"],
        "collection2": ["target_2"],
    }

    body = (
        "This is the first line of my pull request description\n"
        "TARGETSTOTEST=collection1:target_01,target_02;collection2:target_2;"
    )
    monkeypatch.setenv("PULL_REQUEST_BODY", body)
    assert read_targets_to_test() == {
        "collection1": ["target_01", "target_02"],
        "collection2": ["target_2"],
    }


def test_read_collections_to_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test read_collections_to_test function.

    :param monkeypatch: monkey patch
    """
    collection_to_test = "col1,col2\n  ,col3"
    monkeypatch.setenv("COLLECTIONS_TO_TEST", collection_to_test)
    assert read_collections_to_test() == [PosixPath("col1"), PosixPath("col2"), PosixPath("col3")]
