from importlib import util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "custom_components" / "hsv_utilities_energy"


def load_component_module(module_name: str):
    module_path = COMPONENT_DIR / f"{module_name}.py"
    spec = util.spec_from_file_location(
        f"hsv_utilities_energy_{module_name}", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
