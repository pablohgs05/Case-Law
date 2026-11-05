# Why a search for one common word took 95 seconds

Where the time went, what was measured against what, and why the fix is a
materialised ranking rather than a different index.

Measured on **2026-10-31** against production and on **2026-11-02** against the
same collection on the development machine: 991.163 decisions, 876.996 from the
STJ and 114.167 from the TJDFT.

---

## The complaint, as a number

| term | decisions matched | time on production |
|---|---:|---:|
| `recurso` | 765.840 | **95,3 s** |
| `direito` | 309.257 | 39,3 s |
| `prazo` | 121.402 | 29,5 s |
| `dano moral` | 29.783 | 0,6 s |

Every one of the slow terms is a single word, and the fast one is two. That is
not a coincidence and it is the first thing the fix depends on: the
intersection of two common words is a small set, so a two-word search is
already cheap however common each word is.

## Where the time goes

Not in finding the matches. `EXPLAIN (ANALYZE, BUFFERS)` over `recurso`, with
the GIN index forced:

```
Bitmap Index Scan on ..._ementa_busca_idx   (actual time=45.802..45.802 rows=765840)
      Buffers: shared hit=1 read=125
Parallel Bitmap Heap Scan                   (actual time=46.042..489.172 rows=255280 loops=3)
      Heap Blocks: exact=11248 lossy=44226
      Buffers: shared hit=1968125 read=432767
```

**The index answers in 46 ms and finds all 765.840.** Everything after that is
the cost of reading `ementa_busca` back so `ts_rank` can score each match.

Left to itself the planner does not even use the index — it chooses a parallel
sequential scan, which for a term in 77% of the rows is the cheaper of two
expensive options. Forcing the index changes nothing worth measuring: 515 ms
against 516 ms for the count, 782 ms against 729 ms for the page.

### The bytes

```
heap  1.299 MB        indexes  410 MB        TOAST  2.602 MB
```

| column | total | average per decision |
|---|---:|---:|
| `ementa_busca` | **1.488 MB** | 1.574 bytes |
| `ementa` | 1.225 MB | 1.296 bytes |
| `decisao_texto` | 346 MB | — |
| `tese` | 25 MB | — |

The search vector is the largest column in the table, larger than the text it
was built from, and the ranking path has to read all of it that matches.

### The throughput that explains everything

Dividing matched bytes by measured seconds gives the same answer three times:

| term | tsvector read | time | MB/s |
|---|---:|---:|---:|
| `recurso` | 1.205 MB | 95,3 s | 12,6 |
| `direito` | 487 MB | 39,3 s | 12,4 |
| `prazo` | 191 MB | 29,5 s | 6,5 |
| `dano moral` | 47 MB | 0,6 s | 78 (served from cache) |

**About 12,5 MB/s of effective read on the production server**, and a cache
that holds a small search but not a broad one. `shared_buffers` is at its
128 MB default against a 4,3 GB table, so for a broad term almost every block
is a physical read.

The same query on the development machine takes 729 ms. The work is identical;
only the disk and the page cache differ. Any fix that still reads a gigabyte
will look fine here and stay broken there.

---

## What was considered

**The ceiling the story asks for is 2 s, and it must not change the order of
the results.** That second half rules out most of the obvious answers.

| approach | result |
|---|---|
| Force the GIN index | **No gain.** The index was never the slow part. |
| RUM index, which ranks inside the index | **Rejected.** Not in the image the project runs, and its ranking is a different function — the first page would come back in a different order. |
| Cap the candidates before ranking | **Rejected.** Scoring a subset is a different ranking; broad terms would be the ones to change, which is exactly the case the story is about. |
| Materialise the ranking | **Chosen.** |

### Why materialising works, and exactly

`ts_rank` of a one-lexeme query depends only on that lexeme in that document.
Nothing else about the query enters the number — so it can be computed once and
read later, and the value read is the value the search would have computed, not
an approximation of it.

That is testable, and it was tested: the stored first 100 for `recurso` against
the live first 100, position by position, **0 divergences**; and the stored
rank against a freshly computed `ts_rank` at the first position of every stored
term, **0 divergences**.

### Where the floor comes from

A ceiling of 2 s at 12,5 MB/s is 25 MB, and at 1.574 bytes of vector per
decision that is **16.000 decisions**. Above that a search cannot be answered
the old way inside the ceiling; below it, it already is.

Of the 1.183 lexemes above the floor, **11 are dropped** — they contain a
hyphen, and the text parser reads a hyphenated word as a multi-node phrase, so
no typed word ever produces them as a single lexeme. Their stored ranking would
be unreachable today and wrong tomorrow: checked on the collection, the stored
order of `fatico-probatori` differs from the search's order in 96 of the first
100 positions, because one is the ranking of a lexeme and the other of a
three-word phrase.

### What it costs to keep

| | |
|---|---|
| Terms stored | 1.172 |
| Rows, at 1.000 per term | 1.172.000 |
| Size with both indexes | 211 MB |
| Build time on the development machine | 5 min 54 s |

1.000 rows per term is 50 pages of 20. Materialising all 84 million postings
above the floor would roughly double the database to serve pages nobody opens;
a reader who pages past 50 on a one-word search falls back to the old path and
waits, which is rare and correct.

The table has to be rebuilt in the same run as `core.decisao`, not after it. A
new decision ranked onto the first page of `recurso` but missing here would
make the stored order stop being the search's order.

---

## The result

The first page of `recurso`, through the statements the API actually runs:

| | before | after |
|---|---:|---:|
| Term lookup | — | 1,03 ms |
| Page, with the highlighted snippet | 757,12 ms | 35,68 ms |
| Count | 484,37 ms | 0 — it is stored |
| **Total on the development machine** | **1.241,49 ms** | **36,71 ms** |

34 times faster, and the same page position by position.

Of the 36,71 ms, the index read is 0,043 ms; the rest is `ts_headline` cutting
the snippet out of 20 ementas. That is the point of the change — what remains
expensive costs per row returned, and there are always twenty of those,
instead of per match, of which there can be seven hundred thousand.

The count is read rather than computed: `core.termo_frequente` already holds
the exact number of decisions carrying each term, so the second expensive
statement disappears instead of being made cheaper.

### A defect this found

The first build came out 11.000 rows short, silently — one thousand for each
hyphenated term. `to_tsquery` runs the parser and the dictionaries, which both
strips another suffix from 214 of the frequent lexemes (`acorda`, 323.845
decisions, becomes `acord`) and splits the 11 hyphenated ones into phrases.
Casting a quoted literal to `tsquery` reads the lexeme as it is. Had this
reached production, a search for "acórdão" would have answered an empty first
page.

---

## What this does not fix

**A broad search with a filter applied.** The stored order is the order of the
whole collection; filtering can bring a decision from position 900 onto the
first page, so the stored order cannot serve it. Both statements still cost in
proportion to the matches — `recurso` narrowed to one court measures 427 ms for
the count on the development machine, against 12,6 ms when the count is capped
at ten thousand. Capping it is the obvious next step and is not done here: it
makes `total` a lower bound, which the paging and the export both read.

**A frequent term the parser splits.** `fatico-probatori` matches 89.404
decisions and is read as a three-word phrase, so it takes neither path. It
measures 383 ms on the development machine, which the 12,5 MB/s figure puts at
roughly 11 s on production. Slow, but not the 95 s this story was opened for.

**Pages past the fiftieth** of a one-word search, by design.
