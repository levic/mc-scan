#!/bin/bash -e 
set -o pipefail

killall --signal KILL bedrock_server

sleep 3

#systemctl --user start minecraft@default
