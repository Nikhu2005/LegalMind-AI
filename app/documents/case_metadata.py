from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CaseMetadata:

    case_name: str

    court: str

    judgment_date: Optional[str] = None

    case_number: Optional[str] = None

    citation: Optional[str] = None

    acts: List[str] = field(default_factory=list)

    sections: List[str] = field(default_factory=list)

    document_type: str = "judgment"

    source_url: Optional[str] = None

    jurisdiction: Optional[str] = None


if __name__ == "__main__":

    case = CaseMetadata(
        case_name="Sample Case",
        court="High Court of Bombay",
        judgment_date="2026-01-01",
        case_number="WP/123/2026",
        acts=["Indian Penal Code"],
        sections=["Section 420"],
        document_type="judgment",
        source_url="https://example.com"
    )

    print(case)