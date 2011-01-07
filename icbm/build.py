#!/usr/bin/python
#
# Copyright 2010 Yext, Inc. All Rights Reserved.

__author__ = "ilia@yext.com (Ilia Mirkin)"

import optparse
import os
import sys

import engine
import data
import genautodep


def main():
    parser = optparse.OptionParser()
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose")
    (options, args) = parser.parse_args()
    data.VERBOSE = options.verbose

    try:
        os.mkdir(engine.BUILD_DIR)
    except:
        pass

    modules = genautodep.ComputeDependencies([
        "Core/src",
        "kernel/src",
        "partners/src",
        "src",
        "apps/src",
        "admin/src",
        "Core/jars",
        "kernel/jars",
        "partners/jars",
        "closure",
        "jetty/jetty-distribution-7.0.2.v20100331",
        "play-common/src",
        "play-common/app",
        "play-common/lib",
        "thirdparty",
        "tools/gwt",
        "closure/selenium/src",
        "closure/selenium/lib"])
    for module in modules.itervalues():
        mname = module.name
        for package, farr in module.files.iteritems():
            path = farr[0].path
            for f in farr:
                name = "lib%s" % f.name
                lib = data.JavaLibrary(
                    mname, path, name,
                    list(data.FixPath(mname, path, ["%s.java" % f.name])),
                    [],
                    list(c.DepName() for c in f.classes.itervalues()),
                    [])
                data.DataHolder.Register(mname, path, name, lib)
            # Create a lib in each package as well
            lib = data.JavaLibrary(
                mname, path, "lib",
                [],
                [],
                list(f.DepName() for f in farr),
                [])
            data.DataHolder.Register(mname, path, "lib", lib)
            #print mname, path, "lib"
        for jar in module.jars:
            lib = data.JavaLibrary(
                mname, "", jar.name, [],
                list(data.FixPath(mname, jar.path, ["%s.jar" % jar.name])),
                [], [])
            data.DataHolder.Register(mname, jar.path, jar.name, lib)
        lib = data.JavaLibrary(
            mname, "", "jars",
            [],
            [],
            list(f.DepName() for f in module.jars),
            [])
        data.DataHolder.Register(mname, "", "jars", lib)

    for target in args:
        # load the corresponding spec files
        data.LoadTargetSpec(data.TOPLEVEL, target)
    for target in args:
        d = data.DataHolder.Get(data.TOPLEVEL, target)
        d.LoadSpecs()
    success = data.DataHolder.Go(args)
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
