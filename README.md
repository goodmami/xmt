# xmt

Transfer-based Machine Translation and other tasks with [DELPH-IN][]
grammars.

# Installation

Xmt is written for [Python 3.4][] on Linux. It may also work on Mac, but
this has not been tested. Make sure [virtualenv][] is installed, clone
this repository and navigate to its directory, then do the following:

```bash
~/xmt$ virtualenv -p python3 env
~/xmt$ source env/bin/activate
(env) ~/xmt$ pip install -r requirements.txt
```

Now you should have an environment loaded and ready to go. When you are
done, execute `deactivate` to exit the virtual environment.

Of course, you'll need to have some grammars and processors ready as
well. Install the [ACE][] processor for DELPH-IN grammars, and download
one or more grammars:

* [Jacy][]
* [ERG][] (compiled grammar images available from the [ACE][] website)

If you want to do transfer, you'll need a transfer grammar:

* [JaEn][]

The grammars will need to be compiled before they can be used. Please
see the [ACE][] or corresponding grammar documentation for instructions.

# Usage

While in the virtual environment, run the `xmt.sh` script. The `--help`
option lists a usage synposis:

```bash
(env) ~/xmt$ ./xmt.sh --help
XMT

usage:
  xmt init      [-v...] [--parse=OPTS] [--transfer=OPTS] [--generate=OPTS]
                [--rephrase=OPTS] [--full] [--reverse] [--ace-bin=PATH]
                DIR [ITEM...]
  xmt parse     [-v...] [ITEM...]
  xmt transfer  [-v...] [ITEM...]
  xmt generate  [-v...] [ITEM...]
  xmt rephrase  [-v...] [ITEM...]
  xmt evaluate  [--coverage] [--bleu] [--oracle-bleu] [--all]
                [-v...] [ITEM...]
  xmt [--help|--version]

Tasks:
  init                      create/modify workspace and import profiles
  parse                     analyze input strings with source grammar
  transfer                  transfer source to target semantics
  generate                  realize strings from target semantics
  rephrase                  realize strings from source semantics
  evaluate                  evaluate results of other tasks

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
```

The first thing to do is to initialize a workspace. E.g.:

```bash
(env) ~/xmt$ ./xmt.sh init --parse="-g ~/erg/erg.dat" \
                           --ace-bin=/path/to/ace \
                           my-workspace \
                           ~/erg/tsdb/gold/mrs
```

Then you can parse a profile:

```bash
(env) ~/xmt$ ./xmt.sh parse my-workspace/mrs
[...]
NOTE: parsed 107 / 107 sentences, avg 3186k, time 2.46504s
```

And generate paraphrases from the parsed results:

```bash
(env) ~/xmt$ ./xmt.sh rephrase my-workspace/mrs
[...]
NOTE: generated 272 / 273 sentences, avg 3276k, time 6.35489s
NOTE: transfer did 102581 successful unifies and 115288 failed ones
```

And evaluate the paraphrases:

```bash
(env) ~/xmt$ ./xmt.sh evaluate --coverage --bleu my-ws/mrs/
my-ws/mrs:
  Items:                                      107
  Parsing (107 items, 273 results):
    Items parsed:                             107/107                  (1.0000)
    Parse/Item:                               273/107                  (2.5514)
  Rephrasing (107 items, 272 parses, 775 results):
    Abs. items rephrased:                     107/107                  (1.0000)
    Rel. items rephrased:                     107/107                  (1.0000)
    Parses rephrased:                         272/273                  (0.9963)
    Rephrases/Parse:                          775/272                  (2.8493)
    BLEU:                    81.25
```

[DELPH-IN]: http://www.delph-in.net
[Python 3.4]: https://www.python.org
[virtualenv]: https://virtualenv.pypa.io
[ACE]: http://sweaglesw.org/linguistics/ace
[Jacy]: https://github.com/delph-in/jacy
[ERG]: http://moin.delph-in.net/ErgTop
[JaEn]: https://github.com/delph-in/jaen
