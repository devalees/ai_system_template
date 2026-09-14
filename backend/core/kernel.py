"""Sovereign Micro-Kernel Core Architecture & Dynamic Module Loader."""

import importlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, APIRouter

from core.manifest import ModuleManifest
from core.exceptions import (
    KernelBootException,
    CircularDependencyError,
    MissingDependencyError,
)

logger = logging.getLogger("sovereign.kernel")


class Kernel:
    """Micro-Kernel responsible for dynamic module discovery, acyclic DAG resolution, and lifecycle orchestration."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path(__file__).resolve().parent.parent
        self.modules_dir = self.root_dir / "modules"
        self.manifests: Dict[str, ModuleManifest] = {}
        self.load_order: List[str] = []
        self.routers: Dict[str, APIRouter] = {}
        self.loaded_packages: Dict[str, Any] = {}
        self._booted = False

    def register_manifest(self, manifest: ModuleManifest) -> None:
        """Register a module manifest explicitly in the kernel."""
        self.manifests[manifest.name] = manifest
        logger.info(f"Registered module manifest: '{manifest.name}' (v{manifest.version}) [{manifest.tier}]")

    def discover(self) -> Dict[str, ModuleManifest]:
        """Phase 1: Discover all module manifests under backend/modules/base and backend/modules/apps."""
        if not self.modules_dir.exists():
            logger.warning(f"Modules directory does not exist: {self.modules_dir}")
            return self.manifests

        # Search both base utilities and domain apps
        search_dirs = [
            self.modules_dir / "base",
            self.modules_dir / "apps",
        ]

        for base_path in search_dirs:
            if not base_path.exists():
                continue
            for entry in base_path.iterdir():
                if entry.is_dir() and (entry / "manifest.py").exists():
                    self._load_manifest_file(entry)

        return self.manifests

    def _load_manifest_file(self, module_dir: Path) -> None:
        """Parse and load a manifest.py file from a module directory."""
        manifest_file = module_dir / "manifest.py"
        module_name = module_dir.name

        try:
            # Dynamically import manifest module
            spec = importlib.util.spec_from_file_location(f"modules.{module_dir.parent.name}.{module_name}.manifest", manifest_file)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                manifest_obj = getattr(mod, "MANIFEST", None)
                if isinstance(manifest_obj, ModuleManifest):
                    manifest_obj.module_dir = module_dir
                    self.manifests[manifest_obj.name] = manifest_obj
                    logger.debug(f"Discovered module '{manifest_obj.name}' in {module_dir}")
                elif isinstance(manifest_obj, dict):
                    manifest = ModuleManifest(**manifest_obj, module_dir=module_dir)
                    self.manifests[manifest.name] = manifest
                    logger.debug(f"Discovered module '{manifest.name}' from dict in {module_dir}")
                else:
                    logger.warning(f"Module manifest in {manifest_file} missing valid MANIFEST instance.")
        except Exception as exc:
            logger.error(f"Failed loading manifest from {manifest_file}: {exc}", exc_info=True)
            raise KernelBootException(
                message=f"Failed loading manifest for module '{module_name}': {str(exc)}",
                details={"module_dir": str(module_dir), "error": str(exc)},
            )

    def resolve_dependencies(self) -> List[str]:
        """Perform topological sort on registered modules using Kahn's algorithm to enforce acyclic DAG."""
        # 1. Verify all dependencies exist
        for name, manifest in self.manifests.items():
            for dep in manifest.depends_on:
                if dep not in self.manifests:
                    raise MissingDependencyError(module=name, missing_dep=dep)

        # 2. Build graph and in-degree counts
        in_degree: Dict[str, int] = {name: 0 for name in self.manifests}
        adj_list: Dict[str, List[str]] = {name: [] for name in self.manifests}

        for name, manifest in self.manifests.items():
            for dep in manifest.depends_on:
                adj_list[dep].append(name)
                in_degree[name] += 1

        # 3. Kahn's Algorithm
        queue = [name for name, deg in in_degree.items() if deg == 0]
        sorted_order: List[str] = []

        while queue:
            node = queue.pop(0)
            sorted_order.append(node)

            for neighbor in adj_list[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 4. Check for cycles
        if len(sorted_order) != len(self.manifests):
            remaining = [name for name, deg in in_degree.items() if deg > 0]
            raise CircularDependencyError(cycle=remaining)

        self.load_order = sorted_order
        logger.info(f"Resolved module DAG load order ({len(sorted_order)} modules): {' -> '.join(sorted_order)}")
        return self.load_order

    def load(self, app: Optional[FastAPI] = None) -> None:
        """Phase 2: Import module packages, initialize models, and mount routes in topological order."""
        if not self.load_order:
            self.resolve_dependencies()

        for module_name in self.load_order:
            manifest = self.manifests[module_name]
            if not manifest.auto_install:
                logger.info(f"Skipping module '{module_name}' (auto_install=False)")
                continue

            try:
                tier_dir = "base" if manifest.tier == "base" else "apps"
                pkg_prefix = f"modules.{tier_dir}.{manifest.name}"

                # Import module routes if exists
                if manifest.module_dir and (manifest.module_dir / "routes.py").exists():
                    routes_mod = importlib.import_module(f"{pkg_prefix}.routes")
                    router = getattr(routes_mod, "router", None)
                    if isinstance(router, APIRouter):
                        self.routers[module_name] = router
                        if app:
                            prefix = f"/api/v1/{module_name}"
                            app.include_router(router, prefix=prefix, tags=[manifest.title])
                            logger.info(f"Mounted API router for '{module_name}' at '{prefix}'")

                # Import module models if exists
                if manifest.module_dir and (manifest.module_dir / "models.py").exists():
                    models_mod = importlib.import_module(f"{pkg_prefix}.models")

                self.loaded_packages[module_name] = manifest
            except Exception as exc:
                logger.error(f"Failed loading module package '{module_name}': {exc}", exc_info=True)
                raise KernelBootException(
                    message=f"Failed loading package for module '{module_name}': {str(exc)}",
                    details={"module": module_name, "error": str(exc)},
                )

    async def migrate(self) -> None:
        """Phase 3: Execute programmatic module schema migrations."""
        logger.info("Executing Kernel Phase 3: Module Schema Migrations (Alembic / DDL)")
        # In later stages, alembic migrations will execute here in topological order.

    async def bootstrap(self, db_session: Optional[Any] = None) -> None:
        """Phase 4: Run module bootstrap hooks and automated capability harvesting."""
        logger.info("Executing Kernel Phase 4: Module Bootstrap Hooks")
        try:
            from modules.base.identity_rbac.harvester import harvest_model_permissions
            from core.database import AsyncSessionLocal
            if db_session:
                await harvest_model_permissions(db_session)
            else:
                async with AsyncSessionLocal() as session:
                    await harvest_model_permissions(session)
        except Exception as exc:
            logger.warning(f"Permission harvesting deferred or skipped during bootstrap: {exc}")

        self._booted = True

    async def boot(self, app: Optional[FastAPI] = None) -> None:
        """Execute full 4-Phase Kernel Boot Sequence."""
        logger.info("Initiating Sovereign Micro-Kernel 4-Phase Boot Sequence...")
        self.discover()
        self.resolve_dependencies()
        self.load(app)
        await self.migrate()
        await self.bootstrap()
        logger.info("Sovereign Micro-Kernel Boot Sequence successfully completed.")

    def get_module(self, name: str) -> Optional[ModuleManifest]:
        """Retrieve a registered module manifest by name."""
        return self.manifests.get(name)

    def list_modules(self) -> List[Dict[str, Any]]:
        """Return a structured summary of all registered modules."""
        return [
            {
                "name": m.name,
                "title": m.title,
                "version": m.version,
                "tier": m.tier,
                "depends_on": m.depends_on,
                "ai_enabled": m.ai_enabled,
                "auto_install": m.auto_install,
            }
            for m in self.manifests.values()
        ]

    def get_ai_enabled_modules(self) -> List[ModuleManifest]:
        """Filter modules that declare ai_enabled=True for dynamic FastMCP tool reflection."""
        return [m for m in self.manifests.values() if m.ai_enabled]


# Global Kernel instance
kernel = Kernel()
