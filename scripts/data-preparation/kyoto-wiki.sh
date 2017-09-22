#!/bin/bash

# usage: kyoto-wiki.sh DIR [DIR..]
#
# Extract the parallel sentences from the Japanese-English Bilingual
# Corpus of Wikipedia's Kyoto Articles:
#     http://alaginrc.nict.go.jp/WikiCorpus/index_E.html.
#
# For each DIR, extract the parallel data in DIR/*.xml and write the
# sentences to DIR.ja and DIR.en.
#
# Requires:
#     xmlstarlet
#
# Examples:
#     kyoto-wiki.sh ~/kyoto/{BDS,BLD,CLT,EPR}

contextpath='//j/..'  # xpath to context node (parent of Japanese sentence j)
sourcepath='./j/text()'  # xpath for japanese text from context node
targetpath='./e[@type="check"][1]/text()'  # xpath for english text

for d in "$@"; do
	d=`readlink -f "$d"`  # normalize path
	xmlstarlet sel -T -t \
    	-m "$contextpath" \
    	-v "$sourcepath" -n \
    	-v "$targetpath" -n \
    	"$d"/*.xml > "$d.ja-en"
    sed -n '1~2p' "$d.ja-en" > "$d.ja"
    sed -n '2~2p' "$d.ja-en" > "$d.en"
    rm "$d.ja-en"
done
