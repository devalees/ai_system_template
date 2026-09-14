"""Automated OpenAPI specification and Postman Collection v2.1 exporter.

Mandated by fastapi_standards.md to continuously synchronize API contracts,
Postman collections with Bearer auth inheritance, and dynamic token capture scripts.
"""

import json
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.app import create_app

logger = logging.getLogger("sovereign.exporter")

POSTMAN_LOGIN_EVENT_SCRIPT = """if (pm.response.code === 200) {
    var json = pm.response.json();
    if (json.access_token) {
        pm.environment.set("auth_token", json.access_token);
    }
    if (json.company_id) {
        pm.environment.set("active_company_id", json.company_id);
    }
    if (json.user && json.user.id) {
        pm.environment.set("current_user_id", json.user.id);
        pm.environment.set("active_user_id", json.user.id);
    }
}
"""


def _infer_resource_id_name(path: str) -> str:
    """Infer path parameter key for a collection path. e.g. /users -> user_id, /companies -> company_id"""
    if "/identity_rbac/auth/register" in path:
        return "user_id"
    if "/documents/upload" in path:
        return "attachment_id"
    if "/backup/create" in path:
        return "backup_id"
    if "/import_export/" in path:
        return "job_id"
    if "/mail_gateway/send" in path:
        return "queue_id"
    if "/notification_engine/send" in path:
        return "notification_id"

    segments = [s for s in path.split("/") if s and not s.startswith("{")]
    if not segments:
        return "record_id"
    last = segments[-1].lower().replace("-", "_")
    if last.endswith("ies"):
        singular = last[:-3] + "y"
    elif last.endswith("ses"):
        singular = last[:-2]
    elif last.endswith("s") and not last.endswith("ss"):
        singular = last[:-1]
    else:
        singular = last
    return f"{singular}_id"


def _build_postman_url(path: str) -> Dict[str, Any]:
    """Convert OpenAPI path to Postman URL object with path variables mapped to environment variables."""
    # Convert {param} to :param for Postman path variables
    segments = [s for s in path.split("/") if s]
    raw_path = "/".join(f":{s[1:-1]}" if s.startswith("{") and s.endswith("}") else s for s in segments)
    raw_url = f"{{{{base_url}}}}/{raw_path}"

    variable_list = []
    path_segments = []
    for s in segments:
        if s.startswith("{") and s.endswith("}"):
            var_name = s[1:-1]
            path_segments.append(f":{var_name}")

            # Smart default mapping for path variables to environment variables
            if var_name == "company_id":
                default_val = "{{active_company_id}}"
            elif var_name == "user_id":
                default_val = "{{active_user_id}}"
            elif var_name in ("module_name", "module"):
                default_val = "{{active_module_name}}"
            elif var_name in ("model_name", "res_model"):
                default_val = "{{active_model_name}}"
            elif var_name in ("record_id", "res_id"):
                default_val = "{{active_record_id}}"
            elif var_name == "id":
                idx = segments.index(f"{{{var_name}}}")
                if idx > 0:
                    preceding_path = "/" + "/".join(segments[:idx])
                    resource_key = _infer_resource_id_name(preceding_path)
                    default_val = f"{{{{active_{resource_key}}}}}"
                else:
                    default_val = "{{active_record_id}}"
            else:
                clean_name = var_name.replace("-", "_")
                default_val = f"{{{{active_{clean_name}}}}}"

            variable_list.append({
                "key": var_name,
                "value": default_val,
                "description": f"Dynamic path parameter bound to {default_val}",
            })
        else:
            path_segments.append(s)

    return {
        "raw": raw_url,
        "host": ["{{base_url}}"],
        "path": path_segments,
        "variable": variable_list,
    }


def _substitute_env_vars_in_example(data: Any) -> Any:
    """Recursively map hardcoded dummy IDs to dynamic Postman environment variables."""
    if isinstance(data, dict):
        new_data = {}
        for k, v in data.items():
            if k == "company_id" and isinstance(v, str):
                new_data[k] = "{{active_company_id}}"
            elif k == "user_id" and isinstance(v, str):
                new_data[k] = "{{active_user_id}}"
            elif k == "server_id" and isinstance(v, str):
                new_data[k] = "{{active_server_id}}"
            elif k == "template_id" and isinstance(v, str):
                new_data[k] = "{{active_template_id}}"
            elif k == "queue_id" and isinstance(v, str):
                new_data[k] = "{{active_queue_id}}"
            elif k == "group_id" and isinstance(v, str):
                new_data[k] = "{{active_group_id}}"
            elif k == "group_ids" and isinstance(v, list) and v:
                new_data[k] = ["{{active_group_id}}"]
            elif k in ("res_id", "record_id") and isinstance(v, str):
                new_data[k] = "{{active_record_id}}"
            elif k in ("res_model", "model_name") and isinstance(v, str):
                new_data[k] = "{{active_model_name}}"
            else:
                new_data[k] = _substitute_env_vars_in_example(v)
        return new_data
    elif isinstance(data, list):
        return [_substitute_env_vars_in_example(item) for item in data]
    return data


def _extract_body_example(method_data: Dict[str, Any], openapi_schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract realistic JSON request body example from OpenAPI schema with Postman variable bindings."""
    req_body = method_data.get("requestBody", {})
    content = req_body.get("content", {}).get("application/json", {})
    if not content:
        return None

    example_val = None
    # Check for direct example
    if "example" in content:
        example_val = content["example"]
    else:
        # Check schema reference
        schema = content.get("schema", {})
        ref = schema.get("$ref")
        if ref:
            schema_name = ref.split("/")[-1]
            component_schema = openapi_schema.get("components", {}).get("schemas", {}).get(schema_name, {})
            if "example" in component_schema:
                example_val = component_schema["example"]
            else:
                # Fallback build from properties
                props = component_schema.get("properties", {})
                fallback = {}
                for p_name, p_val in props.items():
                    if "example" in p_val:
                        fallback[p_name] = p_val["example"]
                    elif p_val.get("type") == "string":
                        fallback[p_name] = "string"
                    elif p_val.get("type") == "integer":
                        fallback[p_name] = 0
                    elif p_val.get("type") == "boolean":
                        fallback[p_name] = True
                example_val = fallback or None

    if example_val is not None:
        return _substitute_env_vars_in_example(example_val)
    return None


def _format_markdown_docs(op: Dict[str, Any], openapi_schema: Dict[str, Any], path: str, method: str) -> str:
    """Synthesize comprehensive GitHub Markdown documentation for Postman request description."""
    summary = op.get("summary") or f"{method.upper()} {path}"
    description = op.get("description", "").strip()

    lines = [f"## {summary}\n"]
    if description:
        lines.append(f"{description}\n")

    lines.append(f"**Endpoint**: `{method.upper()} {{{{base_url}}}}{path}`  \n**Tags**: `{', '.join(op.get('tags', []))}`\n")

    # 1. URL Path & Query Parameters Table
    params = op.get("parameters", [])
    if params:
        lines.append("### URL & Query Parameters\n")
        lines.append("| Parameter | In | Type | Required | Description |\n| :--- | :--- | :--- | :--- | :--- |")
        for p in params:
            p_name = p.get("name", "")
            p_in = p.get("in", "")
            p_req = "**Yes**" if p.get("required") else "No"
            p_desc = p.get("description", "").replace("\n", " ").strip() or "-"
            p_schema = p.get("schema", {})
            p_type = p_schema.get("type", "string")
            lines.append(f"| `{p_name}` | `{p_in}` | `{p_type}` | {p_req} | {p_desc} |")
        lines.append("\n")

    # 2. Request Body Schema Table
    req_body = op.get("requestBody", {})
    content = req_body.get("content", {}).get("application/json", {})
    if content:
        schema = content.get("schema", {})
        ref = schema.get("$ref")
        component_schema = {}
        if ref:
            schema_name = ref.split("/")[-1]
            component_schema = openapi_schema.get("components", {}).get("schemas", {}).get(schema_name, {})
        else:
            component_schema = schema

        props = component_schema.get("properties", {})
        required_fields = set(component_schema.get("required", []))

        if props:
            lines.append("### Request Body Fields (JSON Payload)\n")
            lines.append("| Field | Type | Required | Allowed Values / Choices | Description |\n| :--- | :--- | :--- | :--- | :--- |")
            for prop_name, prop_val in props.items():
                p_type = prop_val.get("type", "string")
                p_req = "**Yes**" if prop_name in required_fields else "No"

                enums = prop_val.get("enum")
                if not enums and "anyOf" in prop_val:
                    for opt in prop_val["anyOf"]:
                        if "enum" in opt:
                            enums = opt["enum"]
                            break
                        elif "type" in opt and opt["type"] != "null":
                            p_type = opt["type"]

                allowed_str = f"`{', '.join(str(e) for e in enums)}`" if enums else "Any valid " + p_type
                p_desc = prop_val.get("description", "").replace("\n", " ").strip()
                if not p_desc:
                    p_desc = f"{prop_name} attribute"

                lines.append(f"| `{prop_name}` | `{p_type}` | {p_req} | {allowed_str} | {p_desc} |")
            lines.append("\n")

    # 3. Response Status Codes Table
    responses = op.get("responses", {})
    if responses:
        lines.append("### Expected HTTP Responses\n")
        lines.append("| Status Code | Description |\n| :--- | :--- |")
        for code, resp_val in sorted(responses.items()):
            r_desc = resp_val.get("description", "").replace("\n", " ").strip() or "Standard response"
            lines.append(f"| `{code}` | {r_desc} |")
        lines.append("\n")

    return "\n".join(lines)


def convert_openapi_to_postman(openapi_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert OpenAPI 3.1 document to Postman Collection v2.1.0."""
    collection = {
        "info": {
            "_postman_id": str(uuid.uuid4()),
            "name": openapi_data.get("info", {}).get("title", "Sovereign Platform API"),
            "description": openapi_data.get("info", {}).get("description", "Enterprise Sovereign Headless Backend API"),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {
            "type": "bearer",
            "bearer": [
                {"key": "token", "value": "{{auth_token}}", "type": "string"}
            ]
        },
        "item": [],
    }

    SUBFOLDER_ORDER: Dict[str, List[str]] = {
        "Normalized Master Data & Lookups": [
            "Categories",
            "Units of Measure",
            "Countries",
            "Cities",
            "Currencies",
            "Tax Types",
            "Tags",
        ],
        "Identity & Contextual RBAC": [
            "Authentication",
            "Identity Administration",
            "RBAC Administration",
            "Tenant Administration",
        ],
        "Mail Gateway & Async Email Pipeline": [
            "Mail Gateway - Pipeline",
            "Mail Gateway - Servers",
            "Mail Gateway - Templates",
        ],
        "Multi-Channel Notification Engine": [
            "Notification Engine - Dispatch",
            "Notification Engine - In-App",
            "Notification Engine - Preferences",
            "Notification Engine - Subscriptions",
        ],
        "Polymorphic Discussion & Real-time Collaboration": [
            "Chatter Activities",
            "Chatter Messages",
        ],
        "Event-Driven Automated Actions & TCA Engine": [
            "Automated Actions - Rules",
            "Automated Actions - Registry",
            "Automated Actions - Testing",
            "Automated Actions - Logs",
        ],
    }

    folders: Dict[str, Dict[str, Any]] = {}

    for path, path_item in openapi_data.get("paths", {}).items():
        for method in ("get", "post", "put", "patch", "delete"):
            if method not in path_item:
                continue

            op = path_item[method]
            tags = op.get("tags", ["General"])
            primary_tag = tags[0] if tags else "General"
            sub_tag = tags[1] if len(tags) > 1 and tags[1] != primary_tag else None
            summary = op.get("summary") or f"{method.upper()} {path}"
            markdown_description = _format_markdown_docs(op, openapi_data, path, method)

            # Headers
            headers = [
                {"key": "Accept", "value": "application/json", "type": "text"},
            ]
            if not ("login" in path or "health" in path):
                headers.append({"key": "X-Company-ID", "value": "{{active_company_id}}", "type": "text"})

            req_item: Dict[str, Any] = {
                "name": summary,
                "request": {
                    "method": method.upper(),
                    "header": headers,
                    "url": _build_postman_url(path),
                    "description": markdown_description,
                },
                "response": [],
            }

            # Handle body
            body_example = _extract_body_example(op, openapi_data)
            if body_example is not None:
                headers.append({"key": "Content-Type", "value": "application/json", "type": "text"})
                req_item["request"]["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(body_example, indent=2),
                    "options": {"raw": {"language": "json"}},
                }

            # Handle public authentication endpoints
            if "login" in path or "register" in path or "health" in path:
                req_item["request"]["auth"] = {"type": "noauth"}

            # Attach Postman test script for automatic token & company_id capture on login
            if "login" in path:
                req_item["request"]["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(
                        {
                            "identifier": "{{admin_username}}",
                            "password": "{{admin_password}}",
                        },
                        indent=2,
                    ),
                    "options": {"raw": {"language": "json"}},
                }
                req_item["event"] = [
                    {
                        "listen": "test",
                        "script": {
                            "exec": POSTMAN_LOGIN_EVENT_SCRIPT.splitlines(),
                            "type": "text/javascript",
                        },
                    }
                ]
            elif method.lower() == "post":
                resource_var = _infer_resource_id_name(path)
                post_capture_script = f"""if (pm.response.code === 201 || pm.response.code === 200 || pm.response.code === 202) {{
    var json = pm.response.json();
    if (json) {{
        var recId = json.id || json.queue_id || json.notification_id || json.job_id || json.backup_id || (json.data && json.data.id);
        if (recId) {{
            pm.environment.set("active_{resource_var}", recId);
            pm.environment.set("active_record_id", recId);
            pm.environment.set("active_id", recId);
        }}
        if (json.queue_id) {{
            pm.environment.set("active_queue_id", json.queue_id);
        }}
        if (json.notification_id) {{
            pm.environment.set("active_notification_id", json.notification_id);
        }}
        if (json.job_id) {{
            pm.environment.set("active_job_id", json.job_id);
        }}
    }}
}}"""
                req_item["event"] = [
                    {
                        "listen": "test",
                        "script": {
                            "exec": post_capture_script.splitlines(),
                            "type": "text/javascript",
                        },
                    }
                ]

            if primary_tag not in folders:
                folders[primary_tag] = {"direct_items": [], "subfolders": {}}

            if sub_tag:
                if sub_tag not in folders[primary_tag]["subfolders"]:
                    folders[primary_tag]["subfolders"][sub_tag] = []
                folders[primary_tag]["subfolders"][sub_tag].append(req_item)
            else:
                folders[primary_tag]["direct_items"].append(req_item)

    # Sort folders into collection
    for tag_name, folder_data in sorted(folders.items()):
        direct_items = folder_data["direct_items"]
        subfolders = folder_data["subfolders"]

        # Case 1: No subfolders at all -> flat items list
        if not subfolders:
            collection["item"].append({
                "name": tag_name,
                "item": direct_items,
            })
        # Case 2: Only 1 subfolder and no direct items -> flatten to avoid redundant nesting
        elif len(subfolders) == 1 and not direct_items:
            only_sub = list(subfolders.keys())[0]
            collection["item"].append({
                "name": tag_name,
                "item": subfolders[only_sub],
            })
        # Case 3: Multiple subfolders or mixed direct items & subfolders -> hierarchical structure
        else:
            folder_items: List[Dict[str, Any]] = []

            # Determine order of subfolders
            preferred_order = SUBFOLDER_ORDER.get(tag_name, [])
            subfolder_names = list(subfolders.keys())
            if preferred_order:
                ordered_subs = [s for s in preferred_order if s in subfolders]
                remaining = sorted([s for s in subfolder_names if s not in preferred_order])
                sorted_sub_keys = ordered_subs + remaining
            else:
                sorted_sub_keys = sorted(subfolder_names)

            for sub_name in sorted_sub_keys:
                folder_items.append({
                    "name": sub_name,
                    "item": subfolders[sub_name],
                })

            # Append any direct items at the root of this folder
            folder_items.extend(direct_items)

            collection["item"].append({
                "name": tag_name,
                "item": folder_items,
            })

    return collection


def build_postman_environment(
    admin_username: str = "admin",
    admin_password: str = "AdminPassword2026!",
    company_id: str = "",
    token: str = "",
) -> Dict[str, Any]:
    """Generate default Postman environment template with pre-configured credentials and resource IDs."""
    return {
        "id": "sovereign-environment-v1",
        "name": "Sovereign Platform Local Environment",
        "values": [
            {"key": "base_url", "value": "http://localhost:8000", "type": "default", "enabled": True},
            {"key": "admin_username", "value": admin_username, "type": "default", "enabled": True},
            {"key": "admin_password", "value": admin_password, "type": "secret", "enabled": True},
            {"key": "auth_token", "value": token, "type": "secret", "enabled": True},
            {"key": "active_company_id", "value": company_id, "type": "default", "enabled": True},
            {"key": "current_user_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_user_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_group_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_permission_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_server_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_template_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_queue_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_notification_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_subscription_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_term_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_attachment_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_job_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_backup_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_activity_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_country_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_city_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_currency_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_uom_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_tax_type_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_tag_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_category_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_rule_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_action_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_record_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_id", "value": "", "type": "default", "enabled": True},
            {"key": "active_module_name", "value": "identity_rbac", "type": "default", "enabled": True},
            {"key": "active_model_name", "value": "User", "type": "default", "enabled": True},
        ],
        "_postman_variable_scope": "environment",
    }


def export_api_specifications(
    output_dir: Optional[Path] = None,
    admin_username: str = "admin",
    admin_password: str = "AdminPassword2026!",
    company_id: str = "",
    token: str = "",
) -> Dict[str, str]:
    """Export OpenAPI and Postman files to target directory."""
    if output_dir is None:
        if Path("/docs").exists():
            output_dir = Path("/docs/api")
        elif (Path(__file__).resolve().parent.parent.parent / "docs").exists():
            output_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "api"
        else:
            output_dir = Path(__file__).resolve().parent.parent / "docs" / "api"
    elif isinstance(output_dir, str):
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    app = create_app()
    openapi_schema = app.openapi()

    openapi_path = output_dir / "openapi.json"
    collection_path = output_dir / "postman_collection.json"
    environment_path = output_dir / "postman_environment.json"

    # 1. Export OpenAPI JSON
    with open(openapi_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

    # 2. Export Postman Collection
    postman_coll = convert_openapi_to_postman(openapi_schema)
    with open(collection_path, "w", encoding="utf-8") as f:
        json.dump(postman_coll, f, indent=2, ensure_ascii=False)

    # 3. Export Postman Environment
    postman_env = build_postman_environment(
        admin_username=admin_username,
        admin_password=admin_password,
        company_id=company_id,
        token=token,
    )
    with open(environment_path, "w", encoding="utf-8") as f:
        json.dump(postman_env, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully exported OpenAPI and Postman artifacts to {output_dir}")
    return {
        "openapi": str(openapi_path),
        "postman_collection": str(collection_path),
        "postman_environment": str(environment_path),
    }


if __name__ == "__main__":
    export_api_specifications()
