from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class LibraryStatus(str, Enum):
    approved = "approved"
    restricted = "restricted"
    forbidden = "forbidden"


class LibraryEntry(BaseModel):
    name: str
    version: str
    status: LibraryStatus
    reason: str
    effective_date: date
    updated_by: str


class StandardEntry(BaseModel):
    id: str
    domain: str
    title: str
    description: str
    policy_version: str
    effective_date: date
    updated_by: str


class ComplianceStatus(str, Enum):
    compliant = "compliant"
    warning = "warning"
    non_compliant = "non_compliant"


class CitedChunk(BaseModel):
    chunk_id: str
    origin: str
    policy_version: Optional[str] = None


class ComplianceResult(BaseModel):
    status: ComplianceStatus
    justification: str
    cited_chunks: list[CitedChunk]
    policy_version: str
    effective_date: str
