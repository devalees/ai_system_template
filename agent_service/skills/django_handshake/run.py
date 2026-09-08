#!/usr/bin/env python3
"""
Hermes Agent to Django API Handshake Runner.
Executed inside the Hermes container or directly by the agent runtime.
"""

import os
import sys
import json
import time
import socket
import datetime
import urllib.request
import urllib.error

DJANGO_API_URL = os.getenv('DJANGO_API_URL', 'http://backend:8000/api').rstrip('/')

def make_request(url, method='GET', data=None, headers=None):
    if headers is None:
        headers = {}
    
    req_data = None
    if data is not None:
        req_data = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode('utf-8')
            return response.status, json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        return e.code, {"error": f"HTTP {e.code}", "details": err_body}
    except Exception as e:
        return 0, {"error": str(e)}

def execute_handshake():
    print(f"[Hermes -> Django] Target API Base: {DJANGO_API_URL}")
    
    # 1. Test Backend Health Check
    health_url = f"{DJANGO_API_URL}/health/"
    print(f"[Hermes -> Django] Checking health at {health_url}...")
    status_code, health_resp = make_request(health_url)
    
    if status_code != 200:
        print(f"[FAIL] Backend health check failed with code {status_code}: {health_resp}")
        return False
    
    print(f"[OK] Backend health verified: status={health_resp.get('status')}, db={health_resp.get('database')}")

    # 2. Perform Handshake Registration
    handshake_url = f"{DJANGO_API_URL}/handshake/"
    handshake_payload = {
        "agent_id": "hermes-autonomous-runtime",
        "version": "1.0.0",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "message": "Hermes Agent runtime successfully initialized and connected.",
        "metadata": {
            "hostname": socket.gethostname(),
            "python_version": sys.version.split()[0],
            "skills_loaded": ["django_handshake"]
        }
    }

    print(f"[Hermes -> Django] Transmitting handshake payload to {handshake_url}...")
    status_code, handshake_resp = make_request(handshake_url, method='POST', data=handshake_payload)

    if status_code in (200, 201):
        print(f"[OK] Handshake Acknowledged by Django!")
        print(f"     Log ID: {handshake_resp.get('log_id')}")
        print(f"     Server Message: {handshake_resp.get('message')}")
        print(f"     Server Timestamp: {handshake_resp.get('server_time')}")
        return True
    else:
        print(f"[FAIL] Handshake rejected with code {status_code}: {handshake_resp}")
        return False

if __name__ == '__main__':
    success = execute_handshake()
    sys.exit(0 if success else 1)
