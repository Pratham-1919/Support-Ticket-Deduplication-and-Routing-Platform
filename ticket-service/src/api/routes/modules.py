from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.session import get_db
from src.db.models import Module, Ticket
from src.core.security import require_role, get_current_user
from src.api.schemas.module import ModuleRequest

router = APIRouter(prefix="/modules", tags=["modules"])



# ============================================================
# CREATE MODULE -- admin only
# ============================================================

@router.post("/")
def create_module(
    payload: ModuleRequest,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Module name cannot be empty")

    existing = db.query(Module).filter(Module.name.ilike(name)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Module '{name}' already exists")

    new_module = Module(name=name)
    db.add(new_module)
    db.commit()
    db.refresh(new_module)

    return {"id": new_module.id, "name": new_module.name, "created_at": new_module.created_at}


# ============================================================
# LIST MODULES -- authenticated users
# ============================================================

@router.get("/")
def list_modules(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    modules = db.query(Module).order_by(Module.id).all()
    return [{"id": m.id, "name": m.name, "created_at": m.created_at} for m in modules]


# ============================================================
# GET SINGLE MODULE -- authenticated users
# ============================================================

@router.get("/{module_id}")
def get_module(
    module_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    module = db.query(Module).filter(Module.id == module_id).first()
    if module is None:
        raise HTTPException(status_code=404, detail="module not found")

    return {"id": module.id, "name": module.name, "created_at": module.created_at}


# ============================================================
# UPDATE MODULE -- admin only
# ============================================================

@router.put("/{module_id}")
def update_module(
    module_id: int,
    payload: ModuleRequest,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Module name cannot be empty")

    module = db.query(Module).filter(Module.id == module_id).first()
    if module is None:
        raise HTTPException(status_code=404, detail="module not found")

    duplicate = (
        db.query(Module)
        .filter(Module.name.ilike(name), Module.id != module_id)
        .first()
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail=f"Module '{name}' already exists")

    module.name = name
    db.commit()
    db.refresh(module)

    return {"id": module.id, "name": module.name, "created_at": module.created_at}


# ============================================================
# DELETE MODULE -- admin only
# ============================================================

@router.delete("/{module_id}")
def delete_module(
    module_id: int,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    module = db.query(Module).filter(Module.id == module_id).first()
    if module is None:
        raise HTTPException(status_code=404, detail="module not found")

    ticket_count = db.query(func.count(Ticket.id)).filter(Ticket.module_id == module_id).scalar()
    if ticket_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete module '{module.name}' because {ticket_count} ticket(s) are associated with it",
        )

    module_name = module.name
    db.delete(module)
    db.commit()

    return {"module_id": module_id, "name": module_name, "deleted": True}