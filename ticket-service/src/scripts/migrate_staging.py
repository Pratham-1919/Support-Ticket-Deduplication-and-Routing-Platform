from pathlib import Path
import sys


# ============================================================
# Project root
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.append(str(PROJECT_ROOT))


# ============================================================
# Database connection
# ============================================================

from src.db.connection import get_connection


# ============================================================
# Migration
# ============================================================

def migrate_staging():

    sql_file = PROJECT_ROOT / "sql" / "03_migrate_staging.sql"

    if not sql_file.exists():
        raise FileNotFoundError(
            f"Migration SQL file not found:\n{sql_file}"
        )

    print("=" * 70)
    print("STAGING -> APPLICATION DATABASE MIGRATION")
    print("=" * 70)

    print("\nSQL file:")
    print(sql_file)

    # --------------------------------------------------------
    # Read SQL migration file
    # --------------------------------------------------------

    migration_sql = sql_file.read_text(
        encoding="utf-8"
    )

    conn = None

    try:

        # ----------------------------------------------------
        # Connect to PostgreSQL
        # ----------------------------------------------------

        print("\nConnecting to PostgreSQL...")

        conn = get_connection()

        print("PostgreSQL connection successful.")

        # ----------------------------------------------------
        # Execute migration
        # ----------------------------------------------------

        print("\nExecuting migration...")

        with conn.cursor() as cursor:

            cursor.execute(migration_sql)

        conn.commit()

        print("\nMigration completed successfully.")

    except Exception as error:

        if conn:
            conn.rollback()

        print("\nMigration FAILED.")
        print("Error:")
        print(error)

        raise

    finally:

        if conn:
            conn.close()

            print("\nPostgreSQL connection closed.")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    migrate_staging()