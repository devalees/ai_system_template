"""Comprehensive test suite for Multi-Hop Relational Traversal and Transactional Document Reporting."""

import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.app import create_app
from core.database import get_db
from modules.base.identity_rbac.security import create_access_token
from modules.base.identity_rbac.models import User, Company
from modules.base.lookups.models import Country, City, Category
from modules.base.reporting.models import ReportTemplate, ReportDefinition
from modules.base.reporting.engine.dynamic_builder import DynamicReportQueryEngine
from modules.base.reporting.service import ReportService
from modules.base.reporting.renderers.pdf_renderer import PDFReportRenderer
from modules.base.reporting.renderers.excel_renderer import ExcelReportRenderer
from modules.base.reporting.renderers.csv_renderer import CSVReportRenderer
from modules.base.automated_actions.introspection import (
    get_model_fields,
    resolve_field_path,
)


@pytest.fixture
def app_instance():
    return create_app()


@pytest.fixture
def override_db(app_instance, db_session: AsyncSession):
    async def _get_db_override():
        yield db_session

    app_instance.dependency_overrides[get_db] = _get_db_override
    yield
    app_instance.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_multi_hop_m1_relational_query_traversal(db_session: AsyncSession):
    """Verify DynamicReportQueryEngine resolves dot-notation foreign keys with aliased joins."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Relational Query Co", code=f"REL_{comp_id.hex[:4]}")
    db_session.add(company)
    await db_session.commit()

    # Create Country & City
    country = Country(
        id=uuid.uuid4(),
        company_id=comp_id,
        name="United Arab Emirates",
        code="ARE",
        dialing_code="+971",
    )
    db_session.add(country)
    await db_session.commit()

    city = City(
        id=uuid.uuid4(),
        company_id=comp_id,
        country_id=country.id,
        name="Dubai",
        postal_code="00000",
    )
    db_session.add(city)
    await db_session.commit()

    # Query City with dot-notation to country
    result = await DynamicReportQueryEngine.execute_query(
        db=db_session,
        company_id=comp_id,
        target_model="City",
        selected_fields=["name", "postal_code", "country.name", "country.code", "country.dialing_code"],
    )

    assert result.total_rows >= 1
    found = next((r for r in result.rows if r.get("name") == "Dubai"), None)
    assert found is not None
    assert found["country.name"] == "United Arab Emirates"
    assert found["country.code"] == "ARE"
    assert found["country.dialing_code"] == "+971"

    # Verify column metadata reflects path titles
    country_col = next((c for c in result.columns if c["name"] == "country.name"), None)
    assert country_col is not None
    assert "Country > Name" in country_col["title"]


@pytest.mark.asyncio
async def test_self_referencing_recursive_joins(db_session: AsyncSession):
    """Verify multi-hop joins on self-referential models (Category -> parent -> parent)."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Hierarchy Query Co", code=f"HIER_{comp_id.hex[:4]}")
    db_session.add(company)
    await db_session.commit()

    # 3-level Category hierarchy: Electronics -> Computers -> Laptops
    uid = uuid.uuid4().hex[:4]
    cat_root = Category(id=uuid.uuid4(), company_id=comp_id, name="Electronics", code=f"ELEC_{uid}")
    db_session.add(cat_root)
    await db_session.commit()

    cat_mid = Category(id=uuid.uuid4(), company_id=comp_id, parent_id=cat_root.id, name="Computers", code=f"COMP_{uid}")
    db_session.add(cat_mid)
    await db_session.commit()

    cat_leaf = Category(id=uuid.uuid4(), company_id=comp_id, parent_id=cat_mid.id, name="Laptops", code=f"LAP_{uid}")
    db_session.add(cat_leaf)
    await db_session.commit()

    # Query Category with multi-hop parent traversal
    result = await DynamicReportQueryEngine.execute_query(
        db=db_session,
        company_id=comp_id,
        target_model="Category",
        selected_fields=["name", "parent.name", "parent.parent.name"],
    )

    laptop_row = next((r for r in result.rows if r.get("name") == "Laptops"), None)
    assert laptop_row is not None
    assert laptop_row["parent.name"] == "Computers"
    assert laptop_row["parent.parent.name"] == "Electronics"


@pytest.mark.asyncio
async def test_multi_hop_introspection_and_path_resolution():
    """Verify get_model_fields reflects relationships and resolve_field_path validates dot paths."""
    # Test depth=1
    spec_d1 = get_model_fields("City", depth=1)
    assert spec_d1 is not None
    assert "relationships" in spec_d1
    rel_country = next((r for r in spec_d1["relationships"] if r["name"] == "country"), None)
    assert rel_country is not None
    assert rel_country["target_model"] == "Country"
    assert rel_country["direction"] == "MANYTOONE"
    assert rel_country["is_collection"] is False
    assert rel_country["fields"] is None

    # Test depth=2
    spec_d2 = get_model_fields("City", depth=2)
    assert spec_d2 is not None
    rel_country_d2 = next((r for r in spec_d2["relationships"] if r["name"] == "country"), None)
    assert rel_country_d2 is not None
    assert rel_country_d2["fields"] is not None
    assert any(f["name"] == "name" for f in rel_country_d2["fields"])
    assert any(f["name"] == "code" for f in rel_country_d2["fields"])

    # Test resolve_field_path
    resolved = resolve_field_path(City, "country.name")
    assert resolved is not None
    assert resolved["column_name"] == "name"
    assert resolved["type"] == "string"
    assert resolved["title"] == "Country > Name"
    assert resolved["relationship_chain"] == ["country"]

    # Test invalid path
    invalid = resolve_field_path(City, "nonexistent_rel.field")
    assert invalid is None


@pytest.mark.asyncio
async def test_transactional_document_query_execution(db_session: AsyncSession):
    """Verify execute_document_query loads parent header and iterates 1:M child lines."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Doc Query Co", code=f"DOC_{comp_id.hex[:4]}")
    db_session.add(company)
    await db_session.commit()

    # Create Parent Country with 3 child Cities
    country = Country(
        id=uuid.uuid4(),
        company_id=comp_id,
        name="Kingdom of Saudi Arabia",
        code="SAU",
        dialing_code="+966",
    )
    db_session.add(country)
    await db_session.commit()

    cities = [
        City(id=uuid.uuid4(), company_id=comp_id, country_id=country.id, name="Riyadh", postal_code="11111"),
        City(id=uuid.uuid4(), company_id=comp_id, country_id=country.id, name="Jeddah", postal_code="22222"),
        City(id=uuid.uuid4(), company_id=comp_id, country_id=country.id, name="Dammam", postal_code="33333"),
    ]
    db_session.add_all(cities)
    await db_session.commit()

    # Execute Document Query on Country with lines_relationship='cities'
    doc_result = await DynamicReportQueryEngine.execute_document_query(
        db=db_session,
        company_id=comp_id,
        target_model="Country",
        record_id=country.id,
        header_fields=["name", "code", "dialing_code"],
        recipient_fields=["name"],
        lines_relationship="cities",
        lines_fields=["name", "postal_code"],
        document_title="Country Territory Dossier",
    )

    assert doc_result.target_model == "Country"
    assert doc_result.report_name == "Country Territory Dossier"
    assert doc_result.metadata["report_type"] == "document"
    assert doc_result.metadata["has_lines"] is True
    assert doc_result.metadata["lines_count"] == 3
    assert doc_result.metadata["header"]["name"] == "Kingdom of Saudi Arabia"
    assert len(doc_result.rows) == 3

    city_names = [r["name"] for r in doc_result.rows]
    assert "Riyadh" in city_names
    assert "Jeddah" in city_names
    assert "Dammam" in city_names


@pytest.mark.asyncio
async def test_document_mode_multi_format_rendering(db_session: AsyncSession):
    """Verify document mode outputs executive PDF layout, Excel sheet, and CSV."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Executive Print Co", code=f"PRT_{comp_id.hex[:4]}")
    db_session.add(company)
    await db_session.commit()

    country = Country(
        id=uuid.uuid4(),
        company_id=comp_id,
        name="State of Qatar",
        code="QAT",
        dialing_code="+974",
    )
    db_session.add(country)
    await db_session.commit()

    city = City(id=uuid.uuid4(), company_id=comp_id, country_id=country.id, name="Doha", postal_code="00000")
    db_session.add(city)
    await db_session.commit()

    doc_result = await DynamicReportQueryEngine.execute_document_query(
        db=db_session,
        company_id=comp_id,
        target_model="Country",
        record_id=country.id,
        header_fields=["name", "code"],
        recipient_fields=["name"],
        lines_relationship="cities",
        lines_fields=["name", "postal_code"],
        document_title="Territory Invoice",
    )

    template = ReportTemplate(
        id=uuid.uuid4(),
        company_id=comp_id,
        name="Executive Blue",
        code="exec_blue",
        primary_color="#0284C7",
        orientation="portrait",
        footer_text="Executive Confidential Document",
    )

    # 1. Test PDF Rendering
    pdf_bytes = PDFReportRenderer.render(doc_result, template)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")

    # 2. Test Excel Rendering
    excel_bytes = ExcelReportRenderer.render(doc_result, template)
    assert isinstance(excel_bytes, bytes)
    assert excel_bytes.startswith(b"PK")

    # 3. Test CSV Rendering
    csv_bytes = CSVReportRenderer.render(doc_result)
    assert isinstance(csv_bytes, bytes)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM


@pytest.mark.asyncio
async def test_document_export_api_endpoints(override_db, db_session: AsyncSession, app_instance):
    """Verify document definition creation and single-record export endpoint."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="API Doc Co", code=f"APID_{comp_id.hex[:4]}")
    uid = uuid.uuid4().hex[:6]
    user = User(
        id=uuid.uuid4(),
        company_id=comp_id,
        email=f"doc_admin_{uid}@test.com",
        username=f"doc_admin_{uid}",
        full_name="Doc Administrator",
        hashed_password="pw",
        is_superuser=True,
    )
    db_session.add_all([company, user])
    await db_session.commit()

    country = Country(
        id=uuid.uuid4(),
        company_id=comp_id,
        name="Kingdom of Bahrain",
        code="BHR",
        dialing_code="+973",
    )
    db_session.add(country)
    await db_session.commit()

    city = City(id=uuid.uuid4(), company_id=comp_id, country_id=country.id, name="Manama", postal_code="00000")
    db_session.add(city)
    await db_session.commit()

    # Create Document ReportDefinition in DB
    report_def = ReportDefinition(
        id=uuid.uuid4(),
        company_id=comp_id,
        name="Country Dossier Document",
        code="country_dossier",
        target_model="Country",
        report_type="document",
        document_title="Official Country Dossier",
        header_fields=["name", "code"],
        recipient_fields=["name"],
        lines_relationship="cities",
        lines_fields=["name", "postal_code"],
        selected_fields=["name", "code"],
    )
    db_session.add(report_def)
    await db_session.commit()

    token = create_access_token(user_id=user.id, company_id=comp_id, user_type="human")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Company-ID": str(comp_id),
    }

    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as client:
        # Test Document Export Route
        export_resp = await client.post(
            f"/api/v1/reporting/documents/country_dossier/{country.id}/export?format=pdf",
            headers=headers,
        )
        assert export_resp.status_code == 200
        assert export_resp.headers["content-type"] == "application/pdf"
        assert export_resp.content.startswith(b"%PDF")

        # Test with format=json
        json_resp = await client.post(
            f"/api/v1/reporting/documents/country_dossier/{country.id}/export?format=json",
            headers=headers,
        )
        assert json_resp.status_code == 200
        data = json_resp.json()
        assert data["report_name"] == "Official Country Dossier"
        assert data["metadata"]["report_type"] == "document"
        assert len(data["rows"]) >= 1
