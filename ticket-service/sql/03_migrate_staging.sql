-- ============================================================
-- 03_migrate_staging.sql
-- Move cleaned data from staging_tickets into application tables
-- ============================================================

BEGIN;


-- ============================================================
-- 1. Normalize module names
-- ============================================================

UPDATE staging_tickets
SET module = CASE
    WHEN LOWER(module) = 'birt' THEN 'BIRT'
    WHEN LOWER(module) = 'mylyn' THEN 'Mylyn'
    WHEN LOWER(module) = 'cdt' THEN 'CDT'
    WHEN LOWER(module) = 'equinox' THEN 'Equinox'
    WHEN LOWER(module) = 'jdt' THEN 'JDT'
    WHEN LOWER(module) = 'papyrus' THEN 'Papyrus'
    WHEN LOWER(module) = 'pde' THEN 'PDE'
    WHEN LOWER(module) = 'platform' THEN 'Platform'
    WHEN LOWER(module) = 'tptp' THEN 'TPTP'
    ELSE module
END;


-- ============================================================
-- 2. Insert modules
-- ============================================================

INSERT INTO modules (name)
SELECT DISTINCT module
FROM staging_tickets
WHERE module IS NOT NULL
  AND TRIM(module) <> ''
ON CONFLICT (name) DO NOTHING;


-- ============================================================
-- 3. Insert tickets
-- ============================================================

INSERT INTO tickets (
    external_id,
    module_id,
    ticket_type,
    title,
    description,
    classification,
    component,
    product,
    version,
    severity,
    priority,
    status,
    resolution,
    creator,
    assigned_to,
    is_confirmed,
    is_open,
    source_created_at,
    source_updated_at
)
SELECT
    st.external_id,
    m.id,
    st.ticket_type,
    st.title,
    st.description,
    st.classification,
    st.component,
    st.product,
    st.version,
    st.severity,
    st.priority,
    st.status,
    st.resolution,
    st.creator,
    st.assigned_to,
    st.is_confirmed,
    st.is_open,
    st.creation_time,
    st.last_change_time
FROM staging_tickets st
JOIN modules m
    ON m.name = st.module
ON CONFLICT (external_id) DO NOTHING;


-- ============================================================
-- 4. Create historical duplicate relationships
-- ============================================================

INSERT INTO duplicate_links (
    ticket_id,
    duplicate_of_ticket_id,
    source,
    similarity_score,
    status
)
SELECT
    duplicate_ticket.id,
    original_ticket.id,
    'ground_truth',
    NULL,
    'confirmed'
FROM staging_tickets st

JOIN tickets duplicate_ticket
    ON duplicate_ticket.external_id = st.external_id

JOIN tickets original_ticket
    ON original_ticket.external_id = st.dupe_of

WHERE st.dupe_of IS NOT NULL
  AND TRIM(st.dupe_of) <> ''
  AND UPPER(st.resolution) = 'DUPLICATE'

ON CONFLICT (
    ticket_id,
    duplicate_of_ticket_id
)
DO NOTHING;


COMMIT;