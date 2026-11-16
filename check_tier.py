import pandas as pd

df = pd.read_csv('outputs/pipeline/14_benchmark_jobs.csv')
print('Tier overall:')
print(df['__tier'].value_counts().to_string())
print()
print('Tier × portal:')
print(df.groupby(['source_portal', '__tier']).size().to_string())

