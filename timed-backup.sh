#!/bin/bash -e
set -o pipefail

cd "$( dirname "${BASH_SOURCE[0]}")"
source "settings.inc"

backup_limit=3

mkdir -p backups

while true ; do
	backups=(backups/"$level_name".*)
	backup_count=${#backups[@]}
	echo "backup count is $backup_count"
	if [[ $backup_count -gt $backup_limit ]] ; then
		echo "More than $backup_limit backups; deleting the oldest"
		for x in "${backups[@]:0:$(( $backup_count - $backup_limit ))}"; do
			echo "Deleting $x"
			rm -rf "$x"
		done
	fi
	target="backups/$level_name.$( date +%Y%m%d.%H%M%S )"
	echo -n "Backup to $target"
	cp -pr "$source_worlds/$level_name" "$target"
	echo "."
	sleep 60
done
