#!/usr/bin/python
#
# Copyright 2011 Yext, Inc. All Rights Reserved.

__author__ = "ilia@yext.com (Ilia Mirkin)"

import cPickle
import os
import re
import sys
import threading
import time
import zipfile

CLEAN_CODE_RE = re.compile(
    r"""(
    /\*.*?\*/ # Matches /* */
      |
    //[^\n]* # Matches //
      |
    # Matches a class-looking reference inside of a "-enclosed string literal
    "(?P<repl>(?:com|org|net|javax)\.[a-zA-Z0-9_\.]*\.[A-Z][A-Za-z0-9_]+)"
      |
    "[^\\"]*(\\.[^\\"]*)*" # Matches a "-enclosed string literal
      |
    '[^\\']*(\\.[^\\']*)*' # Matches a '-enclosed string literal
    )""", re.M | re.X | re.S)

# Package specification
PACKAGE_RE = re.compile(r"package (.*);")

# import statement
IMPORT_RE = re.compile(r"import(?: static)? (.*);")

# Class(?) reference, not preceded with a .
LOCAL_RE = re.compile(r"(?!\.).\b([A-Z]\w+)\b")

# Fully-qualified class reference
FULL_RE = re.compile(r"\b(?:com|org|net|javax)\.[a-zA-Z0-9_\.]*\.[A-Z][A-Za-z0-9_]+\b")

# Class reference inside of an import
IMPORT_PARSE_RE = re.compile(r"\b([A-Z]\w+)\b")

# Finds the (likely) package name from an import
IMPORT_PACKAGE_RE = re.compile(
    r"((TARGUS)?[a-z0-9\._]+)\.([A-Z\*][A-Za-z0-9_]*)")

# Figures out if we should ignore a missing dependency based on the fq name
IGNORE_MISSING_DEP_RE = re.compile(
    r"""^(
    javax
      |
    org\.w3c\.dom
      |
    org\.xml\.sax
      |
    com\.sun\.org\.apache\.xml\.internal
    )\.""", re.X)

# Figures out if we should ignore classes that are inside of a JAR for
# the purposes of depending on those jars.
IGNORE_JAR_CLASSES_RE = re.compile(
    r"""^(
    javax\.xml\.parsers
      |
    javax\.xml\.xpath
      |
    org\.w3c\.dom
      |
    org\.xml\.sax
      |
    com\.sun\.org\.apache\.xml\.internal
    )\.""", re.X)

class File(object):
    """
    """

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.name)

    def DepName(self):
        raise NotImplementedError

class JavaFile(File):

    def __init__(self, module, path, name, contents):
        self.module = module
        self.path = path
        self.name = name

        contents = CLEAN_CODE_RE.sub(lambda x: x.group("repl") or "", contents)

        package = PACKAGE_RE.search(contents).group(1)
        imports = IMPORT_RE.findall(contents)
        local_refs = LOCAL_RE.findall(contents)
        full_refs = FULL_RE.findall(contents)

        classes = dict((m, None) for m in local_refs)

        for m in imports + full_refs:
            if (m.startswith("java.") or
                m.startswith("com.sun.management") or
                m.startswith("com.sun.net.httpserver")):
                continue
            match = IMPORT_PARSE_RE.search(m)
            if match:
                classes[match.group(1)] = m

        #print package
        #print classes

        self.parsed_classes = classes
        self.package = package
        self.stat = None

    def __repr__(self):
        return "%s(%s.%s)" % (self.__class__.__name__, self.package, self.name)

    def __getstate__(self):
        return (self.module, self.path, self.name, self.package, self.stat,
                self.parsed_classes)

    def __setstate__(self, state):
        self.module = state[0]
        self.path = state[1]
        self.name = state[2]
        self.package = state[3]
        self.stat = state[4]
        self.parsed_classes = state[5]

    def PopulateDependencies(self, packages, classes, protos):
        self.classes = {}

        fqdns = {}
        other = set()

        for name, fqdn in self.parsed_classes.iteritems():
            if name == self.name:
                continue
            elif fqdn:
                fqdns[name] = fqdn
            else:
                other.add(name)

        # Go through the rest of the classes and map class name -> JavaFile
        for name, fqdn in fqdns.iteritems():
            m = IMPORT_PACKAGE_RE.match(fqdn)
            assert m, fqdn
            package = m.group(1)
            # Do we know about this package from parsing the various files?
            pmap = packages.get(package, {})
            if name in pmap:
                self.classes[name] = pmap[name]
            else:
                # Couldn't match any existing files, check the passed
                # in classes (aka JARs).
                match = m.group(0)
                if match in classes:
                    self.classes[name] = classes[match]

        pmap = packages[self.package]
        for name in other:
            if name in pmap:
                self.classes[name] = pmap[name]

        for name, fqdn in fqdns.iteritems():
            if name in self.classes:
                continue

            if not IGNORE_MISSING_DEP_RE.match(fqdn):
                print "Ignoring unresolved dependency from", repr(self), ":", fqdn

        #print self.DepName(), "{"
        #for c in sorted(self.classes):
        #    print "  ", c, ":", self.classes[c].DepName()
        #print "}"

    def DepName(self):
        return "%s=%s:lib%s" % (self.module, self.path, self.name)

class JarFile(File):

    def __init__(self, module, path, name, filename):
        self.module = module
        self.name = name
        self.path = path

        self.classes = set()

        f = zipfile.ZipFile(filename, "r")
        for info in f.infolist():
            if info.filename.endswith(".class"):
                self.classes.add(info.filename[:-6].replace("/", "."))
        f.close()

    def DepName(self):
        return "%s=%s:%s" % (self.module, self.path, self.name)


PROTO_PACKAGE_RE = re.compile(r"option java_package.*\"(.*)\";")
PROTO_CLASSNAME_RE = re.compile(r"option java_outer_classname.*\"(.*)\";")
PROTO_IMPORT_RE = re.compile(r"import \"(.*)\";")

class ProtoFile(File):

    def __init__(self, module, path, name, filename):
        self.module = module
        self.protoname = name
        self.path = path

        proto = open(filename).read()

        self.package = PROTO_PACKAGE_RE.search(proto).group(1)
        m = PROTO_CLASSNAME_RE.search(proto)
        if m:
            self.name = m.group(1)
        else:
            self.name = name

        self.deps = PROTO_IMPORT_RE.findall(proto)

        self.classes = dict([(self.name, self)])

    def DepName(self):
        return "%s=%s:lib%s" % (self.module, self.path, self.name)

    def PopulateDependencies(self, packages, classes, protos):
        self.extras = []
        for dep in self.deps:
            assert dep.endswith(".proto"), (
                "Dependency %s of %s does not end in .proto" %
                (dep, self.DepName()))
            proto = dep[:-len(".proto")]

            assert proto in protos, (
                "Could not find dependency %s of %s" % (dep, self.DepName()))
            proto_file = protos[proto]

            dep_path = os.path.abspath(os.path.join(proto_file.module, dep))
            self.extras.append((dep, dep_path))


class Module(object):

    def __init__(self, name):
        self.name = name
        # Package Name -> [JavaFile]
        self.files = {}

        # List of jars
        self.jars = []

        # List of protos
        self.protos = []

def ComputeDependencies(dirs):
    print >>sys.stderr, "autodep", time.time(), "...",
    try:
        with open("build/autodep.cache", "rb") as f:
            cache = cPickle.load(f)
    except:
        cache = {}
    dirty = False
    modules = {}

    for d in dirs:
        #print >>sys.stderr, "parsing", d, time.time()
        module = modules[d] = Module(d)
        for root, dirs, files in os.walk(d):
            path = root[len(d)+1:]
            if path.startswith("src"):
                continue
            if path.startswith("build") or "/build/" in path:
                continue
            if path.startswith("jars-build") or "/jars-build/" in path:
                continue
            if path and d in ("closure",):
                continue
            for f in files:
                if f.startswith("."):
                    continue
                fname = os.path.join(root, f)
                stat = os.stat(fname)
                jf = None
                if (fname in cache and
                    cache[fname].stat.st_mtime >= stat.st_mtime):
                    jf = cache[fname]
                if f.endswith(".java") and d not in ("thirdparty", "closure"):
                    if not jf:
                        jf = JavaFile(d, path, f[:-5], open(fname).read())
                        cache[fname] = jf
                        dirty = True
                    jf.stat = stat
                    module.files.setdefault(jf.package, []).append(jf)
                elif f.endswith(".jar"):
                    if not jf:
                        jf = JarFile(d, path, f[:-4], fname)
                        cache[fname] = jf
                        dirty = True
                    jf.stat = stat
                    module.jars.append(jf)
                elif f.endswith(".proto"):
                    if not jf:
                        jf = ProtoFile(d, path, f[:-6], fname)
                        cache[fname] = jf
                        dirty = True
                    jf.stat = stat
                    module.files.setdefault(jf.package, []).append(jf)
                    module.protos.append(jf)
                # TODO: Add support for dealing with JSP imports

    #print >>sys.stderr, "linking", time.time()
    packages = {}
    for module in modules.itervalues():
        for package in module.files:
            packages.setdefault(package, {}).update(dict(
                    (f.name, f) for f in module.files[package]))

    classes = {}
    for module in modules.itervalues():
        for jar in module.jars:
            for c in jar.classes:
                #assert c not in classes, "%s: %r, %r" % (c, classes[c], jar)
                # Prefer non-obscure jars
                if IGNORE_JAR_CLASSES_RE.match(c):
                    continue
                if c in classes and module.name not in (
                    "Core/jars", "kernel/jars", "partners/jars"):
                    continue
                classes[c] = jar

    protos = {}
    for module in modules.itervalues():
        for proto in module.protos:
            protofn = os.path.join(proto.path, proto.protoname)
            assert protofn not in protos, protofn
            protos[protofn] = proto

    for module in modules.itervalues():
        for farr in module.files.itervalues():
            for f in farr:
                f.PopulateDependencies(packages, classes, protos)

    if dirty:
        def _WriteCache():
            with open("build/autodep.cache", "wb") as f:
                cPickle.dump(cache, f, -1)
        threading.Thread(target=_WriteCache).start()

    print >>sys.stderr, " done", time.time()

    return modules

if __name__ == '__main__':
    modules = ComputeDependencies(sys.argv[1:])
    for module in modules.itervalues():
        print module.name, ":"
        for pkg in module.files:
            print "  ", pkg, ":", len(module.files[pkg]), "files"

