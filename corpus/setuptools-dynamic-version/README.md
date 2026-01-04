A project using using the Setuptools `[build-system]` and a `dynamic = ["version"]`.
When doing an editable install of such a package, no version will be set.
This reproduces the problem in <https://github.com/latk/ganzua/issues/4>.
