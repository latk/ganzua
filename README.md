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

## License

Copyright 2025 Lukas Atkinson

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
