"""Universal Sequence & Legal Auto-Numbering Engine Module."""

from modules.base.sequences.models import Sequence
from modules.base.sequences.service import SequenceService

__all__ = ["Sequence", "SequenceService"]
