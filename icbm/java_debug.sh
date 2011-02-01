#!/bin/sh
#
# Specify the JVM_ARGS environment variable to contain any other JVM args 
# needed

BASE=`dirname $0`
exec jdb -sourcepath ${BASE}/src -classpath ${BASE}/classes:${BASE}/jars/* ${JVM_ARGS} %(main_class)s "$@"
