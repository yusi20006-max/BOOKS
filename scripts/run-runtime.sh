#!/bin/sh
set -eu
exec python -m books.runtime "$@"
