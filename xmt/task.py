
import os
from collections import namedtuple
from configparser import ConfigParser
import logging

from delphin.interfaces import ace
from delphin import itsdb

from xmt import util

_TaskDefinition = namedtuple(
    'TaskDefinition',
    ('processor', 'cmdargs', 'tsdbinfo',
     'prefix', 'in_table', 'in_field',
     'id_fields', 'out_fields')
)

tasks = {
    'parse': _TaskDefinition(
        ace.AceParser, [], True,
        'p', 'item', 'i-input',
        ('i-id',), ('derivation', 'mrs')
    ),
    'transfer': _TaskDefinition(
        ace.AceTransferer, [], False,
        'x', 'p-result', 'mrs', 
        ('i-id', 'p-id'), ('mrs',)
    ),
    'generate': _TaskDefinition(
        ace.AceGenerator, ['--show-realization-mrses'], False,
        'g', 'x-result', 'mrs',
        ('i-id', 'p-id', 'x-id'), ('mrs', 'surface')
    ),
    'rephrase': _TaskDefinition(
        ace.AceGenerator, ['--show-realization-mrses'], False,
        'r', 'p-result', 'mrs',
        ('i-id', 'p-id'), ('mrs', 'surface')
    )
}


def do(taskname, args):
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
                cmdargs=task.cmdargs + _get_cmdargs(task_conf),
                tsdbinfo=task.tsdbinfo) as ap:

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


def _clear_itsdb_file(root, fn, clear_gzip):
    fn = os.path.join(root, fn)
    if os.path.isfile(fn):
        os.remove(fn)
    if clear_gzip and os.path.isfile(fn + '.gz'):
        os.remove(fn + '.gz')


def _item_config(section, itemdir, args):
    workspace = os.path.dirname(itemdir)
    config = ConfigParser()
    config.read([
        os.path.join(workspace, 'default.conf'),
        os.path.join(itemdir, 'run.conf')
    ])
    util._update_config(config[section], args, section)
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
    if conf.getboolean('yy-mode', fallback=False):
        cmdargs.extend(['-y'])
    return cmdargs
