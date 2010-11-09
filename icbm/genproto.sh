#!/bin/sh

PROTOC=${PROTOC:-protoc}

exec ${PROTOC} -I. --java_out=. "$1"
