# ganzua diff

<!-- command output: ganzua help diff --markdown --markdown-links=md-file -->

Usage: `ganzua diff [OPTIONS] OLD NEW`

Compare two lockfiles.

The `OLD` and `NEW` arguments must each point to an `uv.lock` or `poetry.lock` file,
or to a directory containing such a file.

There is no direct support for comparing a file across Git commits,
but it's possible to retrieve other versions via [`git show`][git-show].
Here is an example using a Bash redirect to show non-committed changes in a lockfile:

```bash
ganzua diff <(git show HEAD:uv.lock) uv.lock
```

[git-show]: https://git-scm.com/docs/git-show

**Options:**

* `--format [json|markdown]`
  Choose the output format, e.g. Markdown. [default: json]
* `--help`
  Show this help message and exit.

<!-- command output end -->
