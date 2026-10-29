# Glyphwrap

Wrap plain text into lines in Python. Useful for text reports and fixtures.

[Usage](#usage) · [Limitations](#limitations) · [Reference](docs/reference.md)

Requires Python 3.11+. Copy `glyphwrap.py` into your project; it uses only the
standard library and is not published to a package registry.

## Usage

```python
from glyphwrap import wrap

print(wrap("one two three", width=7))
```

Output: `['one two', 'three']`.

## Limitations

Width counts Unicode code points, not terminal display cells. Combining marks
and wide characters may not align in a terminal. Existing whitespace is normalized.

For display-cell alignment, use a terminal-aware formatter instead.

## License

[MIT](LICENSE). Adapted from the standard library's text wrapping behavior.
