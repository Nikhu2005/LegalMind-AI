import fitz


def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF while preserving page numbers.
    """

    document = fitz.open(pdf_path)

    pages = []

    for page_number, page in enumerate(document, start=1):

        text = page.get_text("text")

        if text.strip():
            pages.append({
                "page_number": page_number,
                "text": text.strip()
            })

    document.close()

    return pages


if __name__ == "__main__":

    pdf_path = "data/sample.pdf"

    pages = extract_text_from_pdf(pdf_path)

    print(f"Total pages extracted: {len(pages)}")

    for page in pages[:2]:
        print("\n--- PAGE", page["page_number"], "---")
        print(page["text"][:1000])