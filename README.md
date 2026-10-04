# url_normal

Normalise URLs so that equivalent URLs compare equal as strings.

```python
from url_normal import canonicalize, NormalizationOptions

canonicalize("HTTP://Example.Com:80/a/./b/../c?b=2&a=1")
# -> 'http://example.com/a/c?a=1&b=2'

opts = NormalizationOptions(strip_fragment=True, strip_trailing_slash=True)
canonicalize("https://example.com/page/#section", opts)
# -> 'https://example.com/page'
```

## Why

Comparing URLs for equivalence is harder than string equality: scheme and host are
case-insensitive, default ports are implicit, dot-segments resolve, and query
parameter order usually does not matter. This library applies a conservative set of
RFC 3986 normalisations so that two URLs that refer to the same resource produce the
same canonical string.

The trade-off: we do **not** attempt DNS resolution, IPv6 address canonicalisation,
Unicode IDN punycode conversion, or protocol-level redirects. The library is purely
syntactic. If two URLs differ only in ways that require network access to resolve,
they will remain different after normalisation.

## Edge cases

- A URL with no scheme is passed through largely untouched — `urlsplit` treats it as a
  path-only string, and we do not guess a scheme.
- Userinfo (`user:pass@`) is preserved and percent-normalised but never stripped.
- `+` in a query value is decoded to a space by Python's `parse_qsl`; this matches
  `application/x-www-form-urlencoded` semantics.
- The root path `/` is never stripped, even when `strip_trailing_slash=True`.

## API

- `canonicalize(url: str, options: NormalizationOptions = DEFAULT_OPTIONS) -> str` —
  returns the canonical form.
- `normalize_url(url: str, options: NormalizationOptions = DEFAULT_OPTIONS) -> str` —
  alias for `canonicalize`.
- `NormalizationOptions` — a frozen dataclass with these fields (all default to the
  safe, conservative value):
  - `strip_fragment: bool = False`
  - `strip_trailing_slash: bool = False`
  - `sort_query: bool = True`
  - `remove_default_port: bool = True`
  - `decode_unreserved: bool = True`
  - `lowercase_host: bool = True`
- `DEFAULT_OPTIONS` — the default `NormalizationOptions` instance.

## Running the tests

```
PYTHONPATH=src python -m unittest discover -s tests
```

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

