"""Standard domain report auditing user accounts, 2FA enforcement, and access roles."""

import uuid
import datetime
from typing import Dict, Any
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.identity_rbac.models import User
from modules.base.reporting.registry import BaseReport, ReportDataResult


class UserDirectoryReport(BaseReport):
    """Corporate user directory, security profile, and two-factor authentication governance report."""

    report_code = "identity.user_directory"
    name = "Corporate User Directory & 2FA Governance Report"
    description = "Audit list of active company personnel, root administrative privileges, email verification, and 2FA status."
    target_model = "User"
    supported_formats = ["json", "csv", "xlsx", "pdf"]

    async def get_data(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        params: Dict[str, Any],
    ) -> ReportDataResult:
        stmt = (
            sa.select(User)
            .where(
                User.company_id == company_id,
                User.deleted_at.is_(None),
            )
            .order_by(User.created_at.asc())
        )
        users = (await db.execute(stmt)).scalars().all()

        columns = [
            {"name": "username", "title": "Username", "type": "string"},
            {"name": "full_name", "title": "Full Name", "type": "string"},
            {"name": "email", "title": "Corporate Email", "type": "string"},
            {"name": "is_active", "title": "Account Active", "type": "string"},
            {"name": "two_factor", "title": "2FA Enforced", "type": "string"},
            {"name": "role", "title": "System Role", "type": "string"},
            {"name": "joined_date", "title": "Joined Date", "type": "datetime"},
        ]

        rows = []
        active_count = 0
        mfa_count = 0

        for u in users:
            if u.is_active:
                active_count += 1
            if getattr(u, "two_factor_enabled", False):
                mfa_count += 1

            role_str = "Root Superuser" if u.is_superuser else "Standard User"
            if getattr(u, "is_primary_admin", False):
                role_str = "Primary Root Admin"

            rows.append({
                "username": u.username,
                "full_name": u.full_name or "—",
                "email": u.email,
                "is_active": "YES" if u.is_active else "NO",
                "two_factor": "ENABLED" if getattr(u, "two_factor_enabled", False) else "DISABLED",
                "role": role_str,
                "joined_date": u.created_at.strftime("%Y-%m-%d") if u.created_at else "—",
            })

        aggregates = {
            "total_users": len(users),
            "active_users": active_count,
            "two_factor_enabled": mfa_count,
        }

        return ReportDataResult(
            report_code=self.report_code,
            report_name=self.name,
            target_model=self.target_model,
            columns=columns,
            rows=rows,
            aggregates=aggregates,
            total_rows=len(rows),
            generated_at=datetime.datetime.utcnow().isoformat(),
        )
