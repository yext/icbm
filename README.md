# UNMAINTAINED

Yext has moved primarily to using [Bazel][] to manage our builds, and no further updates are planned for ICBM.

[Bazel]: https://bazel.build/

# ICBM

ICBM is a build tool that specializes in building Java applications. It also includes support for handling [protocol buffer][] definitions, [Play framework 1.x] projects, and build steps that are arbitrary commands.

[protocol buffer]: https://developers.google.com/protocol-buffers/docs/overview
[Play framework 1.x]: http://www.playframework.com/documentation/1.2.7/home

ICBM was the primary Java build tool used at [Yext][] from 2010 until 2018.

[Yext]: https://www.yext.com/

## System Requirements

* Python 2.7
* Apache Ant
* Java 6 *

\* Java 6 is required only because compiling with Java 6 specifically is currently hardcoded in the default Ant buildfile ICBM uses.

## Quick Start by Example

The `example/` folder contains an example project that shows off some of the features of ICBM. To try it out, run the following in the `example/` folder:

    ../icbm/build.py src/com/example/foo/Foo.java
    ./build/Foo/Foo
    ../icbm/build.py src=com/example/foo:Foo_deploy
    ./build/Foo_deploy.jar
