"""HTTPS requests from Decky's Python."""
import ssl
import urllib.request

HEADERS = {"User-Agent": "Mozilla/5.0 (rom-library Decky plugin)"}
# Decky's loader is a PyInstaller bundle whose OpenSSL looks for CA certs at
# the build distro's paths, so the default context can come up empty.
CA_BUNDLES = (
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/ssl/cert.pem",
)
_context = None


def context():
    global _context
    if _context is None:
        _context = ssl.create_default_context()
        if not _context.cert_store_stats().get("x509_ca"):
            for bundle in CA_BUNDLES:
                try:
                    _context.load_verify_locations(bundle)
                    break
                except OSError:
                    continue
    return _context


def urlopen(url, body=None, headers=None, timeout=30):
    request = urllib.request.Request(url, data=body, headers={**HEADERS, **(headers or {})})
    return urllib.request.urlopen(request, timeout=timeout, context=context())
