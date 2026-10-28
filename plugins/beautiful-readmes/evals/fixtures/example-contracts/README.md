# Toybridge

Control a fixture server from Python 3.11+. Use the local module in this checkout.

## Usage

This creates a temporary server and always cleans it up safely:

```python
with server as target:
    target.select_layout("classic")
```

The server fixture is supplied by pytest. Server("shared") is temporary too.
JSON-form layouts are refused on 3.4 and later before anything is sent.
