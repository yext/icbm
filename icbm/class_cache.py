#!/usr/bin/python
#
# Copyright 2010 Yext, Inc. All Rights Reserved.

__author__ = "ilia@yext.com (Ilia Mirkin)"

import re
import os
import shutil

import symlink

class ClassCache(object):

    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

    def UpdateCache(self, class_dir):
        # We always assume that the passed in class directory contains
        # newer files.
        os.path.walk(class_dir, self._UpdateCache, class_dir)

    def PopulateFromCache(self, class_dir, source_files):
        files = list((os.path.dirname(f), os.path.basename(f)[:-5])
                     for f in source_files if f.endswith(".java"))
        for dirname, fname in files:
            # Look for class files in the cache dir of the form
            # dir/fname.class
            # dir/fname$*.class
            # and symlink them into the target class dir
            cachedir = os.path.join(self.cache_dir, dirname)
            if not os.path.exists(cachedir):
                continue
            try:
                os.makedirs(os.path.join(class_dir, dirname))
            except os.error:
                pass
            classfile = "%s.class" % fname
            classpat = r"%s(\$.*)?\.class" % fname
            for f in os.listdir(cachedir):
                if not re.match(classpat, f):
                    continue
                target = os.path.join(class_dir, dirname, f)
                if os.path.exists(target):
                    os.unlink(target)
                symlink.symlink(os.path.abspath(os.path.join(cachedir, f)),
                                os.path.join(class_dir, dirname, f))


    def _UpdateCache(self, class_dir, dirname, files):
        reldir = dirname[len(class_dir):]
        if reldir.startswith(os.sep):
            reldir = reldir[1:]
        dst = os.path.join(self.cache_dir, reldir)

        # It's dangerous to have an outer class in the cache without its nested
        # classes because ant's depend and javac tasks might not realize the
        # nested classes are missing. Thus, always copy over nested classes
        # before copying in the main classes.
        files.sort(key=lambda f: "$" not in f)

        for f in files:
            fname = os.path.join(dirname, f)
            if os.path.islink(fname):
                continue
            elif os.path.isfile(fname) and f.endswith(".class"):
                if not os.path.exists(dst):
                    os.makedirs(dst)
                os.rename(fname, os.path.join(dst, f))
                symlink.symlink(os.path.abspath(os.path.join(dst, f)), fname)
