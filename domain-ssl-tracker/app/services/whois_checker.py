import logging
import time
from datetime import datetime

import whois

logger = logging.getLogger(__name__)


def _normalize_date(value) -> datetime | None:
    """
    python-whois can return a datetime, a list of datetimes, or a string.
    Normalize to a single naive datetime (UTC assumed).
    """
    if value is None:
        return None

    # Some registrars return a list; take the first entry
    if isinstance(value, list):
        value = value[0]

    if isinstance(value, datetime):
        return value.replace(tzinfo=None)

    if isinstance(value, str):
        # Try common formats
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue

    return None


def check_whois(domain: str, retries: int = 2, delay: int = 3) -> dict:
    """
    Perform a WHOIS lookup and extract the domain expiry date.

    Returns a dict with:
        - expiry_date (datetime | None)
        - error (str | None)
    """
    result = {"expiry_date": None, "error": None}

    # Use the apex domain for WHOIS (strip subdomains)
    apex = _get_apex_domain(domain)

    for attempt in range(1, retries + 1):
        try:
            w = whois.whois(apex)
            result["expiry_date"] = _normalize_date(w.expiration_date)
            if result["expiry_date"] is None:
                result["error"] = "Expiry date not found in WHOIS response"
            return result

        except whois.parser.PywhoisError as e:
            result["error"] = f"WHOIS parse error: {e}"
            logger.warning("WHOIS parse error for %s (attempt %d): %s", apex, attempt, e)
        except Exception as e:
            result["error"] = f"WHOIS lookup failed: {e}"
            logger.warning("WHOIS error for %s (attempt %d): %s", apex, attempt, e)

        if attempt < retries:
            time.sleep(delay)

    return result


def _get_apex_domain(domain: str) -> str:
    """
    Strip protocol and subdomains to get the registrable domain.
    e.g. 'sub.example.co.uk' → 'example.co.uk'
    This is a simple heuristic; for production use tldextract.
    """
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    parts = domain.split(".")

    # Handle common two-part TLDs (co.uk, com.au, etc.)
    two_part_tlds = {"co.uk", "com.au", "co.nz", "co.in", "org.uk", "net.au"}
    if len(parts) >= 3 and ".".join(parts[-2:]) in two_part_tlds:
        return ".".join(parts[-3:])

    # Default: last two parts
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain
