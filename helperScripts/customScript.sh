#!/bin/bash

CWD=$(pwd)
for d in */ ; do
    cd "$d"
    python "/home/arpit/Programming/Python/VGMDB-Auto-Tagger/helperScripts/customTask.py" "$(pwd)"
    cd "$CWD"
done
