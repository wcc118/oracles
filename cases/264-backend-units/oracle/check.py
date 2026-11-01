"""Focused units check of the workspace's actual station reaction method."""
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import numpy as np


def evaluate(workspace):
    # Explicit boundary fixtures: identity attitude and standard gravity.
    # Geometry construction, flight dynamics and aerodynamic models are out of scope.
    package = ModuleType("unit_probe")
    package.__path__ = []
    sys.modules[package.__name__] = package
    boundaries = {
        "aircraft_transient": {"G_N": np.array([0., 0., 9.80665]), "IN_M": .0254},
        "conventions": {"rotation_matrix": lambda q: np.eye(3)},
        "aero_strip_provider": {"component_of": lambda row: "unused"},
    }
    for name, values in boundaries.items():
        module = ModuleType("unit_probe." + name)
        module.__dict__.update(values)
        sys.modules[module.__name__] = module
    spec = importlib.util.spec_from_file_location(
        "unit_probe.station_loads", workspace / "station_loads.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = module.StationModel.__new__(module.StationModel)
    model.cg = np.zeros(3)
    model.element_names = ["zero-applied"]
    model.prepared = [{
        "id": "known-part", "kind": "part", "reference": np.zeros(3),
        # lbf*s^2/in, NOT slug: weight divided by gravity in inches/s^2.
        "masses": np.array([12. / (9.80665 / .0254)]),
        "positions": np.zeros((1, 3)),
        "inertias": np.array([np.diag([2., 3., 4.])]),  # lbf*in*s^2
        "weights": np.ones(1), "points": np.zeros((1, 3)), "panel_frame": None,
    }]
    state = SimpleNamespace(omega_B_radps=np.zeros(3), v_CG_B_mps=np.zeros(3),
                            q_NB=np.array([1., 0., 0., 0.]))
    field = {"ledger": [{"name": "zero-applied", "force_B_lbf": [0., 0., 0.],
                         "free_couple_B_in_lbf": [0., 0., 0.]}]}
    results = []
    # Body z points down; reactions act on the retained part. An upward 12 lbf
    # support balances weight. With downward acceleration 2g, net reaction is +12.
    # At zero omega and a CG-located mass, intrinsic Ixx=2 and alpha_x=3 require +6.
    probes = [
        ("weight", [0., 0., 0.], [0., 0., 0.], [0., 0., -12.], [0., 0., 0.]),
        ("acceleration", [0., 0., 19.6133], [0., 0., 0.], [0., 0., 12.], [0., 0., 0.]),
        ("inertia-couple", [0., 0., 0.], [3., 0., 0.], [0., 0., -12.], [6., 0., 0.]),
    ]
    for name, acceleration, alpha, force, moment in probes:
        derivative = SimpleNamespace(vdot_B_mps2=np.array(acceleration),
                                     omegadot_B_radps2=np.array(alpha))
        actual = model.evaluate(state, field, derivative)["stations"][0]
        okay = all(np.allclose(actual[key], expected, rtol=1e-12, atol=1e-12)
                   for key, expected in [("force_B_lbf", force), ("moment_B_in_lbf", moment)])
        results.append({"name": name, "ok": bool(okay), "actual": actual,
                        "expected_force_B_lbf": force, "expected_moment_B_in_lbf": moment})
    return {"ok": all(item["ok"] for item in results), "checks": results}


if __name__ == "__main__":
    try:
        result = evaluate(Path(sys.argv[1]))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc)}))
        sys.exit(2)
    print(json.dumps(result))
    sys.exit(0 if result["ok"] else 1)
