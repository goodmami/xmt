
import os
from itertools import groupby
import logging

from nltk.translate import bleu_score
from nltk.tokenize.toktok import ToktokTokenizer

from delphin import itsdb

from xmt import select

_tokenize = ToktokTokenizer().tokenize
_smoother = bleu_score.SmoothingFunction().method3


def do(args):
    if args['--all']:
        args['--coverage'] = True
        args['--bleu'] = True
        args['--oracle-bleu'] = True
        # args['--meteor'] = True

    numitems = len(args['ITEM'])
    width = len(str(numitems))
    stats = {}

    for i, itemdir in enumerate(args['ITEM']):
        itemdir = os.path.normpath(itemdir)
        logging.info(
            'Evaluate {0:{1}d}/{2} {3}'
            .format(i+1, width, numitems, itemdir)
        )
        p = itsdb.ItsdbProfile(itemdir)
        p_stats = {}
        if args['--coverage']:
            update_stats(p_stats, coverage(p))

        if args['--bleu']:
            update_stats(p_stats, bleu(p))

        if args['--oracle-bleu']:
            update_stats(p_stats, oracle_bleu(p))

        # if args['--meteor']:
        #     update_stats(p_stats, meteor(p))

        print(format_eval(itemdir, p_stats, args))

        update_stats(stats, p_stats)

    if numitems > 1:
        print(format_eval('Summary', stats, args))


def coverage(p):
    logging.debug('Calculating coverage for {}'.format(p.root))
    p_results = list(p.read_table('p-result'))
    x_results = list(p.read_table('x-result'))
    g_results = list(p.read_table('g-result'))
    cov = {
        'items':             len(list(p.read_table('item'))),
        'items-parsed':      len(set(r['i-id'] for r in p_results)),
        'parses':            len(p_results),
        'items-transferred': len(set(r['i-id'] for r in x_results)),
        'parses-transferred':len(set((r['i-id'], r['p-id'])
                                     for r in x_results)),
        'transfers':         len(x_results),
        'items-realized':    len(set(r['i-id'] for r in g_results)),
        'transfers-realized':len(set((r['i-id'], r['p-id'], r['x-id'])
                                     for r in g_results)),
        'realizations':      len(g_results)
    }
    return cov

def bleu(p):
    logging.debug('Calculating BLEU for {}'.format(p.root))
    pairs = select.select_first(p)
    score = bleu_score.corpus_bleu(
        [[_tokenize(ref)] for _, ref in pairs],
        [_tokenize(hyp) for hyp, _ in pairs],
        smoothing_function=_smoother
    )
    return {'bleu': [score]}

def oracle_bleu(p):
    logging.debug('Calculating Oracle-BLEU for {}'.format(p.root))
    pairs = select.select_oracle(p)
    score = bleu_score.corpus_bleu(
        [[_tokenize(ref)] for _, ref in pairs],
        [_tokenize(hyp) for hyp, _ in pairs],
        smoothing_function=_smoother
    )
    return {'oracle-bleu': [score]}


# def meteor(p):
#     return {}

def format_eval(name, stats, args):
    w = max(len(str(v)) for k, v in stats.items()
            if k not in ('bleu', 'oracle-bleu'))
    s = '{name}:\n'
    if args['--coverage']:
        s += (
            '  Items:                     {i:>{w}}\n'
            '  Parsing ({ip} items, {p} results):\n'
            '    Items parsed:            {ip:>{w}}/{i:<{w}} ({pa:0.4f})\n'
            '    Parse/Item:              {p:>{w}}/{ip:<{w}} ({pb:0.4f})\n'
            '  Transfer ({it} items, {pt} parses, {t} results):\n'
            '    Abs. items transferred:  {it:>{w}}/{i:<{w}} ({ta:0.4f})\n'
            '    Rel. items transferred:  {it:>{w}}/{ip:<{w}} ({tb:0.4f})\n'
            '    Parses transferred:      {pt:>{w}}/{p:<{w}} ({tc:0.4f})\n'
            '    Transfer/Parse:          {t:>{w}}/{pt:<{w}} ({td:0.4f})\n'
            '  Generation ({ir} items, {tr} transfers, {r} results):\n'
            '    Abs. items realized:     {ir:>{w}}/{i:<{w}} ({ra:0.4f})\n'
            '    Rel. items realized:     {ir:>{w}}/{it:<{w}} ({rb:0.4f})\n'
            '    Transfers realized:      {tr:>{w}}/{t:<{w}} ({rc:0.4f})\n'
            '    Realization/Transfer:    {r:>{w}}/{tr:<{w}} ({rd:0.4f})\n'
        )
    if args['--bleu']:
        s +='  BLEU {avg_lbl}:            {bleu:4.2f}\n'
    if args['--oracle-bleu']:
        s +='  Oracle BLEU {avg_lbl}:     {oraclebleu:4.2f}\n'
    return s.format(
        w =w,
        name=name,
        i =stats['items'],
        p =stats['parses'],
        ip=stats['items-parsed'],
        t =stats['transfers'],
        it=stats['items-transferred'],
        pt=stats['parses-transferred'],
        r =stats['realizations'],
        ir=stats['items-realized'],
        tr=stats['transfers-realized'],
        pa=stats['items-parsed']/float(stats['items']),
        pb=stats['parses']/float(stats['items-parsed']),
        ta=stats['items-transferred']/float(stats['items']),
        tb=stats['items-transferred']/float(stats['items-parsed']),
        tc=stats['parses-transferred']/float(stats['parses']),
        td=stats['transfers']/float(stats['parses-transferred']),
        ra=stats['items-realized']/float(stats['items']),
        rb=stats['items-realized']/float(stats['items-transferred']),
        rc=stats['transfers-realized']/float(stats['transfers']),
        rd=stats['realizations']/float(stats['transfers-realized']),
        bleu=(sum(stats['bleu'])/len(stats['bleu']))*100,
        oraclebleu=(sum(stats['oracle-bleu'])/len(stats['oracle-bleu']))*100,
        avg_lbl='(average)' if len(args['ITEM']) > 1 else (' ' * 9),
    )

def update_stats(stats, prof_stats):
    for key, val in prof_stats.items():
        if key in ('bleu', 'oracle-bleu'):
            stats[key] = stats.get(key, []) + val
        else:
            stats[key] = stats.get(key, 0) + val
