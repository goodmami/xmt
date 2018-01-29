
import re
from collections import defaultdict

from delphin import itsdb
from delphin.mrs.components import var_re

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


def aligned_rows(p1, pid1, p2, pid2):
    p1_mrss = {}
    for i_id, p_id, mrs in rows(p1):
        if p_id == pid1:
            p1_mrss[i_id] = mrs
    for i_id, p_id, mrs in rows(p2):
        if (p_id == pid2) and i_id in p1_mrss:
            yield (
                i_id,
                p1_mrss[i_id],
                mrs
            )


def predlist(x, dropset=None, get_eps=None, mode=None):
    if dropset is None:
        dropset = set()

    eps = x.eps() if get_eps is None else get_eps(x)

    nmz = set()
    val = {}
    if mode == 'hb':
        for ep in eps:
            if ep.pred.short_form() == 'nominalization' and ep.cfrom != -1:
                nmz.add((ep.cfrom,  ep.cto))
            val[ep.nodeid] = _extract_valency(ep)

    pl = []
    for ep in eps:
        normpred = ep.pred.short_form()
        pred = ep.pred.string
        if mode == 'hb':
            if normpred == 'nominalization' or normpred.endswith('unknown'):
                continue
            if normpred == 'named':
                pred = 'nmd_"{}"'.format(str(ep.carg or ''))
            if ep.pred.pos == 'v':
                if (ep.cfrom, ep.cto) in nmz:
                    pred = 'nmz_' + ep.pred.string
                pred += '@' + val[ep.nodeid]
        elif normpred in dropset:
            continue
        elif mode == 'xmt':
            pred = normpred
            if pred == 'pron':
                props = x.properties(ep.nodeid)
                pred += '({}.{}.{})'.format(
                    props.get('PERS',''),
                    props.get('NUM',''),
                    props.get('GEND','')
                )
            if ep.carg:
                pred += '("{}")'.format(ep.carg)
        elif mode == 'short':
            pred = normpred
        pl.append(pred)
    return pl

# adapted from https://github.com/delph-in/jaen
def _extract_valency(ep):
    valencies = []
    for role in ('ARG1', 'ARG2', 'ARG3', 'ARG4'):
        v = ep.args.get(role)
        if v is not None:
            m = var_re.match(v)
            if m is not None:
                n = role[-1]
                vs = m.group(1)
                if vs not in ('u', 'i', 'p'):
                    valencies.append(n + vs)
    return ''.join(valencies)


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


def read_subgraph_file(f):
    meta_re = re.compile(r'::([^ ]+)(?: ((?:(?!::).)*)|$)')
    meta = []
    lines = []
    try:
        line = next(f).strip()
        while True:
            while line == '':
                line = next(f).strip()
            while line.startswith('#'):
                for key, value in meta_re.findall(line.lstrip('#')):
                    value = value.strip()
                    if value == '':
                        value = None
                    meta.append((key, value))
                line = next(f).strip()
            while line != '':
                lines.append(line)
                line = next(f).strip()
            if lines:
                yield meta, '\n'.join(lines)
                meta = []
                lines = []
    except (StopIteration, IOError, OSError):
        pass
    if lines:
        yield meta, '\n'.join(lines)

def penman_structure(s):
    s = re.sub(r'(:[^ ]+ )([eihpux]\d+)', r'\1(\2)', s)
    return ''.join(re.findall(r'(\([eihpux]\d+(?=[ )])|:[^ ]+(?= \()|\))', s))

