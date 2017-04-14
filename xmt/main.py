#!/usr/bin/env python3

USAGE="""
XMT

usage:
  xmt init      [--parse=OPTS] [--transfer=OPTS] [--generate=OPTS]
                [--ace-bin=PATH] [-v...] DIR [ITEM...]
  xmt parse     [-g PATH] [--ace-bin=PATH] [-n N] [--timeout=S]
                [--max-chart-megabytes=M] [--max-unpack-megabytes=M]
                [-v...] [ITEM...]
  xmt transfer  [-g PATH] [--ace-bin=PATH] [-n N] [--timeout=S]
                [-v...] [ITEM...]
  xmt generate  [-g PATH] [--ace-bin=PATH] [-n N] [--timeout=S]
                [--only-subsuming] [-v...] [ITEM...]
  xmt evaluate  [--coverage] [--bleu] [--oracle-bleu] [--all]
                [-v...] [ITEM...]
  xmt [--help|--version]

Arguments:
  DIR
  ITEM

Options:
  -h, --help                print usage and exit
  -V, --version             print version and exit
  -v, --verbose             increase logging verbosity (may be repeated)
  --parse OPTS              configure parsing with OPTS
  --transfer OPTS           configure transfer with OPTS
  --generate OPTS           configure generation with OPTS
  --ace-bin PATH            path to ace binary [default=ace]
  -g PATH                   path to a grammar image
  -n N                      only record the top N results [default=5]
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

from xmt import task, select, evaluate

__version__ = '0.2.0'

default_config = {
    'DEFAULT': {
        'ace-bin': 'ace',
        'num-results': 5,
        'timeout': 60,
        'result-buffer-size': 1000,
    },
    'parse': {
        'max-chart-megabytes': 1200,
        'max-unpack-megabytes': 1500,
    },
    'transfer': {},
    'generate': {},
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
  mrs :string                           # mrs for this reading
  score :float                          # parse reranker score

x-info:
  i-id :integer :key
  p-id :integer :key
  time :integer
  memory :integer

x-result:
  i-id :integer :key
  p-id :integer :key
  x-id :integer :key
  mrs :string                           # transferred mrs
  score :float                          # transfer reranker score

g-info:
  i-id :integer :key
  p-id :integer :key
  x-id :integer :key
  time :integer
  memory :integer

g-result:
  i-id :integer :key
  p-id :integer :key
  x-id :integer :key
  g-id :integer :key
  surface :string                       # realization string
  mrs :string                           # specified mrs used in realization
  score :float                          # realization reranker score
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
    elif args['evaluate']:
        evaluate.do(args)

def init(args):
    d = args['DIR']

    prepare_workspace_dir(d)
    config = ConfigParser()
    config.read(os.path.join(d, 'default.conf'))

    config['DEFAULT'] = dict(default_config['DEFAULT'])
    _update_config(config['DEFAULT'], args, None)

    for task in ('parse', 'transfer', 'generate'):
        config.setdefault(task, default_config.get(task), {})
        if args['--' + task]:
            argv = [task] + shlex.split(args['--' + task])
            taskargs = docopt(USAGE, argv=argv)
            _update_config(config[task], taskargs, task)

    for item in args['ITEM']:
        item = os.path.normpath(item)
        rows = item_rows(item)
        itemdir = _unique_pathname(d, os.path.basename(item))
        os.makedirs(itemdir)
        with open(os.path.join(itemdir, 'relations'), 'w') as fh:
            print(relations_string, file=fh)
        p = itsdb.ItsdbProfile(itemdir)
        p.write_table('item', rows, gzip=True)

    with open(os.path.join(d, 'default.conf'), 'w') as fh:
        config.write(fh)


def item_rows(item):
    rows = []
    makerow = lambda a, b, c: {
        'i-id': a, 'i-input': b, 'i-length': len(b.split()), 'i-translation': c
    }
    if os.path.isdir(item):
        p = itsdb.ItsdbProfile(item)
        output_fn = os.path.join(p.root, 'output')
        if ((os.path.isfile(output_fn) or os.path.isfile(output_fn + '.gz'))
                and len(list(p.read_table('output'))) > 0):
            for row in p.join('item', 'output'):
                rows.append(makerow(row['item:i-id'], row['item:i-input'],
                                    row['output:o-surface']))
        else:
            rows.extend(
                makerow(a, b, c) for a, b, c in p.select(
                    'item', ['i-id', 'i-input', 'i-translation'])
            )
    elif os.path.isfile(item):
        for i, line in enumerate(open(item)):
            src, tgt = line.split('\t')
            rows.append(makerow((i+1)*10, src.rstrip(), tgt.rstrip()))
    else:
        raise ValueError('Invalid item: ' + str(item))
    return rows


def _unique_pathname(d, bn):
    fn = os.path.join(d, bn)
    i = 0
    while os.path.exists(fn):
        i += 1
        fn = os.path.join(d, bn + '.' + str(i))
    return fn


def _update_config(cfg, args, task):
    if args['--ace-bin'] is not None:
        cfg['ace-bin'] = args['--ace-bin']
    if args['-g'] is not None:
        cfg['grammar'] = args['-g']
    if args['-n'] is not None:
        cfg['num-results'] = args['-n']
    if args['--timeout'] is not None:
        cfg['timeout'] = args['--timeout']
    if task == 'parse':
        if args['--max-chart-megabytes'] is not None:
            cfg['max-chart-megabytes'] = args['--max-chart-megabytes']
        if args['--max-unpack-megabytes'] is not None:
            cfg['max-unpack-megabytes'] = args['--max-unpack-megabytes']
    if task == 'generate':
        cfg['only-subsuming'] = 'yes' if args['--only-subsuming'] else 'no'


def validate(args):
    defaults = docopt(ACE_OPTS_USAGE, argv=args['--ace-opts'] or '')
    p_opts = docopt(ACE_OPTS_USAGE, argv=args['--parse'] or '')
    t_opts = docopt(ACE_OPTS_USAGE, argv=args['--transfer'] or '')
    g_opts = docopt(ACE_OPTS_USAGE, argv=args['--generate'] or '')


def prepare_workspace_dir(d):
    if not os.path.isdir(d):
        os.makedirs(d)


if __name__ == '__main__':
    main()
