#!/usr/bin/env python3

USAGE="""
XMT

usage:
  xmt init      [-v...] [--parse=OPTS] [--transfer=OPTS] [--generate=OPTS]
                [--rephrase=OPTS] [--full] [--reverse] [--ace-bin=PATH]
                DIR [ITEM...]
  xmt parse     [-v...] [ITEM...]
  xmt transfer  [-v...] [ITEM...]
  xmt generate  [-v...] [ITEM...]
  xmt rephrase  [-v...] [ITEM...]
  xmt evaluate  [--coverage] [--bleu] [--oracle-bleu] [--all] [--ignore=S]
                [-v...] [ITEM...]
  xmt select    [--oracle-bleu] [--tokenize] [--rephrasing] [--item-id]
                [-v...] [ITEM...]
  xmt [--help|--version]

Tasks:
  init                      create/modify workspace and import profiles
  parse                     analyze input strings with source grammar
  transfer                  transfer source to target semantics
  generate                  realize strings from target semantics
  rephrase                  realize strings from source semantics
  evaluate                  evaluate results of other tasks
  select                    print translation/realization pairs

Arguments:
  DIR                       workspace directory
  ITEM                      profile to process

Options:
  -h, --help                print usage and exit
  -V, --version             print version and exit
  -v, --verbose             increase logging verbosity (may be repeated)
  --parse OPTS              configure parsing with OPTS
  --transfer OPTS           configure transfer with OPTS
  --generate OPTS           configure generation with OPTS
  --rephrase OPTS           configure rephrasing with OPTS
  --full                    import full profiles, not just item info
  --reverse                 switch input and translation sentences
  --ace-bin PATH            path to ace binary [default=ace]

Evaluation Options:
  --coverage
  --bleu
  --oracle-bleu
  --all
  --ignore S

"""

OPTS_USAGE="""
Usage: task -g PATH [-n N] [-y] [--timeout S]
            [--max-chart-megabytes=M] [--max-unpack-megabytes=M]
            [--only-subsuming]

Options:
  -g PATH                   path to a grammar image
  -n N                      only record the top N results [default=5]
  -y                        use yy mode on input
  --timeout S               allow S seconds per item [default=60]
  --max-chart-megabytes M   max RAM for parse chart in MB [default=1200]
  --max-unpack-megabytes M  max RAM for unpacking in MB [default=1500]
  --only-subsuming          realization MRS must subsume input MRS

"""

import os
import re
import shlex
from glob import glob
import json
import logging
from configparser import ConfigParser

from docopt import docopt

from delphin import itsdb

from xmt import task, select, evaluate, util

__version__ = '0.2.0'

default_config = {
    'DEFAULT': {
        'ace-bin': 'ace',
        'num-results': 5,
        'timeout': 60,
        'result-buffer-size': 1000,
        'max-chart-megabytes': 1200,
        'max-unpack-megabytes': 1500,
        'only-subsuming': 'no',
        'yy-mode': 'no',
    },
    'parse': {},
    'transfer': {},
    'generate': {},
    'rephrase': {},
}


relations_string = '''
item:
  i-id :integer :key                    # item id
  i-input :string                       # input string
  i-length :integer                     # number of tokens in input
  i-translation :string                 # reference translation

p-info:
  i-id :integer :key                    # item parsed
  time :integer                         # processing time (msec)
  memory :integer                       # bytes of memory allocated

p-result:
  i-id :integer :key                    # item parsed
  p-id :integer :key                    # parse result id
  derivation :string                    # derivation tree for this reading
  mrs :string                           # mrs for this reading
  score :float                          # parse reranker score

x-info:
  i-id :integer :key                    # item parsed
  p-id :integer :key                    # parse result id
  time :integer                         # processing time (msec)
  memory :integer                       # bytes of memory allocated

x-result:
  i-id :integer :key                    # item parsed
  p-id :integer :key                    # parse result id
  x-id :integer :key                    # transfer result id
  mrs :string                           # transferred mrs
  score :float                          # transfer reranker score

g-info:
  i-id :integer :key                    # item parsed
  p-id :integer :key                    # parse result id
  x-id :integer :key                    # transfer result id
  time :integer                         # processing time (msec)
  memory :integer                       # bytes of memory allocated

g-result:
  i-id :integer :key                    # item parsed
  p-id :integer :key                    # parse result id
  x-id :integer :key                    # transfer result id
  g-id :integer :key                    # generation result id
  surface :string                       # realization string
  mrs :string                           # specified mrs used in realization
  score :float                          # realization reranker score

r-info:
  i-id :integer :key                    # item parsed
  p-id :integer :key                    # parse result id
  time :integer                         # processing time (msec)
  memory :integer                       # bytes of memory allocated

r-result:
  i-id :integer :key                    # item parsed
  p-id :integer :key                    # parse result id
  r-id :integer :key                    # rephrase result id
  surface :string                       # realization string
  mrs :string                           # specified mrs used in realization
  score :float                          # parse reranker score

'''


def main():
    args = docopt(
        USAGE,
        version='Xmt {}'.format(__version__),
        # options_first=True
    )
    logging.basicConfig(level=50 - ((args['--verbose'] + 2) * 10))

    args['ITEM'] = [i for pattern in args['ITEM'] for i in glob(pattern)]

    if args['init']:
        init(args)
    elif args['parse']:
        task.do('parse', args)
    elif args['transfer']:
        task.do('transfer', args)
    elif args['generate']:
        task.do('generate', args)
    elif args['rephrase']:
        task.do('rephrase', args)
    elif args['evaluate']:
        evaluate.do(args)
    elif args['select']:
        select.do(args)

def init(args):
    d = args['DIR']

    prepare_workspace_dir(d)
    config = ConfigParser()
    config.read(os.path.join(d, 'default.conf'))

    config['DEFAULT'] = dict(default_config['DEFAULT'])
    util._update_config(config['DEFAULT'], args, None)

    for task in ('parse', 'transfer', 'generate', 'rephrase'):
        config.setdefault(task, default_config.get(task, {}))
        if args['--' + task]:
            argv = shlex.split(args['--' + task])
            taskargs = docopt(OPTS_USAGE, argv=argv)
            util._update_config(config[task], taskargs, task)

    # default rephrase grammar to parse grammar
    if 'grammar' not in config['rephrase'] and 'grammar' in config['parse']:
        config['rephrase']['grammar'] = config['parse']['grammar']

    for item in args['ITEM']:
        item = os.path.normpath(item)
        rows = item_rows(item, args['--reverse'])
        itemdir = _unique_pathname(d, os.path.basename(item))
        os.makedirs(itemdir)
        with open(os.path.join(itemdir, 'relations'), 'w') as fh:
            print(relations_string, file=fh)
        p = itsdb.ItsdbProfile(itemdir)
        p.write_table('item', rows, gzip=True)
        if args['--full']:
            info, results = _parse_tables(item)
            p.write_table('p-info', info, gzip=True)
            p.write_table('p-result', results, gzip=True)

    with open(os.path.join(d, 'default.conf'), 'w') as fh:
        config.write(fh)


def item_rows(item, reverse=False):
    data = []
    if os.path.isdir(item):
        p = itsdb.ItsdbProfile(item)
        output_fn = os.path.join(p.root, 'output')
        if ((os.path.isfile(output_fn) or os.path.isfile(output_fn + '.gz'))
                and len(list(p.read_table('output'))) > 0):
            for row in p.join('item', 'output'):
                data.append((
                    row['item:i-id'],
                    row['item:i-input'],
                    row['output:o-surface']
                ))
        else:
            data.extend(p.select('item', ['i-id', 'i-input', 'i-translation']))
    elif os.path.isfile(item):
        for i, line in enumerate(open(item)):
            src, tgt = line.split('\t', 1)
            data.append(((i+1)*10, src.rstrip(), tgt.rstrip()))
    else:
        raise ValueError('Invalid item: ' + str(item))

    rows = []
    for i_id, src, tgt in data:
        if reverse:
            src, tgt = tgt, src
        rows.append({
            'i-id': i_id,
            'i-input': src,
            'i-length': len(src.split()),
            'i-translation': tgt
        })
    return rows


def _parse_tables(item):
    info, results = [], []
    makeinfo = lambda a, b, c: {
        'i-id': a, 'time': b, 'memory': c
    }
    makeresult = lambda a, b, c, d, e: {
        'i-id': a, 'p-id': b, 'derivation': c, 'mrs': d, 'score': e
    }
    if os.path.isdir(item):
        p = itsdb.ItsdbProfile(item)
        fn = os.path.join(p.root, 'parse')
        if os.path.isfile(fn) or os.path.isfile(fn + '.gz'):
            for row in p.read_table('parse'):
                info.append(makeinfo(row['i-id'], row['total'], row['others']))
        fn = os.path.join(p.root, 'result')
        if os.path.isfile(fn) or os.path.isfile(fn + '.gz'):
            for row in p.join('parse', 'result'):
                results.append(makeresult(
                    row['parse:i-id'], row['result:result-id'],
                    row['result:derivation'], row['result:mrs'],
                    '1.0'  # for now
                    ))
    else:
        raise ValueError('Only profiles allowed with --full: ' + str(item))
    return info, results


def _unique_pathname(d, bn):
    fn = os.path.join(d, bn)
    i = 0
    while os.path.exists(fn):
        i += 1
        fn = os.path.join(d, bn + '.' + str(i))
    return fn


def validate(args):
    defaults = docopt(ACE_OPTS_USAGE, argv=args['--ace-opts'] or '')
    p_opts = docopt(ACE_OPTS_USAGE, argv=args['--parse'] or '')
    t_opts = docopt(ACE_OPTS_USAGE, argv=args['--transfer'] or '')
    g_opts = docopt(ACE_OPTS_USAGE, argv=args['--generate'] or '')
    g_opts = docopt(ACE_OPTS_USAGE, argv=args['--rephrase'] or '')


def prepare_workspace_dir(d):
    if not os.path.isdir(d):
        os.makedirs(d)


if __name__ == '__main__':
    main()
