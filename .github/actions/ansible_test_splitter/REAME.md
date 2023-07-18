# ansible_test_splitter

This action identifies the targets impacted by the changes on a pull request and split them into a number of jobs defined by the user.

## Usage

<!-- start usage -->

```yaml
- uses: ansible-network/github_actions/.github/actions/ansible_test_splitter@main
  with:
    # Path to a list of collections
    collections_to_test: |
      path_to_collection_1
      path_to_collection_2
      (...)
      path_to_collection_n

    # The total number of jobs to share
    total_jobs: 5
```

The action output is a variable `test_targets` containing a list of chunk for each collection with the targets for each chunk.
e.g: `community.aws-1:dynamodb_table;community.aws-2:elb_target;community.aws-3:msk_cluster-auth;community.aws-4:secretsmanager_secret;community.aws-5:redshift,ec2_transit_gateway_vpc_attachment`

<!-- end usage -->

## Relationship between plugins/roles and targets

This action reads elements to test from `plugins` and `roles` directories and corresponding tests from `tests/integration/targets` directory. Here after more details on the relationship between plugins/roles and integration tests targets:

- `modules`, the test target should have the same name as the module or defines the module name into the `aliases` file

_Example_:

```
    |___plugins/modules/my_module.py
    |___tests
        |___integration
            |___targets
                |___my_module
                |___another_test
                    |___aliases (contains this line my_module)
```

For any change on `plugins/modules/my_module.py`, this action will produce `my_module` and `another_test` as impacted targets.

- `roles`, the test target should defines the role name with the prefix `role` into the `aliases` file.

_Example_:

```
    |___roles/some_role
    |___tests
        |___integration
            |___targets
                |___test_of_some_role
                    |___aliases (contains this line role/some_role)
```

For any change on `roles/some_role`, this action will produce `test_of_some_role` as impacted target.

- For any other plugin (inventory, connection, module_utils, plugin_utils, lookup), the test target should have the same name as the plugin or defines the plugin name prefixed by the plugin type and underscore (e.g: **inventory_myinventory**) into the `aliases` file.

_Example_:

```
    |___plugins/lookup/random.py
    |___tests
        |___integration
            |___targets
                |___lookup_random
                |___test_random
                    |___aliases (contains this line lookup_random)
```

For any change on `plugins/lookup/random.py`, this action will produce `lookup_random` and `test_random` as impacted targets.

## Debugging

- Set the label `test-all-the-targets` on the pull request to run the full test suite instead of the impacted changes.
- Use `TargetsToTest=collection1:target01,target02;collection2:target03,target4` in the pull request description to run a specific list of targets.
  _Example_: You need to test the following targets for a pull request

```yaml
- collection1: some_test_1 some_test_2
- collection2: another_test
```

The pull request should contain the following line `TargetsToTest=collection1:some_test_1,some_test_2;collection2:another_test`.
