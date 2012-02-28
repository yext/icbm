#!/bin/bash

GRAMMAR="$1"
OUTPUTDIR="$(dirname "$GRAMMAR")"

java -classpath ../../Core/jars/antlr-2.7.6.jar \
     antlr.Tool -o "$OUTPUTDIR" "$GRAMMAR"
