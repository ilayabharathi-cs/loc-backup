"""Instant Virtual Recovery module for RetroVault V12."""

from app.services.v12.virtual_recovery.provider_base import (
    VirtualRecoveryProviderBase,
    VirtualRecoveryError,
    SessionStateError,
    ObjectUnavailableError,
    IntegrityVerificationError,
    MountError,
    UnmountError
)
from app.services.v12.virtual_recovery.cache import BoundedLruCache, get_ivr_cache
from app.services.v12.virtual_recovery.read_engine import ReadOnDemandEngine
from app.services.v12.virtual_recovery.hydrator import BackgroundHydrator
from app.services.v12.virtual_recovery.local_provider import LocalVirtualRecoveryProvider
from app.services.v12.virtual_recovery.session_manager import VirtualRecoverySessionManager

__all__ = [
    "VirtualRecoveryProviderBase",
    "VirtualRecoveryError",
    "SessionStateError",
    "ObjectUnavailableError",
    "IntegrityVerificationError",
    "MountError",
    "UnmountError",
    "BoundedLruCache",
    "get_ivr_cache",
    "ReadOnDemandEngine",
    "BackgroundHydrator",
    "LocalVirtualRecoveryProvider",
    "VirtualRecoverySessionManager"
]
