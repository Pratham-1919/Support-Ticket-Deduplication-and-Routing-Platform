# src/ml/train_classifier.py
import joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from src.db.connection import get_connection
from src.ml.ticket_text import build_ticket_text

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_DIR.mkdir(exist_ok=True)

def load_training_data():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.title, t.description, m.name AS module, t.severity, t.ticket_type
        FROM tickets t JOIN modules m ON t.module_id = m.id
        WHERE t.title IS NOT NULL AND t.description IS NOT NULL
    """)
    rows = cur.fetchall()
    conn.close()
    texts = [build_ticket_text(r[0], r[1]) for r in rows]
    modules = [r[2] for r in rows]
    severities = [r[3] for r in rows]
    ticket_types = [r[4] for r in rows]
    return texts, modules, severities, ticket_types


def train_and_save(texts, labels, label_name):
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    vectorizer = TfidfVectorizer(max_features=20000, ngram_range=(1, 2))
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    clf = LogisticRegression(max_iter=1000, class_weight="balanced")
    clf.fit(X_train_vec, y_train)

    print(f"\n--- {label_name} classifier ---")
    print(classification_report(y_test, clf.predict(X_test_vec)))

    joblib.dump(vectorizer, MODEL_DIR / f"{label_name}_vectorizer.joblib")
    joblib.dump(clf, MODEL_DIR / f"{label_name}_classifier.joblib")

if __name__ == "__main__":
    texts, modules, severities, ticket_types = load_training_data()
    train_and_save(texts, modules, "module")

    # Severity: only meaningful for actual bug reports -- enhancement is
    # already fully determined by ticket_type, so including it here just
    # inflates accuracy with an easy, redundant class.
    bug_texts = [t for t, tt in zip(texts, ticket_types) if tt == "bug_report"]
    bug_severities = [s for s, tt in zip(severities, ticket_types) if tt == "bug_report"]
    train_and_save(bug_texts, bug_severities, "severity")