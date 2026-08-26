from sqlalchemy.orm import Session
from src.db.models import User
from src.core.security import hash_password, verify_password

VALID_ROLES = {"admin", "support_engineer", "reporter"}


def create_user(db: Session, username, email, password, role="reporter"):
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")

    existing = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing:
        raise ValueError("Username or email already registered")

    new_user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"user_id": new_user.id, "username": username, "email": email, "role": role}


def authenticate_user(db: Session, username, password):
    user = db.query(User).filter(User.username == username).first()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return {"user_id": user.id, "username": user.username, "role": user.role}