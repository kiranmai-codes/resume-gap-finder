import pandas as pd

df = pd.read_csv('outputs/pipeline/14_benchmark_jobs.csv')
print('Portal distribution of the 171 benchmark jobs:')
print(df['source_portal'].value_counts().to_string())
print()
print('Portal × tier:')
print(df.groupby(['source_portal', 'eligible_tier']).size().to_string())
