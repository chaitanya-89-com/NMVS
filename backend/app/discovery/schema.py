# schema.py — fixed to match actual return shape
from pydantic import BaseModel, IPvAnyAddress

class DiscoveryResult(BaseModel):
    ip: IPvAnyAddress
    status: str