import ssl
import socket
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def check_ssl(domain: str, port: int = 443, timeout: int = 10) -> dict:
    """
    Connect to domain over TLS and extract certificate info.

    Returns a dict with:
        - expiry_date (datetime | None)
        - ssl_type ("wildcard" | "single" | None)
        - issuer (str | None)  — human-readable issuer string
        - error (str | None)
    """
    result = {"expiry_date": None, "ssl_type": None, "issuer": None, "error": None}

    # Strip protocol prefix if accidentally included
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]

    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        # Parse expiry date — format: 'May 10 12:00:00 2025 GMT'
        not_after = cert.get("notAfter")
        if not_after:
            expiry_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
            # Store as UTC-aware then strip tz for DB compatibility
            result["expiry_date"] = expiry_dt.replace(tzinfo=None)

        # Detect wildcard via Subject Alternative Names
        san = cert.get("subjectAltName", [])
        is_wildcard = any(name.startswith("*.") for _, name in san)
        result["ssl_type"] = "wildcard" if is_wildcard else "single"

        # Extract issuer as a readable string: "countryName=US, organizationName=Let's Encrypt, commonName=R13"
        issuer_tuples = cert.get("issuer", ())
        issuer_parts = [f"{k}={v}" for rdn in issuer_tuples for k, v in rdn]
        result["issuer"] = ", ".join(issuer_parts) if issuer_parts else None

    except ssl.SSLCertVerificationError as e:
        result["error"] = f"SSL verification failed: {e}"
        logger.warning("SSL verification error for %s: %s", domain, e)
    except socket.timeout:
        result["error"] = f"Connection timed out after {timeout}s"
        logger.warning("SSL check timeout for %s", domain)
    except ConnectionRefusedError:
        result["error"] = "Connection refused on port 443"
        logger.warning("Connection refused for %s", domain)
    except socket.gaierror as e:
        result["error"] = f"DNS resolution failed: {e}"
        logger.warning("DNS error for %s: %s", domain, e)
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
        logger.error("Unexpected SSL check error for %s: %s", domain, e)

    return result
