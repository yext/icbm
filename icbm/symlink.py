import os
import subprocess
import sys

def symlink_win(src, dst):
    subprocess.call(["mklink", dst, src])

def symlink_other(src, dst):
    os.symlink(src, dst)

if hasattr(sys, "winver"):
    symlink = symlink_win
else:
    symlink = symlink_other

