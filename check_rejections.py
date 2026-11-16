import pandas as pd
from pathlib import Path

OUT = Path('outputs/pipeline')
stages = [
    ('Entry Gate',      '03_entry_gate_rejected.csv',  '__tier_reason'),
    ('Role Relevance',  '04_role_relevance_rejected.csv', '__role_rel_reason'),
    ('Content Quality', '05_content_rejected.csv',     None),
    ('Experience',      '07_experience_rejected.csv',  None),
    ('Role Family',     '08_role_family_rejected.csv', None),
]

for label, fname, reason_col in stages:
    path = OUT / fname
    if not path.exists():
        print(f'{label}: no file')
        continue
    df = pd.read_csv(path)
    if len(df) == 0:
        print(f'{label}: 0 rejections')
        continue
    print(f'--- {label} ({len(df)} total) ---')
    print(df['source_portal'].value_counts().to_string())
    if reason_col and reason_col in df.columns:
        print('  Top reasons:')
        for reason, count in df[reason_col].value_counts().head(3).items():
            print(f'    {count:3d}  {reason}')
    print()
