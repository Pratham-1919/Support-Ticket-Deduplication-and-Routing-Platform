from pathlib import Path
import sys

# Allow importing from src/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from src.db.connection import get_connection


def create_schema():

    # Location of SQL file
    sql_file = PROJECT_ROOT / "sql" / "02_create_schema.sql"

    if not sql_file.exists():
        raise FileNotFoundError(
            f"Schema file not found: {sql_file}"
        )

    print("=" * 70)
    print("CREATING POSTGRESQL APPLICATION SCHEMA")
    print("=" * 70)

    print(f"\nSQL file:")
    print(sql_file)

    # Read SQL
    sql_script = sql_file.read_text(encoding="utf-8")

    conn = None

    try:
        print("\nConnecting to PostgreSQL...")

        conn = get_connection()

        print("PostgreSQL connection successful.")

        with conn.cursor() as cursor:

            print("\nExecuting schema...")

            cursor.execute(sql_script)

        conn.commit()

        print("\nSchema created successfully.")

    except Exception as error:

        if conn:
            conn.rollback()

        print("\nERROR:")
        print(error)

        raise

    finally:

        if conn:
            conn.close()
            print("\nPostgreSQL connection closed.")


if __name__ == "__main__":
    create_schema()