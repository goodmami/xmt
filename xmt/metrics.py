

from nltk.translate import bleu_score
from nltk.tokenize.toktok import ToktokTokenizer

_tokenize = ToktokTokenizer().tokenize
_smoother = bleu_score.SmoothingFunction().method3


def bleu(pairs):
    score = bleu_score.corpus_bleu(
        [[_tokenize(ref.lower())] for _, ref in pairs],
        [_tokenize(hyp.lower()) for hyp, _ in pairs],
        smoothing_function=_smoother
    )
    return score

