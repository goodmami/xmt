#!/bin/bash

CWD=$( cd `dirname "$0"` && pwd )
export PATH=${CWD}/bin:"$PATH"

python3 -m xmt.main "$@"

