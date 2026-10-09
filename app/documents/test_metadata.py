from app.documents.case_metadata import CaseMetadata


case = CaseMetadata(
    case_name="Sample Case v. State",
    court="Supreme Court of India",
    judgment_date="2026-01-15",
    case_number="Civil Appeal No. 123 of 2026",
    citation="2026 SCC OnLine SC 123",
    acts=[
        "Indian Contract Act, 1872"
    ],
    sections=[
        "Section 73",
        "Section 74"
    ],
    document_type="judgment",
    source_url="Official Court Source",
    jurisdiction="India"
)


print("CASE METADATA")
print("====================")

print("Case:", case.case_name)
print("Court:", case.court)
print("Date:", case.judgment_date)
print("Case Number:", case.case_number)
print("Citation:", case.citation)
print("Acts:", case.acts)
print("Sections:", case.sections)
print("Type:", case.document_type)
print("Source:", case.source_url)
print("Jurisdiction:", case.jurisdiction)