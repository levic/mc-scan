#!/bin/bash -e
set -o errexit
set -o nounset
set -o pipefail

cd "$( dirname $( realpath "${BASH_SOURCE[0]}") )"
source "./settings.inc"

if [[ ${VIRTUAL_ENV:-} = "" ]] ; then
	[[ -e venv/bin/activate ]] || { echo "Can't find venv" >&2 ; exit 1 ; }
	source venv/bin/activate
fi

tmpdir="/run/user/$UID/mc-worlds"
if ! [[ -e $tmpdir ]]  ; then
	mkdir -p "$tmpdir"
fi

if ! [[ -e worlds ]] ; then
	ln -s "$tmpdir" worlds
fi

if [[ -e worlds ]] && [[ ! -l worlds ]]; then
  echo "expected worlds dir to be a symlink" >&2
  exit 1
fi

rm -rf "worlds/$level_name"
cp -pr "$source_worlds/$level_name" worlds/

newest_file=$( ls -1 -t  "worlds/$level_name/db" | head -n 2 | tail -n 1 )
touch -r "$source_worlds/$level_name/db/$newest_file" "worlds/$level_name/last_updated"
#cp -rp "$source_worlds/$level_name/db/$newest_file" "worlds/$level_name/last_updated"
#cat /dev/null > "worlds/$level_name/last_updated"

./scan.py "$@" --world "worlds/$level_name"
