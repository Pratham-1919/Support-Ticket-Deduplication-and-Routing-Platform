# src/ml/classification_service.py
import joblib
from pathlib import Path
from src.ml.ticket_text import build_ticket_text

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"

_module_vectorizer = joblib.load(MODEL_DIR / "module_vectorizer.joblib")
_module_clf = joblib.load(MODEL_DIR / "module_classifier.joblib")
_severity_vectorizer = joblib.load(MODEL_DIR / "severity_vectorizer.joblib")
_severity_clf = joblib.load(MODEL_DIR / "severity_classifier.joblib")

def predict_module(title, description):
    text = build_ticket_text(title, description)
    X = _module_vectorizer.transform([text])
    probs = _module_clf.predict_proba(X)[0]
    best_idx = probs.argmax()
    return {
        "predicted_module": _module_clf.classes_[best_idx],
        "confidence": float(probs[best_idx]),
    }

def predict_severity(title, description):
    text = build_ticket_text(title, description)
    X = _severity_vectorizer.transform([text])
    probs = _severity_clf.predict_proba(X)[0]
    best_idx = probs.argmax()
    return {
        "predicted_severity": _severity_clf.classes_[best_idx],
        "confidence": float(probs[best_idx]),
    }