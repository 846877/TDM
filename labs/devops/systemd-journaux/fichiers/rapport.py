"""Écrit une ligne de rapport toutes les 10 secondes (visible avec journalctl -u rapport)."""
import time
from datetime import datetime

while True:
    print(f"rapport généré à {datetime.now():%H:%M:%S}", flush=True)
    time.sleep(10)
