
from collections import defaultdict

from delphin import itsdb

def rows(p):
    if p.exists('p-result'):
        return p.select('p-result', ('i-id', 'p-id', 'mrs'))
    elif p.exists('result') and p.exists('parse'):
        return itsdb.select_rows(
            ('parse:i-id', 'result:result-id', 'result:mrs'),
            p.join('parse', 'result')
        )
    else:
        raise Exception('Invalid profile: ' + str(p.root))


def aligned_rows(p1, p2, pid=None):
    # it doesn't make much sense to align pid for both profiles;
    # consider doing a many-to-many mapping across profiles
    p1_mrss = {}
    for i_id, p_id, mrs in rows(p1):
        if pid is None or p_id == pid:
            p1_mrss[(i_id, p_id)] = mrs
    for i_id, p_id, mrs in rows(p2):
        if (pid is None or p_id == pid) and (i_id, p_id) in p1_mrss:
            yield (
                i_id,
                p_id,
                p1_mrss[(i_id, p_id)],
                mrs
            )


def predlist(x, dropset=None, sortkey=None):
    if dropset is None:
        dropset = set()

    def blacklist(pred):
        return pred not in dropset

    eps = x.eps()
    if sortkey is not None:
        eps = sorted(eps, key=sortkey)

    return list(filter(blacklist, [ep.pred.short_form() for ep in eps]))


# NOTE: anymalign can align 2+ languages, but the following function
# works with two languages only
def read_anymalign_model(path):
    model = defaultdict(list)
    for line in open(path):
        if not line.strip():
            continue
        src, tgt, lexwts, transprobs, freq = line.split('\t')
        src = tuple(src.split())
        tgt = tuple(tgt.split())
        if lexwts.strip() != '-':
            lexwts = tuple(float(wt) for wt in lexwts.split())
        else:
            lexwts = None
        transprobs = tuple(float(tp) for tp in transprobs.split())
        freq = int(freq)
        model[src].append((tgt, lexwts, transprobs, freq))
    return model

