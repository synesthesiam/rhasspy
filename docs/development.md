# Development

Rhasspy's code can be found [on GitHub](https://github.com/synesthesiam/rhasspy).

## Set up your development environment

If you want to start developing on Rhasspy, [fork](https://help.github.com/en/github/getting-started-with-github/fork-a-repo) the repository, and clone your fork:

```bash
git clone https://github.com/<your_username>/rhasspy.git
cd rhasspy
```

Add the original repository as an [upstream remote](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/configuring-a-remote-for-a-fork):

```bash
git remote add upstream https://github.com/synesthesiam/rhasspy.git
```

Then follow the installation steps for a [virtual environment](installation.md#virtual-environment). If the `create-venv.sh` script fails, please [report an issue](https://github.com/synesthesiam/rhasspy/issues) before proceeding.

If you pull changes, make sure to re-download and extract `rhasspy-web-dist.tar.gz` from [the releases page](https://github.com/synesthesiam/rhasspy/releases/tag/v2.0). This contains the pre-compiled web artifacts. Alternatively, you can install [yarn](https://yarnpkg.com) and run `yarn build` in the `rhasspy` directory after a `git pull`.

## Run the unit tests

A good start to check whether your development environment is set up correctly (or to find some bugs) is to run the unit tests:

```bash
./run-tests.sh
```

This will run tests against pre-recorded WAV files in `rhasspy/etc/test` for specific languages. You can run tests only for a specific language (profile) like this:

```bash
./run-tests.sh -p en
```

It’s good practice to run the unit tests before and after you work on something, to be sure your changes don't accidentally break something.

## Keeping your fork synchronized

When the upstream repository has new commits, you should [synchronize your fork](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/syncing-a-fork):

```bash
git fetch upstream
git checkout master
git merge upstream/master
```

Then [update your fork on GitHub](https://help.github.com/en/github/using-git/pushing-commits-to-a-remote-repository):

```bash
git push
```

Your fork is now synchronized to the original repository.

## Development practices

* Before starting significant work, please propose it and discuss it first on the [issue tracker](https://github.com/synesthesiam/rhasspy/issues) on GitHub. Other people may have suggestions, will want to collaborate and will wish to review your code.
* Please work on one piece of conceptual work at a time. Keep each narrative of work in a different branch.
* As much as possible, have each commit solve one problem.
* A commit must not leave the project in a non-functional state.
* Run the unit tests before you create a commit.
* Treat code, tests and documentation as one.
* Create a [pull request](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request-from-a-fork) from your fork.

## Development workflow

If you want to start working on a specific feature or bug fix, this is an example workflow:

* Synchronize your fork with the upstream repository.
* Create a new branch: `git checkout -b <nameofbranch>`
* Create your changes.
* Add the changed files with `git add <files>`.
* Commit your changes with `git commit`.
* Push your changes to your fork on GitHub.
* Create a pull request from your fork.

## License of contributions

By submitting patches to this project, you agree to allow them to be redistributed under the project’s [license](license.md) according to the normal forms and usages of the open source community.

It is your responsibility to make sure you have all the necessary rights to contribute to the project.
