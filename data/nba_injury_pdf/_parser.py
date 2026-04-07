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

# Wrap pdfplumber import so the app degrades gracefully if the package is absent.
try:
    import pdfplumber as _pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _pdfplumber = None  # type: ignore[assignment]
    _PDFPLUMBER_AVAILABLE = False


def fetch_pdf_bytes(url: str, timeout: int = 15) -> bytes:
    """Download the PDF from the NBA CDN.

    Args:
        url:     Full URL to the injury report PDF.
        timeout: Request timeout in seconds.

    Returns:
        Raw PDF bytes.

    Raises:
        URLRetrievalError: If the request fails (non-200 status or network error).
    """
    try:
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

    # Fallback settings for merged-header PDFs where line-based extraction
    # produces only 2 wide columns instead of the expected 7.
    _fallback_settings = {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "snap_tolerance": 3,
        "join_tolerance": 3,
    }

    header: list | None = None
    all_rows: list[list] = []

    with _pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables(table_settings)
            for table in (tables or []):
                if not table:
                    continue
                for row in table:
                    # Normalise cell values: None → ""
                    cleaned = [str(cell).strip() if cell is not None else "" for cell in row]

                    if header is None:
                        # First non-empty row across the whole document = header
                        if any(cleaned):
                            header = cleaned
                    else:
                        # Skip repeated header rows
                        if cleaned == header:
                            continue
                        # Handle column count mismatches from merged cells
                        if len(cleaned) < len(header):
                            cleaned += [""] * (len(header) - len(cleaned))
                        elif len(cleaned) > len(header):
                            cleaned = cleaned[: len(header)]
                        all_rows.append(cleaned)

    # ── Validate primary extraction — retry with fallbacks if needed ──
    if header is not None and all_rows:
        primary_df = pd.DataFrame(all_rows, columns=header)
        if validate_columns(primary_df):
            return primary_df

    # Primary extraction produced a merged-header format (e.g. 2 columns
    # named "Injury Report: …") or no data at all.  Try alternative strategies.
    for strategy_label, settings in [
        ("text-based", _fallback_settings),
    ]:
        fb_header: list | None = None
        fb_rows: list[list] = []

        with _pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables(settings)
                for table in (tables or []):
                    if not table:
                        continue
                    for row in table:
                        cleaned = [str(cell).strip() if cell is not None else "" for cell in row]
                        # Skip rows that look like a merged report header
                        if any("Injury Report:" in c for c in cleaned):
                            # Check if a real 7-column header follows later
                            continue
                        if fb_header is None:
                            if any(cleaned):
                                fb_header = cleaned
                        else:
                            if cleaned == fb_header:
                                continue
                            if len(cleaned) < len(fb_header):
                                cleaned += [""] * (len(fb_header) - len(cleaned))
                            elif len(cleaned) > len(fb_header):
                                cleaned = cleaned[: len(fb_header)]
                            fb_rows.append(cleaned)

        if fb_header and fb_rows:
            fb_df = pd.DataFrame(fb_rows, columns=fb_header)
            if validate_columns(fb_df):
                return fb_df

    # Last resort: try page.extract_table() (singular) which sometimes
    # handles merged headers better than extract_tables().
    sg_header: list | None = None
    sg_rows: list[list] = []

    with _pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            table = page.extract_table(_fallback_settings)
            if not table:
                continue
            for row in table:
                cleaned = [str(cell).strip() if cell is not None else "" for cell in row]
                if any("Injury Report:" in c for c in cleaned):
                    continue
                if sg_header is None:
                    if any(cleaned):
                        sg_header = cleaned
                else:
                    if cleaned == sg_header:
                        continue
                    if len(cleaned) < len(sg_header):
                        cleaned += [""] * (len(sg_header) - len(cleaned))
                    elif len(cleaned) > len(sg_header):
                        cleaned = cleaned[: len(sg_header)]
                    sg_rows.append(cleaned)

    if sg_header and sg_rows:
        sg_df = pd.DataFrame(sg_rows, columns=sg_header)
        if validate_columns(sg_df):
            return sg_df

    # If we had a primary result (even with wrong columns), return it so
    # the caller can see what was parsed.  Otherwise raise.
    if header is not None and all_rows:
        return pd.DataFrame(all_rows, columns=header)

    raise DataValidationError(
        "No tables found in the PDF. "
        "The document may be empty or in an unexpected format."
    )


def validate_columns(df: pd.DataFrame) -> bool:
    """Check that all expected columns are present in the DataFrame.

    Args:
        df: The DataFrame to validate.

    Returns:
        ``True`` if all ``EXPECTED_COLUMNS`` are present; ``False`` otherwise.
    """
    return all(col in df.columns for col in EXPECTED_COLUMNS)
