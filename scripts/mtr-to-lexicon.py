
import sys
import json

from delphin import tdl
from delphin.mrs import semi
from delphin.mrs.components import Pred

import docopt

USAGE = '''
Usage: mtr-to-lexicon [--sem-i PATH] TYPEMAP MTR...

Arguments:
  TYPEMAP                   template for lexicon entries
  MTR                       MTR file(s)

Options:
  -h, --help                display this help and exit
  -i PATH, --sem-i PATH     use semantic interface at PATH for filtering
'''

def main():
    args = docopt.docopt(USAGE)

    typemap = json.load(open(args['TYPEMAP']))

    if args['--sem-i']:
        smi = semi.load(args['--sem-i'])
    else:
        smi = semi.SemI()

    for mtr in args['MTR']:
        rules = tdl.parse(open(mtr, 'r'))
        for rule in rules:
            assert len(rule.supertypes) == 1
            print_lex_entries(rule, typemap, smi)


def print_lex_entries(rule, typemap, smi):
    lename = rule.identifier.rpartition('-')[0] + '_le'
    rule_supertype = rule.supertypes[0]

    if rule_supertype not in typemap:
        return
    supertypes = typemap[rule_supertype]

    rels = rule['OUTPUT.RELS'].values()
    if any('PRED' not in rel for rel in rels):
        return
    preds = [rel['PRED'] for rel in rels]
    if len(supertypes) != len(rels):
        return

    for i in range(len(supertypes)):
        supertype = supertypes[i]

        pred = preds[i]
        # if pred is not a string, type symbol is the supertype
        if isinstance(pred, tdl.TdlDefinition):
            pred = pred.supertypes[0]
        pred = Pred.string_or_grammar_pred(pred)

        # don't create a new one if it exists
        if pred.short_form() in smi.predicates:
            continue

        # lemma can be single ("_pattern_n_1_rel") or multi (_at+all_a_1_rel)
        orth = ', '.join('"{}"'.format(part) for part in pred.lemma.split('+'))

        # guess if phonological onset is vocalic or consonant
        cv = 'voc' if pred.lemma[0] in 'aeiou' else 'con'

        print(
            '{lename} := {supertype} &\n'
            ' [ ORTH < {orth} >,\n'
            '   SYNSEM [ LKEYS.KEYREL.PRED {pred},\n'
            '            PHON.ONSET {cv} ] ].\n'
            .format(
                lename=lename + str(i),
                supertype=supertype,
                orth=orth,
                pred=pred.string,
                cv=cv
            )
        )

if __name__ == '__main__':
    main()
