"""Comprehensive automated test suite for Hybrid Model Extension Engine (@extend_model)."""

import uuid
import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from core.extensions import ModelExtensionRegistry, extend_model, model_extension_registry
from modules.base.parties.models import Party
from modules.base.automated_actions.introspection import get_registered_models


# Register canonical test extension at module level
@extend_model("Party")
class PartyCustomExtension:
    compliance_rating: Mapped[str] = mapped_column(sa.String(20), default="STANDARD", nullable=True)
    risk_score: Mapped[int] = mapped_column(sa.Integer, default=50, nullable=True)

    def calculate_risk_level(self) -> str:
        score = getattr(self, "risk_score", 50)
        return "HIGH" if score > 75 else "LOW"


@pytest_asyncio.fixture(autouse=True)
async def ensure_extensions_and_migrations(db_session: AsyncSession):
    """Ensure in-place extensions are applied to models and migrated in DB before tests."""
    model_extension_registry.apply_extensions()
    conn = await db_session.connection()
    await model_extension_registry.execute_migrations(conn)
    await db_session.commit()
    yield


@pytest.mark.asyncio
async def test_extension_registration_and_inspection():
    """Verify that @extend_model correctly registers and inspects extension class attributes."""
    reg = ModelExtensionRegistry()

    @reg.register("parties.Party")
    class SamplePartyExtension:
        test_score: Mapped[int] = mapped_column(default=100, nullable=True)
        test_category: sa.Column = sa.Column(sa.String(30), nullable=True)

        def get_formatted_score(self) -> str:
            return f"Score: {getattr(self, 'test_score', 0)}"

    # Verify registration
    assert any(ext.target_name == "parties.Party" for ext in reg.extensions)
    matching_ext = next(ext for ext in reg.extensions if ext.extension_cls == SamplePartyExtension)
    assert "test_score" in matching_ext.columns
    assert "test_category" in matching_ext.columns
    assert "get_formatted_score" in matching_ext.methods


@pytest.mark.asyncio
async def test_apply_extension_to_party_model():
    """Verify in-place injection of columns and methods into Party model."""
    assert "compliance_rating" in Party.__table__.columns
    assert "risk_score" in Party.__table__.columns
    assert hasattr(Party, "calculate_risk_level")

    # Instantiate Party and test injected attributes and methods
    p = Party(name="Test Partner Alpha", compliance_rating="PREMIUM", risk_score=85)
    assert p.compliance_rating == "PREMIUM"
    assert p.risk_score == 85
    assert p.calculate_risk_level() == "HIGH"


@pytest.mark.asyncio
async def test_to_dict_includes_injected_columns():
    """Verify that BaseModel.to_dict() automatically serializes dynamically injected columns."""
    p = Party(
        name="Serialization Test Corp",
        compliance_rating="VERIFIED",
        risk_score=20,
    )
    serialized = p.to_dict()
    assert "compliance_rating" in serialized
    assert serialized["compliance_rating"] == "VERIFIED"
    assert "risk_score" in serialized
    assert serialized["risk_score"] == 20


@pytest.mark.asyncio
async def test_ddl_generation_and_database_migration(db_session: AsyncSession):
    """Verify automated DDL generation and PostgreSQL migration verification."""
    reg = model_extension_registry
    col = Party.__table__.columns["compliance_rating"]
    ddl = reg.generate_column_ddl("parties", "compliance_rating", col)
    assert "ALTER TABLE public.parties ADD COLUMN IF NOT EXISTS compliance_rating" in ddl
    assert "VARCHAR(20)" in ddl

    # Verify column exists in PostgreSQL information_schema
    res = await db_session.execute(sa.text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'parties' AND column_name = 'compliance_rating';
    """))
    row = res.fetchone()
    assert row is not None
    assert row[0] == "compliance_rating"


@pytest.mark.asyncio
async def test_orm_database_persistence_and_query(db_session: AsyncSession):
    """Verify end-to-end ORM save, commit, and query with the injected columns in PostgreSQL."""
    test_rating = f"TEST_{uuid.uuid4().hex[:6]}"
    comp_id = uuid.uuid4()
    partner = Party(
        name=f"Enterprise Partner {test_rating}",
        company_id=comp_id,
        compliance_rating=test_rating,
        risk_score=42,
    )
    db_session.add(partner)
    await db_session.commit()
    partner_id = partner.id

    # Query back in the session
    stmt = sa.select(Party).where(Party.id == partner_id)
    result = await db_session.execute(stmt)
    fetched = result.scalar_one()

    assert fetched is not None
    assert fetched.name == f"Enterprise Partner {test_rating}"
    assert fetched.compliance_rating == test_rating
    assert fetched.risk_score == 42
    assert fetched.calculate_risk_level() == "LOW"

    # Query using injected column in filter
    filter_stmt = sa.select(Party).where(Party.compliance_rating == test_rating)
    filter_result = await db_session.execute(filter_stmt)
    filtered_partner = filter_result.scalar_one_or_none()
    assert filtered_partner is not None
    assert filtered_partner.id == partner_id


@pytest.mark.asyncio
async def test_introspection_and_flac_awareness():
    """Verify that Automated Actions and Query Engine introspection automatically reflects injected columns."""
    catalog = get_registered_models()
    party_meta = next((m for m in catalog if m["model_name"] == "Party"), None)
    assert party_meta is not None
    # Introspection should dynamically see the newly added columns
    assert party_meta["fields_count"] >= len(Party.__table__.columns)
