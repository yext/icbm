#!/bin/bash

# Assume first arg is the classpath extras
# Assume second arg is config file
CONFIG=$2
# Assume last arg is output file
OUTPUT=${!#}
java -cp ../closure/plovr.jar:$1 org.plovr.cli.Main build $CONFIG > $OUTPUT
