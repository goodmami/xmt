
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
