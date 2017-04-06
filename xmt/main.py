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
from collections import namedtuple
import shlex
from glob import glob
import json
import logging
from configparser import ConfigParser

from docopt import docopt

from delphin.interfaces import ace
from delphin import itsdb

__version__ = '0.1.0'

defaults = {
    'ace-bin': 'ace',
    'num-results': 5,
    'timeout': 60,
    'max-chart-megabytes': 1200,
    'max-unpack-megabytes': 1500,
    'result-buffer-size': 1000,
}

_TaskDefinition = namedtuple(
    'TaskDefinition', ('processor', 'prefix', 'in_table', 'in_field',
                       'id_fields', 'out_fields')
)

tasks = {
    'parse': _TaskDefinition(
        ace.AceParser, 'p', 'item', 'i-input', ('i-id',), ('mrs',)
    ),
    'transfer': _TaskDefinition(
        ace.AceTransferer, 'x', 'p-result', 'mrs', ('i-id', 'p-id'), ('mrs',)
    ),
    'generate': _TaskDefinition(
        ace.AceGenerator, 'g', 'x-result', 'mrs', ('i-id', 'p-id', 'x-id'),
        ('mrs', 'surface')
    ),
}

RESULTBUFFERSIZE = 5000

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
        do_task('parse', args)
    elif args['transfer']:
        do_task('transfer', args)
    elif args['generate']:
        do_task('generate', args)


def init(args):
    d = args['DIR']

    prepare_workspace_dir(d)
    config = ConfigParser()
    config.read(os.path.join(d, 'default.conf'))

    config['DEFAULT'] = dict(defaults)
    _update_config(config['DEFAULT'], args, None)

    for task in ('parse', 'transfer', 'generate'):
        config.setdefault(task, {})        
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


def _item_config(section, itemdir, args):
    workspace = os.path.dirname(itemdir)
    config = ConfigParser()
    config.read([
        os.path.join(workspace, 'default.conf'),
        os.path.join(itemdir, 'run.conf')
    ])
    _update_config(config[section], args, section)
    return config


def _get_cmdargs(conf):
    cmdargs = []
    if 'num-results' in conf:
        cmdargs.extend(['-n', conf['num-results']])
    if 'timeout' in conf:
        cmdargs.extend(['--timeout', conf['timeout']])
    if 'max-chart-megabytes' in conf:
        cmdargs.extend(['--max-chart-megabytes', conf['max-chart-megabytes']])
    if 'max-unpack-megabytes' in conf:
        cmdargs.extend(['--max-unpack-megabytes', conf['max-unpack-megabytes']])
    if not conf.getboolean('only-subsuming', fallback=False):
        cmdargs.extend(['--disable-subsumption-test'])
    return cmdargs


def _clear_itsdb_file(root, fn, clear_gzip):
    fn = os.path.join(root, fn)
    if os.path.isfile(fn):
        os.remove(fn)
    if clear_gzip and os.path.isfile(fn + '.gz'):
        os.remove(fn + '.gz')


def do_task(taskname, args):
    task = tasks[taskname]
    infotbl = task.prefix + '-info'
    rslttbl = task.prefix + '-result'
    numitems = len(args['ITEM'])
    width = len(str(numitems))

    for i, itemdir in enumerate(args['ITEM']):
        itemdir = os.path.normpath(itemdir)
        logging.info(
            '{0} {1:{2}d}/{3} {4}'
            .format(taskname.title(), i+1, width, numitems, itemdir)
        )
        config = _item_config(taskname, itemdir, args)
        with open(os.path.join(itemdir, 'run.conf'), 'w') as fh:
            config.write(fh)
        task_conf = config[taskname]
        n = task_conf.getint('num-results', -1)
        bufsize = task_conf.getint('result-buffer-size', fallback=500)

        p = itsdb.ItsdbProfile(itemdir)
        # clear previous files
        _clear_itsdb_file(p.root, infotbl, True)
        _clear_itsdb_file(p.root, rslttbl, True)

        with task.processor(
                os.path.expanduser(task_conf['grammar']),
                executable=task_conf['ace-bin'],
                cmdargs=_get_cmdargs(task_conf)) as ap:

            inforows = []
            resultrows = []
            for row in p.read_table(task.in_table):
                logging.debug('Process: {}\t{}'.format(
                    '|'.join(row[f] for f in task.id_fields),
                    row[task.in_field]
                ))

                response = ap.interact(row[task.in_field])
                logging.debug('  {} results'.format(len(response['results'])))

                source_ids = [(f, row[f]) for f in task.id_fields]

                inforows.append(dict(
                    source_ids +    
                    [('time', int(response.get('tcpu', -1))),
                     ('memory', int(response.get('others', -1)))]
                ))
                    
                for i, result in enumerate(response.results()[:n]):
                    score = -1.0
                    for attr, val in result.get('flags', []):
                        if attr == ':probability':
                            score = float(val)
                    resultrows.append(dict(
                        source_ids +
                        [(f, result[f]) for f in task.out_fields] +
                        [(task.prefix + '-id', i),
                         ('score', score)]
                    ))

                if len(resultrows) >= bufsize:
                    logging.debug('Writing intermediate results to disk.')
                    p.write_table(infotbl, inforows, append=True, gzip=True)
                    p.write_table(rslttbl, resultrows, append=True, gzip=True)
                    inforows = []
                    resultrows = []

            # write remaining data; also gzip at this time
            p.write_table(infotbl, inforows, append=True, gzip=True)
            p.write_table(rslttbl, resultrows, append=True, gzip=True)


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
