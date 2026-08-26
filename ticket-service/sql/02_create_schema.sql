CREATE TABLE IF NOT EXISTS modules (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    external_id TEXT NOT NULL UNIQUE,

    module_id INTEGER NOT NULL
        REFERENCES modules(id),

    ticket_type TEXT NOT NULL
        CHECK (
            ticket_type IN (
                'bug_report',
                'feature_request'
            )
        ),

    title TEXT,
    description TEXT,

    classification TEXT,
    component TEXT,
    product TEXT,
    version TEXT,
    severity TEXT,
    priority TEXT,
    status TEXT,
    resolution TEXT,

    creator TEXT,
    assigned_to TEXT,

    is_confirmed BOOLEAN DEFAULT FALSE,
    is_open BOOLEAN DEFAULT TRUE,

    source_created_at TIMESTAMP,
    source_updated_at TIMESTAMP,

    ingested_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS duplicate_links (
    id SERIAL PRIMARY KEY,

    ticket_id INTEGER NOT NULL
        REFERENCES tickets(id),

    duplicate_of_ticket_id INTEGER NOT NULL
        REFERENCES tickets(id),

    source TEXT NOT NULL
        CHECK (
            source IN (
                'ground_truth',
                'model_detected'
            )
        ),

    similarity_score DOUBLE PRECISION,

    status TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (
            status IN (
                'pending_review',
                'confirmed',
                'rejected'
            )
        ),

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (
        ticket_id,
        duplicate_of_ticket_id
    )
);


CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,

    username TEXT NOT NULL UNIQUE,

    email TEXT NOT NULL UNIQUE,

    hashed_password TEXT NOT NULL,

    role TEXT NOT NULL
        CHECK (
            role IN (
                'admin',
                'support_engineer',
                'reporter'
            )
        ),

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS review_decisions (
    id SERIAL PRIMARY KEY,

    duplicate_link_id INTEGER
        REFERENCES duplicate_links(id),

    ticket_id INTEGER
        REFERENCES tickets(id),

    reviewer_id INTEGER
        REFERENCES users(id),

    decision_type TEXT NOT NULL
        CHECK (
            decision_type IN (
                'duplicate_confirm',
                'severity_override',
                'module_override',
                'routing_confirm'
            )
        ),

    decision TEXT NOT NULL,

    notes TEXT,

    decided_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);