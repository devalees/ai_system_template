"""Interactive Database Setup & Super Administrator Provisioning CLI Script.

Wipes and initializes PostgreSQL schemas, seeds ISO lookups data,
creates the primary tenant company, prompts interactively for Super Admin
credentials (with strict validation), and configures universal RBAC.
"""

import sys
import os
import re
import uuid
import asyncio
import getpass
import argparse
from typing import Optional, Tuple
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import settings
from core.base_models import Base
from core.kernel import kernel
from modules.base.identity_rbac.models import (
    Company,
    User,
    Group,
    Permission,
    UserGroupLink,
    GroupPermissionLink,
)
from modules.base.identity_rbac.security import hash_password
from modules.base.identity_rbac.harvester import harvest_model_permissions
from modules.base.lookups.fixtures import seed_iso_data
from core.exporter import export_api_specifications


def validate_username(username: str) -> Tuple[bool, str]:
    """Validate username: 3-50 chars, alphanumeric + underscores/hyphens, no spaces."""
    username = username.strip()
    if len(username) < 3 or len(username) > 50:
        return False, "Username must be between 3 and 50 characters."
    if " " in username:
        return False, "Username must not contain any spaces."
    if not re.match(r"^[a-zA-Z0-9_-]+$", username):
        return False, "Username may only contain letters, numbers, hyphens (-), and underscores (_)."
    return True, ""


def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password: minimum 8 characters, non-empty."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if password.strip() == "":
        return False, "Password cannot be empty or purely whitespace."
    return True, ""


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format."""
    email = email.strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return False, "Invalid email address format."
    return True, ""


def prompt_with_validation(prompt_text: str, validator_fn, default: Optional[str] = None) -> str:
    """Prompt user repeatedly until input satisfies validation rules."""
    while True:
        display_prompt = f"{prompt_text} [{default}]: " if default else f"{prompt_text}: "
        user_input = input(display_prompt).strip()
        if not user_input and default is not None:
            user_input = default

        is_valid, err_msg = validator_fn(user_input)
        if is_valid:
            return user_input
        print(f"  [ERROR] {err_msg} Please try again.")


def prompt_password_with_confirmation(min_length: int = 8) -> str:
    """Prompt for password twice using masked input."""
    while True:
        pwd1 = getpass.getpass("Enter Super Admin Password: ")
        is_valid, err_msg = validate_password(pwd1)
        if not is_valid:
            print(f"  [ERROR] {err_msg}")
            continue

        pwd2 = getpass.getpass("Confirm Super Admin Password: ")
        if pwd1 != pwd2:
            print("  [ERROR] Passwords do not match. Please try again.")
            continue

        return pwd1


async def setup_database(
    username: Optional[str] = None,
    password: Optional[str] = None,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    company_name: Optional[str] = None,
    company_code: Optional[str] = None,
    allow_registration: Optional[bool] = None,
    force: bool = False,
    interactive: bool = True,
):
    """Execute clean database setup and seed initial Super Admin."""
    print("=" * 70)
    print("   SOVEREIGN ENTERPRISE BACKEND - DATABASE SETUP & INSTALLER")
    print("=" * 70)

    # 1. Interactive confirmation and prompts
    if interactive and not force:
        confirm = input("\n[WARNING] This will reset the database and ERASE ALL DATA! Continue? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Setup cancelled by user.")
            return

    # Company details
    if interactive and company_name is None:
        print("\n--- [Step 1: Primary Organization Configuration] ---")
        company_name = input("Enter Primary Company Name [Sovereign Enterprise System]: ").strip() or "Sovereign Enterprise System"
        company_code = input("Enter Primary Company Code [SOV-MAIN]: ").strip() or "SOV-MAIN"
        allow_reg_input = input("Allow public self-registration for this company? (y/N) [N]: ").strip().lower()
        allow_registration = allow_reg_input in ("y", "yes")
    else:
        company_name = company_name or "Sovereign Enterprise System"
        company_code = company_code or "SOV-MAIN"
        allow_registration = bool(allow_registration)

    # Super Admin credentials
    if interactive and (username is None or password is None):
        print("\n--- [Step 2: Super Administrator Credentials] ---")
        if username is None:
            username = prompt_with_validation("Enter Super Admin Username", validate_username, default="admin")
        if email is None:
            email = prompt_with_validation("Enter Super Admin Email", validate_email, default="admin@sovereign.local")
        if full_name is None:
            full_name = input("Enter Super Admin Full Name [Super Administrator]: ").strip() or "Super Administrator"
        if password is None:
            password = prompt_password_with_confirmation()
    else:
        username = username or "admin"
        email = email or "admin@sovereign.local"
        password = password or "AdminPassword2026!"
        full_name = full_name or "Super Administrator"

        # Validate provided non-interactive args
        u_valid, u_err = validate_username(username)
        if not u_valid:
            raise ValueError(f"Invalid username: {u_err}")
        p_valid, p_err = validate_password(password)
        if not p_valid:
            raise ValueError(f"Invalid password: {p_err}")

    print("\n--- [Step 3: Discovering Modules & Initializing Schemas] ---")
    kernel.discover()
    kernel.resolve_dependencies()
    kernel.load()
    print(f"  [OK] Loaded {len(kernel.manifests)} modules in topological order.")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    print("\n--- [Step 4: Wiping and Recreating PostgreSQL Tables] ---")
    async with engine.begin() as conn:
        print("  Dropping existing schema public...")
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        print("  Creating database tables from SQLAlchemy declarative models...")
        await conn.run_sync(Base.metadata.create_all)
    print("  [OK] Database schema initialized successfully.")

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        print("\n--- [Step 5: Seeding Primary Tenant & Super Admin] ---")
        # 1. Create Primary Company
        company = Company(
            name=company_name,
            code=company_code,
            email_domain=email.split("@")[-1] if "@" in email else None,
            currency_id="USD",
        )
        db.add(company)
        await db.flush()
        print(f"  [OK] Primary Company created: '{company.name}' (Code: {company.code}, ID: {company.id})")

        # Seed identity_rbac module settings
        from modules.base.settings.service import SettingsService
        await SettingsService.update_settings(
            db=db,
            module_name="identity_rbac",
            company_id=company.id,
            new_data={"allow_registration": allow_registration},
        )
        print(f"       Identity Settings Seeded (Allow Registration: {allow_registration})")

        # 2. Seed ISO Master Data Lookups
        print("  Seeding ISO Master Data (Countries, Currencies, UoMs, Tax Types)...")
        counts = await seed_iso_data(db, company.id)
        print(f"  [OK] Seeded {counts.get('currencies', 0)} currencies, {counts.get('countries', 0)} countries, {counts.get('uom', 0)} UoMs.")

        # 3. Create Super Admin User
        super_admin = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
            user_type="human",
            is_superuser=True,
            is_primary_admin=True,
            email_verified=True,
            two_factor_enabled=False,
            preferred_language="en",
            company_id=company.id,
        )
        db.add(super_admin)
        await db.flush()
        print(f"  [OK] Super Admin user created: '{super_admin.username}' (Email: {super_admin.email}, ID: {super_admin.id})")

        # 4. Harvest All Model-Level CRUD Permissions
        print("  Harvesting automated CRUD permissions across all module declarative models...")
        harvest_result = await harvest_model_permissions(db, company_id=company.id, auto_link_super_admin_group=False)
        print(f"  [OK] Harvested {harvest_result['new_permissions_created']} CRUD permissions across {harvest_result['models_inspected']} models.")

        # 5. Create Super Admin Group and assign all existing permissions
        admin_group = Group(
            name="Super Administrators",
            description="Universal system administration and governance authority",
            company_id=company.id,
        )
        db.add(admin_group)
        await db.flush()

        # Link Super Admin User to Super Administrators Group
        user_link = UserGroupLink(user_id=super_admin.id, group_id=admin_group.id, company_id=company.id)
        db.add(user_link)

        # Link all harvested permissions
        all_perms = (await db.execute(select(Permission))).scalars().all()
        for perm in all_perms:
            g_link = GroupPermissionLink(group_id=admin_group.id, permission_id=perm.id, company_id=company.id)
            db.add(g_link)

        await db.commit()
        print(f"  [OK] Linked Super Admin to '{admin_group.name}' group ({len(all_perms)} permissions).")

        # 6. Seed Default Automated Actions
        from modules.base.automated_actions.fixtures import seed_default_automated_actions
        action_count = await seed_default_automated_actions(db, company.id)
        print(f"  [OK] Seeded {action_count} default automated action rules.")

    await engine.dispose()

    # Step 6: Synchronize Postman Specifications
    print("\n--- [Step 6: Synchronizing OpenAPI & Postman Files] ---")
    try:
        from core.exporter import export_api_specifications
        export_api_specifications(
            admin_username=username,
            admin_password=password,
            company_id=str(company.id),
        )
        print("  [OK] Exported fresh openapi.json, postman_collection.json, and postman_environment.json")
    except Exception as exc:
        print(f"  [WARN] Could not auto-sync postman files: {exc}")

    print("\n" + "=" * 70)
    print("   SETUP COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print(f"   * Company Name       : {company_name}")
    print(f"   * Company Code       : {company_code}")
    print(f"   * Company ID         : {company.id}")
    print(f"   * Allow Registration : {allow_registration}")
    print(f"   * Super Admin User   : {username}")
    print(f"   * Super Admin Email  : {email}")
    print(f"   * Super Admin Role   : is_superuser=True, is_primary_admin=True (Primary Root Administrator)")
    print("=" * 70)
    print("   Postman Environment is ready with your Super Admin credentials!")
    print("   Simply import into Postman and execute POST /auth/login.\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Sovereign Backend Platform Database Setup CLI")
    parser.add_argument("--username", "-u", help="Super Admin username")
    parser.add_argument("--password", "-p", help="Super Admin password")
    parser.add_argument("--email", "-e", help="Super Admin email")
    parser.add_argument("--full-name", help="Super Admin display name")
    parser.add_argument("--company-name", help="Primary Company name")
    parser.add_argument("--company-code", help="Primary Company code")
    parser.add_argument("--allow-registration", action="store_true", help="Enable public self-registration")
    parser.add_argument("--force", "-f", action="store_true", help="Bypass confirmation prompt")
    parser.add_argument("--non-interactive", action="store_true", help="Run without interactive prompts")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    interactive = not args.non_interactive

    asyncio.run(
        setup_database(
            username=args.username,
            password=args.password,
            email=args.email,
            full_name=args.full_name,
            company_name=args.company_name,
            company_code=args.company_code,
            allow_registration=args.allow_registration,
            force=args.force,
            interactive=interactive,
        )
    )
