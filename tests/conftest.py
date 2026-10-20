import os
import sys
from pathlib import Path

# Tests never call the real API.
os.environ["CHATQUADRA_MOCK"] = "1"
os.environ.setdefault("CHATQUADRA_MIN_WORDS", "20")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
