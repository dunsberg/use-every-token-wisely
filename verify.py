import sys
sys.path.insert(0, ".")
from ui.usage_card import ServiceCard

c = ServiceCard("ZCODE")
print("collapsed:", c.is_collapsed)
c.set_collapsed(True)
print("after collapse:", c.is_collapsed)
print("model_label text when collapsed:", c.model_label.text())
c.set_collapsed(False)
print("after expand:", c.is_collapsed)
print("OK")
