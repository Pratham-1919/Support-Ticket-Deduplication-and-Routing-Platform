from pydantic import BaseModel


class ModuleRequest(BaseModel):
    """Used by POST /modules/ and PUT /modules/{module_id}."""
    name: str