import pandas as pd

dates = pd.to_datetime([
    '2010-01-01 10:00:00', # Friday
    '2010-01-02 10:00:00', # Saturday
    '2010-01-03 10:00:00', # Sunday
    '2010-01-04 10:00:00', # Monday
    '2010-01-05 10:00:00', # Tuesday
])

print("PANDAS WEEKLY FREQUENCY AUDIT:")
for freq in ['W-MON', 'W-SUN']:
    print(f"\n--- Frequency: {freq} ---")
    periods = dates.to_period(freq)
    for d, p in zip(dates, periods):
        print(f"Date {d.strftime('%Y-%m-%d')} ({d.day_name():<9}) -> Period: {str(p):<25} | Start: {p.start_time} ({p.start_time.day_name()}) | End: {p.end_time} ({p.end_time.day_name()})")
