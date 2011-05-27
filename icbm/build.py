#!/usr/bin/python
#
# Copyright 2010 Yext, Inc. All Rights Reserved.

__author__ = "ilia@yext.com (Ilia Mirkin)"

import optparse
import os
import sys
import time

import engine
import data
import genautodep


def RegisterJavaLibrary(module, f):
    name = "lib%s" % f.name
    lib = data.JavaLibrary(
        module.name, f.path, name,
        list(data.FixPath(module.name, f.path, ["%s.java" % f.name])),
        [],
        list(c.DepName() for c in f.classes.itervalues()),
        [])
    data.DataHolder.Register(module.name, f.path, name, lib)
    #print "reg %s=%s:%s" % (module.name, f.path, name)

    # Create a binary target that depends solely on the lib
    binary = data.JavaBinary(
        module.name, f.path, f.name,
        "%s/%s" % (f.path, f.name),
        ["%s:%s" % (f.path, name)])
    data.DataHolder.Register(module.name, f.path, f.name, binary)

    # Create a jar target for the binary as well
    jar = data.JavaJar(
        module.name, f.path, f.name + "_deploy", binary.FullName())
    data.DataHolder.Register(module.name, f.path, f.name + "_deploy", jar)


def main():
    start_time = time.time()

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
        "test",
        "khan/common/src",
        "khan/pss/src",
        "khan/babykhan/src",
        "khan/khanmaster/src",
        "pageshooter/src",
        "scripts/src",
        "apps/src",
        "admin/src",
        "Core/jars",
        "kernel/jars",
        "partners/jars",
        "khan/pss/jars",
        "closure",
        "apache-tomcat-6.0.16/bin",
        "jetty/jetty-distribution-7.0.2.v20100331",
        "play-common/src",
        "play-common/app",
        "play-common/lib",
        "thirdparty",
        "selenium-jars",
        "tools/gwt",
        "closure/selenium/src"])

    for module in modules.itervalues():
        mname = module.name
        for package, farr in module.files.iteritems():
            # Process non-protos before protos, in case there is
            # already a checked-in version, so that they don't
            # conflict.
            filemap = {}

            java_files = []
            proto_files = []
            for f in farr:
                filemap.setdefault(f.path, []).append(f)
                if isinstance(f, genautodep.ProtoFile):
                    proto_files.append(f)
                else:
                    java_files.append(f)

            for f in java_files:
                RegisterJavaLibrary(module, f)

            for f in proto_files:
                # Skip protos if there's already a lib for that name
                # that is out there.
                if data.DataHolder.Get(mname, f.DepName()):
                    continue

                RegisterJavaLibrary(module, f)

                gen = data.Generate(
                    mname, f.path, f.name + "_proto",
                    "../../tools/icbm/genproto.sh",
                    list(data.FixPath(mname, f.path, ["%s.proto" % f.protoname])) + f.extras,
                    [os.path.join(f.path, "%s.java" % f.name)])
                data.DataHolder.Register(mname, f.path, f.name + "_proto", gen)

            # Create a lib in each package as well
            for path, file_arr in filemap.iteritems():
                lib = data.JavaLibrary(
                    mname, path, "lib",
                    [],
                    [],
                    list(f.DepName() for f in file_arr),
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
        if not d:
            print "Unknown target:", target
            sys.exit(1)
        d.LoadSpecs()
    success = data.DataHolder.Go(args)

    elapsed_time = time.time() - start_time
    print
    print "Total ICBM build time: %.1f seconds" % elapsed_time

    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
