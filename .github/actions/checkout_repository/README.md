# Checkout_repository

This action checks-out your repository under the specified destination directory using the action actions/checkout. Use the `depends-On: repository/pull/xx` to override the reference to checkout.

# Usage

<!-- start usage -->

```yaml
- uses: ansible-network/github_actions/.github/actions/checkout_repository@main
  with:
    # Repository name with owner. For example, ansible-collections/kubernetes.core
    repository: ""

    # The branch, tag, or SHA to checkout when the pull request body does not
    # contain any override for this repository.
    ref: ""

    # Relative path under $GITHUB_WORKSPACE to place the repository
    path: ""
```

<!-- end usage -->

# Depending on others PRs

The pull request body should contain the following sequence:

```
Depends-On: repository/pull/xx
```

# Scenarios

- [checkout pull request 12345 from repository my_org/my_collection](#Checkout-depending-pull-request)

## Checkout depending pull request

Github action step:

```yaml
- uses: ansible-network/github_actions/.github/actions/checkout_repository@main
  with:
    repository: my_org/my_collection
    ref: main
    path: /path/to/checkout/repository
```

Pull request body:

```text
Depends-On: https://github.com/my_org/my_collection/pull/12345
```
