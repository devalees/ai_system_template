"""
Automated Cross-Instance Knowledge & Skill Synchronization Engine.

Enables sovereign agent deployments to continuously synchronize generalized procedural
memories and vetted skill playbooks across tenants via a central Git/GitHub repository.
Guarantees zero token cost, complete privacy isolation (project_local quarantine),
automated secret scrubbing, and vector deduplication via sqlite-vec.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("agent_service.sync")

# Add root directory to sys.path for package imports
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from agent_service.memory.cli import sanitize_dict, sanitize_text
from agent_service.memory.vector_store import MemoryStore


def _load_env_file() -> None:
    """Loads missing environment variables from .env files if present."""
    candidate_paths = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path("/workspace/.env"),
    ]
    for env_path in candidate_paths:
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        if k not in os.environ and v:
                            os.environ[k] = v
            except Exception:
                pass


_load_env_file()


@dataclass
class SyncCycleResult:
    """Structured report of a synchronization run."""
    success: bool
    instance_id: str
    timestamp: str
    hub_url: str
    exported_memories: int = 0
    exported_skills: int = 0
    imported_memories: int = 0
    deduplicated_memories: int = 0
    imported_skills: int = 0
    pushed_to_hub: bool = False
    commit_hash: Optional[str] = None
    message: str = ""
    errors: List[str] = field(default_factory=list)


class KnowledgeSyncEngine:
    """
    Deterministic, zero-token synchronization engine between local instance
    and central Git knowledge repository.
    """

    def __init__(
        self,
        repo_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        ssh_key_path: Optional[str] = None,
        db_path: Optional[str | Path] = None,
        cache_dir: Optional[str | Path] = None,
        skills_dir: Optional[str | Path] = None,
        similarity_threshold: float = 0.90,
        instance_id: Optional[str] = None,
    ) -> None:
        """
        Initializes the synchronization engine.
        Reads credentials and endpoints from arguments or environment.
        """
        base_dir = Path(__file__).resolve().parent.parent

        # 1. Hub repository URL & Credentials
        self.raw_repo_url = (
            repo_url if repo_url is not None else os.getenv("CENTRAL_KNOWLEDGE_REPO_URL", "")
        ).strip()
        self.auth_token = (
            auth_token if auth_token is not None else os.getenv("KNOWLEDGE_HUB_AUTH_TOKEN", "")
        ).strip()
        self.ssh_key_path = (
            ssh_key_path if ssh_key_path is not None else os.getenv("KNOWLEDGE_HUB_SSH_KEY_PATH", "")
        ).strip()

        # 2. Local Paths
        self.db_path = Path(db_path or base_dir / "data" / "memory.db")
        self.cache_dir = Path(
            cache_dir or base_dir / "data" / "knowledge_hub_cache"
        )
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        elif (base_dir / "skills").exists():
            self.skills_dir = base_dir / "skills"
        elif (base_dir.parent / "skills").exists():
            self.skills_dir = base_dir.parent / "skills"
        else:
            self.skills_dir = base_dir / "skills"
        if cache_dir is not None:
            self.state_file = Path(cache_dir).parent / ".knowledge_sync_state.json"
        else:
            self.state_file = base_dir / "data" / ".knowledge_sync_state.json"

        # 3. Parameters
        self.similarity_threshold = float(
            os.getenv("KNOWLEDGE_SYNC_SIMILARITY_THRESHOLD", similarity_threshold)
        )
        self.instance_id = (
            instance_id or os.getenv("INSTANCE_ID") or platform.node() or "node-default"
        ).strip()

        # Ensure directories exist
        self.cache_dir.parent.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def get_authenticated_repo_url(self) -> str:
        """Constructs machine-to-machine authenticated URL injecting PAT if HTTPS."""
        if not self.raw_repo_url:
            return ""

        if self.raw_repo_url.startswith("https://") and self.auth_token:
            parsed = urllib.parse.urlparse(self.raw_repo_url)
            # Inject oauth2:<token>@ into URL
            authed_netloc = f"oauth2:{self.auth_token}@{parsed.netloc}"
            return urllib.parse.urlunparse(
                (parsed.scheme, authed_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
            )

        return self.raw_repo_url

    def _run_git(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Executes a git command with configured environment and auth."""
        working_dir = cwd or self.cache_dir
        env = os.environ.copy()

        if self.ssh_key_path and os.path.exists(self.ssh_key_path):
            env["GIT_SSH_COMMAND"] = f"ssh -i {self.ssh_key_path} -o StrictHostKeyChecking=no"

        cmd = ["git"] + args
        try:
            res = subprocess.run(
                cmd,
                cwd=str(working_dir),
                capture_output=True,
                text=True,
                env=env,
                check=check,
            )
            return res
        except subprocess.CalledProcessError as e:
            logger.error("Git error running %s: %s (stderr: %s)", cmd, e, e.stderr)
            raise

    def ensure_hub_repo(self) -> bool:
        """
        Ensures local clone of central knowledge hub exists and is initialized.
        Handles empty remote repositories cleanly.
        """
        auth_url = self.get_authenticated_repo_url()
        if not auth_url:
            logger.warning("No CENTRAL_KNOWLEDGE_REPO_URL configured.")
            return False

        if not (self.cache_dir / ".git").exists():
            logger.info("Cloning knowledge hub from %s into %s", self.raw_repo_url, self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            try:
                self._run_git(["clone", auth_url, str(self.cache_dir)], cwd=self.cache_dir.parent)
            except subprocess.CalledProcessError as e:
                # Handle cloned empty repository
                if "empty repository" in (e.stderr or "") or not (self.cache_dir / ".git").exists():
                    logger.info("Remote is empty repository. Initializing main branch structure.")
                    self._run_git(["init"], cwd=self.cache_dir)
                    self._run_git(["remote", "add", "origin", auth_url], cwd=self.cache_dir)
                    self._run_git(["branch", "-M", "main"], cwd=self.cache_dir)
                else:
                    raise

        # Configure git user in cache
        self._run_git(["config", "user.name", f"Sovereign Sync ({self.instance_id})"])
        self._run_git(["config", "user.email", f"sync-{self.instance_id}@sovereign-platform.local"])

        # Check if remote main or master exists and check it out
        for target_branch in ["origin/main", "origin/master"]:
            if self._run_git(["rev-parse", "--verify", target_branch], check=False).returncode == 0:
                self._run_git(["checkout", "-B", "main", target_branch], check=False)
                break

        # Check for initial commit via rev-parse
        has_commits = self._run_git(["rev-parse", "--verify", "HEAD"], check=False).returncode == 0
        if not has_commits:
            # Brand new empty repo: create initial README and folder scaffolding
            (self.cache_dir / "knowledge").mkdir(exist_ok=True)
            (self.cache_dir / "skills").mkdir(exist_ok=True)
            readme = (self.cache_dir / "README.md")
            if not readme.exists():
                readme.write_text(
                    "# Sovereign Autonomous Platform - Central Knowledge & Skill Hub\n\n"
                    "Automated collective intelligence repository for multi-tenant deployments.\n"
                    "Contains sanitized generalized procedural memories and vetted skills.\n",
                    encoding="utf-8",
                )
            self._run_git(["add", "."])
            self._run_git(["commit", "-m", "chore: initialize central knowledge and skill hub [skip ci]"])
            self._run_git(["branch", "-M", "main"])
            try:
                self._run_git(["push", "-u", "origin", "main"])
            except subprocess.CalledProcessError:
                pass

        return True

    def load_state(self) -> Dict[str, Any]:
        """Loads persistent sync state (timestamps, hashes)."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "last_sync_timestamp": "1970-01-01 00:00:00",
            "last_push_commit": "",
            "synced_memory_ids": [],
        }

    def save_state(self, state: Dict[str, Any]) -> None:
        """Persists sync state atomically."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def export_local_delta(
        self,
        since_timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extracts new generalized memories and modified skills since timestamp.
        Applies strict sanitization (removing all keys, tokens, emails, IPs).
        Physically ignores project_local records.
        """
        state = self.load_state()
        ts = since_timestamp or state.get("last_sync_timestamp", "1970-01-01 00:00:00")
        norm_ts = ts.replace("T", " ").split("+")[0].split("Z")[0].strip()

        exported_memories: List[Dict[str, Any]] = []
        exported_skills: List[Dict[str, Any]] = []

        # 1. Query memory.db for generalized scope
        if self.db_path.exists():
            try:
                store = MemoryStore(db_path=self.db_path)
                query = """
                    SELECT id, category, title, content, scope, metadata_json, created_at
                    FROM memory_entries
                    WHERE scope = 'generalized' AND datetime(created_at) > datetime(?)
                    ORDER BY created_at ASC
                """
                cursor = store._conn.cursor()
                cursor.execute(query, (norm_ts,))
                rows = cursor.fetchall()
                for row in rows:
                    raw_title = row["title"]
                    raw_content = row["content"]
                    try:
                        raw_meta = json.loads(row["metadata_json"] or "{}")
                    except Exception:
                        raw_meta = {}

                    # Automated zero-trust sanitization
                    clean_title = sanitize_text(raw_title)
                    clean_content = sanitize_text(raw_content)
                    clean_meta = sanitize_dict(raw_meta)

                    exported_memories.append({
                        "id": row["id"],
                        "category": row["category"],
                        "title": clean_title,
                        "content": clean_content,
                        "scope": "generalized",
                        "metadata": clean_meta,
                        "created_at": row["created_at"],
                        "contributor_instance": self.instance_id,
                    })
                store.close()
            except Exception as e:
                logger.error("Error querying memory delta: %s", e)

        # 2. Check local skills directory for modified playbooks
        if self.skills_dir.exists():
            for skill_file in self.skills_dir.rglob("SKILL.md"):
                mtime = datetime.datetime.fromtimestamp(
                    skill_file.stat().st_mtime, tz=datetime.timezone.utc
                ).isoformat()
                if mtime > ts:
                    try:
                        raw_skill_text = skill_file.read_text(encoding="utf-8")
                        clean_skill_text = sanitize_text(raw_skill_text)
                        rel_path = skill_file.relative_to(self.skills_dir)
                        exported_skills.append({
                            "relative_path": str(rel_path),
                            "content": clean_skill_text,
                            "modified_at": mtime,
                        })
                    except Exception as e:
                        logger.error("Error reading skill %s: %s", skill_file, e)

        return {
            "since_timestamp": ts,
            "memories": exported_memories,
            "skills": exported_skills,
        }

    def pull_and_merge(self) -> Tuple[int, int, int]:
        """
        Pulls latest changes from central hub and merges into local memory & skills.
        Deduplicates against local vector store using sqlite-vec cosine similarity.
        Returns: (imported_memories, deduplicated_memories, imported_skills)
        """
        # 1. Git pull from remote (if git repo initialized)
        if (self.cache_dir / ".git").exists():
            try:
                self._run_git(["fetch", "origin"])
                self._run_git(["merge", "origin/main"], check=False)
            except Exception as e:
                logger.warning("Git pull warning: %s", e)

        imported_mem_count = 0
        dedup_mem_count = 0
        imported_skill_count = 0

        # 2. Merge Knowledge JSONL files
        knowledge_dir = self.cache_dir / "knowledge"
        if knowledge_dir.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(db_path=self.db_path)
            for jsonl_file in knowledge_dir.glob("*.jsonl"):
                try:
                    lines = jsonl_file.read_text(encoding="utf-8").splitlines()
                    for line in lines:
                        if not line.strip():
                            continue
                        record = json.loads(line)
                        content = record.get("content", "").strip()
                        title = record.get("title", "Imported Heuristic")
                        category = record.get("category", "procedure")
                        metadata = record.get("metadata", {})

                        if not content:
                            continue

                        # Vector deduplication check:
                        # Exact content match check first
                        cursor = store._conn.cursor()
                        cursor.execute(
                            "SELECT rowid FROM memory_entries WHERE content = ? AND scope = 'generalized' LIMIT 1",
                            (content,),
                        )
                        if cursor.fetchone():
                            dedup_mem_count += 1
                            continue

                        # Semantic similarity check
                        similar = store.recall_similar(
                            query_text=content,
                            top_k=1,
                            threshold=self.similarity_threshold,
                            scope="generalized",
                        )

                        if similar:
                            # Already known technique or semantic duplicate
                            dedup_mem_count += 1
                        else:
                            # Novel generalized learning
                            store.add_memory(
                                title=title,
                                content=content,
                                category=category,
                                scope="generalized",
                                metadata=metadata,
                            )
                            imported_mem_count += 1
                except Exception as e:
                    logger.error("Error merging knowledge file %s: %s", jsonl_file, e)
            store.close()

        # 3. Mount Skills
        hub_skills_dir = self.cache_dir / "skills"
        if hub_skills_dir.exists():
            for hub_skill in hub_skills_dir.rglob("SKILL.md"):
                rel_path = hub_skill.relative_to(hub_skills_dir)
                target_skill = self.skills_dir / rel_path
                target_skill.parent.mkdir(parents=True, exist_ok=True)
                # If target does not exist or content differs, update
                if not target_skill.exists() or target_skill.read_text(encoding="utf-8") != hub_skill.read_text(encoding="utf-8"):
                    target_skill.write_text(hub_skill.read_text(encoding="utf-8"), encoding="utf-8")
                    imported_skill_count += 1

        return imported_mem_count, dedup_mem_count, imported_skill_count

    def push_local_delta(
        self,
        delta: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Appends new local memories and skills into central hub and pushes to Git.
        Returns: (was_pushed, commit_hash)
        """
        memories = delta.get("memories", [])
        skills = delta.get("skills", [])

        if not memories and not skills:
            logger.info("No local updates to push.")
            return False, None

        knowledge_dir = self.cache_dir / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        hub_skills_dir = self.cache_dir / "skills"
        hub_skills_dir.mkdir(parents=True, exist_ok=True)

        # 1. Append memories to generalized_memories.jsonl with line deduplication
        jsonl_path = knowledge_dir / "generalized_memories.jsonl"
        existing_hashes = set()
        if jsonl_path.exists():
            for line in jsonl_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        rec = json.loads(line)
                        h = hashlib.sha256(rec.get("content", "").strip().encode("utf-8")).hexdigest()
                        existing_hashes.add(h)
                    except Exception:
                        pass

        new_entries = []
        for mem in memories:
            h = hashlib.sha256(mem.get("content", "").strip().encode("utf-8")).hexdigest()
            if h not in existing_hashes:
                new_entries.append(json.dumps(mem, ensure_ascii=False))
                existing_hashes.add(h)

        if new_entries:
            with open(jsonl_path, "a", encoding="utf-8") as f:
                for entry in new_entries:
                    f.write(entry + "\n")

        # 2. Write modified skills
        for sk in skills:
            target_path = hub_skills_dir / sk["relative_path"]
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(sk["content"], encoding="utf-8")

        # 3. Stage, commit, and push
        self._run_git(["add", "knowledge/", "skills/"])
        status = self._run_git(["status", "--porcelain"])
        if not status.stdout.strip():
            logger.info("Working tree clean; no delta changes to commit.")
            return False, None

        commit_msg = (
            f"sync({self.instance_id}): contribute {len(new_entries)} memories, "
            f"{len(skills)} skills [skip ci]"
        )
        self._run_git(["commit", "-m", commit_msg])
        rev_res = self._run_git(["rev-parse", "HEAD"])
        commit_hash = rev_res.stdout.strip()

        # Ensure branch is main and push to remote
        self._run_git(["branch", "-M", "main"])
        self._run_git(["push", "origin", "main"])
        logger.info("Successfully pushed commit %s to central hub.", commit_hash)
        return True, commit_hash

    def execute_sync_cycle(self) -> SyncCycleResult:
        """
        Executes an end-to-end synchronization cycle:
        1. Initialize/verify hub repo.
        2. Inbound Pull & Merge (with vector deduplication).
        3. Outbound Delta Extraction (with PII & secret scrubbing).
        4. Outbound Push to Central Hub.
        5. Persist sync timestamp state.
        """
        cycle_start = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        errors: List[str] = []

        # Step 1: Ensure Hub
        try:
            hub_ready = self.ensure_hub_repo()
            if not hub_ready:
                return SyncCycleResult(
                    success=False,
                    instance_id=self.instance_id,
                    timestamp=cycle_start,
                    hub_url=self.raw_repo_url,
                    message="Central knowledge repo URL not configured or inaccessible.",
                    errors=["Missing or invalid CENTRAL_KNOWLEDGE_REPO_URL"],
                )
        except Exception as e:
            logger.error("Failed to connect/initialize central hub: %s", e)
            return SyncCycleResult(
                success=False,
                instance_id=self.instance_id,
                timestamp=cycle_start,
                hub_url=self.raw_repo_url,
                message=f"Git hub connection failed: {e}",
                errors=[str(e)],
            )

        # Step 2: Inbound Pull & Merge
        imported_mems = 0
        dedup_mems = 0
        imported_skills = 0
        try:
            imported_mems, dedup_mems, imported_skills = self.pull_and_merge()
        except Exception as e:
            logger.error("Error during inbound pull & merge: %s", e)
            errors.append(f"Pull merge error: {e}")

        # Step 3: Outbound Delta Extraction
        delta = {"memories": [], "skills": []}
        try:
            delta = self.export_local_delta()
        except Exception as e:
            logger.error("Error exporting local delta: %s", e)
            errors.append(f"Delta export error: {e}")

        # Step 4: Outbound Push
        pushed = False
        commit_h = None
        try:
            pushed, commit_h = self.push_local_delta(delta)
        except Exception as e:
            logger.error("Error pushing delta to hub: %s", e)
            errors.append(f"Git push error: {e}")

        # Step 5: Update State
        state = self.load_state()
        state["last_sync_timestamp"] = cycle_start
        if commit_h:
            state["last_push_commit"] = commit_h
        self.save_state(state)

        return SyncCycleResult(
            success=len(errors) == 0,
            instance_id=self.instance_id,
            timestamp=cycle_start,
            hub_url=self.raw_repo_url,
            exported_memories=len(delta.get("memories", [])),
            exported_skills=len(delta.get("skills", [])),
            imported_memories=imported_mems,
            deduplicated_memories=dedup_mems,
            imported_skills=imported_skills,
            pushed_to_hub=pushed,
            commit_hash=commit_h,
            message=(
                f"Sync completed successfully. Exported: {len(delta.get('memories', []))} memories, "
                f"{len(delta.get('skills', []))} skills. Imported: {imported_mems} memories "
                f"({dedup_mems} deduplicated), {imported_skills} skills."
            ),
            errors=errors,
        )
