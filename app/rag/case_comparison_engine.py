import json

from app.rag.case_comparator import compare_cases, _load_cases


class CaseComparisonEngine:
    """
    LegalMind AI Case Comparison Engine.

    This engine compares two Indian judicial decisions using
    their unique case keys.

    The actual comparison and Gemini generation are handled by
    case_comparator.py.
    """

    def __init__(self):
        print("\n========================================")
        print("       LEGALMIND AI")
        print("   CASE COMPARISON ENGINE")
        print("========================================")

        print("Case comparison engine loaded successfully.")

    def compare(self, case1_key, case2_key):
        """
        Compare two cases using their unique case keys.

        Parameters
        ----------
        case1_key : str
            Unique key of the first case.

        case2_key : str
            Unique key of the second case.

        Returns
        -------
        dict
            Complete comparison result.
        """

        if not case1_key:
            raise ValueError("Case 1 key is required.")

        if not case2_key:
            raise ValueError("Case 2 key is required.")

        if case1_key == case2_key:
            raise ValueError(
                "Please select two different cases for comparison."
            )

        print("\n========================================")
        print("STARTING CASE COMPARISON")
        print("========================================")

        print("\nCase 1 Key:")
        print(case1_key)

        print("\nCase 2 Key:")
        print(case2_key)

        print("\nGenerating legal case comparison...")

        result = compare_cases(
            case1_key,
            case2_key
        )

        print("\nCase comparison completed successfully.")

        return result


def get_available_cases():
    """
    Return all unique cases available in the legal knowledge base.
    """

    return _load_cases()


def print_available_cases(cases):
    """
    Print available cases in a readable format.
    """

    print("\n========================================")
    print("AVAILABLE CASES")
    print("========================================")

    if not cases:
        print("\nNo cases found in the legal knowledge base.")
        return

    print(f"\nTotal cases: {len(cases)}")

    for index, case in enumerate(cases, start=1):

        print("\n----------------------------------------")
        print(f"Case {index}")
        print("----------------------------------------")

        print("Case Name:", case.get("case_name"))
        print("Court:", case.get("court"))
        print("Judgment Date:", case.get("judgment_date"))
        print("Case Number:", case.get("case_number"))
        print("Citation:", case.get("citation"))
        print("Document Type:", case.get("document_type"))
        print("Case Key:", case.get("case_key"))


def run_test():
    """
    Test the case comparison engine using the first two
    cases available in the legal knowledge base.
    """

    print("\n========================================")
    print("        LEGALMIND AI")
    print(" SMART CASE COMPARISON TEST")
    print("========================================")

    try:

        cases = get_available_cases()

        print_available_cases(cases)

        if len(cases) == 0:

            print("\nERROR:")
            print("No legal cases are available.")

            print(
                "Please ingest at least two judgments "
                "before testing comparison."
            )

            return

        if len(cases) < 2:

            print("\nERROR:")
            print("At least two cases are required.")

            return

        case1 = cases[0]
        case2 = cases[1]

        case1_key = case1.get("case_key")
        case2_key = case2.get("case_key")

        if not case1_key:

            print("\nERROR:")
            print("Case 1 does not have a case_key.")

            return

        if not case2_key:

            print("\nERROR:")
            print("Case 2 does not have a case_key.")

            return

        print("\n========================================")
        print("CASES SELECTED FOR COMPARISON")
        print("========================================")

        print("\nCASE A")
        print("----------------------------------------")
        print("Name:", case1.get("case_name"))
        print("Court:", case1.get("court"))
        print("Date:", case1.get("judgment_date"))
        print("Case Number:", case1.get("case_number"))
        print("Citation:", case1.get("citation"))

        print("\nCASE B")
        print("----------------------------------------")
        print("Name:", case2.get("case_name"))
        print("Court:", case2.get("court"))
        print("Date:", case2.get("judgment_date"))
        print("Case Number:", case2.get("case_number"))
        print("Citation:", case2.get("citation"))

        engine = CaseComparisonEngine()

        result = engine.compare(
            case1_key,
            case2_key
        )

        print("\n========================================")
        print("CASE COMPARISON RESULT")
        print("========================================")

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False
            )
        )

    except Exception as error:

        print("\n========================================")
        print("CASE COMPARISON ERROR")
        print("========================================")

        print(type(error).__name__)
        print(str(error))


if __name__ == "__main__":
    run_test()