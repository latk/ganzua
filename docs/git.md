# Git

Ganzua can read files from the Git history, which is especially useful for diffs.
Support varies by subcommand:

* [`ganzua inspect`](cli/ganzua-inspect.md) (`LOCKFILE`)\
  Added in *Ganzua NEXT*.

* [`ganzua diff`](cli/ganzua-diff.md) (`OLD`, `NEW`)\
  Added in *Ganzua NEXT*.

## Security

Using the Git feature will invoke the `git` executable.
Depending on your `PATH`, this may run arbitrary code on your system.
Make sure that `git` resolves to the expected git client (e.g. by using `which git`).

You can **override the Git executable name** via the `--git-executable` option.
If you use this to provide a path (not just a name),
this avoids the `PATH` lookup, thus giving you full control.

You can **disable the Git feature** via the `--no-git` option.

Depending on your Git configuration, Git may run additional hooks or commands.
Only use Ganzua's Git mode in repositories that you trust.

## Supported syntax

Files from the Git history are named as `<rev>:<path>`,
where the `<rev>` identifies a commit,
and the `<path>` identifies a file as of that commit.
For example, `HEAD:uv.lock` loads the `uv.lock` file as of the last commit on the current branch.

Ganzua doesn't parse Git object names itself and just hands them over to Git.
So the entire [`gitrevisions` syntax](https://git-scm.com/docs/gitrevisions) is supported.
Ganzua only requires that the argument names a “blob object”,
not other Git object types like commits or trees.
Such object names have the shape `<rev>:<path>`, i.e. always include a `:` colon separator.

In Git mode, Ganzua determines the type of an argument as follows:

1. If the argument starts with `/`, `./`, or `../`, it is treated as a plain path.
   So Unix-style absolute or relative paths can always be named.
2. If the argument contains a `:` separator, it is treated as a git object name.
3. Otherwise, the argument is treated as a plain file.

**Escape hatches:** In the unlikely event that you're dealing with files or revisions that don't match these syntax heuristics, you can

* disable the Git feature via `--no-git`, or
* load the data outside of Ganzua.

For example, you can use the `<(...)` Bash process substitution operator
and use commands like `git show` (to load data from a Git repo)
or `cat` (for reading plain files).
The following two commands are equivalent in Bash:

```bash
$ ganzua diff HEAD:uv.lock uv.lock
$ ganzua diff <(git show HEAD:uv.lock) <(cat uv.lock)
```

## Examples

Let's set up a Git repository where we commit an old `uv.lock`,
and then copy a new version over it:

```console
$ git -C $EXAMPLE init .
Initialized empty Git repository in ${EXAMPLE}/.git/
$ cp $CORPUS/old-uv-project/uv.lock $EXAMPLE/uv.lock
$ git -C $EXAMPLE add uv.lock
$ git -C $EXAMPLE commit -m "old lockfile"
[main (root-commit) 90cb4d4] old lockfile
 1 file changed, 23 insertions(+)
 create mode 100644 uv.lock
$ cp $CORPUS/new-uv-project/uv.lock $EXAMPLE/uv.lock
```

We can now inspect the new version of the file – all of these are equivalent:

<!-- doctest: compare output -->
* `$ env -C $EXAMPLE ganzua inspect uv.lock`
* `$ env -C $EXAMPLE ganzua inspect ./uv.lock`

<details><summary>output for the above commands</summary>

```json
{
  "packages": [
    {
      "name": "annotated-types",
      "version": "0.7.0",
      "source": "pypi"
    },
    {
      "name": "example",
      "version": "0.1.0",
      "source": {
        "direct": "."
      }
    },
    {
      "name": "typing-extensions",
      "version": "4.14.1",
      "source": "pypi"
    }
  ]
}
```

</details>

And we can inspect the file from the commit history –
all of these git object names are equivalent in this scenario:

<!-- doctest: compare output -->
* `$ env -C $EXAMPLE ganzua inspect HEAD:uv.lock` (`HEAD`)
* `$ env -C $EXAMPLE ganzua inspect @:uv.lock`  (`@` as alias for `HEAD`)
* `$ env -C $EXAMPLE ganzua inspect main:uv.lock` (branch name)
* `$ env -C $EXAMPLE ganzua inspect 90cb4d4:uv.lock` (commit hash)
* `$ env -C $EXAMPLE ganzua inspect :uv.lock` (staged file)
* `$ env -C $EXAMPLE ganzua inspect HEAD:./uv.lock` (relative paths within the commit)

<details><summary>output for the above commands</summary>

```json
{
  "packages": [
    {
      "name": "example",
      "version": "0.1.0",
      "source": {
        "direct": "."
      }
    },
    {
      "name": "typing-extensions",
      "version": "3.10.0.2",
      "source": "pypi"
    }
  ]
}
```

</details>

We can compare a lockfile across Git revisions:

```console
$ env -C $EXAMPLE ganzua diff HEAD:uv.lock uv.lock --format=markdown
2 changed packages (1 added, 1 updated)

| package           | old      | new    | notes |
|-------------------|----------|--------|-------|
| annotated-types   | -        | 0.7.0  |       |
| typing-extensions | 3.10.0.2 | 4.14.1 | (M)   |

* (M) major change
```

Git mode can be disabled.
Passing a Git object name will then produce an error because no such file can be found:

```console
$ env -C $EXAMPLE ganzua inspect HEAD:uv.lock --no-git
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: LOCKFILE: Path `HEAD:uv.lock` does not exist.
[command exited with status 2]
```

If the Git object name points to a nonexistent or invalid Git object,
that error is reported as well.

<details><summary>nonexistent commit</summary>

```console
$ env -C $EXAMPLE ganzua inspect no-such-branch:uv.lock
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Could not read file from Git history: `no-such-branch:uv.lock`
Note: Command `git cat-file blob no-such-branch:uv.lock` exited with status 128
[command exited with status 2]
```
</details>

<details><summary>not a blob</summary>

```console
$ env -C $EXAMPLE ganzua inspect :/old
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Could not read file from Git history: `:/old`
Note: Command `git cat-file blob :/old` exited with status 128
[command exited with status 2]
```

</details>

<details><summary>nonexistent path</summary>

```console
$ env -C $EXAMPLE ganzua inspect HEAD:does-not-exist
Usage: ganzua inspect [OPTIONS] [LOCKFILE]
Try 'ganzua inspect --help' for help.

Error: Could not read file from Git history: `HEAD:does-not-exist`
Note: Command `git cat-file blob HEAD:does-not-exist` exited with status 128
[command exited with status 2]
```

</details>
