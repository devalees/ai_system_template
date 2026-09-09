"""
Topological Dependency Resolution Engine for Modular Apps.

Calculates the exact, linear installation order for modular application
packages using directed acyclic graph (DAG) topological sorting.
Detects cycles and missing dependencies before running schema migrations.
"""

from collections import defaultdict, deque
from typing import Dict, Iterable, List, Optional, Set

from apps.meta_engine.models import SystemModule


class DependencyResolutionError(Exception):
    """Base exception for modular dependency resolution failures."""
    pass


class MissingDependencyError(DependencyResolutionError):
    """Raised when a required module dependency is not available in the registry."""
    pass


class CyclicDependencyError(DependencyResolutionError):
    """Raised when a circular dependency loop is detected in the dependency graph."""
    pass


class DependencyResolver:
    """
    Computes deterministic topological installation sequences for modular applications.
    """

    @classmethod
    def get_dependency_map(cls) -> Dict[str, List[str]]:
        """
        Build a dictionary mapping every known app_id to its list of dependency app_ids.
        Reads from registered SystemModule instances in the database.
        """
        dep_map: Dict[str, List[str]] = {}
        for mod in SystemModule.objects.all():
            dep_map[mod.app_id] = list(mod.dependencies or [])
        return dep_map

    @classmethod
    def resolve_install_order(
        cls,
        target_app_ids: Iterable[str],
        dependency_map: Optional[Dict[str, List[str]]] = None,
        installed_app_ids: Optional[Set[str]] = None,
    ) -> List[str]:
        """
        Compute the topological installation order for target_app_ids.

        :param target_app_ids: List/Set of app_id strings requested for installation.
        :param dependency_map: Optional mapping of {app_id: [dependency_ids]}.
                               If omitted, dynamically fetched from the database.
        :param installed_app_ids: Optional set of already installed app_ids to exclude
                                  from the installation execution list.
        :return: Ordered list of app_ids to install, from base prerequisites to dependents.
        """
        if dependency_map is None:
            dependency_map = cls.get_dependency_map()

        if installed_app_ids is None:
            installed_app_ids = set(
                SystemModule.objects.filter(status="installed").values_list("app_id", flat=True)
            )

        # 1. Discover full transitive closure of dependencies needed
        required_nodes: Set[str] = set()
        queue = deque(target_app_ids)

        while queue:
            current = queue.popleft()
            if current in required_nodes:
                continue
            required_nodes.add(current)

            deps = dependency_map.get(current)
            if deps is None:
                # Target or dependency not found in available modules
                raise MissingDependencyError(
                    f"Required module '{current}' was not found in the application registry."
                )

            for dep in deps:
                if dep not in required_nodes:
                    queue.append(dep)

        # 2. Filter out already installed modules (unless explicitly in target)
        nodes_to_install = {n for n in required_nodes if n not in installed_app_ids}

        if not nodes_to_install:
            return []

        # 3. Build DAG for nodes_to_install
        # graph: prerequisite -> list of dependent nodes that need prerequisite installed first
        # in_degree: count of prerequisites each node is waiting on
        graph: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = {node: 0 for node in nodes_to_install}

        for node in nodes_to_install:
            deps = dependency_map.get(node, [])
            for dep in deps:
                if dep in nodes_to_install:
                    # 'dep' must be installed before 'node'
                    graph[dep].append(node)
                    in_degree[node] += 1

        # 4. Kahn's algorithm for topological sorting
        # Start with nodes that have in_degree == 0 (no uninstalled prerequisites)
        ready_queue = deque(sorted([node for node, degree in in_degree.items() if degree == 0]))
        ordered_install_list: List[str] = []

        while ready_queue:
            prereq = ready_queue.popleft()
            ordered_install_list.append(prereq)

            for dependent in graph[prereq]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready_queue.append(dependent)

        # 5. Cycle check
        if len(ordered_install_list) != len(nodes_to_install):
            unresolved = [node for node, degree in in_degree.items() if degree > 0]
            raise CyclicDependencyError(
                f"Circular dependency loop detected involving modules: {', '.join(sorted(unresolved))}"
            )

        return ordered_install_list
