from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from models.experiment import Experiment
from gui.panels.properties_panel import PropertiesPanel

app = QApplication.instance() or QApplication([])

experiment = Experiment(experiment_id="test-base-model-ui")
panel = PropertiesPanel(experiment)

panel.set_base_model_choices([
    "dreamshaperXL_alpha2Xl10.safetensors",
    "juggernautXL_v8Rundiffusion.safetensors",
])

assert panel.base_model_list.count() == 2
assert panel.base_model_selection_label.text() == "0 base models selected"

panel.base_model_list.item(0).setCheckState(Qt.Checked)
panel.base_model_list.item(1).setCheckState(Qt.Checked)

assert len(experiment.generation.base_models) == 2
assert len(experiment.generation.base_models) == 2
assert panel.base_model_selection_label.text() == "2 base models selected"

print("Base model choices load: OK")
print("Base model multi-selection: OK")
print("Base model selection counter: OK")
print("=== ALL BASE MODEL UI TESTS PASSED ===")
