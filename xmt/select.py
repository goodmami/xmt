
from itertools import groupby

from nltk.translate.gleu_score import sentence_gleu as gleu
from nltk.tokenize.toktok import ToktokTokenizer

_tokenize = ToktokTokenizer().tokenize

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
        hrs = ((r['g-result:surface'], r['item:i-translation']) for r in group)
        ranked = [(gleu(_tokenize(r), _tokenize(h)), h, r) for h, r in hrs]
        _, hyp, ref = sorted(ranked, key=lambda r: r[0])[-1]
        pairs.append((hyp, ref))
    return pairs
