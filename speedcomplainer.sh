#!/usr/bin/env bash

PYTHON=/usr/local/bin/python2
if [ ! -f $PYTHON ]; then
   PYTHON=/usr/bin/python
fi
# echo [Python: $PYTHON]
# $PYTHON --version

CONFIG=$1
cd ~/Dropbox/Projects/speedcomplainer/
$PYTHON speedcomplainer.py ${CONFIG} > /dev/null
