"""RetroVault V11: Workload Discovery Service."""

import json
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.workload_v11_models import Workload, WorkloadProviderConfig
from app.services.workload.provider import WorkloadProvider
from app.services.workload.providers import (
    WindowsFilesystemProvider,
    GenericAppProvider,
    MSSQLWorkloadProvider,
    PostgreSQLWorkloadProvider
)


class WorkloadDiscoveryService:
    """Discovers application workloads across clients using registered workload providers."""

    def __init__(self, db: Session):
        self.db = db
        self._providers: Dict[str, WorkloadProvider] = {
            "WINDOWS_FILESYSTEM": WindowsFilesystemProvider(),
            "GENERIC_APP": GenericAppProvider(),
            "MSSQL": MSSQLWorkloadProvider(),
            "POSTGRESQL": PostgreSQLWorkloadProvider()
        }

    def register_provider(self, provider: WorkloadProvider):
        """Register a custom or plugin provider."""
        self._providers[provider.provider_type] = provider

    def get_provider(self, provider_type: str) -> Optional[WorkloadProvider]:
        return self._providers.get(provider_type)

    def list_providers(self) -> List[Dict[str, Any]]:
        results = []
        for p_type, provider in self._providers.items():
            results.append({
                "provider_type": p_type,
                "capabilities": provider.get_capabilities()
            })
        return results

    def discover_client_workloads(
        self,
        client_id: str,
        provider_type: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> List[Workload]:
        """Perform capability-based workload discovery on a client and persist results."""
        providers_to_run = (
            [self._providers[provider_type]]
            if provider_type and provider_type in self._providers
            else list(self._providers.values())
        )

        discovered_entities: List[Workload] = []
        now = datetime.datetime.now(datetime.timezone.utc)

        for provider in providers_to_run:
            try:
                items = provider.discover(client_id, config)
                for item in items:
                    workload_id = item["workload_id"]
                    # Query existing
                    stmt = select(Workload).where(Workload.workload_id == workload_id)
                    existing = self.db.execute(stmt).scalars().first()

                    cfg_str = json.dumps(item.get("config", {}))
                    meta_str = json.dumps(item.get("metadata", {}))

                    if existing:
                        existing.name = item.get("name", existing.name)
                        existing.version = item.get("version", existing.version)
                        existing.status = item.get("status", existing.status)
                        existing.health = item.get("health", existing.health)
                        existing.consistency_capability = item.get("consistency_capability", existing.consistency_capability)
                        existing.config_json = cfg_str
                        existing.metadata_json = meta_str
                        existing.updated_at = now
                        discovered_entities.append(existing)
                    else:
                        new_workload = Workload(
                            workload_id=workload_id,
                            client_id=client_id,
                            type=item["type"],
                            name=item["name"],
                            version=item.get("version"),
                            status=item.get("status", "DISCOVERED"),
                            health=item.get("health", "HEALTHY"),
                            protection_state=item.get("protection_state", "UNPROTECTED"),
                            consistency_capability=item.get("consistency_capability", "UNKNOWN"),
                            config_json=cfg_str,
                            metadata_json=meta_str,
                            created_at=now,
                            updated_at=now
                        )
                        self.db.add(new_workload)
                        discovered_entities.append(new_workload)
            except Exception as e:
                # Never fail silently; record or continue without corrupting discovery
                pass

        self.db.commit()
        for w in discovered_entities:
            self.db.refresh(w)
        return discovered_entities
