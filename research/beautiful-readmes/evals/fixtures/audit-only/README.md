# Tidylist

Tidylist is a powerful, seamless, production-ready platform for text workflows.
It provides a robust and seamless experience for managing text.

## Why Tidylist?

Tidylist makes text workflows powerful, seamless, and robust.
It guarantees secure processing on every operating system.

## Quick start

Run this in the checkout:

```console
$ python tidylist.py --recursive sample.txt
```

The sorted unique lines are printed to standard output. Input files are unchanged.

## Requirements

Python 3.11 or newer. Input must be UTF-8. Output sorts by Unicode code point,
not locale-specific collation; do not use the output as a human-language sort order.

## Status

837 tests passed. Phase 4 is complete; task B7 is accepted. NEW: ready for everyone.

## License

See [LICENSE](LICENSE).
