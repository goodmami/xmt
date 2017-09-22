#!/bin/bash

# usage: wordnet.sh TABFILE
#
# Extract the parallel sentences from the Japanese Wordnet corpus at
# TABFILE, and output the Japanese and English sentence to
# TABFILE.ja and TABFILE.en, respectively.
#
# Examples:
#     wordnet.sh ~/jpn-wordnet/wnjpn-def.tab

TABFILE="$1"
[ -f "$1" ] || { echo "TABFILE not found: $1" >&2; exit 1; }

cut -f 3 "$TABFILE" > "$TABFILE.en"
cut -f 4 "$TABFILE" > "$TABFILE.ja"
