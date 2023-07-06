#!/usr/bin/env python3
"""Define collection module for list_changed_targets executable."""

import ast
import os
import re
import subprocess

from collections import defaultdict
from collections.abc import Generator
from pathlib import PosixPath
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import yaml


def read_collection_name(collection_path: PosixPath) -> str:
    """Read collection namespace from galaxy.yml.

    :param collection_path: path to the collection
    :returns: collection name as string
    """
    with (collection_path / "galaxy.yml").open() as file_handler:
        content = yaml.safe_load(file_handler)
        return f'{content["namespace"]}.{content["name"]}'


def run_command(command: str, chdir: Optional[PosixPath]) -> str:
    """Run shell command using subprocess.

    :param command: command to execute
    :param chdir: directory to place in before running the command
    :returns: command output
    """
    with subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, cwd=chdir
    ) as proc:
        out, _ = proc.communicate()
        return out.decode()


def list_pyimport(prefix: str, subdir: str, module_content: str) -> Generator[str, None, None]:
    """Read collection namespace from galaxy.yml.

    :param prefix: files prefix
    :param subdir: sub directory
    :param module_content: module content
    :yields: python module import
    """
    root = ast.parse(module_content)
    for node in ast.walk(root):
        if isinstance(node, ast.Import):
            yield node.names[0].name
        elif isinstance(node, ast.ImportFrom):
            if node.level == 1:
                current_prefix = f"{prefix}{subdir}."
            elif node.level == 2:
                current_prefix = f"{prefix}"
            else:
                current_prefix = ""
            yield f"{current_prefix}{node.module}"


def build_import_tree(
    import_path: PosixPath, module_collection_name: str, all_collections_names: list[str]
) -> tuple[dict[str, list[Any]], dict[str, list[Any]]]:
    """Generate import dependencies for the modules and the module_utils.

    Let say we have the following input:

        modules: ec2_mod1
            import a_py_mod
            import ansible.basic
        modules: ec2_mod2
            import another_py_mod
            import ansible_collections.amazon.aws.plugins.module_utils.core
        modules: ec2_mod3
            import ansible_collections.amazon.aws.plugins.module_utils.tagging
            import ansible_collections.amazon.aws.plugins.module_utils.waiters

        module_utils: waiters
            import some_py_mod
            import ansible_collections.amazon.aws.plugins.module_utils.core
        module_utils: tagging
            import some_py_tricky_mod
            import ansible_collections.amazon.aws.plugins.module_utils.core
        module_utils: core
            import some_py_fancy_mod

    This will generated the following dicts (list only import part of this collection):

    modules_imports
        {
            "ec2_mod1": [],
            "ec2_mod2": [
                "ansible_collections.amazon.aws.plugins.module_utils.core",
            ],
            "ec2_instance_info": [
                "ansible_collections.amazon.aws.plugins.module_utils.tagging",
                "ansible_collections.amazon.aws.plugins.module_utils.waiters"
            ],
        }

    utils_import
        {
            "ansible_collections.amazon.aws.plugins.module_utils.core": [
                "ansible_collections.amazon.aws.plugins.module_utils.waiters"
                "ansible_collections.amazon.aws.plugins.module_utils.tagging"
            ]
        }

    :param all_collections_names: collections names
    :param module_collection_name: current collection name
    :param import_path: the path to import from
    :returns: tuple of modules and utils imports
    """
    modules_import = defaultdict(list)  # type: Dict[str, List[Any]]
    prefix = f"ansible_collections.{module_collection_name}.plugins."
    all_prefixes = [f"ansible_collections.{n}.plugins." for n in all_collections_names]
    utils_to_visit = []
    for mod in import_path.glob("plugins/modules/*"):
        for i in list_pyimport(prefix, "modules", mod.read_text()):
            if any(i.startswith(p) for p in all_prefixes) and i not in modules_import[mod.stem]:
                modules_import[mod.stem].append(i)
                if i not in utils_to_visit:
                    utils_to_visit.append(i)

    utils_import = defaultdict(list)  # type: Dict[str, List[Any]]
    visited = []
    while utils_to_visit:
        utils = utils_to_visit.pop()
        if utils in visited:
            continue
        visited.append(utils)
        try:
            utils_path = import_path / PosixPath(
                utils.replace(f"ansible_collections.{module_collection_name}.", "").replace(
                    ".", "/"
                )
                + ".py"
            )
            for i in list_pyimport(prefix, "module_utils", utils_path.read_text()):
                if i.startswith(prefix) and i not in utils_import[utils]:
                    utils_import[utils].append(i)
                    if i not in visited:
                        utils_to_visit.append(i)
        except Exception:  # pylint: disable=broad-except
            pass
    return modules_import, utils_import


class WhatHaveChanged:
    """A class to store information about changes for a specific collection."""

    def __init__(self, change_path: PosixPath, base_ref: str) -> None:
        """Class constructor.

        :param change_path: path to the change
        :param base_ref: pull request base reference
        """
        assert isinstance(change_path, PosixPath)
        self.collection_path = change_path
        self.base_ref = base_ref
        self.collection_name = read_collection_name(change_path)
        self.files = []  # type: List[PosixPath]

    def changed_files(self) -> list[PosixPath]:
        """List of changed files.

        :returns: a list of pathlib.PosixPath
        """
        if not self.files:
            changed_files_cmd = f"git diff origin/{self.base_ref} --name-only"
            stdout = run_command(command=changed_files_cmd, chdir=self.collection_path)
            self.files = [PosixPath(p) for p in stdout.split("\n") if p]
        return self.files

    def targets(self) -> Generator[str, None, None]:
        """List the test targets impacted by the change.

        :yields: targets impacted by this change
        """
        for change in self.changed_files():
            if str(change).startswith("tests/integration/targets/"):
                # These are a special case, we only care that 'something' changed in that test
                yield str(change).replace("tests/integration/targets/", "").split("/", maxsplit=1)[
                    0
                ]

    def _path_matches(self, base_path: str) -> Generator[PosixPath, None, None]:
        """Simplest case, just a file name.

        :param base_path: path of the module
        :yields: path to a change file
        """
        for changed_file in self.changed_files():
            if str(changed_file).startswith(base_path):
                yield PosixPath(changed_file)

    def connection(self) -> Generator[PosixPath, None, None]:
        """List the connection plugins impacted by the change.

        :yields: path to a connection plugin change
        """
        yield from self._path_matches("plugins/connection/")

    def inventory(self) -> Generator[PosixPath, None, None]:
        """List the inventory plugins impacted by the change.

        :yields: path to an inventory plugin change
        """
        yield from self._path_matches("plugins/inventory/")

    def lookup(self) -> Generator[PosixPath, None, None]:
        """List the lookup plugins impacted by the change.

        :yields: path to a connection lookup change
        """
        yield from self._path_matches("plugins/lookup/")

    def modules(self) -> Generator[PosixPath, None, None]:
        """List the modules impacted by the change.

        :yields: path to a module plugin change
        """
        yield from self._path_matches("plugins/modules/")

    def roles(self) -> Generator[PosixPath, None, None]:
        """List the roles impacted by the change.

        :yields: path to a role change
        """
        yield from self._path_matches("roles/")

    def _util_matches(
        self, base_path: str, import_path: str
    ) -> Generator[tuple[PosixPath, str], None, None]:
        """List matching utils files.

        :param base_path: path of the module or plugin util
        :param import_path: path of the import library
        :yields: path to a module or plugin utils change
        """
        # We care about the file, but we also need to find what potential side effects would be for
        # our change
        base_name = f"ansible_collections.{self.collection_name}.plugins.{import_path}."
        for util_change in self.changed_files():
            if str(util_change).startswith(base_path):
                yield (
                    PosixPath(util_change),
                    f"{base_name}{util_change.stem}",
                )

    def module_utils(self) -> Generator[tuple[PosixPath, str], None, None]:
        """List the Python modules impacted by the change.

        :yields: path to a module util change
        """
        yield from self._util_matches("plugins/module_utils/", "module_utils")

    def plugin_utils(self) -> Generator[tuple[PosixPath, str], None, None]:
        """List the Python modules impacted by the change.

        :yields: path to a plugin util change
        """
        yield from self._util_matches("plugins/plugin_utils/", "plugin_utils")


class Target:
    """A class to store information about a specific target."""

    def __init__(self, target_path: PosixPath) -> None:
        """Class constructor.

        :param target_path: path to the target
        """
        self.path = target_path
        self.lines = [line.split("#")[0] for line in target_path.read_text().split("\n") if line]
        self.name = target_path.parent.name
        self.exec_time = 0

    def is_alias_of(self, name: str) -> bool:
        """Test alias target.

        :param name: the name of the source target
        :returns: whether target is an alias or not
        """
        return name in self.lines or self.name == name

    def is_unstable(self) -> bool:
        """Test unstable target.

        :returns: whether target is unstable or not
        """
        if "unstable" in self.lines:
            return True
        return False

    def is_disabled(self) -> bool:
        """Test disabled target.

        :returns: whether target is disabled or not
        """
        if "disabled" in self.lines:
            return True
        return False

    def is_slow(self) -> bool:
        """Test slow target.

        :returns: whether target is slow or not
        """
        # NOTE: Should be replaced by time=3000
        if "slow" in self.lines or "# reason: slow" in self.lines:
            return True
        return False

    def is_ignored(self) -> bool:
        """Show the target be ignored.

        :returns: whether target is set as ignored or not
        """
        ignore = {"unsupported", "disabled", "unstable", "hidden"}
        return not ignore.isdisjoint(set(self.lines))

    def execution_time(self) -> int:
        """Retrieve execution time of a target.

        :returns: execution time of the target
        """
        if self.exec_time:
            return self.exec_time

        self.exec_time = 3000 if self.is_slow() else 180
        for line in self.lines:
            if match := re.match(r"^time=([0-9]+)s\S*$", line):
                self.exec_time = int(match.group(1))
            elif match := re.match(r"^time=([0-9]+)m\S*$", line):
                self.exec_time = int(match.group(1)) * 60
            elif match := re.match(r"^time=([0-9]+)\S*$", line):
                self.exec_time = int(match.group(1))

        return self.exec_time


class Collection:
    """A class storing collection information."""

    def __init__(self, collection_path: PosixPath) -> None:
        """Class Constructor.

        :param collection_path: path to the collection
        """
        self.collection_path = collection_path
        self._my_test_plan = []  # type: List[Target]
        self.collection_name = read_collection_name(collection_path)  # type: str
        self.modules_import = {}  # type: Dict[str, List[Any]]
        self.utils_import = {}  # type: Dict[str, List[Any]]
        self.test_groups = []  # type: List[Dict[str, Any]]

    @property
    def test_plan_names(self) -> list[str]:
        """Return list of name of the test plan.

        :returns: a list of test plan names
        """
        return [t.name for t in self._my_test_plan]

    @property
    def test_plan(self) -> list[Target]:
        """Get protected attribute _my_test_plan.

        :returns: a list of test plan objects
        """
        return self._my_test_plan

    def targets(self) -> Generator[Target, None, None]:
        """List collection targets.

        :yields: a collection target
        """
        for alias in self.collection_path.glob("tests/integration/targets/*/aliases"):
            yield Target(alias)

    def _is_target_already_added(self, target_name: str) -> bool:
        """Return true if the target is already part of the test plan.

        :param target_name: target name being checked
        :returns: whether the target is already part of the test plan or not
        """
        for target_src in self._my_test_plan:
            if target_src.is_alias_of(target_name):
                return True
        return False

    def add_target_to_plan(self, target_name: str, is_direct: bool = True) -> None:
        """Add specific target to the test plan.

        :param target_name: target name being added
        :param is_direct: whether it is a direct target or an alias
        """
        if not self._is_target_already_added(target_name):
            for plan_target in self.targets():
                if plan_target.is_disabled():
                    continue
                # For indirect targets we want to skip "ignored" tests
                if not is_direct and plan_target.is_ignored():
                    continue
                if plan_target.is_alias_of(target_name):
                    self._my_test_plan.append(plan_target)

    def cover_all(self) -> None:
        """Cover all the targets available."""
        for cover_target in self.targets():
            self.add_target_to_plan(cover_target.name, is_direct=False)

    def cover_module_utils(self, pymodule: str, names: list[str]) -> None:
        """Track the targets to run follow up to a module_utils changed.

        :param pymodule: collection module
        :param names: collections names
        """
        if self.modules_import is None or self.utils_import is None:
            self.modules_import, self.utils_import = build_import_tree(
                self.collection_path, self.collection_name, names
            )

        u_candidates = [pymodule]
        # add as candidates all module_utils which include this module_utils
        u_candidates += [
            import_lib for _, imports in self.utils_import.items() for import_lib in imports
        ]

        for mod, mod_imports in self.modules_import.items():
            if any(util in mod_imports for util in u_candidates):
                self.add_target_to_plan(mod, is_direct=False)

    def slow_targets_to_test(self) -> list[str]:
        """List collection slow targets.

        :returns: list of slow targets
        """
        return sorted(list({t.name for t in self.test_plan if t.is_slow()}))

    def regular_targets_to_test(self) -> list[str]:
        """List regular targets to test.

        :returns: list of regular targets
        """
        return sorted(list({t.name for t in self._my_test_plan if not t.is_slow()}))


class ElGrandeSeparator:
    """A class to build output for the targets to test."""

    def __init__(self, collections_items: list[Collection], number_jobs: int) -> None:
        """Class constructor.

        :param collections_items: list of collections being tested
        :param number_jobs: number of jobs to share targets on
        """
        self.collections = collections_items
        self.total_jobs = number_jobs
        self.targets_per_slot = 10

    def output(self) -> str:
        """Produce output for the targets to test.

        :returns: a string describing the output
        """
        batches = []
        for col in self.collections:
            slots = [f"{col.collection_name}-{i+1}" for i in range(self.total_jobs)]
            for batch in self.build_up_batches(slots, col):
                batches.append(batch)
        return ";".join([f"{x}:{','.join(y)}" for x, y in batches])

    def build_up_batches(
        self, slots: list[str], my_collection: Collection
    ) -> Generator[tuple[str, list[str]], None, None]:
        """Build up batches.

        :param slots: list of slots
        :param my_collection: collection containing list of targets
        :yields: batches
        """
        if not my_collection.test_groups:
            sorted_targets = sorted(
                my_collection.test_plan, key=lambda x: x.execution_time(), reverse=True
            )
            my_collection.test_groups = [{"total": 0, "targets": []} for _ in range(len(slots))]
            my_collection.test_groups = equal_share(sorted_targets, len(slots))

        for group in my_collection.test_groups:
            if group["targets"] == []:
                continue
            my_slot = slots.pop(0)
            yield (my_slot, group["targets"])


def make_unique(data: list[str]) -> list[str]:
    """Remove duplicated items of a list containing string.

    :param data: input list of string
    :returns: A list containing unique items
    """
    tmp = []
    for i in data:
        if i not in tmp:
            tmp.append(i)
    return tmp


def equal_share(targets: list[Target], nbchunks: int) -> list[dict[str, Any]]:
    """Split a list of targets into equal size chunks.

    :param targets: The list of target to share
    :param nbchunks: The number of chunks to share targets into
    :returns: A list of dictionary with a set of targets and the total size
    """
    total_data = [0 for _ in range(nbchunks)]
    targets_data = [[] for _ in range(nbchunks)]  # type: List[List[str]]

    for my_target in targets:
        index = total_data.index(min(total_data))
        total_data[index] += my_target.execution_time()
        targets_data[index].append(my_target.name)

    return [{"total": total_data[i], "targets": targets_data[i]} for i in range(nbchunks)]


def read_test_all_the_targets() -> bool:
    """Test if all targets should be executed.

    :returns: whether the full suite should be run or not
    """
    test_all = os.environ.get("ANSIBLE_TEST_ALL_THE_TARGETS", "")
    test_all_the_targets = False
    if test_all and test_all.lower() == "true":
        test_all_the_targets = True
    return test_all_the_targets


def read_total_jobs() -> int:
    """Read the number of job to divide targets into.

    :returns: total jobs as integer
    """
    default_value = "3"
    total_jobs = os.environ.get("TOTAL_JOBS", default_value)
    try:
        result = int(total_jobs)
    except ValueError:
        result = int(default_value)
    return result


def read_targets_to_test() -> dict[str, list[str]]:
    """Determine specific targets to test based on TargetsToTest flag into pull request body.

    :returns: list of targets to test per collection
    """
    targets_to_test = {}
    body = os.environ.get("PULL_REQUEST_BODY", "")
    regex = re.compile(r"^TargetsToTest=([\w\.\:,;]+)", re.MULTILINE | re.IGNORECASE)
    match = regex.search(body)
    if match:
        for item in match.group(1).split(";"):
            if not item:
                continue
            elements = item.split(":")
            targets_to_test[elements[0]] = elements[1].split(",")
    return targets_to_test


def read_collections_to_test() -> list[PosixPath]:
    """Read module parameters from environment variables.

    :returns: a list of parameters to execute the module
    """
    return [
        PosixPath(path)
        for path in os.environ.get("COLLECTIONS_TO_TEST", "").replace("\n", ",").split(",")
        if path.strip()
    ]
