import unittest

from url_normal import normalize_url, canonicalize, NormalizationOptions, DEFAULT_OPTIONS


class TestSchemeAndHost(unittest.TestCase):
    def test_scheme_lowercased(self):
        self.assertEqual(canonicalize("HTTP://Example.Com/"), "http://example.com/")

    def test_host_lowercased(self):
        self.assertEqual(canonicalize("http://EXAMPLE.COM/Path"), "http://example.com/Path")

    def test_ipv6_address_kept_bracketed(self):
        result = canonicalize("http://[::1]:8080/path")
        self.assertEqual(result, "http://[::1]:8080/path")


class TestDefaultPort(unittest.TestCase):
    def test_http_default_port_removed(self):
        self.assertEqual(canonicalize("http://example.com:80/"), "http://example.com/")

    def test_https_default_port_removed(self):
        self.assertEqual(canonicalize("https://example.com:443/"), "https://example.com/")

    def test_non_default_port_kept(self):
        self.assertEqual(canonicalize("http://example.com:8080/"), "http://example.com:8080/")

    def test_remove_default_port_disabled(self):
        opts = NormalizationOptions(remove_default_port=False)
        self.assertEqual(canonicalize("http://example.com:80/", opts), "http://example.com:80/")


class TestPathNormalization(unittest.TestCase):
    def test_dot_segments_resolved(self):
        self.assertEqual(canonicalize("http://example.com/a/./b"), "http://example.com/a/b")

    def test_double_dot_segments_resolved(self):
        self.assertEqual(canonicalize("http://example.com/a/../b"), "http://example.com/b")

    def test_multiple_double_dot(self):
        self.assertEqual(
            canonicalize("http://example.com/a/b/../../c"),
            "http://example.com/c",
        )

    def test_root_path_preserved(self):
        self.assertEqual(canonicalize("http://example.com/"), "http://example.com/")

    def test_empty_path_becomes_empty(self):
        self.assertEqual(canonicalize("http://example.com"), "http://example.com")

    def test_trailing_slash_stripped_when_enabled(self):
        opts = NormalizationOptions(strip_trailing_slash=True)
        self.assertEqual(canonicalize("http://example.com/a/", opts), "http://example.com/a")

    def test_root_not_stripped_even_when_enabled(self):
        opts = NormalizationOptions(strip_trailing_slash=True)
        self.assertEqual(canonicalize("http://example.com/", opts), "http://example.com/")

    def test_unreserved_percent_decoded_in_path(self):
        self.assertEqual(canonicalize("http://example.com/%7Euser"), "http://example.com/~user")


class TestQueryNormalization(unittest.TestCase):
    def test_query_sorted(self):
        self.assertEqual(
            canonicalize("http://example.com/?b=2&a=1"),
            "http://example.com/?a=1&b=2",
        )

    def test_query_sort_disabled(self):
        opts = NormalizationOptions(sort_query=False)
        self.assertEqual(
            canonicalize("http://example.com/?b=2&a=1", opts),
            "http://example.com/?b=2&a=1",
        )

    def test_blank_values_kept(self):
        self.assertEqual(
            canonicalize("http://example.com/?a=&b=2"),
            "http://example.com/?a=&b=2",
        )

    def test_unreserved_percent_decoded_in_query(self):
        self.assertEqual(
            canonicalize("http://example.com/?name=%7Ebob"),
            "http://example.com/?name=~bob",
        )


class TestFragment(unittest.TestCase):
    def test_fragment_preserved_by_default(self):
        self.assertEqual(
            canonicalize("http://example.com/path#section"),
            "http://example.com/path#section",
        )

    def test_fragment_stripped_when_enabled(self):
        opts = NormalizationOptions(strip_fragment=True)
        self.assertEqual(
            canonicalize("http://example.com/path#section", opts),
            "http://example.com/path",
        )


class TestEquivalence(unittest.TestCase):
    def test_equivalent_urls_compare_equal(self):
        urls = [
            "HTTP://Example.Com:80/a/./b/../c?b=2&a=1#frag",
            "http://example.com/a/c?a=1&b=2#frag",
            "http://example.com:80/a/c?a=1&b=2#frag",
        ]
        canonical = [canonicalize(u) for u in urls]
        self.assertEqual(len(set(canonical)), 1)

    def test_normalize_url_alias(self):
        self.assertEqual(normalize_url("HTTP://X.COM/"), "http://x.com/")


class TestUserinfo(unittest.TestCase):
    def test_userinfo_preserved(self):
        self.assertEqual(
            canonicalize("http://user:pass@example.com/"),
            "http://user:pass@example.com/",
        )

    def test_userinfo_percent_encoded_normalised(self):
        self.assertEqual(
            canonicalize("http://us%65r@example.com/"),
            "http://user@example.com/",
        )


class TestNoScheme(unittest.TestCase):
    def test_no_scheme_passes_through(self):
        # urlsplit treats a schemeless string as path-only.
        result = canonicalize("example.com/path")
        self.assertEqual(result, "example.com/path")


if __name__ == "__main__":
    unittest.main()
