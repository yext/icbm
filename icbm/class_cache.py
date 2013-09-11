#!/usr/bin/python

import errno
import re
import os
import shutil
import tempfile

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
                _copy_if_newer(os.path.join(cachedir, f),
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
            if os.path.isfile(fname) and f.endswith(".class"):
                _ensure_dir_exists(dst)
                _copy_if_newer(fname, os.path.join(dst, f), atomic=True)


# shutil.copy2() sometimes doesn't copy the mtime exactly.
_MTIME_TOLERANCE = 0.000001

def _copy_if_newer(src, dst, atomic=False):
    if os.path.exists(dst):
        src_stat = os.stat(src)
        dst_stat = os.stat(dst)
        if dst_stat.st_mtime >= src_stat.st_mtime - _MTIME_TOLERANCE:
            # dst is same age as or newer than src, so don't overwrite it.
            return
    if atomic:
        temp_fd, temp_filename = tempfile.mkstemp(dir=os.path.dirname(dst))
        os.close(temp_fd)
        shutil.copy2(src, temp_filename)
        os.rename(temp_filename, dst)
    else:
        shutil.copy2(src, dst)


def _ensure_dir_exists(dst):
    if os.path.isdir(dst):
        return
    try:
        os.makedirs(dst)
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(dst):
            # Some concurrent process made the directory for us, so we're good.
            return
        # Something legitimately went wrong.
        raise
