from pipeline.db import JobDatabase
from pipeline.schema import standardize_schema
from pipeline.dedup import run_cross_portal_dedup

db = JobDatabase('jobs.db')
df = db.export_to_dataframe()
db.close()

print('Part 1: per-portal standardize')
portals = {p: g for p, g in df.groupby('source_portal')}
for name, group in portals.items():
    std = standardize_schema(group, name)
    nan_count = std['description'].isna().sum()
    first_desc = std['description'].iloc[0] if len(std) else ''
    preview = (first_desc[:40] if isinstance(first_desc, str) else 'NON-STRING')
    print(name, '| in=' + str(len(group)), '| out=' + str(len(std)),
          '| nan=' + str(nan_count), '| preview=' + repr(preview))

print('Part 2: full dedup')
unified, _ = run_cross_portal_dedup(portals)
print('Unified rows:', len(unified))
print('Unified desc NaN:', unified['description'].isna().sum())
