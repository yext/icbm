#!/usr/bin/python
#
# Copyright 2010 Yext, Inc. All Rights Reserved.

__author__ = "ilia@yext.com (Ilia Mirkin)"

import glob
import functools
import os
import sys

import engine

def cache(f):
    ret = {}
    def _Wrapper(*args, **kwargs):
        self = args[0]
        if self not in ret:
            ret[self] = f(*args, **kwargs)
        return ret[self]
    return _Wrapper

printed = set()
def pdep(a, b):
    if (a, b) in printed:
        return
    if a == b:
        return
    #print "\"%s\" -> \"%s\"" % (a, b)
    printed.add((a, b))

TOPLEVEL = "_top"

class DataHolder(object):

    # path:name -> fake-o data holders, which know how to insert things
    # into the engine.
    _registered = {}

    _processed = set()

    def __init__(self, module, path, name):
        self.module = module
        self.path = path
        self.name = name

    def FullName(self):
        return "%s=%s:%s" % (self.module, self.path, self.name)

    def Apply(self, e):
        raise NotImplementedError

    def LoadSpecs(self, deps):
        deps = list(self.Canonicalize(deps))
        for dep in deps:
            pdep(self.FullName(), dep)
        while len(deps) > 0:
            depname = deps.pop()
            try:
                LoadTargetSpec(self.module, depname)
            except:
                print "%s: error loading %s=%s" % (self.FullName(), self.module, depname)
                raise
            dep = DataHolder.Get(self.module, depname)
            assert dep, "%s not found by %s:%s" % (depname, self.path, self.name)
            if dep.FullName() in self._processed:
                continue
            self._processed.add(dep.FullName())
            if dep.deps:
                ds = list(dep.Canonicalize(dep.deps))
                deps.extend(ds)
                for d in ds:
                    pdep(dep.FullName(), d)

    def Canonicalize(self, deps):
        for dep in deps:
            if "=" in dep:
                yield dep
            else:
                yield "%s=%s" % (self.module, dep)


    @classmethod
    def Register(cls, module, path, name, obj):
        fname = "%s=%s:%s" % (module, path, name)
        assert fname not in cls._registered
        assert isinstance(obj, DataHolder)
        cls._registered[fname] = obj

    @classmethod
    def Get(cls, module, fname):
        if "=" not in fname:
            fname = "%s=%s" % (module, fname)
        return cls._registered.get(fname)

    @classmethod
    def Go(cls, targets):
        done = set()
        # TODO: is this necessary anymore?
        #while cls._processed | done != set(cls._registered):
        #    todo = set(cls._registered) - cls._processed - done
        #    for key in todo:
        #        cls._registered[key].LoadSpecs()
        #        done.add(key)
        e = engine.Engine()
        target_names = []
        #for target in cls._registered:
        #    holder = cls.Get(None, target)
        #    if not holder:
        #        print >>sys.stderr, "Unknown target", target
        #        continue
        #    holder.Apply(e)
        for target in targets:
            holder = cls.Get(TOPLEVEL, target)
            if not holder:
                print >>sys.stderr, "Unknown target", target
                continue
            ret = holder.TopApply(e)
            if ret:
                target_names.append(ret)
        e.ComputeDependencies()
        for target in target_names:
            e.BuildTarget(e.GetTarget(target))
        e.Go()

class JavaBinary(DataHolder):

    def __init__(self, module, path, name, main, deps, flags):
        DataHolder.__init__(self, module, path, name)
        self.main = main
        self.deps = deps
        self.flags = flags

    @cache
    def Apply(self, e):
        # Build up a list of source files, jars, and data files that
        # we need to get.
        sources = set()
        jars = self.jars = set()
        datas = set()

        deps = list(self.deps)
        processed = set()
        while len(deps) > 0:
            depname = deps.pop()
            dep = DataHolder.Get(self.module, depname)
            assert dep, "%s not found" % depname
            if dep.FullName() in processed:
                continue
            assert isinstance(dep, JavaLibrary)

            dep.Apply(e)

            if dep.files:
                sources.update(dep.files)
            if dep.jars:
                jars.update(dep.jars)
            if dep.data:
                datas.update(dep.data)
            if dep.deps:
                deps.extend(dep.Canonicalize(dep.deps))
            processed.add(dep.FullName())

        c = engine.JavaCompile(self.path, self.name, sources, jars,
                               datas, self.main, self.flags)
        e.AddTarget(c)
        return c.Name()

    TopApply = Apply

    def LoadSpecs(self):
        DataHolder.LoadSpecs(self, self.deps)
        if self.flags:
            DataHolder.LoadSpecs(
                self, ["Core=com/alphaco/util/flags:flag_processor"])


class JavaJar(DataHolder):
    def __init__(self, module, path, name, binary):
        DataHolder.__init__(self, module, path, name)
        self.binary = binary

    @cache
    def Apply(self, e):
        dep = DataHolder.Get(self.module, self.binary)
        assert dep, "%s not found" % self.binary
        assert isinstance(dep, JavaBinary)
        dep.Apply(e)
        #name = dep.Apply(e)
        #target = e.GetTarget(name)
        j = engine.JarBuild(self.path, self.name + ".jar", dep.name,
                            dep.jars, dep.main)
        e.AddTarget(j)
        return j.Name()

    TopApply = Apply

    def LoadSpecs(self):
        DataHolder.LoadSpecs(self, [self.binary])


class JavaLibrary(DataHolder):

    def __init__(self, module, path, name, files, jars, deps, data):
        DataHolder.__init__(self, module, path, name)
        self.jars = jars
        self.deps = deps
        self.data = data
        self.files = files

    @cache
    def TopApply(self, e):
        sources = set(self.files)
        jars = self.jars = set(self.jars)
        datas = set(self.data)

        deps = list(self.deps)
        processed = set()
        while len(deps) > 0:
            depname = deps.pop()
            dep = DataHolder.Get(self.module, depname)
            assert dep, "%s not found" % depname
            if dep.FullName() in processed:
                continue
            assert isinstance(dep, JavaLibrary)

            dep.Apply(e)

            if dep.files:
                sources.update(dep.files)
            if dep.jars:
                jars.update(dep.jars)
            if dep.data:
                datas.update(dep.data)
            if dep.deps:
                deps.extend(dep.Canonicalize(dep.deps))
            processed.add(dep.FullName())

        c = engine.JavaCompile(self.path, self.name, sources, jars,
                               datas, None, None)
        e.AddTarget(c)
        return c.Name()

    def Apply(self, e):
        pass

    def LoadSpecs(self):
        if self.deps:
            DataHolder.LoadSpecs(self, self.deps)


class Generate(DataHolder):

    def __init__(self, module, path, name, compiler, ins, outs):
        DataHolder.__init__(self, module, path, name)
        self.compiler = compiler
        self.ins = ins
        self.outs = outs

    @cache
    def Apply(self, e):
        target = engine.Generate(self.path, self.name, self.compiler,
                                 self.ins, self.outs)
        e.AddTarget(target)
        return target.Name()

    def LoadSpecs(self):
        pass

class Alias(DataHolder):

    def __init__(self, module, path, name, deps):
        DataHolder.__init__(self, module, path, name)
        self.deps = deps

    def Apply(self, e):
        deps = []
        for depname in self.deps:
            dep = DataHolder.Get(self.module, depname)
            deps.append(dep.Apply(e))
        target = engine.Alias(self.path, "__alias_%s" % self.name, deps)
        e.AddTarget(target)
        return target.Name()

    TopApply = Apply

    def LoadSpecs(self):
        DataHolder.LoadSpecs(self, self.deps)

def FixPath(module, path, lst):
    if not lst:
        return
    for l in lst:
        fake_path = os.path.join(path, l)
        if module != TOPLEVEL:
            base = "."
            if not fake_path.startswith("jars"):
                base = SRCDIR
            real_path = os.path.join(module, base, fake_path)
        else:
            real_path = fake_path
        if os.path.exists(real_path):
            yield fake_path, os.path.abspath(real_path)
        else:
            yield fake_path, fake_path

def java_library(module, dpath, name, path=None,
                 files=None, jars=None, deps=None, data=None):
    if path:
        dpath = path
    obj = JavaLibrary(module, dpath, name,
                      list(FixPath(module, dpath, files)),
                      list(FixPath(module, dpath, jars)),
                      deps,
                      list(FixPath(module, dpath, data)))
    DataHolder.Register(module, dpath, name, obj)

def java_binary(module, dpath, name, main=None, deps=None,
                flags=False, path=None):
    if path:
        dpath = path
    obj = JavaBinary(module, dpath, name, main, deps, flags)
    DataHolder.Register(module, dpath, name, obj)
    obj = JavaJar(module, dpath, name + "_deploy", obj.FullName())
    DataHolder.Register(module, dpath, name + "_deploy", obj)

def java_deploy(module, dpath, name, binary, path=None):
    if path:
        dpath = path
    obj = JavaJar(module, dpath, name, binary)
    DataHolder.Register(module, dpath, name, obj)

def generate(module, dpath, name, compiler, ins, outs, path=None):
    if path:
        dpath = path
    obj = Generate(module, dpath, name, compiler,
                   list(FixPath(module, dpath, ins)),
                   map(lambda x: x[0], FixPath(module, dpath, outs)))
    DataHolder.Register(module, dpath, name, obj)

def alias(module, path, name, deps):
    obj = Alias(module, path, name, deps)
    DataHolder.Register(module, path, name, obj)

loaded = set()

def LoadTargetSpec(module, target):
    # TODO: cache eval results, perhaps reorganize things so that they
    # are cacheable, to avoid reparsing all the files every time.
    if "=" in target:
        module, target = target.split("=", 1)
    assert module, "module unknown for target %s" % target
    assert ":" in target, target
    dirname, tgt = target.split(":")
    if module == TOPLEVEL:
        fn = os.path.join(dirname, "build.spec")
    else:
        base = "."
        if not dirname.startswith("jars"):
            base = SRCDIR
        fn = os.path.join(module, base, dirname, "build.spec")
    if fn in loaded:
        return
    #print "loading", fn
    loaded.add(fn)
    builtins = dict(globals()["__builtins__"])
    del builtins["__import__"]
    d = os.path.dirname(fn)
    def relglob(pattern):
        return map(lambda x: os.path.relpath(x, d),
                   glob.glob(os.path.join(d, pattern)))
    scope = {
        "__builtins__": builtins,
        "java_library": functools.partial(java_library, module, dirname),
        "java_binary": functools.partial(java_binary, module, dirname),
        "java_deploy": functools.partial(java_deploy, module, dirname),
        "generate": functools.partial(generate, module, dirname),
        "alias": functools.partial(alias, module, dirname),
        "glob": relglob,
        }
    execfile(fn, scope)

SRCDIR = "src"
