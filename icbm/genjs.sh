#!/bin/bash

# Assume first arg is config file
CONFIG=$1
# Assume last arg is output file
OUTPUT=${!#}
java -cp ../subscriptions_deps/classes/:../closure/plovr.jar org.plovr.cli.Main build $CONFIG > $OUTPUT
