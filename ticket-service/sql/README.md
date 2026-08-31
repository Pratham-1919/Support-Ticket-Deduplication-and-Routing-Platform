# Historical bootstrap scripts

These scripts were used once, manually, to perform the initial data 
ingestion and schema creation for this project, before the schema was 
migrated to Alembic-managed migrations

They are NOT executed by the application or by any automated process.
They are retained only as documentation of the original data pipeline:
raw CSV -> staging_tickets -> normalized schema -> ground-truth 
duplicate-link resolution.

Current schema changes should go through Alembic migrations only.