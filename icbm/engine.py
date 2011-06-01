#!/usr/bin/python
#
# Copyright 2010 Yext, Inc. All Rights Reserved.

__author__ = "ilia@yext.com (Ilia Mirkin)"

import commands
import glob
import itertools
import Queue
import os
import os.path
import shutil
import subprocess
import sys
import threading
import time
import traceback
import zipfile

import class_cache
import symlink

BUILD_DIR = "build"

class BuildError(Exception):

    def __init__(self, target):
        Exception.__init__(self, "Error building %s" % target.Name())

class Engine(object):

    def __init__(self):
        # target name -> target
        self.targets = {}

        # target -> set(filename)
        self.target_deps = {}
        # filename -> target
        self.target_provides = {}

        self.ready_queue = Queue.Queue()

        self.waitor_lock = threading.Lock()
        self.done = set()
        self.waitors = []
        self.build_visited = set()
        self.success = True
        self.class_cache = class_cache.ClassCache(
            os.path.join(BUILD_DIR, "classcache"))

    def Worker(self):
        while True:
            try:
                item = self.ready_queue.get()
            except:
                return
            with self.waitor_lock:
                print "building", item.Name(), time.time()
            try:
                item.Setup(self)
                if not item.Run(self):
                    raise BuildError(item)
                self.done.add(item)
            except Exception:
                traceback.print_exc()
                self.success = False

            with self.waitor_lock:
                self.EvalWaitors()

            self.ready_queue.task_done()

    def EvalWaitors(self):
        todel = []
        for waitor in self.waitors:
            deps = set()
            for f in self.target_deps[waitor]:
                deps.add(self.target_provides[f])
            if not (deps - self.done):
                todel.append(waitor)
        for waitor in todel:
            self.waitors.remove(waitor)
            self.ready_queue.put(waitor)

    def Depend(self, target, f):
        #print "----- Requiring", target, f
        self.target_deps.setdefault(target, set()).add(f)

    def Provide(self, target, f):
        #print "----- Providing", target, f
        assert f not in self.target_provides
        self.target_provides[f] = target

    def AddTarget(self, target):
        assert target.Name() not in self.targets, "duplicate target: %s" % target.Name()
        self.targets[target.Name()] = target

    def ComputeDependencies(self):
        for target in self.targets.itervalues():
            target.AddDependencies(self)

    def GetTarget(self, target):
        return self.targets.get(target)

    def GetFilename(self, path):
        if path.startswith("/"):
            return path
        assert path in self.target_provides, "path not provided: %s" % path
        return os.path.abspath(self.target_provides[path].GetOutput(path))

    def BuildTarget(self, target):
        if target in self.build_visited:
            return
        deps = self.target_deps.get(target, [])
        for f in deps:
            assert f in self.target_provides, "No target provides %s" % f
            self.BuildTarget(self.target_provides[f])
        if not deps:
            self.ready_queue.put(target)
        else:
            self.waitors.append(target)
        self.build_visited.add(target)

    def Go(self, workers=4):
        # Start up workers
        for i in xrange(workers):
            t = threading.Thread(target=self.Worker)
            t.daemon = True
            t.start()

        self.ready_queue.join()

        if self.waitors:
            print "Following targets not built:", map(
                lambda x: x.name, self.waitors)

        return self.success


    def VerifyGraph(self, target, current=None, seen=None):
        # Make sure that there aren't any cyclical dependencies. Does
        # a DFS, keeping track of the current path so far to make sure
        # that there are no cycles, as well as a list of nodes that
        # have been verified as "good" and don't need to be recursed
        # down.
        return True

class Target(object):

    def __init__(self, path, name):
        self.path = path
        self.name = name

    def Name(self):
        return self.name

    def AddDependencies(self, engine):
        raise NotImplementedError

    def Setup(self, engine):
        raise NotImplementedError

    def Run(self, engine):
        raise NotImplementedError

    def GetOutput(self, path):
        raise NotImplementedError

    @staticmethod
    def NewerChanges(paths, timestamp):
        """Computes whether the task needs to do any changes

        Iterates through all the paths and recursively finds the
        newest file. If it was modified after the timestamp, then
        there are changes that need to be addressed by the target.

        Args:
          paths: An array of paths. Directories are walked recursively.

        Returns True if the target needs to perform work.
        """
        if not os.path.exists(timestamp):
            return True

        newest = [0]
        def _Update(path):
            s = os.stat(path)
            if s.st_mtime > newest[0]:
                newest[0] = s.st_mtime

        def _Visit(arg, dirname, names):
            for name in names:
                path = os.path.join(dirname, name)
                if not os.path.isfile(path):
                    continue
                if os.path.samefile(path, timestamp):
                    continue
                _Update(path)

        for path in paths:
            if os.path.isdir(path):
                os.path.walk(path, _Visit, newest)
            else:
                _Update(path)
        return newest[0] > os.stat(timestamp).st_mtime

    @staticmethod
    def DependenciesChanged(depstr, store):
        if not os.path.exists(store):
            return True
        f = open(store)
        with f:
            stored = f.read()
        return stored != depstr


class JavaCompile(Target):

    def __init__(self, path, name, sources, jars, data, main, flags):
        Target.__init__(self, path, name)
        self.sources = dict(sources)
        self.jars = dict(jars)
        self.data = dict(data)
        self.main = main
        self.flags = flags

    def AddDependencies(self, engine):
        if self.flags:
            engine.Depend(self, "flag_processor")
        for fake, real in self.sources.iteritems():
            if not real.startswith("/"):
                engine.Depend(self, real)
        for fake, real in self.data.iteritems():
            if not real.startswith("/"):
                engine.Depend(self, real)
        engine.Provide(self, self.name)

    def Setup(self, engine):
        # Create the prefix where we're going to build everything
        prefix = self.prefix = os.path.join(BUILD_DIR, self.name)
        if not os.path.exists(prefix):
            os.makedirs(prefix)

        # Link in the compile.xml which will tell ant to build things
        compile_xml = os.path.join(prefix, "compile.xml")
        if not os.path.exists(compile_xml):
            symlink.symlink(
                os.path.join(os.path.abspath("."), "tools/icbm/compile.xml"),
                compile_xml)

        # Set up the src/ directory, by symlinking in all the
        # depending source files.
        srcprefix = self.srcprefix = os.path.join(prefix, "src")
        if os.path.exists(srcprefix):
            shutil.rmtree(srcprefix)
        os.makedirs(srcprefix)
        for source, filename in self.sources.iteritems():
            path = os.path.join(srcprefix, os.path.dirname(source))
            if not os.path.exists(path):
                os.makedirs(path)
            dest = os.path.join(path, os.path.basename(source))
            symlink.symlink(engine.GetFilename(filename), dest)

        # Set up the jars/ directory by symlinking in all the depending jars.
        jarprefix = self.jarprefix = os.path.join(prefix, "jars")
        if os.path.exists(jarprefix):
            shutil.rmtree(jarprefix)
        os.makedirs(jarprefix)
        for jar, filename in self.jars.iteritems():
            symlink.symlink(engine.GetFilename(filename),
                            os.path.join(jarprefix, os.path.basename(jar)))

        # Set up the output directory where all the class files will go
        outprefix = self.outprefix = os.path.join(prefix, "classes")
        if not os.path.exists(outprefix):
            os.makedirs(outprefix)

        # Data files are meant to be on the classpath, so put them
        # into classes as well.
        for data, filename in self.data.iteritems():
            path = os.path.join(outprefix, os.path.dirname(data))
            if not os.path.exists(path):
                os.makedirs(path)
            dest = os.path.join(path, os.path.basename(data))
            if os.path.exists(dest):
                os.unlink(dest)
            symlink.symlink(engine.GetFilename(filename), dest)

        # Map in any existing class files from the class cache
        engine.class_cache.PopulateFromCache(outprefix, self.sources)

        # Create an eclipse file
        with open(os.path.join(prefix, ".classpath"), "w") as f:
            f.write("""<?xml version="1.0" encoding="UTF-8"?>
<classpath>
  <classpathentry kind="src" path="src"/>
  <classpathentry kind="output" path="classes"/>
  <classpathentry kind="con" path="org.eclipse.jdt.launching.JRE_CONTAINER"/>
""")
            for jar in self.jars:
                f.write('<classpathentry kind="lib" path="jars/%s"/>\n' %
                        os.path.basename(jar))
            f.write("</classpath>\n")

        # Create a findbugs file
        with open(os.path.join(prefix, "findbugs.fbp"), "w") as f:
            loc = os.path.abspath(prefix)
            f.write('<Project projectName="">\n')
            for jar in self.jars:
                f.write("<AuxClasspathEntry>%s</AuxClasspathEntry>\n" %
                        os.path.join(loc, "jars", os.path.basename(jar)))
            f.write("<Jar>%s</Jar>\n" % os.path.join(loc, "classes"))
            f.write("<SrcDir>%s</SrcDir>\n" % os.path.join(loc, "src"))
            f.write("""<SuppressionFilter>
<LastVersion value="-1" relOp="NEQ"/>
</SuppressionFilter>
""")
            f.write("</Project>\n")

    def GenerateRunner(self):
        # Create a script to run the whole thing with appropriate
        # class path and main class.
        srcrunner = open("tools/icbm/java_run.sh")
        with srcrunner:
            text = srcrunner.read()
            runner_path = os.path.join(self.prefix, self.name)
            if not os.path.exists(os.path.dirname(runner_path)):
                os.makedirs(os.path.dirname(runner_path))
            outrunner = open(runner_path, "w")
            with outrunner:
                outrunner.write(text % {"main_class": self.main})
            os.chmod(runner_path, 0755)

        srcdebugger = open("tools/icbm/java_debug.sh")
        with srcdebugger:
            text = srcdebugger.read()
            debugger_path = os.path.join(self.prefix, "%s-debug" % self.name)
            if not os.path.exists(os.path.dirname(debugger_path)):
                os.makedirs(os.path.dirname(debugger_path))
            outdebugger = open(debugger_path, "w")
            with outdebugger:
                outdebugger.write(text % {"main_class": self.main})
            os.chmod(debugger_path, 0755)

    def Run(self, engine):
        # Ant is slow at figuring out that it has nothing to do, so
        # check for a build tstamp, and compare against files. If none
        # of them are newer, skip this step.

        depstr = "%r%r%r%r%r" % (
            self.sources, self.jars, self.data, self.main, self.flags)
        deplist = os.path.join(self.prefix, ".deplist")

        tstamp_path = os.path.join(self.prefix, self.name)
        if (not self.NewerChanges(
                [self.srcprefix, self.jarprefix], tstamp_path) and
            not self.DependenciesChanged(depstr, deplist)):
            return True

        cmd = ["ant", "-f", os.path.join(self.prefix, "compile.xml")]
        print cmd
        p = subprocess.Popen(cmd,
                             bufsize=1,
                             #stdout=subprocess.STDOUT,
                             #stderr=subprocess.STDOUT,
                             close_fds=True,
                             shell=False)
        p.wait()

        engine.class_cache.UpdateCache(self.outprefix)

        if p.returncode != 0:
            return False

        if not self.flags:
            self.Complete(deplist, depstr)
            return True

        # Execute the flagprocessor with all of its classpath, as well
        # as with the classpath of the target. We can assume that the
        # target is a java_binary, so it has a fairly standard layout.
        #
        # java -cp flag_processor/*:target/* \
        #     com.alphaco.util.flags.FlagProcessor target/classes
        flags = subprocess.Popen(
            "java -cp flag_processor/classes:flag_processor/jars/* "
            "com.alphaco.util.flags.FlagProcessor "
            "%(target)s/classes "
            "'%(target)s/jars/*'" % {"target" : self.name},
            cwd=BUILD_DIR,
            bufsize=1,
            stdout=subprocess.PIPE,
            close_fds=True,
            shell=True)

        output = flags.stdout.read()
        if flags.wait() != 0:
            return False

        f = open(os.path.join(self.outprefix, "flagdescriptors.cfg"), "w")
        with f:
            f.write(output)

        self.Complete(deplist, depstr)

        return True

    def Complete(self, deplist, depstr):
        self.GenerateRunner()
        f = open(deplist, "w")
        with f:
            f.write(depstr)

    def GetOutput(self, path):
        assert path == os.path.join(self.name, self.name)
        return os.path.join(self.prefix, self.name)



class JarBuild(Target):

    def __init__(self, path, name, target, jars, main, premain):
        Target.__init__(self, path, name)
        self.target = target
        self.jars = dict(jars)
        self.main = main
        self.premain = premain

    def AddDependencies(self, engine):
        engine.Depend(self, self.target)
        engine.Provide(self, self.name)

    def Setup(self, engine):
        pass

    def Run(self, engine):
        prefix = os.path.join(BUILD_DIR, self.target, "classes")
        # Verify that we actually need to do something. Otherwise
        # leave it alone.
        tstamp_path = os.path.join(BUILD_DIR, self.name)
        if not self.NewerChanges(self.jars.values() + [prefix], tstamp_path):
            return True

        # Put together the classes dir from the compiles, as well as
        # all of the jars into a single jar.
        out = os.path.join(BUILD_DIR, ".%s" % self.name)
        f = open(out, "wb")
        os.fchmod(f.fileno(), 0755)
        f.write("""#!/bin/sh
exec java ${JVM_ARGS} -jar $0 "$@"
""")
        f = zipfile.ZipFile(f, "w")
        added = set()
        def _Add(arg, dirname, files):
            for fn in files:
                fn = os.path.join(dirname, fn)
                if os.path.isfile(fn):
                    f.write(fn, os.path.relpath(fn, arg))
                    added.add(os.path.relpath(fn, arg))
        os.path.walk(prefix, _Add, prefix)

        def _Exclude(fn):
            # Don't include manifest file or signatures
            if fn.startswith("META-INF/"):
                for end in ("MANIFEST.MF", ".SF", ".RSA"):
                    if fn.endswith(end):
                        return True
            # Don't include play.plugins file as this causes play to load
            # duplicate plugins
            if fn == "play.plugins":
                return True
            if fn in added:
                return True
            return False

        for jar, filename in self.jars.iteritems():
            j = zipfile.ZipFile(engine.GetFilename(filename), "r")
            for info in j.infolist():
                if not _Exclude(info.filename):
                    contents = j.open(info).read()
                    f.writestr(info, contents)

        rev = commands.getoutput("hg parent -q")
        if rev and ":" in rev:
            rev = rev.split(":")[0]
        premain = "Premain-Class: %s\n" % self.premain if self.premain else ""
        manifest = (
"""Manifest-Version: 1.0
Main-Class: %s
%sBuilt-By: %s
Built-On: %s
Build-Revision: %s
""" % (self.main, premain, os.getenv("USER"), time.strftime("%b %d, %Y %I:%M:%S %p"), rev.strip()))

        f.writestr("META-INF/MANIFEST.MF", manifest)
        f.close()

        os.rename(out, os.path.join(BUILD_DIR, self.name))

        return True

    def GetOutput(self, path):
        assert path == self.name
        return os.path.join(BUILD_DIR, self.name)

class WarBuild(Target):

    def __init__(self, path, name, data, target, jars):
        Target.__init__(self, path, name)
        self.data = dict(data)
        self.target = target
        self.jars = dict(jars)

    def AddDependencies(self, engine):
        engine.Depend(self, self.target)
        for fake, real in self.data.iteritems():
            if not real.startswith("/"):
                engine.Depend(self, real)
        engine.Provide(self, self.name)

    def Setup(self, engine):
        pass

    def Run(self, engine):
        prefix = os.path.join(BUILD_DIR, self.target, "classes")
        # Verify that we actually need to do something. Otherwise
        # leave it alone.
        tstamp_path = os.path.join(BUILD_DIR, self.name)
        if not self.NewerChanges(
            self.jars.values() + self.data.values() + [prefix], tstamp_path):
            return True

        # Put together the classes dir from the compiles, as well as
        # all of the jars into a single jar.
        out = os.path.join(BUILD_DIR, ".%s" % self.name)
        f = zipfile.ZipFile(out, "w")
        for fake, fn in self.data.iteritems():
            fn = engine.GetFilename(fn)
            if os.path.isfile(fn):
                f.write(fn, fake)

        def _Add(arg, dirname, files):
            for fn in files:
                fn = os.path.join(dirname, fn)
                if os.path.isfile(fn):
                    f.write(fn, os.path.join("WEB-INF/classes", os.path.relpath(fn, arg)))
        os.path.walk(prefix, _Add, prefix)

        for jar, fn in self.jars.iteritems():
            fn = engine.GetFilename(fn)
            f.write(fn, os.path.join("WEB-INF/lib", jar))

        rev = commands.getoutput("hg parent -q")
        if rev and ":" in rev:
            rev = rev.split(":")[0]
        manifest = (
"""Manifest-Version: 1.0
Built-By: %s
Built-On: %s
Build-Revision: %s
""" % (os.getenv("USER"), time.strftime("%b %d, %Y %I:%M:%S %p"), rev.strip()))

        f.writestr("META-INF/MANIFEST.MF", manifest)
        f.close()

        os.rename(out, os.path.join(BUILD_DIR, self.name))

        return True

    def GetOutput(self, path):
        assert path == self.name
        return os.path.join(BUILD_DIR, self.name)


class PlayCompile(Target):

    def __init__(self, path, name, modules, deps, data, play_home):
        Target.__init__(self, path, name)
        self.modules = modules
        self.deps = deps
        self.data = dict(data)
        self.play_home = play_home

    def AddDependencies(self, engine):
        for dep in self.deps:
            engine.Depend(self, dep)
        for fake, real in self.data.iteritems():
            if not real.startswith("/"):
                engine.Depend(self, real)
        engine.Provide(self, self.name)

    def Setup(self, engine):
        # Make the directory, set up symlinks
        prefix = self.prefix = os.path.join(BUILD_DIR, self.name.rsplit(".zip")[0])
        if not os.path.exists(self.prefix):
            os.makedirs(self.prefix)

    def Run(self, engine):
        # Always run the precompilation for now
        def _CopyPlayApp(src):
            for dir in ("app", "conf", "public"):
                for root, dirs, files in os.walk(os.path.join(src, dir)):
                    dest_dir = os.path.join(self.prefix, root)
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)
                    for file in files:
                        dest = os.path.join(dest_dir, file)
                        if not os.path.exists(dest):
                            symlink.symlink(
                                os.path.realpath(os.path.join(root, file)),
                                dest)

        # Copy over the play modules
        for module in self.modules:
            _CopyPlayApp(module)

        # Execute the play compiler
        generate = subprocess.Popen(
            [self.play_home + '/play',
             'precompile',
             os.path.join(self.prefix, self.modules[0])],
            bufsize=1,
            close_fds=True,
            shell=False)

        if generate.wait() != 0:
            return False

        # Copy all the data file as well
        for data, filename in self.data.iteritems():
            srcprefix = os.path.join(self.prefix, "src")
            path = os.path.join(srcprefix, os.path.dirname(data))
            if not os.path.exists(path):
                os.makedirs(path)
            dest = os.path.join(path, os.path.basename(data))
            if os.path.exists(dest):
                os.unlink(dest)
            symlink.symlink(engine.GetFilename(filename), dest)

        # Zip up the compiled play application
        tmp = os.path.join(self.prefix, ".%s" % self.name)
        f = zipfile.ZipFile(tmp, "w")
        for root, dirs, files in os.walk(self.prefix):
            for name in files:
                path = os.path.join(root, name)
                f.write(path, os.path.relpath(path, self.prefix))
        f.close()

        os.rename(tmp, os.path.join(BUILD_DIR, self.name))

        return True

    def GetOutput(self, path):
        assert path == self.name
        return os.path.join(BUILD_DIR, self.name)

class Generate(Target):

    def __init__(self, path, name, compiler, args, sources, outputs, deps):
        Target.__init__(self, path, name)
        self.sources = sources
        self.outputs = set(outputs)
        self.compiler = compiler
        self.args = args or []
        self.deps = deps

    def AddDependencies(self, engine):
        for dep in self.deps:
            engine.Depend(self, dep)
        for fake, real in self.sources:
            if not real.startswith("/"):
                engine.Depend(self, real)
        for out in self.outputs:
            engine.Provide(self, out)

    def Setup(self, engine):
        # Make the directory, set up symlinks
        prefix = self.prefix = os.path.join(BUILD_DIR, self.name)
        if not os.path.exists(self.prefix):
            os.makedirs(self.prefix)

        for fake, real in self.sources:
            path = os.path.join(prefix, os.path.dirname(fake))
            if not os.path.exists(path):
                os.makedirs(path)
            dest = os.path.join(path, os.path.basename(fake))
            if not os.path.exists(dest):
                symlink.symlink(engine.GetFilename(real), dest)

        for out in self.outputs:
            path = os.path.join(prefix, os.path.dirname(out))
            if not os.path.exists(path):
                os.makedirs(path)

    def Run(self, engine):
        # The assumption is that the generation is fully dependent on
        # the inputs. So if none of them have changed, then no need to
        # do anything.
        tstamp_path = os.path.join(self.prefix, "TIMESTAMP")
        if not self.NewerChanges([self.prefix], tstamp_path):
            return True

        # Execute the compiler in the prefix cwd with the sources and
        # outputs as the arguments. It is assumed that it will know
        # what to do with them.
        args = ([self.compiler] + self.args + list(x[0] for x in self.sources) +
                list(self.outputs))
        print args
        generate = subprocess.Popen(
            args,
            cwd=self.prefix,
            bufsize=1,
            close_fds=True,
            shell=False)

        if generate.wait() != 0:
            return False

        with open(tstamp_path, "w"):
            pass

        return True

    def GetOutput(self, path):
        assert path in self.outputs, path
        return os.path.join(self.prefix, path)


class Alias(Target):

    def __init__(self, path, name, deps):
        Target.__init__(self, path, name)
        self.deps = deps

    def AddDependencies(self, engine):
        for dep in self.deps:
            engine.Depend(self, dep)
        engine.Provide(self, self.name)

    def Setup(self, engine):
        pass

    def Run(self, engine):
        return True

    def GetOutput(self, path):
        return path
