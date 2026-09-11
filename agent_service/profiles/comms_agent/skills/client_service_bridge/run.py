#!/usr/bin/env python3
"""
Client Service Bridge Skill Runner.

Enterprise Client Portal concierge runner for `comms_agent` supporting:
- Client AI budget & 4-tier milestone checking (25%, 50%, 75%, 100%)
- Client task status and deliverable inspection
- Zero-trust document inventory and authenticated REST file streaming
- Outbound multi-channel notification dispatching via `apps.notifications`
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def resolve_django_credentials() -> tuple[str, str]:
    """Resolves Django API URL and bot token from env or profile runtime files."""
    api_url = os.getenv("DJANGO_API_URL", "http://host.docker.internal:8000/api").rstrip('/')
    api_token = os.getenv("DJANGO_API_TOKEN", "")

    if not api_token:
        env_paths = [
            Path("/root/.hermes/profiles/comms_agent/.env"),
            Path.home() / ".hermes/profiles/comms_agent/.env",
        ]
        for env_path in env_paths:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("DJANGO_API_TOKEN="):
                        api_token = line.split("=", 1)[1].strip()
                    elif line.startswith("DJANGO_API_URL="):
                        api_url = line.split("=", 1)[1].strip().rstrip('/')
                if api_token:
                    break
    return api_url, api_token


def execute_api_request(
    url: str,
    method: str = "GET",
    payload: dict = None,
    api_token: str = "",
    stream_output_path: Path = None,
) -> tuple[int, any]:
    """Executes authenticated HTTP request to Django backend."""
    headers = {}
    if api_token:
        headers["Authorization"] = f"Token {api_token}"

    data_bytes = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            status_code = resp.status
            if stream_output_path:
                stream_output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(stream_output_path, "wb") as f_out:
                    f_out.write(resp.read())
                return status_code, {"saved_to": str(stream_output_path), "bytes": stream_output_path.stat().st_size}

            content = resp.read().decode("utf-8")
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = content
            return status_code, parsed
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"error": err_body}
        return exc.code, err_json
    except Exception as exc:
        return 500, {"error": str(exc)}


def check_budget_status(api_url: str, api_token: str, client_id: str, log_spend: float = None) -> dict:
    """Checks client AI budget milestones or logs spend delta."""
    endpoint = f"{api_url}/hermes/client-budget-status/"

    if log_spend is not None and log_spend > 0:
        post_url = endpoint
        payload = {"client_id": client_id, "spend_delta_usd": str(log_spend)}
        status_code, data = execute_api_request(post_url, method="POST", payload=payload, api_token=api_token)
    else:
        query_url = f"{endpoint}?client_id={urllib.parse.quote(client_id)}"
        status_code, data = execute_api_request(query_url, method="GET", api_token=api_token)

    return {"status_code": status_code, "data": data}


def list_client_tasks(api_url: str, api_token: str, client_id: str) -> dict:
    """Queries engagement tasks associated with the client."""
    query_url = f"{api_url}/tasks/"
    status_code, data = execute_api_request(query_url, method="GET", api_token=api_token)
    return {"status_code": status_code, "data": data}


def list_client_documents(api_url: str, api_token: str, client_id: str) -> dict:
    """Queries media document catalog associated with the client."""
    query_url = f"{api_url}/v1/media/documents/"
    status_code, data = execute_api_request(query_url, method="GET", api_token=api_token)
    return {"status_code": status_code, "data": data}


def fetch_client_document(api_url: str, api_token: str, doc_id: str, output_path: str) -> dict:
    """Securely streams binary document over REST API to local temporary scratch space."""
    download_url = f"{api_url}/v1/media/documents/{doc_id}/download/"
    out_file = Path(output_path) if output_path else Path(f"/tmp/client_doc_{doc_id}.bin")
    status_code, data = execute_api_request(
        download_url,
        method="GET",
        api_token=api_token,
        stream_output_path=out_file
    )
    return {"status_code": status_code, "data": data}


def dispatch_notification(
    api_url: str,
    api_token: str,
    title: str,
    message: str,
    channel: str = "in_app",
    recipient: str = None
) -> dict:
    """Dispatches multi-channel notification via apps.notifications."""
    endpoint = f"{api_url}/v1/notifications/"
    payload = {
        "title": title,
        "message": message,
        "channel": channel,
        "level": "info",
    }
    if recipient:
        payload["recipient"] = recipient
    status_code, data = execute_api_request(endpoint, method="POST", payload=payload, api_token=api_token)
    return {"status_code": status_code, "data": data}


def main():
    parser = argparse.ArgumentParser(description="Client Service Concierge Bridge for comms_agent.")
    parser.add_argument(
        "--mode",
        choices=["budget-check", "status", "documents", "fetch-doc", "notify"],
        required=True,
        help="Operation mode."
    )
    parser.add_argument("--client-id", type=str, default="", help="Client profile UUID, username, or alias.")
    parser.add_argument("--log-spend", type=float, default=None, help="Incremental LLM spend delta to record in USD.")
    parser.add_argument("--doc-id", type=str, default="", help="Document UUID for fetch-doc mode.")
    parser.add_argument("--output-file", type=str, default="", help="Destination path for fetched document.")
    parser.add_argument("--title", type=str, default="", help="Notification title for notify mode.")
    parser.add_argument("--message", type=str, default="", help="Notification body message.")
    parser.add_argument("--channel", type=str, default="in_app", choices=["in_app", "email", "webhook", "slack"])
    parser.add_argument("--recipient", type=str, default=None, help="Recipient user UUID or username.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON.")
    args = parser.parse_args()

    api_url, api_token = resolve_django_credentials()

    bold = "\033[1m"
    reset = "\033[0m"
    cyan = "\033[96m"
    green = "\033[92m"
    yellow = "\033[93m"
    red = "\033[91m"

    if args.mode == "budget-check":
        if not args.client_id:
            print(f"{red}! Error: --mode budget-check requires --client-id <ID>{reset}", file=sys.stderr)
            sys.exit(1)
        res = check_budget_status(api_url, api_token, args.client_id, args.log_spend)
        if args.json:
            print(json.dumps(res, indent=2))
            return

        data = res["data"]
        if res["status_code"] != 200:
            print(f"{red}! Failed checking budget (HTTP {res['status_code']}): {data}{reset}")
            return

        pct = data.get("percentage_used", 0.0)
        status_label = data.get("budget_status", "OK")
        status_color = green if status_label == "OK" else (yellow if status_label == "WARNING_75" else red)

        print(f"\n{bold}{cyan}═══════════════════════════════════════════════════════════════════{reset}")
        print(f"{bold}    Client Service: Engagement AI Budget & Milestone Audit         {reset}")
        print(f"{bold}{cyan}═══════════════════════════════════════════════════════════════════{reset}")
        print(f"Client:          {data.get('display_name')} ({data.get('client_id')})")
        print(f"Allocated Budget: ${data.get('ai_budget_usd')} USD")
        print(f"Cumulative Spend: ${data.get('ai_spend_usd')} USD ({pct}%)")
        print(f"Budget Status:    {status_color}{bold}{status_label}{reset}")
        print(f"───────────────────────────────────────────────────────────────────")
        milestones = data.get("milestones", {})
        m25 = "✓ Reached" if milestones.get("silent_check_25_reached") else "— Pending"
        m50 = "✓ Reached" if milestones.get("velocity_check_50_reached") else "— Pending"
        m75 = "✓ Reached (Advisory Notice Active)" if milestones.get("advisory_75_reached") else "— Pending"
        m100 = "✓ EXCEEDED (Quota Boundary)" if milestones.get("exceeded_100_reached") else "— Pending"
        print(f"  • Milestone 25% (Silent Health Check):   {m25}")
        print(f"  • Milestone 50% (Velocity Check):        {m50}")
        print(f"  • Milestone 75% (Proactive Advisory):    {m75}")
        print(f"  • Milestone 100% (Quota Escalation):     {m100}")
        print(f"{bold}{cyan}═══════════════════════════════════════════════════════════════════{reset}\n")

    elif args.mode == "status":
        res = list_client_tasks(api_url, api_token, args.client_id)
        if args.json:
            print(json.dumps(res, indent=2))
            return
        print(f"\n{bold}Client Engagement Tasks:{reset}")
        print(json.dumps(res["data"], indent=2))

    elif args.mode == "documents":
        res = list_client_documents(api_url, api_token, args.client_id)
        if args.json:
            print(json.dumps(res, indent=2))
            return
        print(f"\n{bold}Client Document Inventory (apps.media):{reset}")
        print(json.dumps(res["data"], indent=2))

    elif args.mode == "fetch-doc":
        if not args.doc_id:
            print(f"{red}! Error: --mode fetch-doc requires --doc-id <UUID>{reset}", file=sys.stderr)
            sys.exit(1)
        res = fetch_client_document(api_url, api_token, args.doc_id, args.output_file)
        if args.json:
            print(json.dumps(res, indent=2))
            return
        if res["status_code"] == 200:
            print(f"{green}✓ Document streamed securely via REST API: {res['data']}{reset}")
        else:
            print(f"{red}! Failed streaming document (HTTP {res['status_code']}): {res['data']}{reset}")

    elif args.mode == "notify":
        if not args.title or not args.message:
            print(f"{red}! Error: --mode notify requires --title and --message{reset}", file=sys.stderr)
            sys.exit(1)
        res = dispatch_notification(api_url, api_token, args.title, args.message, args.channel, args.recipient)
        if args.json:
            print(json.dumps(res, indent=2))
            return
        if res["status_code"] in (200, 201):
            print(f"{green}✓ Outbound notification dispatched across channel '{args.channel}'.{reset}")
        else:
            print(f"{yellow}! Notification response (HTTP {res['status_code']}): {res['data']}{reset}")


if __name__ == "__main__":
    main()
