
import os
from itertools import groupby

from nltk.translate import bleu_score
from nltk.tokenize.moses import MosesTokenizer

from delphin import itsdb

_tokenize = MosesTokenizer().tokenize
_smoother = bleu_score.SmoothingFunction().method3
bleu = bleu_score.sentence_bleu

def do(args):
    join_table = 'g-result'
    hyp_spec = 'g-result:surface'
    ref_spec = 'item:i-translation'
    if args['--rephrasing']:
        join_table = 'r-result'
        hyp_spec = 'r-result:surface'
        ref_spec = 'item:i-input'
    make_hyp = make_ref = lambda s: s
    if args['--tokenize']:
        make_hyp = make_ref = lambda s: ' '.join(_tokenize(s))

    select = select_oracle if args['--oracle-bleu'] else select_first

    for i, itemdir in enumerate(args['ITEM']):
        itemdir = os.path.normpath(itemdir)
        p = itsdb.ItsdbProfile(itemdir)
        if args['--item-id']:
            for i_id, hyp, ref in select(
                    p, join_table, hyp_spec, ref_spec, with_id=True):
                print(
                    '{}\t{}\t{}'.format(i_id, make_hyp(hyp), make_ref(ref))
                )
        else:
            for hyp, ref in select(p, join_table, hyp_spec, ref_spec):
                print('{}\t{}'.format(make_hyp(hyp), make_ref(ref)))


def select_first(p, join_table, hyp_spec, ref_spec, with_id=False):
    """
    Return (hypothesis, reference) translation pairs using the first
    realization result per item.
    """
    pairs = []
    try:
        rows = list(p.join('item', join_table))
    except itsdb.ItsdbError:
        rows = []
    for i_id, group in groupby(rows, key=lambda row: row['item:i-id']):
        row = next(group)
        pair = [row[hyp_spec], row[ref_spec]]
        if with_id:
            pair = [i_id] + pair
        pairs.append(tuple(pair))
    return pairs


def select_oracle(p, join_table, hyp_spec, ref_spec, with_id=False):
    """
    Return (hypothesis, reference) translation pairs using the
    realization result per item with the highest BLEU score.
    """
    pairs = []
    try:
        rows = list(p.join('item', join_table))
    except itsdb.ItsdbError:
        rows = []
    for i_id, group in groupby(rows, key=lambda row: row['item:i-id']):
        scored = []
        for res in group:
            pair = [res[hyp_spec], res[ref_spec]]
            scored.append(
                tuple(
                    [bleu([_tokenize(pair[1])], _tokenize(pair[0]),
                          smoothing_function=_smoother)] +
                    pair
                )
            )
        best = sorted(scored, key=lambda r: r[0])[-1]
        pair = list(best[1:])
        if with_id:
            pair = [i_id] + pair
        pairs.append(tuple(pair))

    return pairs
