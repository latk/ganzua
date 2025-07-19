Lockinator
==========

A tool for inspecting Python dependency lockfiles.

For example, we can summarize the differences between two `uv.lock` files:

```console
$ lockinator diff tests/{old,new}-uv-project/uv.lock
{
  "annotated-types": {
    "old": null,
    "new": "0.7.0"
  },
  "typing-extensions": {
    "old": "3.10.0.2",
    "new": "4.14.1"
  }
}
```
