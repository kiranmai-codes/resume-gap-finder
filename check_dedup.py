import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.db import JobDatabase
import re

db = JobDatabase('jobs.db')
df = db.export_to_dataframe()
db.close()

def norm(s):
    s = str(s or '').lower()
    s = re.sub(r'\b(pvt|ltd|limited|private|technologies|solutions|inc|llc|corp|corporation|company)\b', '', s)
    s = re.sub(r'[^a-z0-9\s]', '', s)
    return re.sub(r'\s+', ' ', s).strip()

df['norm_company'] = df['company_name'].map(norm)
multi = df.groupby('norm_company').filter(lambda g: g['source_portal'].nunique() > 1)

print(f'Companies appearing on multiple portals: {multi["norm_company"].nunique()}')
print(f'Jobs at those companies: {len(multi)}')
print()

for company, group in multi.groupby('norm_company'):
    portals = group['source_portal'].tolist()
    titles = group['job_title'].tolist()
    print(f'--- {company} ({len(group)} jobs) ---')
    for t, p in zip(titles, portals):
        print(f'  [{p}] {t}')
    print()
