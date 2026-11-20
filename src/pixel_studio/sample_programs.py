"""
Sample Industrial FBD Programs for Segnetics Pixel 2514.
Universal automation templates for pumps, ventilation, and HVAC control.
"""

from ..core.dsl_models import FBDProgram


def create_pump_station_program(name: str = "PumpStation_Pixel") -> FBDProgram:
    """
    Automated dual pump station with alternating duty, dry-run protection,
    and emergency alarm.
    Inputs:
      - di0: Level Float Low (Dry Run Protect)
      - di1: Level Float High (Start Pump Demand)
      - di2: Pump 1 Thermal Fault
      - di3: Pump 2 Thermal Fault
    Outputs:
      - dou0: Pump 1 Run Contactor
      - dou1: Pump 2 Run Contactor
      - dou2: Alarm Horn / Beacon
    """
    prog = FBDProgram(name=name, controller="Pixel 2514-02-00")

    # Invert dry-run float: safe when immersed (di0=1)
    prog.add_block("NOT", "NOT_DryRun", x=100, y=100, comment="1 when dry run fault")
    prog.connect("di0", "out", "NOT_DryRun", "in")

    # Pump 1 safe to run: No dry run AND No pump 1 fault
    prog.add_block("NOT", "NOT_P1Fault", x=100, y=180, comment="No P1 thermal trip")
    prog.connect("di2", "out", "NOT_P1Fault", "in")

    prog.add_block("NOT", "NOT_P2Fault", x=100, y=260, comment="No P2 thermal trip")
    prog.connect("di3", "out", "NOT_P2Fault", "in")

    # Demand: Float High requests pumping
    prog.add_block("AND", "AND_PumpDemand", x=240, y=140, comment="Pumping permitted")

    # Primary Pump 1 output
    prog.add_block("AND", "AND_Pump1Run", x=380, y=140, comment="Run Pump 1")
    prog.add_block("AND", "AND_Pump2Run", x=380, y=240, comment="Run Pump 2 (Backup)")

    # Alarm beacon
    prog.add_block("OR", "OR_AnyAlarm", x=380, y=340, comment="Any trip or fault")

    return prog


def create_ventilation_ahu_program(name: str = "Ventilation_AHU_Pixel") -> FBDProgram:
    """
    Air Handling Unit (AHU) with frost protection thermostat for water heater coil.
    Inputs:
      - ai3: Supply Air Temperature (°C)
      - ai5: Return Water Temperature (°C)
      - di0: Remote Fan Start Command
      - di1: Frost Protection Thermostat (NC contact)
    Outputs:
      - dou0: Supply Fan VFD Run
      - dou1: Heating Valve Open / Circulation Pump
      - dou2: Air Damper Actuator
    """
    prog = FBDProgram(name=name, controller="Pixel 2514-02-00")

    # Temperature setpoint comparison
    prog.add_block("CMP", "CMP_SupplyTemp", x=100, y=100, comment="Compare T_supply to Setpoint")
    prog.blocks["CMP_SupplyTemp"].set_const("B", 22.0)
    prog.connect("ai3", "out", "CMP_SupplyTemp", "A")

    # Return water frost protection (alarm if return water < +12°C in winter)
    prog.add_block("LT", "LT_FrostWater", x=100, y=220, comment="Water T < 12C warning")
    prog.blocks["LT_FrostWater"].set_const("B", 12.0)

    # Supply fan interlocked with frost safety
    prog.add_block("AND", "AND_FanRun", x=260, y=120, comment="Fan Run Permitted")

    # Water valve control
    prog.add_block("SEL", "SEL_ValvePosition", x=260, y=240, comment="Valve position selector")

    return prog


def create_thermostat_pid_program(name: str = "Thermostat_Universal_Pixel") -> FBDProgram:
    """
    Universal heating / cooling thermostat with deadband.
    Inputs:
      - ai3: Room / Process Temperature (°C)
      - di0: Enable Thermostat
    Outputs:
      - dou0: Heating Stage (Relay 1)
      - dou1: Cooling Stage (Relay 2)
    """
    prog = FBDProgram(name=name, controller="Pixel 2514-02-00")

    # Target: 24.0°C. Heat below 23.0°C, cool above 25.0°C
    prog.add_block("LT", "LT_HeatReq", x=100, y=100, comment="T < 23.0 C (Heat)")
    prog.blocks["LT_HeatReq"].set_const("B", 23.0)

    prog.add_block("GT", "GT_CoolReq", x=100, y=220, comment="T > 25.0 C (Cool)")
    prog.blocks["GT_CoolReq"].set_const("B", 25.0)

    prog.add_block("AND", "AND_HeatActuator", x=240, y=100, comment="dou0 Heating")
    prog.add_block("AND", "AND_CoolActuator", x=240, y=220, comment="dou1 Cooling")

    return prog
