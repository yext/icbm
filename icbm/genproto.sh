#!/bin/sh

if [ `uname -s` = "Linux" -a `uname -m` = "x86_64" ]; then
  PROTOC=${PROTOC:-`dirname $0`/protoc}
else
  PROTOC=${PROTOC:-protoc}
fi

exec ${PROTOC} -I. --java_out=. "$1"
