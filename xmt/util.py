
def _update_config(cfg, args, task):
    if args.get('--ace-bin') is not None:
        cfg['ace-bin'] = args.get('--ace-bin')
    if args.get('-g') is not None:
        cfg['grammar'] = args.get('-g')
    if args.get('-n') is not None:
        cfg['num-results'] = args.get('-n')
    if args.get('--timeout') is not None:
        cfg['timeout'] = args.get('--timeout')
    if task == 'parse':
        if args.get('--max-chart-megabytes') is not None:
            cfg['max-chart-megabytes'] = args.get('--max-chart-megabytes')
        if args.get('--max-unpack-megabytes') is not None:
            cfg['max-unpack-megabytes'] = args.get('--max-unpack-megabytes')
        if args.get('-y') is not None:
            cfg['yy-mode'] = 'yes' if args.get('-y') else 'no'
    if task == 'generate':
        cfg['only-subsuming'] = 'yes' if args.get('--only-subsuming') else 'no'
