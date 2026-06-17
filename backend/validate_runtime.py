"""
MedSync AI — Full Runtime Validation Script
Steps 2-8: E2E, API, Agent, Store, Error Handling
"""
import sys, io, json, time, asyncio, urllib.request, urllib.error
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE = "http://localhost:8000"
API  = f"{BASE}/api/v1"

PASS = "PASS"; FAIL = "FAIL"; WARN = "WARN"
results = []

def req(method, path, body=None, base=API, timeout=15):
    url = base + path
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method,
        headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        try: body_e = json.loads(e.read().decode())
        except: body_e = {}
        return body_e, e.code
    except Exception as ex:
        return {"error": str(ex)}, 0

def check(label, status, detail="", expected_status=None):
    if expected_status and status not in expected_status:
        r = FAIL
    elif status == PASS:
        r = PASS
    elif status == FAIL:
        r = FAIL
    elif status == WARN:
        r = WARN
    else:
        r = PASS
    mark = {"PASS":"✅","FAIL":"❌","WARN":"⚠️"}.get(r,"?")
    line = f"  {mark} [{r}] {label}"
    if detail: line += f" | {detail}"
    print(line)
    results.append((r, label))
    return r == PASS

incident_id = None
plan_id = None

# ─────────────────────────────────────────────
# STEP 1: STARTUP VALIDATION
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 1: STARTUP VALIDATION")
print("="*60)

data, status = req("GET", "/health", base=BASE)
check("Backend health endpoint reachable", PASS if status==200 else FAIL, f"HTTP {status} | {data}")
check("status=healthy", PASS if data.get("status")=="healthy" else FAIL, data.get("status","?"))
check("agents=ready", PASS if data.get("agents")=="ready" else FAIL, data.get("agents","?"))

# ─────────────────────────────────────────────
# STEP 2: E2E PIPELINE
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 2: END-TO-END PIPELINE")
print("="*60)

print("\n--- 2a: Simulation Scenarios ---")
data, status = req("GET", "/simulation/scenarios")
check("GET /simulation/scenarios → 200", PASS if status==200 else FAIL, f"HTTP {status}")
scenarios = data if isinstance(data, list) else []
check("5 scenarios available", PASS if len(scenarios)==5 else WARN, f"{len(scenarios)} found")
check("sim_001 present", PASS if any(s.get("id")=="sim_001" for s in scenarios) else FAIL)
check("sim_001 has severity_label", PASS if any(s.get("severity_label") for s in scenarios if s.get("id")=="sim_001") else FAIL)

print("\n--- 2b: Run Simulation sim_001 ---")
data, status = req("POST", "/simulation/run/sim_001")
check("POST /simulation/run/sim_001 → 201", PASS if status==201 else FAIL, f"HTTP {status}")
if status == 201:
    incident_id = data.get("incident", {}).get("id")
    check("incident_id returned", PASS if incident_id else FAIL, incident_id or "MISSING")
    check("websocket_url returned", PASS if data.get("websocket_url") else FAIL, data.get("websocket_url","MISSING"))
    check("scenario metadata returned", PASS if data.get("scenario") else FAIL)
    print(f"  → incident_id: {incident_id}")
else:
    print(f"  ERROR: {json.dumps(data)[:300]}")

print("\n--- 2c: Agent Pipeline (poll 90s) ---")
if incident_id:
    print("  Polling up to 90s...")
    elapsed = 0
    final_status = "unknown"
    last_check = {}
    while elapsed < 90:
        interval = 2 if elapsed < 30 else 5
        time.sleep(interval)
        elapsed += interval
        last_check, _ = req("GET", f"/incidents/{incident_id}")
        final_status = last_check.get("status", "unknown")
        sys.stdout.write(f"\r  [{elapsed:02d}s] status={final_status}   ")
        sys.stdout.flush()
        if final_status in ("plan_ready", "plan_approved"):
            break
    print()
    check("Pipeline reaches plan_ready", PASS if final_status in ("plan_ready","plan_approved") else FAIL, f"final={final_status}")

    # Agent runs
    runs_data, _ = req("GET", f"/incidents/{incident_id}/agent-runs")
    run_names = [r.get("agent_name") for r in (runs_data if isinstance(runs_data,list) else [])]
    print(f"  Agent runs found: {run_names}")
    for expected in ["incident_commander","capacity_agent","staffing_agent","resource_agent","compliance_agent"]:
        check(f"  Run: {expected}", PASS if expected in run_names else FAIL)

    # Confidence scores
    for r in (runs_data if isinstance(runs_data,list) else []):
        conf = r.get("confidence_score")
        check(f"  {r.get('agent_name','?')} confidence_score set", PASS if conf is not None else WARN, str(conf))

print("\n--- 2d: Action Plan ---")
if incident_id:
    plan_data, plan_status = req("GET", f"/incidents/{incident_id}/action-plan")
    check("GET /action-plan → 200", PASS if plan_status==200 else FAIL, f"HTTP {plan_status}")
    if plan_status == 200:
        plan_id = plan_data.get("id")
        check("plan_id exists", PASS if plan_id else FAIL, plan_id or "MISSING")
        check("severity_label set", PASS if plan_data.get("severity_label") else FAIL, plan_data.get("severity_label","?"))
        check("priority_1_actions present", PASS if plan_data.get("priority_1_actions") else FAIL, f"{len(plan_data.get('priority_1_actions',[]))} actions")
        check("priority_2_actions present", PASS if plan_data.get("priority_2_actions") else FAIL, f"{len(plan_data.get('priority_2_actions',[]))} actions")
        check("escalation_items present", PASS if plan_data.get("escalation_items") else FAIL, f"{len(plan_data.get('escalation_items',[]))} items")
        check("compliance_status set", PASS if plan_data.get("compliance_status") else FAIL, plan_data.get("compliance_status","?"))
        check("overall_summary set", PASS if plan_data.get("overall_summary") else FAIL)
        exec_sum = plan_data.get("executive_summary")
        check("executive_summary present", PASS if exec_sum else WARN, "ai_generated="+str(exec_sum.get("ai_generated","?")) if exec_sum else "MISSING")
        if exec_sum:
            check("executive_summary.critical_risks", PASS if exec_sum.get("critical_risks") else WARN, f"{len(exec_sum.get('critical_risks',[]))} risks")
            check("executive_summary.action_plan", PASS if exec_sum.get("action_plan") else WARN, f"{len(exec_sum.get('action_plan',[]))} items")
        print(f"  → severity: {plan_data.get('severity_label')}")
        print(f"  → P1:{len(plan_data.get('priority_1_actions',[]))} P2:{len(plan_data.get('priority_2_actions',[]))} P3:{len(plan_data.get('priority_3_actions',[]))} Esc:{len(plan_data.get('escalation_items',[]))}")
        print(f"  → compliance: {plan_data.get('compliance_status')}")
        print(f"  → summary: {plan_data.get('overall_summary','')[:100]}")

print("\n--- 2e: Human Approval ---")
if plan_id:
    approve_data, approve_status = req("PATCH", f"/action-plans/{plan_id}/approve?approved_by=Operations+Manager")
    check("PATCH /approve → 200", PASS if approve_status==200 else FAIL, f"HTTP {approve_status}")
    if approve_status == 200:
        check("status=approved", PASS if approve_data.get("status")=="approved" else FAIL, approve_data.get("status","?"))
        check("approved_by set", PASS if approve_data.get("approved_by") else FAIL, approve_data.get("approved_by","?"))
        check("approved_at set", PASS if approve_data.get("approved_at") else FAIL, str(approve_data.get("approved_at",""))[:19])
        inc2, _ = req("GET", f"/incidents/{incident_id}")
        check("Incident status → plan_approved", PASS if inc2.get("status")=="plan_approved" else FAIL, inc2.get("status","?"))

print("\n--- 2f: Audit Trail ---")
if incident_id:
    audit_data, audit_status = req("GET", f"/audit-events?incident_id={incident_id}")
    check("GET /audit-events → 200", PASS if audit_status==200 else FAIL, f"HTTP {audit_status}")
    if isinstance(audit_data, list):
        event_types = [e.get("event_type") for e in audit_data]
        print(f"  Events logged: {event_types}")
        for expected in ["incident_created","agent_completed","action_plan_created","plan_approved"]:
            check(f"  Event: {expected}", PASS if expected in event_types else FAIL)
        check("Band notifications logged", PASS if "band_notification_sent" in event_types else WARN,
              f"{event_types.count('band_notification_sent')} Band events")

# ─────────────────────────────────────────────
# STEP 3: API ENDPOINT VALIDATION
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 3: API ENDPOINT VALIDATION")
print("="*60)

endpoints = [
    ("GET",   "/health",                        None,       BASE, 200),
    ("GET",   "/api/v1/simulation/scenarios",   None,       BASE, 200),
    ("GET",   "/api/v1/incidents",              None,       BASE, 200),
    ("GET",   "/api/v1/dashboard/metrics",      None,       BASE, 200),
    ("GET",   "/api/v1/audit-events",           None,       BASE, 200),
    ("GET",   "/docs",                          None,       BASE, 200),
    ("GET",   "/openapi.json",                  None,       BASE, 200),
    ("GET",   f"/api/v1/incidents/{incident_id}",None,      BASE, 200),
    ("GET",   f"/api/v1/incidents/{incident_id}/agent-runs",None, BASE, 200),
    ("GET",   f"/api/v1/incidents/{incident_id}/action-plan",None, BASE, 200),
]

for method, path, body, base, expected_code in endpoints:
    if not incident_id and "{incident_id}" in path:
        print(f"  ⚠️  [SKIP] {method} {path} — no incident_id")
        continue
    data, status = req(method, path, body, base=base)
    ok = status == expected_code
    check(f"{method} {path}", PASS if ok else FAIL, f"HTTP {status} (expected {expected_code})")

# OpenAPI schema
openapi, openapi_status = req("GET", "/openapi.json", base=BASE)
if openapi_status == 200:
    paths = list(openapi.get("paths", {}).keys())
    print(f"\n  Discovered OpenAPI paths ({len(paths)}):")
    for p in sorted(paths):
        print(f"    {p}")

# ─────────────────────────────────────────────
# STEP 4: AGENT-LEVEL VALIDATION
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 4: AGENT VALIDATION")
print("="*60)

if incident_id:
    runs_data, _ = req("GET", f"/incidents/{incident_id}/agent-runs")
    if isinstance(runs_data, list):
        for run in runs_data:
            name = run.get("agent_name", "?")
            print(f"\n  Agent: {name}")
            check(f"  {name} status=completed", PASS if run.get("status")=="completed" else FAIL, run.get("status","?"))
            check(f"  {name} confidence_score", PASS if run.get("confidence_score") is not None else WARN, str(run.get("confidence_score")))
            output = run.get("output_data") or {}
            check(f"  {name} output.summary", PASS if output.get("summary") else FAIL, str(output.get("summary",""))[:80])
            check(f"  {name} output.findings", PASS if output.get("findings") else WARN, f"{len(output.get('findings',[]))} findings")
            check(f"  {name} output.recommendations", PASS if output.get("recommendations") else WARN, f"{len(output.get('recommendations',[]))} recs")
            check(f"  {name} output.flags", PASS, f"{len(output.get('flags',[]))} flags")

# ─────────────────────────────────────────────
# STEP 5 (API side): STORE/DB VALIDATION
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 7: DATA STORE VALIDATION")
print("="*60)

# Create a second incident to test create/read
data2, s2 = req("POST", "/simulation/run/sim_002")
inc2_id = data2.get("incident",{}).get("id") if s2==201 else None
check("Create second incident (sim_002)", PASS if s2==201 else FAIL, f"HTTP {s2}")

incidents_list, ils = req("GET", "/incidents")
check("List all incidents", PASS if ils==200 else FAIL, f"{len(incidents_list) if isinstance(incidents_list,list) else '?'} incidents")

metrics, ms = req("GET", "/dashboard/metrics")
check("Dashboard metrics", PASS if ms==200 else FAIL, f"HTTP {ms}")
if ms == 200:
    check("active_incidents > 0", PASS if metrics.get("active_incidents",0) > 0 else WARN, str(metrics.get("active_incidents")))
    check("agent_runs_today > 0", PASS if metrics.get("agent_runs_today",0) > 0 else WARN, str(metrics.get("agent_runs_today")))
    check("compliance_rate_pct set", PASS if metrics.get("compliance_rate_pct") else WARN, str(metrics.get("compliance_rate_pct")))
    print(f"  → {json.dumps(metrics)[:200]}")

# Test resolve endpoint
if incident_id:
    old_inc, _ = req("GET", f"/incidents/{incident_id}")
    # Don't resolve our test incident — just verify the endpoint exists
    resolve_test, rt_s = req("PATCH", f"/incidents/{inc2_id}/resolve") if inc2_id else ({}, 0)
    check("PATCH /incidents/{id}/resolve", PASS if rt_s==200 else FAIL if rt_s not in (0,404) else WARN, f"HTTP {rt_s}")

# ─────────────────────────────────────────────
# STEP 6: BAND NOTIFICATION ENDPOINT
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 6: BAND NOTIFICATION ENDPOINT")
print("="*60)

band_payload = {
    "incident_id": incident_id or "test-001",
    "plan_id": plan_id or "plan-test",
    "message": "NOTIFY CMO: Level 3 Critical event — validation test",
    "approved_by": "QA Engineer"
}
band_data, band_status = req("POST", "/notifications/band", band_payload)
check("POST /notifications/band → 202", PASS if band_status==202 else FAIL, f"HTTP {band_status}")
if band_status == 202:
    check("status=queued", PASS if band_data.get("status")=="queued" else FAIL, band_data.get("status","?"))
    check("channel=band", PASS if band_data.get("channel")=="band" else FAIL, band_data.get("channel","?"))
    check("notification_id present", PASS if band_data.get("notification_id") else FAIL)
    check("timestamp present", PASS if band_data.get("timestamp") else FAIL)
    print(f"  → {json.dumps(band_data)}")

# ─────────────────────────────────────────────
# STEP 8: ERROR HANDLING
# ─────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 8: ERROR HANDLING")
print("="*60)

# 404 on unknown incident
d404, s404 = req("GET", "/incidents/does-not-exist-00000")
check("404 on unknown incident", PASS if s404==404 else FAIL, f"HTTP {s404}")

# 404 on unknown action plan approval
dap, sap = req("PATCH", "/action-plans/does-not-exist/approve?approved_by=test")
check("404 on unknown plan approval", PASS if sap==404 else FAIL, f"HTTP {sap}")

# 404 on unknown scenario
dsc, ssc = req("POST", "/simulation/run/sim_999")
check("404 on unknown simulation", PASS if ssc==404 else FAIL, f"HTTP {ssc}")

# Invalid incident creation (missing required fields)
bad_data, bad_status = req("POST", "/incidents", {"incident_type": "invalid_type"})
check("422 on invalid incident type", PASS if bad_status==422 else FAIL, f"HTTP {bad_status}")

# Test audit events with unknown incident — should return empty list
audit_empty, ae_s = req("GET", "/audit-events?incident_id=does-not-exist")
check("Empty audit list for unknown incident", PASS if ae_s==200 and audit_empty==[] else FAIL, f"HTTP {ae_s} | {audit_empty}")

# ─────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────
print("\n" + "="*60)
total = len(results)
passing = sum(1 for r,_ in results if r==PASS)
failing = sum(1 for r,_ in results if r==FAIL)
warning = sum(1 for r,_ in results if r==WARN)

print(f"VALIDATION SUMMARY")
print(f"  Total checks : {total}")
print(f"  PASS         : {passing}")
print(f"  FAIL         : {failing}")
print(f"  WARN         : {warning}")
print()
if failing:
    print("FAILED CHECKS:")
    for r,label in results:
        if r==FAIL:
            print(f"  ❌ {label}")
if warning:
    print("WARNINGS:")
    for r,label in results:
        if r==WARN:
            print(f"  ⚠️  {label}")
print()
score = int((passing/total)*100) if total else 0
print(f"API/BACKEND SCORE: {score}% ({passing}/{total})")
if failing == 0:
    print("STATUS: ✅ DEMO READY")
elif failing <= 3:
    print("STATUS: ⚠️  MOSTLY READY — minor issues")
else:
    print("STATUS: ❌ NOT READY — address failures above")
print("="*60)
