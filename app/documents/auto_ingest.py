import os
import re
import fitz
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ==========================================
# CONFIGURATION
# ==========================================

SUPREME_COURT_URL = "https://www.sci.gov.in/"

DOWNLOAD_DIR = "data/ingestion/downloaded"

HEADERS = {
    "User-Agent": (
        "LegalMindAI/1.0 "
        "(educational research project)"
    )
}


# ==========================================
# DISCOVER PDF LINKS
# ==========================================

def discover_pdf_links():
    """
    Discover direct PDF links from the
    Supreme Court website.
    """

    print("\n========================================")
    print(" LEGALMIND AI - SUPREME COURT DISCOVERY")
    print("========================================")

    print("\nConnecting to Supreme Court website...")

    response = requests.get(
        SUPREME_COURT_URL,
        timeout=30,
        headers=HEADERS
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    judgments = []

    # --------------------------------------
    # Find PDF links
    # --------------------------------------

    for link in soup.find_all(
        "a",
        href=True
    ):

        title = link.get_text(
            " ",
            strip=True
        )

        href = link.get(
            "href"
        )

        if not href:
            continue

        full_url = urljoin(
            SUPREME_COURT_URL,
            href
        )

        if ".pdf" in full_url.lower():

            judgments.append({
                "title": title,
                "url": full_url
            })

    # --------------------------------------
    # Remove duplicate URLs
    # --------------------------------------

    unique = {}

    for judgment in judgments:

        unique[judgment["url"]] = judgment

    judgments = list(
        unique.values()
    )

    print(
        "\nDirect PDF links discovered:",
        len(judgments)
    )

    # --------------------------------------
    # Display first 10
    # --------------------------------------

    for i, judgment in enumerate(
        judgments[:10],
        start=1
    ):

        print(
            f"\n{i}. {judgment['title']}"
        )

        print(
            "   PDF:",
            judgment["url"]
        )

    return judgments


# ==========================================
# DOWNLOAD JUDGMENT
# ==========================================

def download_judgment(
    judgment,
    filename
):
    """
    Download a judgment PDF.
    """

    os.makedirs(
        DOWNLOAD_DIR,
        exist_ok=True
    )

    url = judgment["url"]

    filepath = os.path.join(
        DOWNLOAD_DIR,
        filename
    )

    print("\n========================================")
    print("DOWNLOADING JUDGMENT")
    print("========================================")

    print(
        "\nTitle:",
        judgment.get(
            "title",
            "Unknown judgment"
        )
    )

    print(
        "URL:",
        url
    )

    response = requests.get(
        url,
        timeout=60,
        headers=HEADERS
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "content-type",
        ""
    ).lower()

    # --------------------------------------
    # Verify PDF
    # --------------------------------------

    if (
        "pdf" not in content_type
        and not response.content.startswith(
            b"%PDF"
        )
    ):

        print(
            "\nERROR: The downloaded file "
            "is not a PDF."
        )

        print(
            "Content-Type:",
            content_type
        )

        return None

    # --------------------------------------
    # Save PDF
    # --------------------------------------

    with open(
        filepath,
        "wb"
    ) as file:

        file.write(
            response.content
        )

    print(
        "\nDownloaded successfully."
    )

    print(
        "File:",
        filepath
    )

    print(
        "Size:",
        round(
            len(response.content) / 1024,
            2
        ),
        "KB"
    )

    return filepath


# ==========================================
# EXTRACT CASE METADATA
# ==========================================

def extract_case_metadata(
    pdf_path,
    source_title=None
):
    """
    Extract legal metadata from a judgment PDF.

    Uses:
    1. PDF text
    2. Source title
    3. Filename fallback
    """

    print(
        "\nExtracting case metadata..."
    )

    document = fitz.open(
        pdf_path
    )

    text = ""

    # --------------------------------------
    # Read first 5 pages
    # --------------------------------------

    pages_to_read = min(
        5,
        len(document)
    )

    for page_number in range(
        pages_to_read
    ):

        text += document[
            page_number
        ].get_text("text")

        text += "\n"

    document.close()

    # --------------------------------------
    # Clean text
    # --------------------------------------

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    metadata = {

        "case_name": None,

        "court":
            "Supreme Court of India",

        "judgment_date": None,

        "case_number": None,

        "citation": None,

        "document_type":
            "Judgment"
    }

    # ======================================
    # 1. CASE NAME FROM PDF
    # ======================================

    case_patterns = [

        r"(.{2,150})\s+VERSUS\s+(.{2,150})",

        r"(.{2,150})\s+VS\.?\s+(.{2,150})",

        r"(.{2,150})\s+V\.?\s+(.{2,150})"
    ]

    for line in lines:

        if len(line) > 300:
            continue

        for pattern in case_patterns:

            match = re.search(
                pattern,
                line,
                re.IGNORECASE
            )

            if match:

                case_name = (
                    f"{match.group(1).strip()} "
                    f"v. "
                    f"{match.group(2).strip()}"
                )

                metadata[
                    "case_name"
                ] = case_name

                break

        if metadata["case_name"]:
            break

    # ======================================
    # 2. CASE NAME FROM SOURCE TITLE
    # ======================================

    if not metadata["case_name"]:

        if source_title:

            title = source_title.strip()

            if (
                "versus" in title.lower()
                or " vs " in title.lower()
                or " v. " in title.lower()
                or " v " in title.lower()
            ):

                metadata[
                    "case_name"
                ] = title

    # ======================================
    # 3. CASE NAME FROM FILE NAME
    # ======================================

    if not metadata["case_name"]:

        filename = os.path.basename(
            pdf_path
        )

        filename = os.path.splitext(
            filename
        )[0]

        filename = re.sub(
            r"^\d+_",
            "",
            filename
        )

        filename = filename.replace(
            "_",
            " "
        )

        if (
            " vs " in filename.lower()
            or " v. " in filename.lower()
            or " versus " in filename.lower()
        ):

            metadata[
                "case_name"
            ] = filename

    # ======================================
    # CASE NUMBER
    # ======================================

    case_patterns = [

        r"(Civil Appeal No\.?.{0,150})",

        r"(Criminal Appeal No\.?.{0,150})",

        r"(Writ Petition No\.?.{0,150})",

        r"(Special Leave Petition.{0,150})",

        r"(SLP\s*\(C\).{0,150})",

        r"(Diary No\.?.{0,150})"
    ]

    for pattern in case_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            metadata[
                "case_number"
            ] = (
                match.group(1)
                .strip()
            )

            break

    # ======================================
    # JUDGMENT DATE
    # ======================================

    date_patterns = [

        r"Date\s*:\s*"
        r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})",

        r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})",

        r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})"
    ]

    for pattern in date_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            metadata[
                "judgment_date"
            ] = match.group(1)

            break

    # ======================================
    # CITATION
    # ======================================

    citation_pattern = (
        r"\b\d{4}\s+INSC\s+\d+\b"
    )

    match = re.search(
        citation_pattern,
        text,
        re.IGNORECASE
    )

    if match:

        metadata[
            "citation"
        ] = match.group(0)

    # ======================================
    # DOCUMENT TYPE
    # ======================================

    combined_text = (
        text
        + " "
        + str(source_title or "")
        + " "
        + os.path.basename(pdf_path)
    ).lower()

    if "order" in combined_text:

        metadata[
            "document_type"
        ] = "Order"

    elif "judgment" in combined_text:

        metadata[
            "document_type"
        ] = "Judgment"

    # ======================================
    # DISPLAY
    # ======================================

    print(
        "\nMetadata extracted:"
    )

    print(
        "----------------------------------------"
    )

    for key, value in metadata.items():

        print(
            f"{key}: {value}"
        )

    print(
        "----------------------------------------"
    )

    return metadata

    # --------------------------------------
    # Read first 3 pages
    # --------------------------------------

    pages_to_read = min(
        3,
        len(document)
    )

    for page_number in range(
        pages_to_read
    ):

        page = document[
            page_number
        ]

        text += page.get_text(
            "text"
        )

        text += "\n"

    document.close()

    # --------------------------------------
    # Clean lines
    # --------------------------------------

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    # --------------------------------------
    # Metadata structure
    # --------------------------------------

    metadata = {

        "case_name": None,

        "court":
            "Supreme Court of India",

        "judgment_date": None,

        "case_number": None,

        "citation": None,

        "document_type":
            "Judgment"
    }

    # ======================================
    # CASE NAME
    # ======================================

    for line in lines:

        upper_line = line.upper()

        if (
            "VERSUS" in upper_line
            or " VS. " in upper_line
            or " V. " in upper_line
        ):

            if len(line) < 300:

                metadata[
                    "case_name"
                ] = line.strip()

                break

    # ======================================
    # CASE NUMBER
    # ======================================

    case_patterns = [

        r"(Civil Appeal No\.?.{0,100})",

        r"(Criminal Appeal No\.?.{0,100})",

        r"(Writ Petition No\.?.{0,100})",

        r"(Special Leave Petition.{0,100})",

        r"(Diary No\.?.{0,100})"
    ]

    for pattern in case_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            metadata[
                "case_number"
            ] = (
                match.group(1)
                .strip()
            )

            break

    # ======================================
    # JUDGMENT DATE
    # ======================================

    date_patterns = [

        r"Date\s*:\s*"
        r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})",

        r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})",

        r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})"
    ]

    for pattern in date_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            metadata[
                "judgment_date"
            ] = match.group(1)

            break

    # ======================================
    # SUPREME COURT CITATION
    # ======================================

    citation_pattern = (
        r"\b\d{4}\s+INSC\s+\d+\b"
    )

    match = re.search(
        citation_pattern,
        text,
        re.IGNORECASE
    )

    if match:

        metadata[
            "citation"
        ] = match.group(0)

    # ======================================
    # PRINT METADATA
    # ======================================

    print(
        "\nMetadata extracted:"
    )

    print(
        "----------------------------------------"
    )

    for key, value in metadata.items():

        print(
            f"{key}: {value}"
        )

    print(
        "----------------------------------------"
    )

    return metadata


# ==========================================
# MAIN TEST
# ==========================================

if __name__ == "__main__":

    print("\n========================================")
    print("       LEGALMIND AI")
    print("    METADATA EXTRACTION TEST")
    print("========================================")

    pdf_path = (
        "data/judgments/"
        "Judgement_24-Sep-2026.pdf"
    )

    # --------------------------------------
    # Check PDF exists
    # --------------------------------------

    if not os.path.exists(pdf_path):

        print(
            "\nERROR: PDF not found:"
        )

        print(
            pdf_path
        )

    else:

        metadata = extract_case_metadata(
            pdf_path
        )

        print(
            "\n========================================"
        )

        print(
            "METADATA EXTRACTION COMPLETE"
        )

        print(
            "========================================"
        )

        for key, value in metadata.items():

            print(
                f"{key}: {value}"
            )