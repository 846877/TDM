import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("TDM_SANDBOX", "local")
os.environ["TDM_DATA_DIR"] = tempfile.mkdtemp(prefix="tdm-data-")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
