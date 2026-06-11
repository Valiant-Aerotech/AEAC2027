#!/usr/bin/env python3
"""AEAC Task 2 - Vion autonomous fire extinguishing (GCS offload).

Usage:
    python missions/task2_vion_auto_extinguish.py
    python missions/task2_vion_auto_extinguish.py --sim
    python missions/task2_vion_auto_extinguish.py --connection COM5 --baud 57600
"""

from valiant.autonomy.orchestrator import main

if __name__ == "__main__":
    main()
