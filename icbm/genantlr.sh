#!/bin/bash

GRAMMAR="$1"
OUTPUTDIR="$(dirname "$GRAMMAR")"

java -classpath ../../Core/jars/antlr-2.7.6.jar \
     antlr.Tool -o "$OUTPUTDIR" "$GRAMMAR"

# Suppress "redundant cast to char" warnings.
LEXERS=$(grep 'class \(.*\) extends Lexer;' "$GRAMMAR" | \
         sed -e 's/^.*class \(.*\) extends Lexer;.*$/\1.java/')
cd "$OUTPUTDIR"
sed -i.orig -e 's/(char)\(LA([0-9]\+)\)/\1/g' $LEXERS
