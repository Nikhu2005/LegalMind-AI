import json

from app.rag.case_comparator import compare_cases


METADATA_PATH = "data/metadata.json"


class CaseSearchEngine:

    def __init__(self):

        print("Loading legal case database...")

        with open(
            METADATA_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            self.documents = json.load(file)

        print(
            f"Loaded {len(self.documents)} legal chunks."
        )

    # ==========================================
    # GET UNIQUE CASES
    # ==========================================

    def get_cases(self):

        cases = {}

        for document in self.documents:

            case_name = document.get(
                "case_name"
            )

            if not case_name:
                continue

            if case_name not in cases:

                cases[case_name] = {
                    "case_name": case_name,
                    "court": document.get(
                        "court",
                        "Unknown"
                    ),
                    "judgment_date": document.get(
                        "judgment_date",
                        "Unknown"
                    ),
                    "citation": document.get(
                        "citation",
                        "Unknown"
                    ),
                    "document_type": document.get(
                        "document_type",
                        "Unknown"
                    )
                }

        return list(cases.values())

    # ==========================================
    # SEARCH CASE
    # ==========================================

    def search_case(
        self,
        case_name
    ):

        matching_chunks = []

        search_text = case_name.lower()

        for document in self.documents:

            document_case = document.get(
                "case_name",
                ""
            ).lower()

            if search_text in document_case:

                matching_chunks.append(
                    document
                )

        return matching_chunks

    # ==========================================
    # COMPARE TWO CASES
    # ==========================================

    def compare(
        self,
        case1_name,
        case2_name
    ):

        case1_chunks = self.search_case(
            case1_name
        )

        case2_chunks = self.search_case(
            case2_name
        )

        if not case1_chunks:

            return (
                f"Case not found: {case1_name}"
            )

        if not case2_chunks:

            return (
                f"Case not found: {case2_name}"
            )

        print(
            f"\nCase 1 chunks: {len(case1_chunks)}"
        )

        print(
            f"Case 2 chunks: {len(case2_chunks)}"
        )

        print(
            "\nGenerating case comparison..."
        )

        comparison = compare_cases(
            case1_chunks,
            case2_chunks
        )

        return comparison


# ==========================================
# TEST
# ==========================================

if __name__ == "__main__":

    engine = CaseSearchEngine()

    print("\n========================================")
    print("        LEGALMIND AI")
    print("      CASE COMPARISON ENGINE")
    print("========================================")

    cases = engine.get_cases()

    print(
        f"\nUnique cases available: {len(cases)}"
    )

    for i, case in enumerate(
        cases,
        start=1
    ):

        print(
            f"\n{i}. {case['case_name']}"
        )

        print(
            "   Court:",
            case["court"]
        )

        print(
            "   Date:",
            case["judgment_date"]
        )

        print(
            "   Citation:",
            case["citation"]
        )

    if len(cases) >= 2:

        print(
            "\n========================================"
        )

        print(
            "Automatic comparison test"
        )

        print(
            "========================================"
        )

        case1 = cases[0]["case_name"]
        case2 = cases[1]["case_name"]

        print(
            "\nCase 1:",
            case1
        )

        print(
            "Case 2:",
            case2
        )

        result = engine.compare(
            case1,
            case2
        )

        print(
            "\n========================================"
        )

        print(
            "CASE COMPARISON RESULT"
        )

        print(
            "========================================"
        )

        print(result)

    else:

        print(
            "\nAt least two unique cases are required."
        )