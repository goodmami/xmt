
import os
from itertools import groupby
import logging

from nltk.translate import bleu_score
from nltk.tokenize.toktok import ToktokTokenizer

from delphin import itsdb
from delphin.exceptions import ItsdbError

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
            update_stats(p_stats, coverage(p, args['--ignore']))

        if args['--bleu'] and p.size('g-result') > 0:
            update_stats(p_stats, bleu(p, 'realizations'))
        if args['--bleu'] and p.size('r-result') > 0:
            update_stats(p_stats, bleu(p, 'rephrases'))

        if args['--oracle-bleu'] and p.size('g-result') > 0:
            update_stats(p_stats, oracle_bleu(p, 'realizations'))
        if args['--oracle-bleu'] and p.size('r-result') > 0:
            update_stats(p_stats, oracle_bleu(p, 'rephrases'))

        # if args['--meteor']:
        #     update_stats(p_stats, meteor(p))

        print(format_eval(itemdir, p_stats, args))

        update_stats(stats, p_stats)

    if numitems > 1:
        print(format_eval('Summary', stats, args))


def coverage(p, ignore=None):
    logging.debug('Calculating coverage for {}'.format(p.root))
    p_results = rows(p, 'p-result')
    x_results = rows(p, 'x-result')
    g_results = rows(p, 'g-result')
    r_results = rows(p, 'r-result')
    cov = {'items': len(list(p.read_table('item')))}
    if p_results:
        cov['items-parsed'] = len(set(r['i-id'] for r in p_results))
        cov['parses'] = len(p_results)
    if x_results:
        if ignore is not None:
            x_results = [r for r in x_results if ignore not in r['mrs']]
        cov['items-transferred'] = len(set(r['i-id'] for r in x_results))
        cov['parses-transferred'] = len(set((r['i-id'], r['p-id'])
                                        for r in x_results))
        cov['transfers'] = len(x_results)
    if g_results:
        cov['items-realized'] = len(set(r['i-id'] for r in g_results))
        cov['transfers-realized'] = len(set((r['i-id'], r['p-id'], r['x-id'])
                                            for r in g_results))
        cov['realizations'] = len(g_results)
    if r_results:
        cov['items-rephrased'] = len(set(r['i-id'] for r in r_results))
        cov['parses-rephrased'] = len(set((r['i-id'], r['p-id'])
                                          for r in r_results))
        cov['rephrases'] = len(r_results)
    return cov

def rows(p, tablename):
    try:
        return list(p.read_table(tablename))
    except (KeyError, ItsdbError):
        return []

def bleu(p, task):
    if task == 'realizations':
        join_table = 'g-result'
        hyp_spec = 'g-result:surface'
        ref_spec = 'item:i-translation'
        key = 'bleu'
    elif task == 'rephrases':
        join_table = 'r-result'
        hyp_spec = 'r-result:surface'
        ref_spec = 'item:i-input'
        key = 'rephrase-bleu'

    logging.debug('Calculating BLEU for {}'.format(p.root))
    pairs = select.select_first(p, join_table, hyp_spec, ref_spec)
    score = bleu_score.corpus_bleu(
        [[_tokenize(ref.lower())] for _, ref in pairs],
        [_tokenize(hyp.lower()) for hyp, _ in pairs],
        smoothing_function=_smoother
    )
    return {key: [score]}

def oracle_bleu(p, task):
    if task == 'realizations':
        join_table = 'g-result'
        hyp_spec = 'g-result:surface'
        ref_spec = 'item:i-translation'
        key = 'oracle-bleu'
    elif task == 'rephrases':
        join_table = 'r-result'
        hyp_spec = 'r-result:surface'
        ref_spec = 'item:i-input'
        key = 'rephrase-oracle-bleu'

    logging.debug('Calculating Oracle-BLEU for {}'.format(p.root))
    pairs = select.select_oracle(p, join_table, hyp_spec, ref_spec)
    score = bleu_score.corpus_bleu(
        [[_tokenize(ref.lower())] for _, ref in pairs],
        [_tokenize(hyp.lower()) for hyp, _ in pairs],
        smoothing_function=_smoother
    )
    return {key: [score]}


# def meteor(p):
#     return {}

def format_eval(name, stats, args):
    w = max(len(str(v)) for k, v in stats.items()
            if k not in ('bleu', 'oracle-bleu'))
    avg_label=' (average):' if len(args['ITEM']) > 1 else ':' + (' ' * 10)

    s = '{name}:\n'.format(name=name)
    
    if args['--coverage']:
        s += '  Items:                     {i:>{w}}\n'.format(
            w =w,
            i =stats['items']
        )
        if 'parses' in stats:
            s += (
            '  Parsing ({ip} items, {p} results):\n'
            '    Items parsed:            {ip:>{w}}/{i:<{w}} ({pa:0.4f})\n'
            '    Parse/Item:              {p:>{w}}/{ip:<{w}} ({pb:0.4f})\n'
            ).format(
                w =w,
                i =stats['items'],
                p =stats['parses'],
                ip=stats['items-parsed'],
                pa=stats['items-parsed']/float(stats['items']),
                pb=stats['parses']/float(stats['items-parsed'])
            )
        if 'transfers' in stats:
            s += (
            '  Transfer ({it} items, {pt} parses, {t} results):\n'
            '    Abs. items transferred:  {it:>{w}}/{i:<{w}} ({ta:0.4f})\n'
            '    Rel. items transferred:  {it:>{w}}/{ip:<{w}} ({tb:0.4f})\n'
            '    Parses transferred:      {pt:>{w}}/{p:<{w}} ({tc:0.4f})\n'
            '    Transfer/Parse:          {t:>{w}}/{pt:<{w}} ({td:0.4f})\n'
            ).format(
                w =w,
                i =stats['items'],
                p =stats['parses'],
                ip=stats['items-parsed'],
                t =stats['transfers'],
                it=stats['items-transferred'],
                pt=stats['parses-transferred'],
                ta=stats['items-transferred']/float(stats['items']),
                tb=stats['items-transferred']/float(stats['items-parsed']),
                tc=stats['parses-transferred']/float(stats['parses']),
                td=stats['transfers']/(float(stats['parses-transferred'])
                                       or 1.0)  # avoid division by 0
            )
        if 'realizations' in stats:
            s += (
            '  Generation ({ig} items, {tg} transfers, {g} results):\n'
            '    Abs. items realized:     {ig:>{w}}/{i:<{w}} ({ga:0.4f})\n'
            '    Rel. items realized:     {ig:>{w}}/{it:<{w}} ({gb:0.4f})\n'
            '    Transfers realized:      {tg:>{w}}/{t:<{w}} ({gc:0.4f})\n'
            '    Realization/Transfer:    {g:>{w}}/{tg:<{w}} ({gd:0.4f})\n'
            ).format(
                w =w,
                i =stats['items'],
                t =stats['transfers'],
                it=stats['items-transferred'],
                g =stats['realizations'],
                ig=stats['items-realized'],
                tg=stats['transfers-realized'],
                ga=stats['items-realized']/float(stats['items']),
                gb=stats['items-realized']/float(stats['items-transferred']),
                gc=stats['transfers-realized']/float(stats['transfers']),
                gd=stats['realizations']/float(stats['transfers-realized']),
            )
            if args['--bleu']:
                s +='    BLEU{avg_label}          {bleu:4.2f}\n'.format(
                    avg_label=avg_label,
                    bleu=(sum(stats['bleu']) / len(stats['bleu'])) * 100
                )
            if args['--oracle-bleu']:
                s +='    Oracle BLEU{avg_label}   {oracle:4.2f}\n'.format(
                    avg_label=avg_label,
                    oracle=(sum(stats['oracle-bleu']) /
                            len(stats['oracle-bleu'])) * 100
                )

        if 'rephrases' in stats:
            s += (
            '  Rephrasing ({ir} items, {pr} parses, {r} results):\n'
            '    Abs. items rephrased:    {ir:>{w}}/{i:<{w}} ({ra:0.4f})\n'
            '    Rel. items rephrased:    {ir:>{w}}/{ip:<{w}} ({rb:0.4f})\n'
            '    Parses rephrased:        {pr:>{w}}/{p:<{w}} ({rc:0.4f})\n'
            '    Rephrases/Parse:         {r:>{w}}/{pr:<{w}} ({rd:0.4f})\n'
            ).format(
                w =w,
                i =stats['items'],
                p =stats['parses'],
                ip=stats['items-parsed'],
                r =stats['rephrases'],
                ir=stats['items-rephrased'],
                pr=stats['parses-rephrased'],
                ra=stats['items-rephrased']/float(stats['items']),
                rb=stats['items-rephrased']/float(stats['items-parsed']),
                rc=stats['parses-rephrased']/float(stats['parses']),
                rd=stats['rephrases']/float(stats['parses-rephrased'])
            )
            if args['--bleu']:
                s +='    BLEU{avg_label}          {bleu:4.2f}\n'.format(
                    avg_label=avg_label,
                    bleu=(sum(stats['rephrase-bleu']) /
                          len(stats['rephrase-bleu'])) * 100
                )
            if args['--oracle-bleu']:
                s +='    Oracle BLEU{avg_label}   {oracle:4.2f}\n'.format(
                    avg_label=avg_label,
                    oracle=(sum(stats['rephrase-oracle-bleu']) /
                            len(stats['rephrase-oracle-bleu'])) * 100
                )
    return s


def update_stats(stats, prof_stats):
    for key, val in prof_stats.items():
        if key in ('bleu', 'oracle-bleu',
                   'rephrase-bleu', 'rephrase-oracle-bleu'):
            stats[key] = stats.get(key, []) + val
        else:
            stats[key] = stats.get(key, 0) + val
