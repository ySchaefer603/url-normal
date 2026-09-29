from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlsplit, urlunsplit, parse_qsl, quote, unquote
from dataclasses import dataclass


_DEFAULT_PORTS = {
    "http": 80,
    "https": 443,
    "ftp": 21,
    "ws": 80,
    "wss": 443,
}


_SAFE_PATH_CHARS = "/:@!$&'()*+,;=-._~"
_SAFE_QUERY_CHARS = "/:@!$&'()*+,;=-._~?"
_SAFE_FRAGMENT_CHARS = "/:@!$&'()*+,;=-._~?"


@dataclass(frozen=True)
class NormalizationOptions:
    """Options controlling how aggressively URLs are normalised.

    The defaults implement a conservative set of transformations that are safe for
    equivalence comparison in nearly all contexts: lowercasing the scheme and host,
    removing default ports, dot-segment resolution, percent-encoding normalisation,
    and query-string sorting.
    """

    strip_fragment: bool = False
    strip_trailing_slash: bool = False
    sort_query: bool = True
    remove_default_port: bool = True
    decode_unreserved: bool = True
    lowercase_host: bool = True


DEFAULT_OPTIONS = NormalizationOptions()


def _decode_unreserved_percent(s: str) -> str:
    """Decode percent-encoded *unreserved* characters (ALPHA / DIGIT / ``-._~``).

    Percent-encoded unreserved characters are semantically identical to their literal
    forms per RFC 3986 §6.2.2.2, so decoding them is a safe normalisation. Reserved and
    other characters are left percent-encoded to avoid changing meaning.
    """
    result_chars: List[str] = []
    i = 0
    unreserved = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
    n = len(s)
    while i < n:
        c = s[i]
        if c == "%" and i + 2 < n:
            hex_str = s[i + 1:i + 3]
            try:
                code = int(hex_str, 16)
            except ValueError:
                result_chars.append(c)
                i += 1
                continue
            ch = chr(code)
            if ch in unreserved:
                result_chars.append(ch)
            else:
                upper_hex = hex_str.upper()
                result_chars.append("%" + upper_hex)
            i += 3
        else:
            result_chars.append(c)
            i += 1
    return "".join(result_chars)


def _re_encode_path(path: str) -> str:
    """Normalise a URL path so equivalent paths compare equal.

    The approach: fully decode (``unquote``), then re-encode with a stable set of safe
    characters. This collapses the difference between ``%2F`` and ``/`` for unreserved
    chars and produces a canonical encoding for everything else. We deliberately keep
    ``/`` unencoded because it is the path separator.
    """
    decoded = unquote(path)
    return quote(decoded, safe=_SAFE_PATH_CHARS)


def _re_encode_query(query: str) -> str:
    """Normalise the query string encoding.

    Fully decode then re-encode, preserving ``=`` and ``&`` as structural separators
    so that individual parameter values are canonicalised without breaking the pair
    structure.
    """
    decoded = unquote(query)
    return quote(decoded, safe=_SAFE_QUERY_CHARS)


def _re_encode_fragment(fragment: str) -> str:
    """Normalise the fragment encoding (same idea as path/query)."""
    decoded = unquote(fragment)
    return quote(decoded, safe=_SAFE_FRAGMENT_CHARS)


def _resolve_dot_segments(path: str) -> str:
    """Apply RFC 3986 §5.2.4 remove_dot_segments to a path.

    This collapses ``/a/./b`` → ``/a/b`` and ``/a/../b`` → ``/b``, which is essential
    for equivalence comparison. The algorithm is a direct transcription of the RFC.
    """
    input_buf = path
    output_buf: List[str] = []
    while input_buf:
        # A
        if input_buf.startswith("../"):
            input_buf = input_buf[3:]
        elif input_buf.startswith("./"):
            input_buf = input_buf[2:]
        # B
        elif input_buf.startswith("/./"):
            input_buf = "/" + input_buf[3:]
        elif input_buf == "/.":
            input_buf = "/"
        # C
        elif input_buf.startswith("/../") or input_buf == "/..":
            input_buf = "/" + input_buf[4:]
            if output_buf:
                output_buf.pop()
        # D
        elif input_buf == "." or input_buf == "..":
            input_buf = ""
        # E
        else:
            if input_buf.startswith("/"):
                # find the next slash after the first one
                idx = input_buf.find("/", 1)
            else:
                idx = input_buf.find("/")
            if idx == -1:
                output_buf.append(input_buf)
                input_buf = ""
            else:
                output_buf.append(input_buf[:idx])
                input_buf = input_buf[idx:]
    return "".join(output_buf)


def _normalize_host(host: str, lowercase: bool, raw_netloc: str = "") -> str:
    """Normalise the host component.

    IPv6 addresses keep their brackets; the address inside is left as-is because
    IPv6 canonicalisation is a large problem we do not tackle here. Regular hostnames
    are lowercased. Percent-encoding in the host is not decoded (hosts rarely contain
    it and handling it safely requires care we do not claim to provide).
    """
    if not host:
        return host
    is_ipv6 = raw_netloc.startswith("[") or ("@" not in raw_netloc and raw_netloc.rfind("]") != -1) or host.startswith("[")
    if is_ipv6:
        inner = host
        if inner.startswith("[") and inner.endswith("]"):
            inner = inner[1:-1]
        if lowercase:
            inner = inner.lower()
        return "[" + inner + "]"
    if lowercase:
        return host.lower()
    return host


def _normalize_path(path: str, strip_trailing_slash: bool) -> str:
    """Resolve dot segments, re-encode, then optionally strip a trailing slash.

    A trailing slash is only stripped when the path has more than one character, so
    the root path ``/`` is preserved.
    """
    if path:
        path = _resolve_dot_segments(path)
        path = _re_encode_path(path)
    if strip_trailing_slash and len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path


def _normalize_query(query: str, sort: bool) -> str:
    """Re-encode the query string and optionally sort its parameters.

    Sorting uses ``parse_qsl`` which handles ``+`` as space and ``;`` as a regular
    character (not a separator). Parameters with the same key retain their relative
    order due to Python's stable sort.
    """
    if not query:
        return query
    if sort:
        pairs = parse_qsl(query, keep_blank_values=True)
        pairs.sort()
        return "&".join(_re_encode_query(k) + "=" + _re_encode_query(v) for k, v in pairs)
    return _re_encode_query(query)


def _normalize_fragment(fragment: str) -> str:
    if not fragment:
        return fragment
    return _re_encode_fragment(fragment)


def _normalize_port(scheme: str, port: Optional[int], remove_default: bool) -> Optional[int]:
    """Drop the port when it is the well-known default for the scheme."""
    if port is None:
        return None
    if remove_default and _DEFAULT_PORTS.get(scheme) == port:
        return None
    return port


def canonicalize(url: str, options: NormalizationOptions = DEFAULT_OPTIONS) -> str:
    """Return a canonical string form of *url*.

    This is the core transformation. It does not raise on malformed URLs — instead it
    normalises what it can and passes through what it cannot, so that a slightly odd
    URL still produces a stable, comparable string.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = _normalize_host(parts.hostname or "", options.lowercase_host, parts.netloc) if parts.netloc else ""
    port = _normalize_port(scheme, parts.port, options.remove_default_port)

    # Rebuild netloc: host[:port], omitting the port entirely when it is None.
    netloc = host
    if port is not None:
        netloc = host + ":" + str(port)
    # Preserve userinfo if present (normalise its encoding but do not drop it).
    if parts.username is not None:
        userinfo = _re_encode_path(parts.username)
        if parts.password is not None:
            userinfo += ":" + _re_encode_path(parts.password)
        netloc = userinfo + "@" + netloc

    path = _normalize_path(parts.path, options.strip_trailing_slash)
    query = _normalize_query(parts.query, options.sort_query)
    fragment = "" if options.strip_fragment else _normalize_fragment(parts.fragment)

    return urlunsplit((scheme, netloc, path, query, fragment))


def normalize_url(url: str, options: NormalizationOptions = DEFAULT_OPTIONS) -> str:
    """Alias for :func:`canonicalize`.

    Provided so callers can use whichever name reads better at the call site.
    """
    return canonicalize(url, options)
