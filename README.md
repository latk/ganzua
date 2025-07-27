Ganzua
======

A tool for extracting dependency information from Python lockfiles.

For example, we can summarize the differences between two `uv.lock` files:

```console
$ ganzua diff tests/{old,new}-uv-project/uv.lock
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

##  What does Ganzua mean?

The Spanish term *ganzúa* means lockpick. It is pronounced *gan-THU-a*.

This `ganzua` tool for interacting with Python dependency lockfiles
is unrelated to the [2004 cryptoanalysis tool of the same name](https://ganzua.sourceforge.net/en/index.html).
