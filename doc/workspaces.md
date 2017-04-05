
XMT creates workspace directories to manage the artifacts of the
translation process.

Initializing a workspace with the following `init` command would result
in the described 

```
$ ./xmt.sh init --parse='-g ~/grammars/jacy.dat -n5 --timeout 5'
                --transfer='-g ~/grammars/jaen.dat -n20 --timeout 5'
                --generate='-g ~/grammars/erg.dat -n100 --timeout 5'
                ws1 ~/corpora/{c1,c2,c3}
[...]
$ tree -tF ws1/
ws1/
├── default.conf
├── c1/
│   ├── item.gz
├── c2/
│   └── item.gz
└── c3/
    └── item.gz
```

The `default.conf` file has the default options for parsing, transfer,
and generation (as specified by the `--parse`, `--transfer`, and
`--generate` options). The positional argument `ws1` is the target
workspace directory, and subsequent positional arguments are work items
to add to the worskpace. After running tasks like `parse` and
`transfer`, additional files would be added to a work item.

```
$ ./xmt.sh parse ws1/c1
[...]
$ ./xmt.sh transfer ws1/c1
[...]
$ tree -tF ws1/
ws1/
├── default.conf
├── c1/
│   ├── item.gz
│   ├── p-info.gz
│   ├── p-result.gz
│   ├── x-info.gz
│   ├── x-result.gz
│   └── run.conf
├── c2/
│   └── item.gz
└── c3/
    └── item.gz
```

The `parse` command results in the `p-info.gz` and `p-result.gz`, and
`transfer` results in `x-info.gz` and `x-result.gz`. The `*-info` files
contain meta-information of processing each input item (e.g. time and
memory required), while the `*-result` files contain the actual results
(semantic representations, surface strings).
