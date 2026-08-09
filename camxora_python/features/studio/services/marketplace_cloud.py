"""P7 stubs — Marketplace + cloud render contracts (no network deploy)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketplaceListing:
    id: str
    title: str
    kind: str  # asset | plugin | template
    price_cents: int = 0
    license: str = "personal"
    rating: float = 0.0


@dataclass
class CloudRenderJob:
    id: str
    status: str  # queued | running | done | failed
    resolution: str = "1920x1080"
    progress: float = 0.0
    error: str | None = None


@dataclass
class MarketplaceCloudService:
    """Local in-memory stub for future marketplace/cloud integration."""

    listings: list[MarketplaceListing] = field(default_factory=list)
    jobs: dict[str, CloudRenderJob] = field(default_factory=dict)

    def list_marketplace(self) -> list[MarketplaceListing]:
        if not self.listings:
            self.listings = [
                MarketplaceListing("tpl.festival", "Festival Starter", "template", 0, "free", 4.6),
                MarketplaceListing("plug.neon", "Neon Pack", "plugin", 999, "commercial", 4.2),
            ]
        return list(self.listings)

    def enqueue_cloud_render(self, *, project_id: str, resolution: str = "1920x1080") -> CloudRenderJob:
        job_id = f"job.{project_id[:8]}.{len(self.jobs) + 1}"
        job = CloudRenderJob(id=job_id, status="queued", resolution=resolution, progress=0.0)
        self.jobs[job_id] = job
        # Stub: immediately mark running then done for local demos.
        job.status = "done"
        job.progress = 1.0
        return job

    def enterprise_roles(self) -> dict[str, Any]:
        return {
            "roles": ["owner", "editor", "viewer"],
            "note": "RBAC reserved for enterprise phase — local stub only.",
        }
