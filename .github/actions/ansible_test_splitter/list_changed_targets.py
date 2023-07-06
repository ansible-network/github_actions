#!/usr/bin/env python3
"""Script to list target to test for a pull request."""

import json
import os

from pathlib import PosixPath
from typing import Dict
from typing import List
from typing import Union

from list_changed_common import Collection
from list_changed_common import ElGrandeSeparator
from list_changed_common import WhatHaveChanged
from list_changed_common import make_unique
from list_changed_common import read_collections_to_test
from list_changed_common import read_targets_to_test
from list_changed_common import read_test_all_the_targets
from list_changed_common import read_total_jobs


class ListChangedTargets:
    """A class used to list changed impacted for a pull request."""

    def __init__(self) -> None:
        """Class constructor."""
        self.collections_to_test = read_collections_to_test()
        self.total_jobs = read_total_jobs()

        self.test_all_the_targets = read_test_all_the_targets()
        self.targets_to_test = read_targets_to_test()
        self.base_ref = os.environ.get("PULL_REQUEST_BASE_REF", "")

    def make_change_targets_to_test(self, collections: list[Collection]) -> dict[str, list[str]]:
        """Create change for a specific target to test.

        :param collections: list of collections being tested
        :returns: list of target per collection
        """
        changes = {}
        for collection in collections:
            name = collection.collection_name
            if name in self.targets_to_test:
                for target in self.targets_to_test[name]:
                    collection.add_target_to_plan(target)
            changes[name] = collection.test_plan_names

        return changes

    def make_change_for_all_targets(self, collections: list[Collection]) -> dict[str, list[str]]:
        """Create change for full test suite.

        :param collections: list of collections being tested
        :returns: list of all targets per collection
        """
        changes = {}
        for collection in collections:
            collection.cover_all()
            changes[collection.collection_name] = collection.test_plan_names

        return changes

    def make_changed_targets(self, collections: list[Collection]) -> dict[str, list[str]]:
        """Create change for changed targets.

        :param collections: list of collections being tested
        :returns: list of targets per collection
        """
        listed_changes = {}  # type: Dict[str, Dict[str, List[str]]]
        collections_names = [collection.collection_name for collection in collections]

        def _add_changed_target(
            name: str, ref_path: Union[PosixPath, str], plugin_type: str
        ) -> None:
            if plugin_type == "targets":
                file_name, plugin_file_name = str(ref_path), str(ref_path)
            elif plugin_type == "modules":
                file_name = PosixPath(ref_path).stem
                plugin_file_name = file_name
            elif plugin_type == "roles":
                file_name = str(ref_path)
                plugin_file_name = f"role/{file_name}"
            else:
                file_name = PosixPath(ref_path).stem
                plugin_file_name = f"{plugin_type}_{PosixPath(ref_path).stem}"
            listed_changes[name][plugin_type].append(file_name)
            for collection in collections:
                collection.add_target_to_plan(plugin_file_name)

        for whc in [WhatHaveChanged(path, self.base_ref) for path in self.collections_to_test]:
            print(f"changes file for collection [{whc.collection_name}] => {whc.changed_files()}")
            listed_changes[whc.collection_name] = {
                "modules": [],
                "inventory": [],
                "connection": [],
                "module_utils": [],
                "plugin_utils": [],
                "lookup": [],
                "targets": [],
                "roles": [],
            }
            for path in whc.modules():
                _add_changed_target(whc.collection_name, path, "modules")
            for path in whc.inventory():
                _add_changed_target(whc.collection_name, path, "inventory")
            for path in whc.connection():
                _add_changed_target(whc.collection_name, path, "connection")
            for path, pymod in whc.module_utils():
                _add_changed_target(whc.collection_name, path, "module_utils")
                for collection in collections:
                    collection.cover_module_utils(pymod, collections_names)
            for path, pymod in whc.plugin_utils():
                _add_changed_target(whc.collection_name, path, "plugin_utils")
                for collection in collections:
                    collection.cover_module_utils(pymod, collections_names)
            for path in whc.lookup():
                _add_changed_target(whc.collection_name, path, "lookup")
            for target in whc.targets():
                _add_changed_target(whc.collection_name, target, "targets")
            for role in whc.roles():
                _add_changed_target(whc.collection_name, role, "roles")

        print("----------- Listed Changes -----------\n", json.dumps(listed_changes, indent=2))
        return {x: make_unique(y["targets"]) for x, y in listed_changes.items()}

    def run(self) -> str:
        """List changes and divide targets into chunk.

        :returns: resulting string of targets divide into chunks
        """
        collections = [Collection(p) for p in self.collections_to_test]

        if self.targets_to_test:
            changes = self.make_change_targets_to_test(collections)
        elif self.test_all_the_targets:
            changes = self.make_change_for_all_targets(collections)
        else:
            changes = self.make_changed_targets(collections)

        print("----------- Changes -----------\n", json.dumps(changes, indent=2))
        egs = ElGrandeSeparator(collections, self.total_jobs)
        return egs.output()


def write_variable_to_github_output(name: str, value: str) -> None:
    """Write content variable to GITHUB_OUTPUT.

    :param name: variable name to write into GITHUB_OUTPUT
    :param value: variable content
    """
    github_output_file = os.environ.get("GITHUB_OUTPUT") or ""
    if github_output_file:
        with open(github_output_file, "a", encoding="utf-8") as file_write:
            file_write.write(f"{name}={value}\n")


def main() -> None:
    """Perform main process of the module."""
    output = ListChangedTargets().run()
    write_variable_to_github_output("test_targets", output)


if __name__ == "__main__":
    main()
