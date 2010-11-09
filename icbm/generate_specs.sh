#!/bin/sh

DIRECTORY=$1

# Uncomment the lines below to cause this to work recursively.

#for i in `find ${DIRECTORY} -type d`; do
i=${DIRECTORY}
  (echo -e \
"java_library(name=\"lib\",
             files=glob(\"*.java\"),
             deps=["
   grep -hP "import com.(alphaco|yext)" $i/*.java | \
     sed 's/import \(com[^A-Z]*\).*/\1/' | \
     sort -u | \
     sed "s/\./\//g" | \
     sed "s/\/$/:lib\",/" | \
     sed "s/^/                   \"/"
   echo -e "                   ]\n             )"
  ) > $i/build.spec
#done

