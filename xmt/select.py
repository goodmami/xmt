
from itertools import groupby

from nltk.translate import bleu_score
from nltk.tokenize.toktok import ToktokTokenizer

_tokenize = ToktokTokenizer().tokenize
_smoother = bleu_score.SmoothingFunction().method3
bleu = bleu_score.sentence_bleu

def select_first(p, join_table, hyp_spec, ref_spec):
    """
    Return (hypothesis, reference) translation pairs using the first
    realization result per item.
    """
    pairs = []
    rows = p.join('item', join_table)
    for i_id, group in groupby(rows, key=lambda row: row['item:i-id']):
        row = next(group)
        pairs.append((row[hyp_spec], row[ref_spec]))
    return pairs


def select_oracle(p, join_table, hyp_spec, ref_spec):
    """
    Return (hypothesis, reference) translation pairs using the
    realization result per item with the highest GLEU score.
    """
    pairs = []
    rows = p.join('item', join_table)
    for i_id, group in groupby(rows, key=lambda row: row['item:i-id']):
        scored = []
        for res in group:
            ref = res[ref_spec]
            hyp = res[hyp_spec]
            scored.append(
                (bleu([_tokenize(ref)], _tokenize(hyp),
                      smoothing_function=_smoother), hyp, ref)
            )
        _, hyp, ref = sorted(scored, key=lambda r: r[0])[-1]
        pairs.append((hyp, ref))
    return pairs

# class XmtSelector(ItsdbProfile):
#     def items(self):
#         return self.read_table('item')
#     def parses(self):
#         return self
