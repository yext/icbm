#!/usr/bin/python
#
# Copyright 2010 Yext, Inc. All Rights Reserved.

__author__ = "ilia@yext.com (Ilia Mirkin)"

import sys

import engine
import data


def main():
    for target in sys.argv[1:]:
        # load the corresponding spec files
        data.LoadTargetSpec(data.TOPLEVEL, target)
    for target in sys.argv[1:]:
        d = data.DataHolder.Get(data.TOPLEVEL, target)
        d.LoadSpecs()
    data.DataHolder.Go(sys.argv[1:])


if __name__ == '__main__':
    main()
