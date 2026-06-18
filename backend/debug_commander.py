"""Debug script to run the commander analyze and capture the real exception."""
import asyncio, sys, traceback, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def debug():
    from agents.incident_commander import IncidentCommanderAgent
    
    incident_id = "debug-001"
    incident_data = {
        "incoming_patients": 40,
        "icu_occupancy_pct": 91.0,
        "ed_occupancy_pct": 88.0,
        "available_nurses": 12,
        "available_ventilators": 3,
        "blood_bank_units": 60,
        "severity_level": 3,
        "total_icu_beds": 20,
        "incident_type": "mass_casualty",
    }

    commander = IncidentCommanderAgent(incident_id)
    try:
        result = await commander.analyze(incident_data)
        print("SUCCESS:", result.get("status"))
    except Exception as e:
        print("ERROR:", type(e).__name__, str(e))
        traceback.print_exc()

asyncio.run(debug())
