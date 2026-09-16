"""Composite Addresses & Geographic Locations package."""

from modules.base.addresses.manifest import MANIFEST
from modules.base.addresses.models import Address
from modules.base.addresses.service import AddressService, AddressNotFoundException

__all__ = [
    "MANIFEST",
    "Address",
    "AddressService",
    "AddressNotFoundException",
]
