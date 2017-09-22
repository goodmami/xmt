#!/bin/bash

# usage: tanaka.sh [--detokenize] TANAKADIR OUTDIR
#
# Extract the parallel sentences from the Tanaka corpus skeletons at
# TANAKADIR, putting the resulting text files in OUTDIR. If the
# --detokenize option is used, tokenization spaces will be removed.
#
# Requires:
#     PyDelphin
#
# Examples:
#     tanaka.sh ~/grammars/jacy/tsdb/skeletons/tanaka/ out/
#     tanaka.sh --detokenize ~/grammars/jacy/tsdb/skeletons/tanaka/ out/

usage() { echo "usage: tanaka.sh [--detokenize] TANAKADIR OUTDIR"; }

postproc=('cat')
if [ "$1" = --detokenize ]; then
	postproc=('sed' '-r' 's/([^a-zA-Z]) /\1/g')
	shift
fi
TANAKADIR="$1"
OUTDIR="$2"

[ -d "$TANAKADIR" ] || { usage; exit 1; }
[ -n "$OUTDIR" ] || { usage; exit 1; }

mkdir -p "$OUTDIR"

# get items marked as grammatical
get=('delphin' 'select' '--filter' "item:i-wf='x==\"1\"'")

for p in "$TANAKADIR"/tc-{000..002}
do
	bn=$( basename "$p" )
	"${get[@]}" item:i-input "$p" | "${postproc[@]}" > "$OUTDIR/$bn.dev.ja"
	"${get[@]}" output:o-surface "$p"                > "$OUTDIR/$bn.dev.en"
done

for p in "$TANAKADIR"/tc-{003..005}
do
	bn=$( basename "$p" )
	"${get[@]}" item:i-input "$p" | "${postproc[@]}" > "$OUTDIR/$bn.test.ja"
	"${get[@]}" output:o-surface "$p"                > "$OUTDIR/$bn.test.en"
done

for p in "$TANAKADIR"/tc-{006..100}
do
	bn=$( basename "$p" )
	"${get[@]}" item:i-input "$p" | "${postproc[@]}" > "$OUTDIR/$bn.train.ja"
	"${get[@]}" output:o-surface "$p"                > "$OUTDIR/$bn.train.en"
done
