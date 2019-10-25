#!/bin/bash -e
set -o pipefail

name="The Cameron World II (577830886)"

if [[ $VIRTUAL_ENV = "" ]] ; then
	echo "Need to run 'workon mc-scan' first"
	exit 1
fi

cp -pr ~/minecraft/worlds/"$name" worlds/
#ls -l worlds/"$name"/db/LOCK

./scan.py "$@" --world "worlds/$name"

