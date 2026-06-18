"""
Full end-to-end test of the Band coordination workflow.
Creates a room, adds all agents, posts 4 lifecycle messages.
"""
import asyncio
import httpx

CMD_KEY = "band_a_1781718770_qKOH2waRBUF8Ue0HZ9af8BqQxby4fJ0f"
CAP_KEY = "band_a_1781718952_87o6fq_cnIbd0OE1wzkjXltOzWltOrn9"
STF_KEY = "band_a_1781718827_Y2MvuTAm2nHlYG3nk9Koy09z_SDpXIKv"
RES_KEY = "band_a_1781718887_5-rn5N4yfiFoZJ35wR2SAl5gPRIksNAI"
CPL_KEY = "band_a_1781718935_pX0RZVt7bKCPCz2KAci9C4tuymVXsqH3"

CMD_ID = "0b8adbe2-db87-4a2c-8a0b-31b8bc57263e"
CAP_ID = "131a3aa2-8072-487a-9570-d1690ac30e9b"
STF_ID = "7fcc2a8f-b48d-4127-9850-cb329161e98b"
RES_ID = "fbb863c1-6041-4355-9cef-3d9ff56ce236"
CPL_ID = "22134cc9-6d27-4eff-8019-e1d6d4ec1d65"

BASE = "https://app.band.ai/api/v1"


async def run():
    async with httpx.AsyncClient(timeout=20) as c:
        # 1. Create room
        r = await c.post(
            f"{BASE}/agent/chats",
            headers={"X-API-Key": CMD_KEY, "Content-Type": "application/json"},
            json={"chat": {"title": "MedSync | LEVEL 3 CRITICAL | 40 pts | E2E"}},
        )
        assert r.status_code == 201, f"Create room failed: {r.text}"
        chat_id = r.json()["data"]["id"]
        print(f"1. Room created: {chat_id}")

        # 2. Invite specialists
        url_p = f"{BASE}/agent/chats/{chat_id}/participants"
        for name, pid in [("capacity", CAP_ID), ("staffing", STF_ID), ("resource", RES_ID), ("compliance", CPL_ID)]:
            r2 = await c.post(
                url_p,
                headers={"X-API-Key": CMD_KEY, "Content-Type": "application/json"},
                json={"participant": {"participant_id": pid}},
            )
            assert r2.status_code == 201, f"Add {name} failed: {r2.text}"
            print(f"2. Added {name}: OK")

        url_m = f"{BASE}/agent/chats/{chat_id}/messages"

        # 3. Commander dispatches
        r3 = await c.post(url_m,
            headers={"X-API-Key": CMD_KEY, "Content-Type": "application/json"},
            json={"message": {
                "content": "[DISPATCH] INCIDENT COMMANDER: LEVEL 3 CRITICAL — 40 incoming patients, ICU 92%. Activating all specialist agents. @capacity-agent begin assessment.",
                "mentions": [{"id": CAP_ID, "handle": "1821ragav/capacity-agent", "name": "Capacity Agent", "kind": "mention"}],
            }})
        assert r3.status_code == 201, f"Dispatch failed: {r3.text}"
        print(f"3. Commander dispatch: OK — msg={r3.json()['data']['id'][:8]}")

        # 4. Capacity reports
        r4 = await c.post(url_m,
            headers={"X-API-Key": CAP_KEY, "Content-Type": "application/json"},
            json={"message": {
                "content": "[REPORT] CAPACITY AGENT: ICU projected 118%. 8 stable patients transferable to Step-Down. Recommend surge protocol Level 3A. @incident-commander",
                "mentions": [{"id": CMD_ID, "handle": "1821ragav/incident-commander", "name": "Incident Commander", "kind": "mention"}],
            }})
        assert r4.status_code == 201, f"Capacity report failed: {r4.text}"
        print(f"4. Capacity report: OK — msg={r4.json()['data']['id'][:8]}")

        # 5. Staffing reports
        r5 = await c.post(url_m,
            headers={"X-API-Key": STF_KEY, "Content-Type": "application/json"},
            json={"message": {
                "content": "[REPORT] STAFFING AGENT: Nurse deficit 12. On-call: 8 (30min). Agency: 6. CMO auth needed. @incident-commander",
                "mentions": [{"id": CMD_ID, "handle": "1821ragav/incident-commander", "name": "Incident Commander", "kind": "mention"}],
            }})
        assert r5.status_code == 201, f"Staffing report failed: {r5.text}"
        print(f"5. Staffing report: OK — msg={r5.json()['data']['id'][:8]}")

        # 6. Compliance PLAN_READY
        r6 = await c.post(url_m,
            headers={"X-API-Key": CPL_KEY, "Content-Type": "application/json"},
            json={"message": {
                "content": "[PLAN_READY] ACTION PLAN SYNTHESIZED — Awaiting human authorization. Immediate: 3. Follow-up: 4. Compliance: APPROVED. @incident-commander",
                "mentions": [{"id": CMD_ID, "handle": "1821ragav/incident-commander", "name": "Incident Commander", "kind": "mention"}],
            }})
        assert r6.status_code == 201, f"Plan ready failed: {r6.text}"
        print(f"6. Plan ready: OK — msg={r6.json()['data']['id'][:8]}")

        print()
        print("=" * 60)
        print("ALL 6 STEPS PASSED — Band integration is LIVE")
        print(f"Room URL: https://app.band.ai/chats/{chat_id}")
        print("=" * 60)


asyncio.run(run())
