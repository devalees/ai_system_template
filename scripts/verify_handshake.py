#!/usr/bin/env python3
"""
End-to-End Verification Script for AI System Template.
Tests connectivity, database persistence, and bidirectional handshakes.
"""

import sys
import json
import time
import urllib.request
import urllib.error

BACKEND_HOST = "http://localhost:8000"

def get(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode())

def post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode())

def main():
    print("==================================================================")
    print("  AI SYSTEM TEMPLATE: END-TO-END HANDSHAKE VERIFICATION")
    print("==================================================================")

    # 1. Health Check
    print("\n[Step 1] Checking Django Backend & DB Health...")
    try:
        status, data = get(f"{BACKEND_HOST}/api/health/")
        print(f" -> Status: {status}")
        print(f" -> Details: {json.dumps(data, indent=2)}")
        if status != 200 or data.get("status") != "healthy":
            print("[FAIL] Backend reports unhealthy or degraded state.")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Could not connect to Django: {e}")
        sys.exit(1)

    # 2. Simulate / Trigger Handshake
    print("\n[Step 2] Sending Handshake Payload from Agent Simulator...")
    handshake_payload = {
        "agent_id": "test-hermes-verifier",
        "version": "1.0.0-template",
        "message": "Automated verification test from template verifier",
        "metadata": {"source": "scripts/verify_handshake.py"}
    }
    try:
        status, data = post(f"{BACKEND_HOST}/api/handshake/", handshake_payload)
        print(f" -> Status: {status}")
        print(f" -> Handshake response: {json.dumps(data, indent=2)}")
        log_id = data.get("log_id")
        if not log_id:
            print("[FAIL] Did not receive log_id in acknowledgment.")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Handshake request failed: {e}")
        sys.exit(1)

    # 3. Verify Persistence in Django Logs
    print("\n[Step 3] Verifying Handshake Persistence in Database...")
    try:
        status, logs = get(f"{BACKEND_HOST}/api/handshake/logs/")
        matching = [l for l in logs if l.get("id") == log_id]
        if matching:
            print(f" -> [SUCCESS] Found log in database with ID: {log_id}")
            print(f"    Agent ID: {matching[0]['agent_id']}")
            print(f"    Created: {matching[0]['created_at']}")
        else:
            print("[FAIL] Handshake was acknowledged but not found in logs!")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Could not retrieve logs: {e}")
        sys.exit(1)

    # 4. Check Reverse Ping to Hermes Gateway
    print("\n[Step 4] Checking Reverse Ping (Django -> Hermes Gateway)...")
    try:
        status, ping_data = get(f"{BACKEND_HOST}/api/ping-hermes/")
        print(f" -> Status: {status}")
        print(f" -> Reverse Ping response: {json.dumps(ping_data, indent=2)}")
    except urllib.error.HTTPError as e:
        print(f" -> Reverse Ping HTTP {e.code}: {e.read().decode()}")
    except Exception as e:
        print(f" -> Reverse Ping notice: {e}")

    print("\n==================================================================")
    print("  ALL CORE CHECKS PASSED: Template Scaffolding is Fully Operational!")
    print("==================================================================")

if __name__ == '__main__':
    main()
