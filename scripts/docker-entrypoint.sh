#!/bin/sh
# Hosted volumes (Fly, etc.) mount root-owned. Fix ownership of the writable data dir, then drop to the app user.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/data/retail /app/data/eval
  chown -R app:app /app/data/retail /app/data/eval
  export HOME=/home/app
  exec setpriv --reuid=10001 --regid=10001 --init-groups "$@"
fi
exec "$@"
