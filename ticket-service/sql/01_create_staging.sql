"""
Step 2: Test chunked ingestion of ONE Eclipse dataset into PostgreSQL.

Current test:
    C_BIRT / BIRT_dataset_issues.csv

What this script does:
    1. Reads the Eclipse CSV in chunks.
    2. Handles very large CSV fields.
    3. Reads only the required columns.
    4. Cleans/normalizes the selected columns.
    5. Derives ticket_type:
           severity == "enhancement" -> feature_request
           otherwise                  -> bug_report
    6. Inserts the cleaned data into PostgreSQL using COPY.
    7. Stops after 5,000 BIRT rows for testing.

After this test succeeds, we can enable all 9 Eclipse projects.
"""

import csv
import io
import sys
from pathlib import Path

import pandas as pd
import psycopg2


# ============================================================
# 1. HANDLE VERY LARGE CSV FIELDS
# ============================================================

def set_csv_field_limit():
    """
    Increase Python's CSV field-size limit.

    Eclipse issue data can contain very large Description,
    Comments, History, etc. fields.
    """

    limit = sys.maxsize

    while True:
        try:
            csv.field_size_limit(limit)
            break
        except OverflowError:
            limit = limit // 10


set_csv_field_limit()


# ============================================================
# 2. CONFIGURATION
# ============================================================

# Folder containing:
#
# Eclipse/
#   C_BIRT/
#   C_mylyn/
#   P_CDT/
#   P_Equinox/
#   P_JDT/
#   P_Papyrus/
#   P_PDE/
#   P_Platform/
#   P_TPTP/

DATASET_ROOT = (
    r"E:\SS-evaluation\support-ticket-project\venv"
    r"\data\raw\Eclipse_dataset\Eclipse"
)


# ------------------------------------------------------------
# TEST SETTINGS
# ------------------------------------------------------------

# Number of rows read at a time
CHUNK_SIZE = 5_000

# IMPORTANT:
# For the first test, only process 5,000 rows.
#
# Later:
# MAX_ROWS_PER_MODULE = None
#
MAX_ROWS_PER_MODULE = None


# ------------------------------------------------------------
# PostgreSQL connection
# ------------------------------------------------------------

PG_DSN = (
    "dbname=ticketdb "
    "user=postgres "
    "password=Pratham@19 "
    "host=localhost "
    "port=5432"
)


# ============================================================
# 3. COLUMNS WE NEED
# ============================================================

CORE_COLUMNS = [
    "ID",
    "Classification",
    "Component",
    "Product",
    "Version",
    "Status",
    "Resolution",
    "Dupe of",
    "Severity",
    "Priority",
    "Creation time",
    "Last change time",
    "Assigned to",
    "Creator",
    "Is confirmed",
    "Is open",
    "Summary",
    "Description",
]


# ============================================================
# 4. POSTGRESQL TABLE
# ============================================================

CREATE_STAGING_SQL = """
CREATE TABLE IF NOT EXISTS staging_tickets (
    external_id      TEXT,
    module            TEXT,
    classification    TEXT,
    component         TEXT,
    product           TEXT,
    version           TEXT,
    status            TEXT,
    resolution        TEXT,
    dupe_of           TEXT,
    severity          TEXT,
    priority          TEXT,
    ticket_type       TEXT,
    creation_time     TIMESTAMP,
    last_change_time  TIMESTAMP,
    assigned_to       TEXT,
    creator           TEXT,
    is_confirmed      BOOLEAN,
    is_open           BOOLEAN,
    title             TEXT,
    description       TEXT
);
"""


# ============================================================
# 5. FIND CSV FILE
# ============================================================

def find_issue_file(folder: Path) -> Path:
    """
    Find the issue CSV inside a project folder.
    """

    candidates = list(folder.glob("*issues*.csv"))

    if not candidates:
        raise FileNotFoundError(
            f"No issues CSV found in:\n{folder}"
        )

    if len(candidates) > 1:
        print("WARNING: Multiple issue CSV files found:")
        for file in candidates:
            print("   ", file)

    return candidates[0]


# ============================================================
# 6. CLEAN ONE CHUNK
# ============================================================

def clean_chunk(df: pd.DataFrame, module: str) -> pd.DataFrame:
    """
    Clean and transform one DataFrame chunk.
    """

    # --------------------------------------------------------
    # Rename columns
    # --------------------------------------------------------

    df = df.rename(
        columns={
            "ID": "external_id",
            "Classification": "classification",
            "Component": "component",
            "Product": "product",
            "Version": "version",
            "Status": "status",
            "Resolution": "resolution",
            "Dupe of": "dupe_of",
            "Severity": "severity",
            "Priority": "priority",
            "Creation time": "creation_time",
            "Last change time": "last_change_time",
            "Assigned to": "assigned_to",
            "Creator": "creator",
            "Is confirmed": "is_confirmed",
            "Is open": "is_open",
            "Summary": "title",
            "Description": "description",
        }
    )

    # --------------------------------------------------------
    # Add module/project
    # --------------------------------------------------------

    df["module"] = module

    # --------------------------------------------------------
    # Normalize severity
    # --------------------------------------------------------

    df["severity"] = (
        df["severity"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # --------------------------------------------------------
    # Derive ticket type
    #
    # Based on the Eclipse/Bugzilla convention:
    #
    # enhancement -> feature_request
    # everything else -> bug_report
    # --------------------------------------------------------

    df["ticket_type"] = df["severity"].apply(
        lambda value:
        "feature_request"
        if value == "enhancement"
        else "bug_report"
    )

    # --------------------------------------------------------
    # Convert dates
    # --------------------------------------------------------

    df["creation_time"] = pd.to_datetime(
        df["creation_time"],
        errors="coerce"
    )

    df["last_change_time"] = pd.to_datetime(
        df["last_change_time"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Convert boolean fields
    # --------------------------------------------------------

    df["is_confirmed"] = (
        df["is_confirmed"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )

    df["is_open"] = (
        df["is_open"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )

    # --------------------------------------------------------
    # Convert text fields
    # --------------------------------------------------------

    text_columns = [
        "external_id",
        "module",
        "classification",
        "component",
        "product",
        "version",
        "status",
        "resolution",
        "dupe_of",
        "severity",
        "priority",
        "assigned_to",
        "creator",
        "title",
        "description",
    ]

    for column in text_columns:

        df[column] = (
            df[column]
            .fillna("")
            .astype(str)
        )

    # --------------------------------------------------------
    # Clean title and description for PostgreSQL COPY
    #
    # We are using TAB as delimiter.
    #
    # Remove TAB/newline characters from these fields so
    # they don't interfere with the COPY format.
    # --------------------------------------------------------

    # Clean text before sending to PostgreSQL.
    # PostgreSQL TEXT cannot contain the NUL character (\x00).
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].apply(
            lambda x: x.replace("\x00", "") if isinstance(x, str) else x
        )

# Clean characters that can interfere with tab-delimited COPY
    for col in ["title", "description"]:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace("\t", " ", regex=False)
            .str.replace("\r", " ", regex=False)
            .str.replace("\n", " ", regex=False)
        )

    # --------------------------------------------------------
    # Order columns exactly like PostgreSQL table
    # --------------------------------------------------------

    ordered_columns = [
        "external_id",
        "module",
        "classification",
        "component",
        "product",
        "version",
        "status",
        "resolution",
        "dupe_of",
        "severity",
        "priority",
        "ticket_type",
        "creation_time",
        "last_change_time",
        "assigned_to",
        "creator",
        "is_confirmed",
        "is_open",
        "title",
        "description",
    ]

    return df[ordered_columns]


# ============================================================
# 7. COPY CHUNK INTO POSTGRESQL
# ============================================================

def copy_chunk_to_postgres(cur, df: pd.DataFrame):
    """
    Insert a DataFrame chunk into PostgreSQL using COPY.

    COPY is much faster than inserting rows one-by-one.
    """

    buffer = io.StringIO()

    df.to_csv(
        buffer,
        index=False,
        header=False,
        sep="\t",
        na_rep="\\N",
    )

    buffer.seek(0)

    cur.copy_expert(
        """
        COPY staging_tickets
        FROM STDIN
        WITH (
            FORMAT csv,
            DELIMITER E'\\t',
            NULL '\\N'
        )
        """,
        buffer,
    )


# ============================================================
# 8. PROCESS ONE PROJECT FOLDER
# ============================================================

def process_folder(
    folder: Path,
    module: str,
    conn
):
    """
    Process one Eclipse project folder.
    """

    issue_file = find_issue_file(folder)

    print()
    print("=" * 70)
    print(f"[{module}]")
    print(f"Reading:")
    print(issue_file)
    print("=" * 70)

    total_rows = 0

    # --------------------------------------------------------
    # Read CSV in chunks
    # --------------------------------------------------------

    reader = pd.read_csv(
        issue_file,

        # Only load the columns we need
        usecols=CORE_COLUMNS,

        # Read in chunks
        chunksize=CHUNK_SIZE,

        # Python engine handles complicated CSVs better
        engine="python",

        # Normal CSV quoting
        quoting=csv.QUOTE_MINIMAL,

        # Warn about malformed lines instead of immediately
        # stopping the complete process
        on_bad_lines="warn",

        # Avoid automatic dtype guessing problems
        dtype=str,
    )

    # --------------------------------------------------------
    # Process each chunk
    # --------------------------------------------------------

    with conn.cursor() as cur:

        for chunk_number, chunk in enumerate(reader):

            # ------------------------------------------------
            # Stop after MAX_ROWS_PER_MODULE
            # ------------------------------------------------

            if (
                MAX_ROWS_PER_MODULE is not None
                and total_rows >= MAX_ROWS_PER_MODULE
            ):
                break

            # ------------------------------------------------
            # Limit final chunk if necessary
            # ------------------------------------------------

            if MAX_ROWS_PER_MODULE is not None:

                remaining = (
                    MAX_ROWS_PER_MODULE - total_rows
                )

                chunk = chunk.head(remaining)

            # ------------------------------------------------
            # Clean
            # ------------------------------------------------

            cleaned = clean_chunk(
                chunk,
                module
            )

            # ------------------------------------------------
            # Insert into PostgreSQL
            # ------------------------------------------------

            copy_chunk_to_postgres(
                cur,
                cleaned
            )

            conn.commit()

            # ------------------------------------------------
            # Update count
            # ------------------------------------------------

            rows_inserted = len(cleaned)

            total_rows += rows_inserted

            print(
                f"chunk {chunk_number}: "
                f"+{rows_inserted} rows "
                f"(total {total_rows})"
            )

            # ------------------------------------------------
            # Stop after requested number
            # ------------------------------------------------

            if (
                MAX_ROWS_PER_MODULE is not None
                and total_rows >= MAX_ROWS_PER_MODULE
            ):
                break

    print()
    print(
        f"[{module}] DONE -- "
        f"{total_rows} rows loaded"
    )


# ============================================================
# 9. VERIFY DATABASE
# ============================================================

def verify_database(conn):

    print()
    print("=" * 70)
    print("DATABASE VERIFICATION")
    print("=" * 70)

    with conn.cursor() as cur:

        # ----------------------------------------------------
        # Total rows
        # ----------------------------------------------------

        cur.execute(
            "SELECT COUNT(*) FROM staging_tickets;"
        )

        total = cur.fetchone()[0]

        print(
            f"\nTotal rows in staging_tickets: {total}"
        )

        # ----------------------------------------------------
        # Module count
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT module, COUNT(*)
            FROM staging_tickets
            GROUP BY module
            ORDER BY module;
            """
        )

        print("\nRows by module:")

        for module, count in cur.fetchall():

            print(
                f"  {module}: {count}"
            )

        # ----------------------------------------------------
        # Ticket type count
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT ticket_type, COUNT(*)
            FROM staging_tickets
            GROUP BY ticket_type
            ORDER BY ticket_type;
            """
        )

        print("\nTicket types:")

        for ticket_type, count in cur.fetchall():

            print(
                f"  {ticket_type}: {count}"
            )

        # ----------------------------------------------------
        # Severity count
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT severity, COUNT(*)
            FROM staging_tickets
            GROUP BY severity
            ORDER BY COUNT(*) DESC;
            """
        )

        print("\nSeverity distribution:")

        for severity, count in cur.fetchall():

            print(
                f"  {severity}: {count}"
            )

        # ----------------------------------------------------
        # Sample rows
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT
                external_id,
                module,
                ticket_type,
                severity,
                component,
                title
            FROM staging_tickets
            ORDER BY external_id
            LIMIT 10;
            """
        )

        print("\nSample records:")

        for row in cur.fetchall():

            print(
                f"  ID={row[0]} | "
                f"Module={row[1]} | "
                f"Type={row[2]} | "
                f"Severity={row[3]} | "
                f"Component={row[4]} | "
                f"Title={row[5][:80]}"
            )


# ============================================================
# 10. MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("ECLIPSE DATASET -> POSTGRESQL")
    print("TEST MODE: BIRT ONLY")
    print("=" * 70)

    # --------------------------------------------------------
    # Check dataset root
    # --------------------------------------------------------

    dataset_root = Path(DATASET_ROOT)

    if not dataset_root.exists():

        raise FileNotFoundError(
            f"\nDataset root does not exist:\n"
            f"{dataset_root.resolve()}"
        )

    print(
        f"\nDataset root:\n"
        f"{dataset_root.resolve()}"
    )

    # --------------------------------------------------------
    # Connect PostgreSQL
    # --------------------------------------------------------

    print("\nConnecting to PostgreSQL...")

    try:

        conn = psycopg2.connect(
            PG_DSN
        )

    except Exception as error:

        print(
            "\nERROR: Could not connect to PostgreSQL."
        )

        print(
            f"\nDetails:\n{error}"
        )

        return

    print(
        "PostgreSQL connection successful."
    )

    try:

        # ----------------------------------------------------
        # Create table
        # ----------------------------------------------------

        with conn.cursor() as cur:

            cur.execute(
                CREATE_STAGING_SQL
            )

        conn.commit()

        print(
            "\nTable staging_tickets is ready."
        )

        # ----------------------------------------------------
        # FIRST TEST ONLY
        #
        # Do NOT process all 9 projects yet.
        # ----------------------------------------------------

        folder_name = "P_JDT"
        module = "jdt"
        folder_path = (
            dataset_root / folder_name
        )

        if not folder_path.exists():

            raise FileNotFoundError(
                f"\nBIRT folder not found:\n"
                f"{folder_path.resolve()}"
            )

        # ----------------------------------------------------
        # Process BIRT
        # ----------------------------------------------------

        process_folder(
            folder_path,
            module,
            conn
        )

        # ----------------------------------------------------
        # Verify
        # ----------------------------------------------------

        verify_database(
            conn
        )

    except Exception as error:

        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)

        print(
            f"\n{type(error).__name__}: {error}"
        )

        # Roll back current transaction
        conn.rollback()

        raise

    finally:

        conn.close()

        print(
            "\nPostgreSQL connection closed."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()