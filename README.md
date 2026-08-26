
# Support Ticket Deduplication and Routing Platform

An AI-powered support ticket management platform for detecting duplicate tickets, classifying incoming tickets, routing tickets, supporting human review, generating ticket documents, answering questions over historical ticket data, and providing an agentic ticket analysis workflow.

The project uses the public Eclipse Bugzilla dataset and combines FastAPI, PostgreSQL, SQLAlchemy, ChromaDB, machine learning, LLM-based Q&A, and Docker.

---

## Features

The system provides:

- Support ticket creation and management
- Semantic duplicate ticket detection
- Top similar ticket retrieval
- Automatic duplicate detection
- Human review queue for uncertain duplicates
- Module classification
- Severity classification
- Ticket routing
- Classification review and override
- Role-based access control
- JWT authentication
- Rate limiting
- Ticket summary generation
- Weekly ticket reports
- Retrieval-Augmented Generation (RAG) based Q&A
- Agentic ticket analysis
- SQLAlchemy ORM
- Alembic database migrations
- Docker-based deployment

---

## Dataset

The project uses the public Eclipse Bugzilla dataset.

The dataset contains historical tickets from Eclipse modules including:

- BIRT
- CDT
- Equinox
- JDT
- Mylyn
- Papyrus
- PDE
- Platform

The original dataset is not included in this repository because of its large size.

Historical ticket information is stored in PostgreSQL, while ticket embeddings are stored in ChromaDB for semantic similarity search.

---

## System Architecture

```text
                         User / Swagger UI
                                |
                                v
                    +-------------------------+
                    |     Ticket Service      |
                    |      FastAPI :8000      |
                    +-------------------------+
                       |        |         |
                       |        |         |
                       v        v         v
                 PostgreSQL   ChromaDB   ML Models
                       |      Embeddings
                       |
                       +----------------+
                                        |
                                        v
                              Duplicate Detection
                              Classification
                              Routing
                              Human Review
                              Q&A / Agent
                                        |
                                        v
                              +--------------------+
                              |  Document Service  |
                              |   FastAPI :8001    |
                              +--------------------+
                                      |
                                      v
                              Ticket Summaries
                              Weekly Reports
```

---

## Technology Stack

### Backend

- Python
- FastAPI
- Pydantic
- Uvicorn

### Database

- PostgreSQL
- SQLAlchemy ORM
- Alembic

### AI / Machine Learning

- Sentence embeddings
- ChromaDB
- Semantic similarity search
- Machine learning classification
- Groq LLM
- Retrieval-Augmented Generation (RAG)
- Agentic AI workflow

### Security

- JWT authentication
- Role-Based Access Control (RBAC)
- Password hashing
- API rate limiting
- Internal service authentication

### Deployment

- Docker
- Docker Compose

---

## Project Structure

```text
support-ticket-project/
│
├── docker-compose.yml
├── README.md
│
├── ticket-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │
│   └── src/
│       ├── api/
│       │   ├── main.py
│       │   └── routes/
│       │
│       ├── core/
│       │
│       ├── db/
│       │   ├── models/
│       │   ├── session.py
│       │   └── base.py
│       │
│       ├── ml/
│       │
│       └── services/
│
└── doc-service/
    ├── Dockerfile
    ├── requirements.txt
    │
    └── app/
        ├── services/
        └── storage/
```

---

## Duplicate Detection Workflow

When a new ticket is submitted, the system generates an embedding from the ticket title and description.

The embedding is compared with historical ticket embeddings stored in ChromaDB.

```text
New Ticket
    |
    v
Title + Description
    |
    v
Embedding Generation
    |
    v
ChromaDB Similarity Search
    |
    v
Top Similar Tickets
    |
    v
Similarity Threshold
    |
    +--------------------------+
    |                          |
    v                          v
High similarity          Medium similarity
    |                          |
Auto Duplicate            Human Review
                               |
                               v
                         Review Queue
```

The system uses similarity thresholds to decide whether a ticket should be automatically identified as a duplicate, sent for human review, or treated as a new ticket.

---

## Classification and Routing

Incoming tickets are classified by:

- Module
- Severity

The classification results and confidence scores are used together with duplicate analysis to determine ticket routing.

Low-confidence predictions can be sent to the human review queue.

Reviewers can:

- Confirm a classification
- Override the predicted module
- Override the predicted severity
- Confirm a duplicate
- Reject a duplicate

---

## Q&A System

The Q&A system uses Retrieval-Augmented Generation.

```text
User Question
     |
     v
Question Embedding
     |
     v
ChromaDB Retrieval
     |
     v
Relevant Historical Tickets
     |
     v
LLM
     |
     v
Grounded Answer
```

The system retrieves relevant historical tickets before generating an answer.

If the retrieved ticket data does not contain sufficient information, the system avoids answering the question as though it were supported by the ticket dataset.

Example:

```json
{
  "question": "What kinds of issues are commonly reported in the PDE module?"
}
```

---

## Agentic Assistant

The Agentic Assistant analyzes a new ticket using multiple capabilities of the platform.

Example request:

```json
{
  "title": "Plugin manifest editor corrupts plugin.xml",
  "description": "When an extension attribute is modified and saved, duplicate XML elements are sometimes created in plugin.xml."
}
```

The workflow performs:

```text
Ticket
  |
  +--> Duplicate Analysis
  |
  +--> Module Classification
  |
  +--> Severity Classification
  |
  +--> Routing Decision
  |
  +--> Human Review Decision
  |
  +--> Explanation
```

The response includes duplicate analysis, classification results, routing information, review requirements, and an explanation of the decision.

---

## Authentication and Authorization

The API uses JWT-based authentication.

Supported roles include:

- Admin
- Support Engineer
- Reporter

Different endpoints are protected based on the user's role.

For example, administrative operations such as deleting tickets require appropriate authorization.

---

## Environment Variables

Create a `.env` file in the project root.

Example:

```env
POSTGRES_DB=ticketdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password

JWT_SECRET_KEY=your_jwt_secret
INTERNAL_API_KEY=your_internal_api_key
GROQ_API_KEY=your_groq_api_key
```

Do not commit the real `.env` file.

The `.env` file should be included in `.gitignore` and `.dockerignore`.

---

## Running with Docker

Make sure Docker Desktop is running.

From the project root:

```bash
docker compose up --build
```

Check container status:

```bash
docker compose ps
```

The expected services are:

```text
ticket-service
doc-service
postgres
```

---

## API Documentation

After starting the application with Docker:

### Ticket Service

```text
http://127.0.0.1:8000/docs
```

### Document Service

```text
http://127.0.0.1:8001/docs
```

FastAPI Swagger UI can be used to test the APIs.

---

## Main API Capabilities

### Authentication

```text
POST /auth/login
```

### Tickets

```text
POST   /tickets/
GET    /tickets/
GET    /tickets/{ticket_id}
PUT    /tickets/{ticket_id}/status
DELETE /tickets/{ticket_id}
```

### Duplicate Detection

```text
POST /tickets/check
GET  /tickets/duplicates
```

### Review Queue

```text
GET  /review-queue/
POST /review-queue/{duplicate_link_id}/confirm
POST /review-queue/{duplicate_link_id}/reject
```

### Classification Review

```text
GET  /review-queue/classifications
POST /review-queue/classifications/{ticket_id}/confirm
POST /review-queue/classifications/{ticket_id}/override
```

### Weekly Statistics

```text
GET /tickets/stats/weekly
```

Additional Q&A and Agentic Assistant endpoints are available through the ticket-service Swagger documentation.

---

## Document Service

The document service runs independently on port `8001`.

It supports:

### Generate Ticket Summary

```text
POST /documents/ticket-summary
```

### Download Ticket Summary

```text
GET /documents/ticket-summary/{ticket_id}/download
```

### Generate Weekly Report

```text
POST /documents/weekly-report
```

### Download Weekly Report

```text
GET /documents/weekly-report/{report_date}/download
```

Ticket summaries can also be triggered automatically when tickets reach applicable closed/resolved states.

---

## Example Weekly Report

```text
WEEKLY TICKET REPORT
============================================================

Period: last_7_days

Tickets received: 301475
Duplicates detected: 4

Most affected modules:
  - Platform
  - JDT
  - BIRT
  - CDT
  - PDE
```

The actual values depend on the data currently stored in the database.

---

## Running Tests

Run the test suite from the ticket service environment:

```bash
pytest
```

Tests should cover areas such as:

- Authentication
- Ticket creation
- Ticket retrieval
- Duplicate detection
- Classification
- Human review
- RBAC
- Invalid requests
- Q&A
- Agentic assistant
- Document generation

---

## Database Migrations

Database schema changes are managed using Alembic.

Apply migrations with:

```bash
alembic upgrade head
```

Create a new migration after changing SQLAlchemy models:

```bash
alembic revision --autogenerate -m "migration description"
```

---

## Docker Notes

Large raw datasets and generated embedding stores should not be copied directly into Docker images.

The project uses `.dockerignore` to prevent unnecessary files such as virtual environments, raw datasets, secrets, caches, and other large local files from being included in Docker build contexts.

Persistent data should be handled using Docker volumes or external storage where appropriate.

---

## Stopping the Application

If Docker Compose is running in the foreground, press:

```text
Ctrl + C
```

Or stop the Compose deployment with:

```bash
docker compose down
```

To start previously built containers again:

```bash
docker compose up
```

---

## Security Notes

- Never commit `.env` files.
- Never commit API keys or database passwords.
- Use strong JWT secret keys.
- Keep internal service keys private.
- Use role-based authorization for protected operations.
- Use environment-specific secrets in production.

---

## Future Improvements

Potential improvements include:

- Production secret management
- Automated CI/CD
- Monitoring and centralized logging
- More advanced entity extraction / NER
- Improved classifier training
- Model monitoring
- Dedicated production vector database deployment
- Automated database backup and recovery
- Improved agent observability
=======
# Support-Ticket-Deduplication-and-Routing-Platform
Sculptsoft evaluation  task
>>>>>>> 1e4726cbecf0a6e219299e3a3ca7012addf2ff4c
