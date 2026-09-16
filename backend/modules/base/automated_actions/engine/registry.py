"""Central registry for discovering, validating, and dispatching TCA Action Handlers."""

import logging
from typing import Dict, Any, Optional, List, Type
from modules.base.automated_actions.handlers.base import BaseActionHandler
from modules.base.automated_actions.handlers.email_handler import SendEmailActionHandler
from modules.base.automated_actions.handlers.notification_handler import SendNotificationActionHandler
from modules.base.automated_actions.handlers.chatter_handler import PostChatterActionHandler
from modules.base.automated_actions.handlers.record_handler import (
    UpdateRecordActionHandler,
    CreateRecordActionHandler,
)
from modules.base.automated_actions.handlers.webhook_handler import InvokeWebhookActionHandler
from modules.base.automated_actions.handlers.ai_handler import AIAgentActionHandler

logger = logging.getLogger("sovereign.automated_actions.registry")


class ActionRegistry:
    """Singleton registry coordinating available action handlers across the platform."""

    def __init__(self):
        self._handlers: Dict[str, BaseActionHandler] = {}
        self._register_built_in_handlers()

    def _register_built_in_handlers(self) -> None:
        """Register default core action handlers provided by base modules."""
        built_in = [
            SendEmailActionHandler(),
            SendNotificationActionHandler(),
            PostChatterActionHandler(),
            UpdateRecordActionHandler(),
            CreateRecordActionHandler(),
            InvokeWebhookActionHandler(),
            AIAgentActionHandler(),
        ]
        for handler in built_in:
            self.register(handler)


    def register(self, handler: BaseActionHandler) -> None:
        """Register an action handler instance."""
        if handler.action_type in self._handlers:
            logger.warning(f"Overwriting existing action handler for '{handler.action_type}'")
        self._handlers[handler.action_type] = handler
        logger.debug(f"Registered TCA action handler: '{handler.action_type}' ({handler.title})")

    def get(self, action_type: str) -> Optional[BaseActionHandler]:
        """Retrieve action handler by unique action_type identifier."""
        return self._handlers.get(action_type)

    def list_handlers(self) -> List[BaseActionHandler]:
        """List all active action handler instances."""
        return list(self._handlers.values())

    def get_metadata(self) -> List[Dict[str, Any]]:
        """Return self-describing metadata and JSON Schemas for all registered action handlers."""
        metadata = []
        for handler in self._handlers.values():
            meta = {
                "action_type": handler.action_type,
                "title": handler.title,
                "description": handler.description,
                "config_schema": handler.config_schema.model_json_schema() if handler.config_schema else {},
            }
            metadata.append(meta)
        return metadata


# Global singleton instance
action_registry = ActionRegistry()
