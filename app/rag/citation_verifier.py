def verify_sources(retrieved_chunks):
    """
    Verify that every retrieved source has valid
    case and page metadata.
    """

    verified_sources = []

    for result in retrieved_chunks:

        metadata = result.get("metadata", {})

        case_name = metadata.get("case_name")
        court = metadata.get("court")
        page_number = metadata.get("page_number")
        citation = metadata.get("citation")
        source_file = metadata.get("source_file")

        # Basic validation
        valid_case = bool(case_name)
        valid_court = bool(court)
        valid_page = page_number is not None
        valid_file = bool(source_file)

        verified = (
            valid_case
            and valid_court
            and valid_page
            and valid_file
        )

        verified_sources.append({
            "verified": verified,
            "case_name": case_name,
            "court": court,
            "page_number": page_number,
            "citation": citation,
            "source_file": source_file
        })

    return verified_sources


def print_verified_sources(retrieved_chunks):

    sources = verify_sources(
        retrieved_chunks
    )

    print("\n")
    print("=" * 70)
    print("VERIFIED LEGAL SOURCES")
    print("=" * 70)

    for i, source in enumerate(
        sources,
        start=1
    ):

        print(f"\nSOURCE {i}")
        print("-" * 70)

        print(
            "Verified:",
            "YES" if source["verified"] else "NO"
        )

        print(
            "Case:",
            source["case_name"] or "Not available"
        )

        print(
            "Court:",
            source["court"] or "Not available"
        )

        print(
            "Page:",
            source["page_number"]
            if source["page_number"] is not None
            else "Not available"
        )

        print(
            "Citation:",
            source["citation"] or "Not available"
        )

        print(
            "Source File:",
            source["source_file"] or "Not available"
        )


if __name__ == "__main__":

    print(
        "Citation verifier module loaded successfully."
    )