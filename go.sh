#!/bin/bash -e
set -o pipefail

cd "$( dirname "${BASH_SOURCE[0]}")"
source "settings.inc"

if [[ $VIRTUAL_ENV = "" ]] ; then
	echo "Need to run 'workon mc-scan' first"
	exit 1
fi

cp -pr "$source_worlds/$level_name" worlds/
#ls -l worlds/"$name"/db/LOCK

./scan.py "$@" --world "worlds/$level_name"

