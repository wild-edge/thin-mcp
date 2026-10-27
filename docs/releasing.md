# Publishing to PyPI

The `publish.yml` GitHub Actions workflow publishes the wheel and source
distribution when a GitHub Release is published, including a prerelease.
Draft releases and tag pushes alone do not publish anything.

## One-time account setup

1. Create or sign in to your [PyPI account](https://pypi.org/account/login/),
   verify your email, and enable two-factor authentication.
2. In the [repository environment settings](https://github.com/wild-edge/thin-mcp/settings/environments),
   create an environment named **`pypi`**. Under deployment branches and tags,
   choose selected branches and tags and add a **tag** rule matching `v*`.
   Leave required reviewers unset if publishing should run automatically.
3. Open [PyPI's pending publisher form](https://pypi.org/manage/account/publishing/)
   and add a GitHub publisher with these exact values:

   | Field | Value |
   | --- | --- |
   | PyPI project name | `thin-mcp` |
   | Owner | `wild-edge` |
   | Repository name | `thin-mcp` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

   The workflow name is the filename, without `.github/workflows/`.
   If you already own the PyPI project, add the publisher under that project's
   **Manage → Publishing** settings instead. A pending publisher creates the
   project on first upload; it does not reserve the package name.
4. Commit and push the release workflow and this documentation to GitHub before
   creating the release tag. Ensure GitHub Actions is enabled for the repository.

No PyPI API token, password, or GitHub repository secret is needed. The publish
job requests a short-lived credential using GitHub's OIDC identity; only that
job has `id-token: write` permission.

## Each release

1. Choose an unused version according to the compatibility policy. Update
   `project.version` in `pyproject.toml`, run `uv lock`, and move the relevant
   `CHANGELOG.md` entries into a dated version section. For the first upload,
   reconcile the existing `0.1.0` changelog section and unreleased entries with
   the version you choose; the current package version is `0.1.0`.
2. Run the checks in [AGENTS.md](../AGENTS.md#verification), commit, and push the
   release changes. Wait for CI to pass.
3. On the [new GitHub Release page](https://github.com/wild-edge/thin-mcp/releases/new),
   create a tag matching the exact package version with a `v` prefix (for
   example, `v0.1.0` for version `0.1.0`). Target the tested release commit,
   add release notes, and click **Publish release**.
4. Watch **Actions → Publish to PyPI**. It reruns the full Python 3.12–3.14 CI
   matrix, verifies the tag, builds distributions, validates their metadata,
   and checks isolated core and Django-extra installations. Only after these
   pass does it upload those same artifacts to PyPI.
5. Confirm the release at [PyPI](https://pypi.org/project/thin-mcp/) and install
   the published version in a clean environment.

For prereleases, use a PEP 440 version such as `0.2.0rc1` and tag `v0.2.0rc1`;
the GitHub prerelease checkbox alone does not change the package version.
PyPI does not allow uploaded filenames to be reused, even after deletion.
Fix a published package by releasing a new version. If an upload fails, inspect
the workflow logs and PyPI project files before retrying.

References: [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
and [creating a project through a pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
