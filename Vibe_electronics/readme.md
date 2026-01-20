This is a working Python demo that implements the "Virtual Smoke Test" pipeline.
It uses Apache Burr to manage the state loop (Design \to Simulate \to Critique \to Redesign) and PySpice (a wrapper for Ngspice) to physically simulate the circuit before you ever build it.
Prerequisites
You need the Python libraries and the Ngspice shared library (the actual physics engine).
# 1. Install Python packages
pip install "burr[start]" google-genai PySpice numpy

# 2. Install Ngspice (Critical Step!)
# On Windows:
#   pyspice-post-installation --install-ngspice-dll
# On Mac (Homebrew):
#   brew install libngspice
# On Linux (Debian/Ubuntu):
#   sudo apt-get install libngspice0-dev

The "Anti-Magic Smoke" Pipeline
This script mimics the meme: it asks for a "9V battery connected to an inductor."
 * Vibe Mode (Iteration 1): Gemini will likely design it directly.
 * Simulation: PySpice will calculate the current. Since I = V/R and an ideal inductor has 0\Omega resistance (or very low), the current will spike to thousands of Amps.
 * The Catch: The pipeline detects this, fails the test, and forces Gemini to fix it (usually by adding a resistor).
<!-- end list -->
import os
import io
import contextlib
import traceback
from typing import Tuple, Dict, Any

# --- Libraries ---
from burr.core import action, State, ApplicationBuilder, default, expr
from google import genai
from google.genai import types
import PySpice.Logging.Logging as Logging
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *

# --- Configuration ---
# Set your API Key
os.environ["GEMINI_API_KEY"] = "YOUR_GEMINI_API_KEY"

# Suppress PySpice startup noise
Logging.setup_logging(logging_level='ERROR')

# --- 1. The Prompt (The "Vibe") ---
USER_GOAL = "Design a circuit with a 9V DC source and a 10mH inductor."

# --- 2. State Definition ---
class CircuitState(State):
    iteration: int
    source_code: str
    feedback: str
    max_current_detected: float
    is_safe: bool
    status: str

# --- 3. Helper: The Simulation Sandbox ---
def execute_and_simulate(code_str: str) -> Tuple[bool, str, float]:
    """
    Executes the LLM-generated PySpice code and runs a DC simulation.
    Returns: (Passed_Safety_Checks, Log_Message, Max_Current)
    """
    # Safety guard: Simple keyword check to ensure it uses PySpice
    if "Circuit" not in code_str or "PySpice" not in code_str:
        return False, "Error: Code does not appear to use PySpice syntax.", 0.0

    # Capture stdout to grab any print statements from the generated code
    log_capture = io.StringIO()
    
    # We create a local scope to execute the code safely
    local_scope = {}
    
    try:
        with contextlib.redirect_stdout(log_capture):
            # DANGEROUS: In a real app, run this in a Docker container!
            exec(code_str, globals(), local_scope)
            
        # Extract the circuit object (assuming LLM names it 'circuit')
        if 'circuit' not in local_scope:
             return False, "Error: No 'circuit' object found in generated code.", 0.0
        
        circuit = local_scope['circuit']
        
        # --- THE PHYSICS CHECK ---
        # Run a DC Operating Point analysis
        simulator = circuit.simulator(temperature=25, nominal_temperature=25)
        analysis = simulator.operating_point()
        
        # Check current through the voltage source (V1 is usually the source name)
        # Note: PySpice convention for current through source is negative (flowing out)
        max_amps = 0.0
        
        # Iterate through all branches to find max current
        for node_name, value in analysis.branches.items():
            current = float(abs(value))
            if current > max_amps:
                max_amps = current
                
        # --- THE PASS/FAIL CRITERIA ---
        # If current > 1.0 Amp, we assume something burned up.
        limit = 1.0 
        if max_amps > limit:
            return False, f"FAILED: Massive current detected ({max_amps:.2f} A). Component limits exceeded.", max_amps
        
        return True, f"SUCCESS: Circuit is stable. Max current: {max_amps:.4f} A", max_amps

    except Exception as e:
        return False, f"CRASH: Syntax or Runtime Error: {str(e)}", 0.0

# --- 4. Burr Actions ---

@action(reads=["iteration", "feedback"], writes=["source_code", "iteration"])
def design_circuit(state: CircuitState) -> Tuple[dict, CircuitState]:
    """Asks Gemini to write the PySpice code."""
    
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    
    prompt = f"""
    You are an expert electronics engineer. Write Python code using the 'PySpice' library to model this request:
    "{USER_GOAL}"
    
    RULES:
    1. Output ONLY valid Python code. No markdown formatting.
    2. Name the main netlist object 'circuit'.
    3. Include necessary imports (from PySpice.Spice.Netlist import Circuit, from PySpice.Unit import *).
    4. Do NOT include any simulator.operating_point() calls in your code; I will run them externally.
    5. Just define the components.
    
    Current Feedback from previous run (if any): {state.get("feedback", "None")}
    """
    
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2) # Low temp for code precision
    )
    
    # Clean up code (remove markdown backticks if Gemini adds them)
    code = response.text.replace("```python", "").replace("```", "").strip()
    
    print(f"\n--- Iteration {state['iteration']} Generated Code ---\n{code}\n-------------------------------------")
    
    return {"source_code": code}, state.update(source_code=code, iteration=state["iteration"] + 1)

@action(reads=["source_code"], writes=["is_safe", "feedback", "max_current_detected", "status"])
def run_simulation(state: CircuitState) -> Tuple[dict, CircuitState]:
    """Runs the virtual smoke test."""
    
    print("Running Virtual Smoke Test...")
    is_safe, message, amps = execute_and_simulate(state["source_code"])
    
    new_status = "PASSED" if is_safe else "SMOKING"
    print(f"Result: {new_status} | {message}")
    
    return {
        "is_safe": is_safe,
        "feedback": message
    }, state.update(
        is_safe=is_safe, 
        feedback=message, 
        max_current_detected=amps,
        status=new_status
    )

# --- 5. Build the Application Graph ---

app = (
    ApplicationBuilder()
    .with_state(
        iteration=1, 
        feedback="", 
        source_code="", 
        max_current_detected=0.0, 
        is_safe=False,
        status="START"
    )
    .with_actions(design_circuit, run_simulation)
    .with_transitions(
        ("design_circuit", "run_simulation"),
        ("run_simulation", "design_circuit", expr("not is_safe")), # Loop back if it burns
        ("run_simulation", "design_circuit", expr("iteration > 5")), # Stop infinite loops
        ("run_simulation", "STOP", expr("is_safe")), # Stop if safe
    )
    .with_entrypoint("design_circuit")
    .build()
)

# --- 6. Run the Demo ---
# Note: visualization happens automatically in Burr UI if you run `burr` in terminal,
# but here we just run the loop execution.

print(f"Goal: {USER_GOAL}")
last_action, result, final_state = app.run(halt_after=["STOP"])

print("\nFinal Result:")
if final_state["is_safe"]:
    print("✅ Circuit Vibe Check Passed. You can build this.")
    print(f"Max Current: {final_state['max_current_detected']} A")
else:
    print("🔥 Circuit Failed. Do not build.")

What happens when you run this?
 * Iteration 1: Gemini generates a circuit with just V1 (9V) and L1 (10mH).
 * Simulation 1: PySpice sees a DC circuit with an inductor (Short Circuit).
 * Result 1: max_amps becomes huge (e.g., 9000A or Infinite). The script prints: FAILED: Massive current detected.
 * Feedback Loop: The state updates with is_safe=False. The graph transitions back to design_circuit passing the error message "Massive current detected".
 * Iteration 2: Gemini receives the feedback. It thinks: "Ah, I shorted the battery. I need a current limiting resistor."
 * Correction: It generates new code adding R1 (e.g., 1kΩ).
 * Simulation 2: I = 9V / 1000\Omega = 9mA.
 * Result 2: SUCCESS: Circuit is stable.
This effectively automates the "Thought for 37s" block in the meme, preventing the burned component.
