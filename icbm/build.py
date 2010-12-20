#!/usr/bin/python
#
# Copyright 2010 Yext, Inc. All Rights Reserved.

__author__ = "ilia@yext.com (Ilia Mirkin)"

import optparse
import sys

import engine
import data


def main():
    parser = optparse.OptionParser()
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose")
    (options, args) = parser.parse_args()
    data.VERBOSE = options.verbose
    for target in args:
        # load the corresponding spec files
        data.LoadTargetSpec(data.TOPLEVEL, target)
    for target in args:
        d = data.DataHolder.Get(data.TOPLEVEL, target)
        d.LoadSpecs()
    data.DataHolder.Go(args)


if __name__ == '__main__':
    main()
