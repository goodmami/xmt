#!/bin/bash

CWD=$( cd `dirname "$0"` && pwd )
export PATH=${CWD}/bin:"$PATH"
export PYTHONPATH="${CWD}:$PYTHONPATH"

python3 -m xmt.main "$@"

