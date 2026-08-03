"""
Generate synthetic 10-year flight fare training data.
Produces realistic price patterns based on:
  - Days to departure (last-minute premium)
  - Day of week (Tue/Wed cheap, Fri/Sun expensive)
  - Month (peak holiday months expensive)
  - Route baseline price
  - Random noise
"""
import random
import csv
import os
from datetime import date, timedelta

# Top 20 US routes with realistic baseline prices
ROUTES = [
    ("JFK", "LAX", 280), ("LAX", "JFK", 280), ("ORD", "LAX", 240),
    ("JFK", "MIA", 180), ("LAX", "SFO", 120), ("ORD", "DFW", 160),
    ("ATL", "LAX", 260), ("JFK", "ORD", 170), ("DFW", "LAX", 220),
    ("SEA", "LAX", 150), ("BOS", "LAX", 290), ("LAX", "LAS", 90),
    ("JFK", "SFO", 310), ("ORD", "MIA", 200), ("ATL", "JFK", 190),
    ("DEN", "LAX", 180), ("PHX", "LAX", 110), ("MIA", "JFK", 185),
    ("SFO", "SEA", 130), ("JFK", "BOS", 95),
]

AIRLINES = ["AA", "UA", "DL", "WN", "B6", "AS", "NK", "F9"]

DAY_OF_WEEK_MULTIPLIER = {0: 1.0, 1: 0.88, 2: 0.85, 3: 0.92, 4: 1.10, 5: 1.18, 6: 1.12}
MONTH_MULTIPLIER = {1: 0.90, 2: 0.88, 3: 1.05, 4: 1.08, 5: 1.10, 6: 1.20,
                    7: 1.22, 8: 1.18, 9: 0.95, 10: 1.00, 11: 1.15, 12: 1.25}


def days_out_multiplier(days: int) -> float:
    if days <= 3:   return 1.55
    if days <= 7:   return 1.35
    if days <= 14:  return 1.18
    if days <= 21:  return 1.08
    if days <= 30:  return 1.00
    if days <= 45:  return 0.95
    if days <= 60:  return 0.90
    if days <= 90:  return 0.88
    return 0.92


def generate_price(baseline: float, departure_date: date, fetch_date: date) -> float:
    days = (departure_date - fetch_date).days
    if days < 0:
        return None

    price = baseline
    price *= days_out_multiplier(days)
    price *= DAY_OF_WEEK_MULTIPLIER[departure_date.weekday()]
    price *= MONTH_MULTIPLIER[departure_date.month]
    price *= random.uniform(0.85, 1.15)   # market noise
    return round(max(price, 49.0), 2)


def generate_dataset(output_path: str, years: int = 10, samples_per_route: int = 500):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    today = date.today()
    start_date = date(today.year - years, 1, 1)

    rows = []
    for origin, destination, baseline in ROUTES:
        historical_avg = baseline * random.uniform(0.95, 1.05)
        for _ in range(samples_per_route):
            fetch_date = start_date + timedelta(days=random.randint(0, years * 365))
            days_ahead = random.randint(1, 180)
            departure_date = fetch_date + timedelta(days=days_ahead)
            price = generate_price(baseline, departure_date, fetch_date)
            if price is None:
                continue
            rows.append({
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date.isoformat(),
                "fetch_date": fetch_date.isoformat(),
                "days_to_departure": days_ahead,
                "day_of_week": departure_date.weekday(),
                "month": departure_date.month,
                "price": price,
                "airline": random.choice(AIRLINES),
                "cabin_class": "ECONOMY",
                "historical_avg": round(historical_avg, 2),
            })

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} rows → {output_path}")
    return output_path


if __name__ == "__main__":
    generate_dataset("ml/data/fare_training_data.csv")
