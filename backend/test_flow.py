"""
MedSync AI — Full 7-Step Demo Flow Test
Runs: sim_001 → all agents → action plan → approve → audit
"""
import sys
import io

# Fix Windows CP1252 encoding — allow emoji in output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import urllib.request
import urllib.error
import json
import time

BASE = "http://localhost:8000/api/v1"

def req(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method,
        headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(r, timeout=10)
        return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode()), e.code
    except Exception as ex:
        return {"error": str(ex)}, 0

def ok(label, condition, detail=""):
    mark = "✅" if condition else "❌"
    print(f"  {mark} {label}" + (f": {detail}" if detail else ""))
    return condition

passed = []

print("\n=== MedSync AI — Full 7-Step Flow Test ===\n")

# STEP 1: Health
print("STEP 1: Backend Health")
data, status = req("GET", "/health".replace("/api/v1", ""))
data2, status2 = req("GET", "/../health")
# Try root health endpoint directly
try:
    r = urllib.request.urlopen("http://localhost:8000/health", timeout=5)
    health = json.loads(r.read().decode())
    passed.append(ok("GET /health", health.get("status") == "healthy", str(health)))
except Exception as e:
    passed.append(ok("GET /health", False, str(e)))

# STEP 2: Get simulation scenarios
print("\nSTEP 2: Simulation Scenarios Available")
data, status = req("GET", "/simulation/scenarios")
has_sim_001 = any(s.get("id") == "sim_001" for s in (data if isinstance(data, list) else []))
passed.append(ok("GET /simulation/scenarios", status == 200, f"HTTP {status}"))
passed.append(ok("sim_001 exists", has_sim_001, f"{len(data) if isinstance(data, list) else 0} scenarios found"))

# STEP 3: Run sim_001
print("\nSTEP 3: Run sim_001 (Mass Casualty)")
data, status = req("POST", "/simulation/run/sim_001")
passed.append(ok("POST /simulation/run/sim_001", status == 201, f"HTTP {status}"))
if status == 201:
    incident_id = data.get("incident", {}).get("id")
    plan_msg = data.get("message", "")
    passed.append(ok("incident_id returned", bool(incident_id), incident_id))
    passed.append(ok("websocket_url returned", bool(data.get("websocket_url")), data.get("websocket_url")))
    print(f"  → incident_id: {incident_id}")
    print(f"  → message: {plan_msg}")
else:
    print(f"  ERROR: {json.dumps(data)[:200]}")
    incident_id = None

# STEP 4: Wait for agents to complete
print("\nSTEP 4: Wait for 5 Agents to Complete")
if incident_id:
    print("  Polling up to 90 seconds (2s intervals → 5s after 30s)...")
    check = {}
    elapsed = 0
    while elapsed < 90:
        interval = 2 if elapsed < 30 else 5
        time.sleep(interval)
        elapsed += interval
        check, _ = req("GET", f"/incidents/{incident_id}")
        status_val = check.get("status", "unknown")
        sys.stdout.write(f"\r  [{elapsed:02d}s] status: {status_val}   ")
        sys.stdout.flush()
        if status_val in ("plan_ready", "plan_approved"):
            break
    print()
    final_status = check.get("status", "unknown")
    passed.append(ok("Status reaches plan_ready", final_status in ("plan_ready", "plan_approved"), f"final: {final_status}"))


    # Check agent runs
    runs_data, _ = req("GET", f"/incidents/{incident_id}/agent-runs")
    if isinstance(runs_data, list):
        run_names = [r.get("agent_name") for r in runs_data]
        print(f"  Agent runs found: {run_names}")
        passed.append(ok("Agent runs saved", len(runs_data) > 0, f"{len(runs_data)} runs"))
    else:
        passed.append(ok("Agent runs saved", False, str(runs_data)))

# STEP 5: Get Action Plan
print("\nSTEP 5: Action Plan Generated")
if incident_id:
    plan_data, plan_status = req("GET", f"/incidents/{incident_id}/action-plan")
    passed.append(ok("GET action-plan", plan_status == 200, f"HTTP {plan_status}"))
    if plan_status == 200:
        plan_id = plan_data.get("id")
        p1 = plan_data.get("priority_1_actions", [])
        p2 = plan_data.get("priority_2_actions", [])
        p3 = plan_data.get("priority_3_actions", [])
        esc = plan_data.get("escalation_items", [])
        comp = plan_data.get("compliance_status", "UNKNOWN")
        passed.append(ok("plan_id exists", bool(plan_id), plan_id))
        passed.append(ok("Priority 1 actions", len(p1) > 0, f"{len(p1)} actions"))
        passed.append(ok("Priority 2 actions", len(p2) > 0, f"{len(p2)} actions"))
        passed.append(ok("Escalation items", len(esc) > 0, f"{len(esc)} items"))
        passed.append(ok("Compliance status", bool(comp), comp))
        print(f"  → severity: {plan_data.get('severity_label')}")
        print(f"  → P1 actions: {len(p1)}, P2: {len(p2)}, P3: {len(p3)}, Escalations: {len(esc)}")
        print(f"  → compliance: {comp}")
        print(f"  → summary: {plan_data.get('overall_summary', '')[:100]}")
    else:
        print(f"  ERROR: {json.dumps(plan_data)[:200]}")
        plan_id = None

# STEP 6: Approve Plan
print("\nSTEP 6: Approve Action Plan (Human-in-the-Loop)")
if plan_id:
    approve_data, approve_status = req("PATCH", f"/action-plans/{plan_id}/approve?approved_by=Operations+Manager")
    passed.append(ok("PATCH /approve", approve_status == 200, f"HTTP {approve_status}"))
    if approve_status == 200:
        passed.append(ok("status=approved", approve_data.get("status") == "approved", approve_data.get("status")))
        passed.append(ok("approved_by set", bool(approve_data.get("approved_by")), approve_data.get("approved_by")))
        passed.append(ok("approved_at set", bool(approve_data.get("approved_at")), approve_data.get("approved_at", "")[:19]))
    else:
        print(f"  ERROR: {json.dumps(approve_data)[:200]}")

    # Verify incident status updated
    inc_check, _ = req("GET", f"/incidents/{incident_id}")
    passed.append(ok("Incident → plan_approved", inc_check.get("status") == "plan_approved", inc_check.get("status")))

# STEP 7: Audit Trail
print("\nSTEP 7: Audit Trail")
if incident_id:
    audit_data, audit_status = req("GET", f"/audit-events?incident_id={incident_id}")
    passed.append(ok("GET /audit-events", audit_status == 200, f"HTTP {audit_status}"))
    if isinstance(audit_data, list):
        event_types = [e.get("event_type") for e in audit_data]
        print(f"  Audit events: {event_types}")
        passed.append(ok("incident_created logged", "incident_created" in event_types))
        passed.append(ok("agent_completed logged", "agent_completed" in event_types))
        passed.append(ok("plan_approved logged", "plan_approved" in event_types))
    else:
        passed.append(ok("Audit events", False, str(audit_data)[:100]))

# SUMMARY
print("\n" + "="*50)
total = len(passed)
passing = sum(passed)
print(f"RESULT: {passing}/{total} checks passed")
if passing == total:
    print("🎉 ALL STEPS PASS — DEMO READY")
else:
    print(f"⚠️  {total - passing} checks failed — see ❌ above")
print("="*50)
