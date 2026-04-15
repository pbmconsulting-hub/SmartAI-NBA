# ============================================================
# FILE: data/nba_injury_pdf/_parser.py
# PURPOSE: Download and extract tabular data from the official
#          NBA Injury Report PDF using pdfplumber (pure Python).
# ============================================================

import io

import pandas as pd
import requests

from data.nba_injury_pdf._constants import EXPECTED_COLUMNS, REQUEST_HEADERS
from data.nba_injury_pdf._exceptions import DataValidationError, URLRetrievalError

# curl_cffi provides TLS browser-impersonation, bypassing Akamai 403 blocks.
# Fall back to plain requests when curl_cffi is not installed.
try:
    from curl_cffi import requests as _curl_requests
    _CURL_CFFI_AVAILABLE = True
except ImportError:
    _curl_requests = None  # type: ignore[assignment]
    _CURL_CFFI_AVAILABLE = False

# Wrap pdfplumber import so the app degrades gracefully if the package is absent.
try:
    import pdfplumber as _pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _pdfplumber = None  # type: ignore[assignment]
    _PDFPLUMBER_AVAILABLE = False


def fetch_pdf_bytes(url: str, timeout: int = 15) -> bytes:
    """Download the PDF from the NBA CDN.

    Uses ``curl_cffi`` with Chrome browser impersonation when available to
    bypass Akamai TLS fingerprinting (which blocks plain ``requests`` calls
    with HTTP 403).  Falls back to plain ``requests`` if ``curl_cffi`` is
    not installed.

    Note: ``REQUEST_HEADERS`` (custom User-Agent etc.) are only passed on
    the plain-``requests`` path.  When ``curl_cffi`` impersonates Chrome it
    synthesises the full TLS handshake and HTTP headers automatically;
    injecting custom headers on top would break the impersonation.

    Args:
        url:     Full URL to the injury report PDF.
        timeout: Request timeout in seconds.

    Returns:
        Raw PDF bytes.

    Raises:
        URLRetrievalError: If the request fails (non-200 status or network error).
    """
    try:
        if _CURL_CFFI_AVAILABLE:
            # curl_cffi impersonates Chrome's TLS fingerprint end-to-end.
            resp = _curl_requests.get(url, impersonate="chrome", timeout=timeout)
        else:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            raise URLRetrievalError(url, f"HTTP {resp.status_code}")
        return resp.content
    except URLRetrievalError:
        raise
    except Exception as exc:
        raise URLRetrievalError(url, str(exc)) from exc


def extract_tables_from_pdf(pdf_bytes: bytes) -> pd.DataFrame:
    """Parse all tables from a PDF and return a unified DataFrame.

    Uses ``pdfplumber`` with line-based extraction settings that work well
    with the NBA's injury report layout.

    First row of the first table is used as the column header.  Repeated
    header rows on subsequent pages are discarded automatically.

    Args:
        pdf_bytes: Raw bytes of the PDF.

    Returns:
        A ``pd.DataFrame`` containing all rows from all pages.

    Raises:
        DataValidationError: If ``pdfplumber`` is not installed, or if the
                             PDF contains no extractable tables.
    """
    if not _PDFPLUMBER_AVAILABLE:
        raise DataValidationError(
            "pdfplumber is not installed. "
            "Run `pip install pdfplumber` to enable PDF parsing."
        )

    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 5,
        "join_tolerance": 5,
    }

    # Try the primary line-based extraction first, then fall back to
    # text-based strategies for PDFs with merged header columns.
    _settings_chain = [
        table_settings,
        {
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "snap_tolerance": 3,
            "join_tolerance": 3,
        },
    ]

    for attempt_idx, settings in enumerate(_settings_chain):
        header: list | None = None
        all_rows: list[list] = []

        with _pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                # Primary: extract_tables (plural)
                tables = page.extract_tables(settings)
                if not tables and attempt_idx > 0:
                    # Secondary fallback: extract_table (singular)
                    single = page.extract_table(settings)
                    tables = [single] if single else []
                for table in (tables or []):
                    if not table:
                        continue
                    for row in table:
                        # Normalise cell values: None → ""
                        cleaned = [str(cell).strip() if cell is not None else "" for cell in row]

                        if header is None:
                            # First non-empty row across the whole document = header
                            if any(cleaned):
                                # New NBA format uses ≤2 merged columns for the report title
                                # (e.g. "Injury Report: 04/07/26 05:00 PM") — skip to real header
                                if len(cleaned) <= 2 and any("Injury Report" in c for c in cleaned):
                                    continue  # Skip the title row, wait for the real header
                                header = cleaned
                        else:
                            # Skip repeated header rows
                            if cleaned == header:
                                continue
                            # Skip rows that look like the title row even after a header was set
                            if any("Injury Report" in str(c) for c in cleaned) and len(set(cleaned) - {""}) <= 2:
                                continue
                            # Handle column count mismatches from merged cells
                            if len(cleaned) < len(header):
                                cleaned += [""] * (len(header) - len(cleaned))
                            elif len(cleaned) > len(header):
                                cleaned = cleaned[: len(header)]
                            all_rows.append(cleaned)

        if header is not None and all_rows:
            df = pd.DataFrame(all_rows, columns=header)
            if validate_columns(df):
                return df
            # If columns don't validate, try next strategy

    if header is None or not all_rows:
        raise DataValidationError(
            "No tables found in the PDF. "
            "The document may be empty or in an unexpected format."
        )

    return pd.DataFrame(all_rows, columns=header)


def validate_columns(df: pd.DataFrame) -> bool:
    """Check that expected columns are present in the DataFrame.

    Returns ``True`` if **all** expected columns are present, or at least
    the critical subset (Team, Player Name, Current Status) is present so
    the parser can degrade gracefully when the NBA adds/removes columns.

    Args:
        df: The DataFrame to validate.

    Returns:
        ``True`` if columns are sufficient; ``False`` otherwise.
    """
    if all(col in df.columns for col in EXPECTED_COLUMNS):
        return True
    # Degrade gracefully: accept if the critical columns are present
    critical = {"Team", "Player Name", "Current Status"}
    return critical.issubset(set(df.columns))
