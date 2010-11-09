#!/bin/sh

BASE=`dirname $0`
exec java -cp ${BASE}/classes:${BASE}/jars/* %(main_class)s "$@"
