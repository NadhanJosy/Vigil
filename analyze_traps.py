#!/usr/bin/env python
"""
Analyze Bull Trap Detection Performance

Reads evaluated alerts from the database and identifies which trap_reasons
are most correlated with winning vs losing trades. This helps tune penalty
weights in the assess_trap function.
"""

import json
from database import get_conn
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_trap_performance():
    """
    Analyzes historical alerts to see which trap reasons correlate 
    most accurately with actual trade outcomes.
    """
    conn = get_conn()
    cursor = conn.cursor()
    
    # We look for alerts where our trap logic fired AND we have an outcome recorded
    cursor.execute("""
        SELECT trap_reasons, outcome_result, outcome_pct
        FROM alerts
        WHERE trap_reasons IS NOT NULL AND outcome_result IS NOT NULL
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\n[!] No evaluated trap data found. Run /backfill and /evaluate first.")
        return

    reason_stats = {}
    total_evaluated = len(rows)
    
    for reasons_json, result, pct in rows:
        try:
            reasons = json.loads(reasons_json)
        except:
            continue
            
        for r in reasons:
            if r not in reason_stats:
                reason_stats[r] = {"wins": 0, "losses": 0, "pct_sum": 0.0}
            
            reason_stats[r]["pct_sum"] += (pct or 0)
            if result == "WIN":
                reason_stats[r]["wins"] += 1
            else:
                reason_stats[r]["losses"] += 1

    print(f"\nAnalyzed {total_evaluated} evaluated trap events.")
    print("\n" + "="*95)
    print(f"{'TRAP REASON PERFORMANCE ANALYSIS':^95}")
    print("="*95)
    print(f"{'Trap Reason':<65} | {'Count':<6} | {'Win Rate':<8} | {'Avg Pct':<8}")
    print("-" * 95)

    for reason, data in sorted(reason_stats.items(), key=lambda x: x[1]['wins'] + x[1]['losses'], reverse=True):
        total = data["wins"] + data["losses"]
        win_rate = (data["wins"] / total) * 100
        avg_pct = data["pct_sum"] / total
        print(f"{reason:<65} | {total:<6} | {win_rate:>7.1f}% | {avg_pct:>7.1f}%")

    print("="*95)
    print("\nInterpretation:")
    print("  HIGH WIN RATE (>70%) on a reason = penalty may be TOO AGGRESSIVE")
    print("  LOW WIN RATE (<30%) on a reason = penalty is WORKING WELL")
    print("  Count = number of times this reason appeared in evaluated alerts")
    print()


if __name__ == "__main__":
    analyze_trap_performance()
