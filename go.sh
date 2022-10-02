#!/bin/bash -e
set -o errexit
set -o nounset
set -o pipefail

cd "$( dirname $( realpath "${BASH_SOURCE[0]}") )"
source "./settings.inc"

if [[ $VIRTUAL_ENV = "" ]] ; then
	echo "Need to activate virtualenv first"
	exit 1
fi

tmpdir="/run/user/$UID/mc-worlds"
if ! [[ -e $tmpdir ]]  ; then
	mkdir -p "$tmpdir"
fi
if ! [[ -e worlds ]] ; then
	ln -s "$tmpdir" worlds
fi

#rm -rf worlds/*
cp -pr "$source_worlds/$level_name" worlds/
ls -l  -t --time-style=full-iso "worlds/$level_name/db" | head -n 2 | tail -n 1
#ls -l worlds/"$name"/db/LOCK

./scan.py "$@" --world "worlds/$level_name"

