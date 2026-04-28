import ssl
import socket
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Timeout per connection attempt (seconds)
CONNECT_TIMEOUT = 15


def _parse_cert(cert: dict) -> dict:
    """Extract expiry date, ssl_type, and issuer from a parsed cert dict."""
    result = {"expiry_date": None, "ssl_type": None, "issuer": None}

    # Expiry date — format: 'May 10 12:00:00 2025 GMT'
    not_after = cert.get("notAfter")
    if not_after:
        try:
            expiry_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
            result["expiry_date"] = expiry_dt.replace(tzinfo=None)
        except ValueError:
            pass

    # Wildcard detection via Subject Alternative Names
    san = cert.get("subjectAltName", [])
    is_wildcard = any(name.startswith("*.") for _, name in san)
    result["ssl_type"] = "wildcard" if is_wildcard else "single"

    # Issuer string: "organizationName=Let's Encrypt, commonName=R13"
    issuer_tuples = cert.get("issuer", ())
    issuer_parts = [f"{k}={v}" for rdn in issuer_tuples for k, v in rdn]
    result["issuer"] = ", ".join(issuer_parts) if issuer_parts else None

    return result


def check_ssl(domain: str, port: int = 443, timeout: int = CONNECT_TIMEOUT) -> dict:
    """
    Connect to domain over TLS and extract certificate info.

    Strategy:
      1. Try with full verification (strict) — preferred.
      2. If verification fails (expired cert, hostname mismatch, self-signed),
         retry without verification so we can still read the expiry date.
      3. On timeout or DNS failure, return an error immediately (no point retrying).

    Returns a dict with:
        - expiry_date (datetime | None)
        - ssl_type    ("wildcard" | "single" | None)
        - issuer      (str | None)
        - error       (str | None)  — set when connection failed; cert data may still be present
    """
    result = {"expiry_date": None, "ssl_type": None, "issuer": None, "error": None}

    # Normalise domain — strip protocol and path
    domain = domain.strip().lower()
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]

    # ── Attempt 1: strict verification ───────────────────────────────────────
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
        parsed = _parse_cert(cert)
        result.update(parsed)
        return result  # success — return immediately

    except ssl.SSLCertVerificationError as e:
        # Cert is invalid (expired, hostname mismatch, self-signed) but may
        # still be readable — fall through to attempt 2.
        result["error"] = f"SSL cert issue: {e.reason if hasattr(e, 'reason') else str(e)}"
        logger.warning("SSL verification failed for %s (%s) — retrying without verification", domain, e)

    except (socket.timeout, TimeoutError):
        result["error"] = f"Connection timed out after {timeout}s"
        logger.warning("SSL timeout for %s", domain)
        return result  # no point retrying a timeout

    except ConnectionRefusedError:
        result["error"] = "Connection refused on port 443"
        logger.warning("Connection refused for %s", domain)
        return result

    except socket.gaierror as e:
        result["error"] = f"DNS resolution failed: {e}"
        logger.warning("DNS error for %s: %s", domain, e)
        return result

    except OSError as e:
        result["error"] = f"Network error: {e}"
        logger.warning("Network error for %s: %s", domain, e)
        return result

    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
        logger.error("Unexpected SSL error for %s: %s", domain, e, exc_info=True)
        return result

    # ── Attempt 2: no verification — read cert data anyway ───────────────────
    # Used when the cert exists but fails validation (expired, mismatch, etc.)
    try:
        ctx_noverify = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx_noverify.check_hostname = False
        ctx_noverify.verify_mode = ssl.CERT_NONE

        with socket.create_connection((domain, port), timeout=timeout) as sock:
            with ctx_noverify.wrap_socket(sock, server_hostname=domain) as ssock:
                # getpeercert() with binary_form=True always returns data even
                # without verification; decode it via DER → PEM path.
                cert_bin = ssock.getpeercert(binary_form=True)
                cert = ssock.getpeercert()  # may be empty dict without verification

        if cert:
            parsed = _parse_cert(cert)
            result.update(parsed)
        elif cert_bin:
            # Parse the DER binary cert manually using ssl module
            parsed = _parse_der_cert(cert_bin)
            result.update(parsed)

        # Keep the original error message so the dashboard shows the warning
        return result

    except (socket.timeout, TimeoutError):
        result["error"] = f"Connection timed out after {timeout}s"
        logger.warning("SSL fallback timeout for %s", domain)
    except Exception as e:
        result["error"] = f"SSL check failed for {domain}: {e}"
        logger.error("SSL fallback error for %s: %s", domain, e)

    return result


def _parse_der_cert(der_bytes: bytes) -> dict:
    """
    Parse a DER-encoded certificate using the cryptography library if available,
    otherwise fall back to openssl CLI via subprocess.
    Returns the same dict shape as _parse_cert().
    """
    result = {"expiry_date": None, "ssl_type": None, "issuer": None}

    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        cert = x509.load_der_x509_certificate(der_bytes, default_backend())

        # Expiry date
        result["expiry_date"] = cert.not_valid_after_utc.replace(tzinfo=None)

        # Wildcard via SAN
        try:
            san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            dns_names = san_ext.value.get_values_for_type(x509.DNSName)
            result["ssl_type"] = "wildcard" if any(n.startswith("*.") for n in dns_names) else "single"
        except Exception:
            result["ssl_type"] = "single"

        # Issuer
        issuer_parts = []
        for attr in cert.issuer:
            issuer_parts.append(f"{attr.oid._name}={attr.value}")
        result["issuer"] = ", ".join(issuer_parts) if issuer_parts else None

    except ImportError:
        # cryptography library not installed — skip DER parsing
        logger.debug("cryptography library not available for DER cert parsing")
    except Exception as e:
        logger.warning("DER cert parse error: %s", e)

    return result
