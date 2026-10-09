import time
from datetime import datetime

from app.documents.ingestion_manager import IngestionManager


CHECK_INTERVAL = 6 * 60 * 60  # 6 hours


def run_scheduler():
    print("\n" + "=" * 60)
    print("        LEGALMIND AI - AUTO UPDATE SYSTEM")
    print("=" * 60)

    print("\nAutomatic ingestion is enabled.")
    print("Checking for new legal documents every 6 hours.")
    print("Press CTRL+C to stop.\n")

    while True:
        try:
            print("\n" + "-" * 60)
            print("Checking for new judgments...")
            print("Time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print("-" * 60)

            manager = IngestionManager()

            # Check a batch of newly discovered documents.
            manager.run(max_documents=10)

            print("\nNext check in 6 hours.")

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n\nLegalMind AI scheduler stopped.")
            break

        except Exception as error:
            print("\nScheduler error:")
            print(error)
            print("\nRetrying after 10 minutes...")

            time.sleep(10 * 60)


if __name__ == "__main__":
    run_scheduler()