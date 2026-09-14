"""Base classes and execution context for pluggable TCA Action Handlers."""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ActionContext:
    """Execution context provided to an action handler upon trigger invocation."""

    company_id: uuid.UUID
    target_model: str
    target_id: uuid.UUID
    trigger_type: str
    record: Any
    record_data: Dict[str, Any] = field(default_factory=dict)
    old_record_data: Optional[Dict[str, Any]] = None
    diff: Optional[Dict[str, Any]] = None
    user_id: Optional[uuid.UUID] = None
    depth: int = 1
    extra_context: Dict[str, Any] = field(default_factory=dict)


class BaseActionHandler(ABC):
    """Abstract base class for all pluggable TCA Action Handlers."""

    action_type: str
    title: str
    description: str
    config_schema: Type[BaseModel]

    @abstractmethod
    async def execute(
        self,
        db: AsyncSession,
        context: ActionContext,
        config: BaseModel,
    ) -> Dict[str, Any]:
        """Execute the business action and return result metadata for telemetry logging."""
        pass
