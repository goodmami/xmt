
from itertools import groupby

from nltk.translate import bleu_score
from nltk.tokenize.toktok import ToktokTokenizer

_tokenize = ToktokTokenizer().tokenize
_smoother = bleu_score.SmoothingFunction().method3
bleu = bleu_score.sentence_bleu

def select_first(p):
    """
    Return (hypothesis, reference) translation pairs using the first
    realization result per item.
    """
    pairs = []
    rows = p.join('item', 'g-result')
    for i_id, group in groupby(rows, key=lambda row: row['g-result:i-id']):
        row = next(group)
        pairs.append((row['g-result:surface'], row['item:i-translation']))
    return pairs


def select_oracle(p):
    """
    Return (hypothesis, reference) translation pairs using the
    realization result per item with the highest GLEU score.
    """
    pairs = []
    rows = p.join('item', 'g-result')
    for i_id, group in groupby(rows, key=lambda row: row['g-result:i-id']):
        scored = []
        for res in group:
            ref = res['item:i-translation']
            hyp = res['g-result:surface']
            scored.append(
                (bleu([_tokenize(ref)], _tokenize(hyp),
                      smoothing_function=_smoother), hyp, ref)
            )
        _, hyp, ref = sorted(scored, key=lambda r: r[0])[-1]
        pairs.append((hyp, ref))
    return pairs
