"""
Simulation Engine — Pre-built scenarios for demo and tabletop exercises.
"""
from shared.schemas import IncidentCreate, IncidentType, SimulationScenario


SIMULATION_SCENARIOS = [
    SimulationScenario(
        id="sim_001",
        name="Mass Casualty Event — Critical",
        description="50 trauma patients incoming from highway pile-up. ICU near capacity, severe nurse and ventilator shortage.",
        severity_label="LEVEL 3 — CRITICAL",
        incident_data=IncidentCreate(
            incident_type=IncidentType.MASS_CASUALTY,
            incoming_patients=50,
            icu_occupancy_pct=92.0,
            ed_occupancy_pct=78.0,
            available_nurses=4,
            available_ventilators=3,
            available_icu_beds=2,
            total_icu_beds=25,
            blood_bank_units=30,
            reported_by="simulation_engine",
            additional_context="Highway pile-up: I-95 multi-vehicle collision. EMS on scene with 50 confirmed patients.",
        ),
        tags=["mass_casualty", "critical", "ventilator_shortage", "nurse_shortage"],
    ),
    SimulationScenario(
        id="sim_002",
        name="ED Overload — Major",
        description="Flu season surge pushing ED to breaking point. Staff adequate but capacity critical.",
        severity_label="LEVEL 2 — MAJOR",
        incident_data=IncidentCreate(
            incident_type=IncidentType.ER_OVERLOAD,
            incoming_patients=30,
            icu_occupancy_pct=72.0,
            ed_occupancy_pct=95.0,
            available_nurses=12,
            available_ventilators=10,
            available_icu_beds=5,
            total_icu_beds=25,
            blood_bank_units=80,
            reported_by="simulation_engine",
            additional_context="Influenza season peak. ED holding 15 admitted patients awaiting floor beds.",
        ),
        tags=["ed_overload", "major", "capacity"],
    ),
    SimulationScenario(
        id="sim_003",
        name="ICU Saturation — Critical",
        description="ICU at 98% due to post-surgical complications. New critical patients incoming from city-wide emergency.",
        severity_label="LEVEL 3 — CRITICAL",
        incident_data=IncidentCreate(
            incident_type=IncidentType.ICU_SATURATION,
            incoming_patients=15,
            icu_occupancy_pct=98.0,
            ed_occupancy_pct=65.0,
            available_nurses=8,
            available_ventilators=5,
            available_icu_beds=1,
            total_icu_beds=25,
            blood_bank_units=60,
            reported_by="simulation_engine",
            additional_context="3 post-cardiac-surgery patients deteriorated overnight. Regional hospital requesting transfers.",
        ),
        tags=["icu_saturation", "critical"],
    ),
    SimulationScenario(
        id="sim_004",
        name="Staff Shortage Crisis — Critical",
        description="40% nursing staff called out sick. Hospital at normal volume but staffing at dangerous levels.",
        severity_label="LEVEL 3 — CRITICAL",
        incident_data=IncidentCreate(
            incident_type=IncidentType.STAFF_SHORTAGE,
            incoming_patients=20,
            icu_occupancy_pct=70.0,
            ed_occupancy_pct=60.0,
            available_nurses=3,
            available_ventilators=15,
            available_icu_beds=7,
            total_icu_beds=25,
            blood_bank_units=90,
            reported_by="simulation_engine",
            additional_context="Norovirus outbreak among nursing staff. 18 nurses called out across all shifts.",
        ),
        tags=["staff_shortage", "critical"],
    ),
    SimulationScenario(
        id="sim_005",
        name="Resource Shortage — Major",
        description="Supply chain disruption causing critical medication and equipment shortages.",
        severity_label="LEVEL 2 — MAJOR",
        incident_data=IncidentCreate(
            incident_type=IncidentType.RESOURCE_SHORTAGE,
            incoming_patients=10,
            icu_occupancy_pct=65.0,
            ed_occupancy_pct=55.0,
            available_nurses=20,
            available_ventilators=2,
            available_icu_beds=9,
            total_icu_beds=25,
            blood_bank_units=15,
            reported_by="simulation_engine",
            additional_context="National supply chain disruption. Ventilator shipment delayed. Blood bank critically low.",
        ),
        tags=["resource_shortage", "major", "supply_chain"],
    ),
]


def get_scenario(scenario_id: str) -> SimulationScenario:
    for s in SIMULATION_SCENARIOS:
        if s.id == scenario_id:
            return s
    raise ValueError(f"Scenario {scenario_id} not found")


def list_scenarios():
    return SIMULATION_SCENARIOS
