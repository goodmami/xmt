#!/usr/bin/env python3

from itertools import groupby

import docopt

from delphin import itsdb

from xmt.metrics import bleu

from nltk.translate import bleu_score
from nltk.tokenize.toktok import ToktokTokenizer

_tokenize = ToktokTokenizer().tokenize
_smoother = bleu_score.SmoothingFunction().method3


USAGE = '''
Usage: lkb-bleu [--rephrases] [--oracle] PROFILE

Arguments:
  PROFILE                   profile to compute scores for

Options:
  -h, --help                display this help and exit
  --rephrases               compare to item:i-input instead of i-translation
  --oracle                  use best score among an item's candidates
  --sent
'''


def main():
    args = docopt.docopt(USAGE)

    p = itsdb.ItsdbProfile(args['PROFILE'])

    if args['--rephrases']:
        refs = dict(p.select('item', ('i-id', 'i-input')))
    else:
        refs = dict(p.select('item', ('i-id', 'i-translation')))

    if args['--oracle']:
        pairs = oracle_pairs(p, refs)
    else:
        pairs = single_pairs(p, refs)

    print('{:4.2f}'.format(bleu(pairs) * 100))


def oracle_pairs(p, refs):
    pairs = []
    gs = groupby(p.join('parse', 'result'), key=lambda row: row['parse:i-id'])
    for i_id, group in gs:
        ref = refs[i_id]
        scored = []
        for res in group:
            hyp = res['result:surface']
            scored.append(
                (
                    bleu_score.sentence_bleu(
                        [_tokenize(ref)], _tokenize(hyp),
                        smoothing_function=_smoother
                    ),
                    hyp, ref
                )
            )
        _, hyp, ref = sorted(scored, key=lambda r: r[0])[-1]
        pairs.append((hyp, ref))
    return pairs


def single_pairs(p, refs):
    pairs = []
    gs = groupby(p.join('parse', 'result'), key=lambda row: row['parse:i-id'])
    for i_id, group in gs:
        ref = refs[i_id]
        hyp = next(group)['result:surface']
        pairs.append((hyp, ref))
    return pairs

if __name__ == '__main__':
    main()
