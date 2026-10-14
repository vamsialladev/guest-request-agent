"""Projected business value calculator. Every input is an assumption you can change; only the AI cost per email is
measured (eval/reports). This is a projection, not a measured result.

python scripts/business_case.py
python scripts/business_case.py --scenarios
python scripts/business_case.py --properties 100 --emails 30 --wage 24
"""

import argparse

MEASURED_COST_PER_EMAIL = 0.0012  # USD, Claude Haiku 5.5, final eval (docs/BUSINESS_CASE.md)


def project(properties, emails, minutes_saved, wage, comps_avoided, comp_cost, cost_per_email, hosting_per_year):
    hours = properties * emails * minutes_saved / 60 * 365
    labor = hours * wage
    comps = properties * comps_avoided * 52 * comp_cost
    run_cost = properties * emails * 365 * cost_per_email + hosting_per_year
    value = labor + comps
    return {
        "hours": hours,
        "labor": labor,
        "comps": comps,
        "value": value,
        "run_cost": run_cost,
        "net": value - run_cost,
        "roi": value / run_cost if run_cost else float("inf"),
    }


SCENARIOS = {
    # name: (emails per property per day, minutes saved per email, unapproved comps avoided per property per week)
    "Pessimistic": (15, 2.0, 0.25),
    "Base": (30, 4.0, 0.5),
    "Optimistic": (45, 6.0, 1.0),
}


def print_one(a, r):
    rows = [
        ("Staff hours saved per year", f"{r['hours']:,.0f}"),
        ("Value of staff time", f"${r['labor']:,.0f}"),
        ("Unapproved comps and refunds avoided", f"${r['comps']:,.0f}"),
        ("Total projected value per year", f"${r['value']:,.0f}"),
        ("Running cost per year (AI + hosting)", f"${r['run_cost']:,.0f}"),
        ("Net projected value per year", f"${r['net']:,.0f}"),
        ("Return on running cost", f"{r['roi']:,.0f}x"),
    ]
    print(f"\nProjection for {a.properties} properties (assumptions, not measured results)\n")
    for label, value in rows:
        print(f"  {label:<40} {value:>12}")
    print()


def scenarios(a) -> dict:
    print(f"\nScenarios for {a.properties} properties (assumptions, not measured results)\n")
    header = f"  {'Scenario':<12} {'Emails/day':>10} {'Min saved':>9} {'Comps/wk':>8} {'Value/yr':>12} {'Net/yr':>12}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    out = {}
    for name, (emails, minutes, comps) in SCENARIOS.items():
        r = project(a.properties, emails, minutes, a.wage, comps, a.comp_cost, a.cost_per_email, a.hosting)
        out[name] = r
        print(f"  {name:<12} {emails:>10} {minutes:>9} {comps:>8} ${r['value']:>11,.0f} ${r['net']:>11,.0f}")
    print()
    return out


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--properties", type=int, default=2)
    p.add_argument("--emails", type=float, default=30, help="guest emails per property per day")
    p.add_argument("--minutes-saved", type=float, default=4, help="minutes saved per email (draft vs from scratch)")
    p.add_argument("--wage", type=float, default=22, help="loaded front-desk / reservations cost per hour, USD")
    p.add_argument("--comps-avoided", type=float, default=0.5, help="unapproved comps or refunds avoided per week")
    p.add_argument("--comp-cost", type=float, default=100, help="average unapproved comp or refund, USD")
    p.add_argument("--cost-per-email", type=float, default=MEASURED_COST_PER_EMAIL, help="AI cost per email, USD")
    p.add_argument("--hosting", type=float, default=240, help="hosting per year, USD")
    p.add_argument("--scenarios", action="store_true", help="show pessimistic, base and optimistic cases")
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    if a.scenarios:
        return scenarios(a)
    r = project(
        a.properties, a.emails, a.minutes_saved, a.wage, a.comps_avoided, a.comp_cost, a.cost_per_email, a.hosting
    )
    print_one(a, r)
    return r


if __name__ == "__main__":
    main()
