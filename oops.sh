#!/bin/bash -e 
set -o pipefail

# we don't want a clean shutdown, we want to kill it ASAP so that
# if we're lucky then the level data won't have been synced to disk yet
killall --signal KILL bedrock_server

sleep 3

systemctl --user status "$unit"
