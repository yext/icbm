# ICBM

ICBM is a build tool that specializes in building Java applications. It also includes support for handling [protocol buffer][] definitions, [Play framework 1.x] projects, and build steps that are arbitrary commands.

[protocol buffer]: https://developers.google.com/protocol-buffers/docs/overview
[Play framework 1.x]: http://www.playframework.com/documentation/1.2.7/home

ICBM has been the primary Java build tool used at [Yext][] since late 2010.

[Yext]: http://www.yext.com/

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

## To Learn More

This documentation is a work in progress, and it will be fleshed out in more detail leading up to our [live event on September 24, 2013][]. We are also working on sanding off more of the Yext-specific rough edges.

[live event on September 24, 2013]: http://build.splashthat.com/

In the meantime, we invite you to join the project and send questions or contributions through either GitHub or [our Google Group][]!

[our Google Group]: https://groups.google.com/d/forum/icbm-users "icbm-users in Google Groups"
