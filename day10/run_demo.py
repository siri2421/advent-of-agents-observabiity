#!/usr/bin/env python3
"""Interactive Video Demo Runner for Advent of Agents Season 3 - Day 10.

Usage:
    python3 run_demo.py --mode unshielded
    python3 run_demo.py --mode shielded
    python3 run_demo.py --mode compare
"""

import argparse
import sys
import time
from agent_unshielded import run_unshielded_agent
from agent_shielded import run_shielded_agent

def main():
    parser = argparse.ArgumentParser(description="Advent of Agents Day 10 Demo Runner")
    parser.add_argument(
        "--mode",
        choices=["unshielded", "shielded", "compare"],
        default="compare",
        help="Which agent configuration to run (default: compare)"
    )
    args = parser.parse_args()

    if args.mode == "unshielded":
        run_unshielded_agent()
    elif args.mode == "shielded":
        run_shielded_agent()
    elif args.mode == "compare":
        print("\n" + "#" * 74)
        print("# ADVENT OF AGENTS SEASON 3 - DAY 10: PROMPT SHIELDING & MODEL ARMOR")
        print("#" * 74 + "\n")
        
        print(">>> ACT 1: Running Agent 1 (Unshielded / Direct Egress)...")
        time.sleep(1)
        run_unshielded_agent()
        
        print("\n" + "-" * 74)
        print(">>> ACT 2: Attaching Model Armor Template to Agent Gateway Egress...")
        print(">>> Template: agent-prompt-shield | Filter: PI_AND_JAILBREAK (MEDIUM_AND_ABOVE)")
        print("-" * 74 + "\n")
        time.sleep(2)
        
        print(">>> ACT 3: Running Agent 2 (Shielded / Gateway Model Armor Guardrail)...")
        time.sleep(1)
        run_shielded_agent()
        
        print("\n" + "#" * 74)
        print("# RESULT SUMMARY:")
        print("# • Unshielded Agent: Fell for indirect prompt injection -> EXPLOITED (Admin Added)")
        print("# • Shielded Agent:   Model Armor intercepted diff -> QUARANTINED (Zero Tool Calls)")
        print("#" * 74 + "\n")

if __name__ == "__main__":
    main()
