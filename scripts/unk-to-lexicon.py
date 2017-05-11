#!/usr/bin/env python3

import sys
import json
from itertools import chain

from delphin import tdl, itsdb
from delphin.derivation import Derivation, UdfTerminal
from delphin.mrs import semi
from delphin.mrs.components import Pred

import docopt

USAGE = '''
Usage: unk-to-lexicon [--sem-i PATH] [--lexicon PATH]...
                      [--data-specifier SPEC] TYPEMAP
                      [--mtr PATH]... [PROFILE]...

Arguments:
  TYPEMAP                   json file mapping extracted types to lexical types
  PROFILE                   profile to extract unknowns from; the profile
                              should be parsed with the --udx option

Options:
  -h, --help                display this help and exit
  --sem-i PATH              use semantic interface at PATH for filtering
  --lexicon PATH            TDL file for getting lexical entry to lexical type
                            mappings (in case derivation trees don't have
                            lexical type info)
  --data-specifier SPEC     specifier for the 'derivation' and 'mrs' parse
                            result fields [default: result:derivation@mrs]
  --mtr PATH                MTR file to extract lexical entries from; instead
                            of or in addition to profiles
'''

def main():
    args = docopt.docopt(USAGE)

    if args['--sem-i']:
        smi = semi.load(args['--sem-i'])
    else:
        smi = semi.SemI()

    lexmap = {}
    if args['--lexicon']:
        for lexicon in args['--lexicon']:
            lexmap.update(get_lexmap(lexicon))

    typemap = json.load(open(args['TYPEMAP']))

    entry_generators = []
    for prof in args['PROFILE']:
        table, cols = itsdb.get_data_specifier(args['--data-specifier'])
        entry_generators.append(
            prof_entries(prof, typemap, lexmap, table, cols)
        )
    for mtr in args['--mtr']:
        entry_generators.append(mtr_entries(mtr, typemap))
    entries = chain.from_iterable(entry_generators)

    created = set()
    for (lename, supertype, orth, pred, cv) in entries:
        # don't create if pred exists or entry already created
        if (pred.short_form() in smi.predicates or
                (supertype, orth, pred.string) in created):
            continue

        # guess if phonological onset is vocalic or consonant
        if cv is None:
            cv = 'voc' if pred.lemma[0] in 'aeiou' else 'con'

        print(format_lex_entry(lename, supertype, orth, pred, cv))
        created.add((supertype, orth, pred.string))


def mtr_entries(mtr, typemap):
    rules = tdl.parse(open(mtr, 'r'))
    for rule in rules:
        assert len(rule.supertypes) == 1

        lename = rule.identifier.rpartition('-')[0] + '_le'
        rule_supertype = rule.supertypes[0]

        if rule_supertype not in typemap:
            continue
        supertypes = typemap[rule_supertype]

        rels = rule['OUTPUT.RELS'].values()
        if (any('PRED' not in rel for rel in rels)
                or len(supertypes) != len(rels)):
            continue

        preds = [rel['PRED'] for rel in rels]
        for i in range(len(supertypes)):
            supertype = supertypes[i]

            pred = preds[i]
            # if pred is not a string, type symbol is the supertype
            if isinstance(pred, tdl.TdlDefinition):
                pred = pred.supertypes[0]
            pred = Pred.string_or_grammar_pred(pred)

            # lemma can be single (_pattern_n_1_rel) or multi (_at+all_a_1_rel)
            orth = ', '.join('"{}"'.format(part)
                             for part in pred.lemma.split('+'))

            yield (lename + str(i), supertype, orth, pred, None)


def prof_entries(prof, typemap, lexmap,
                 table='result', cols=('derivation', 'mrs')):
    p = itsdb.ItsdbProfile(prof)
    seen = set()
    for derivation, mrs in p.select(table, cols):
        d = Derivation.from_string(derivation)
        for entity, typ, form in _derivation_les(d):
            if typ is None:
                typ = lexmap.get(entity)
            orth = ', '.join('"{}"'.format(part) for part in form)
            if (typ, orth) not in seen and typ in typemap:
                supertype = typemap[typ][0]  # more than 1?
                lename = '+'.join(form) + '-' + supertype
                pred = None
                print(lename, supertype, orth, pred, None)
                yield (lename, supertype, orth, pred, None)
                seen.add((typ, orth))


def _derivation_les(d):
    les = []
    if len(d.daughters) == 1 and isinstance(d.daughters[0], UdfTerminal):
        les.append((d.entity, d.type, d.daughters[0].form.split()))
    else:
        for dtr in d.daughters:
            les.extend(_derivation_les(dtr))
    return les


def get_lexmap(lexicon):
    lexmap = {}
    entries = tdl.parse(open(lexicon, 'r'))
    for entry in entries:
        # ignore things with >1 supertype
        if entry.identifier and len(entry.supertypes) == 1:
            lexmap[entry.identifier] = entry.supertypes[0]
    return lexmap


def format_lex_entry(lename, supertype, orth, pred, cv):
    return (
        '{lename} := {supertype} &\n'
        ' [ ORTH < {orth} >,\n'
        '   SYNSEM [ LKEYS.KEYREL.PRED {pred},\n'
        '            PHON.ONSET {cv} ] ].\n'
        .format(
            lename=lename,
            supertype=supertype,
            orth=orth,
            pred=pred.string,
            cv=cv
        )
    )


if __name__ == '__main__':
    main()
