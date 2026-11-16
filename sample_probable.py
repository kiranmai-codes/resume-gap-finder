import pandas as pd

df = pd.read_csv('outputs/pipeline/14_benchmark_jobs.csv')
naukri_probable = df[(df['source_portal'] == 'Naukri') & (df['__tier'] == 'probable')]

print(f'Naukri probable tier: {len(naukri_probable)} jobs')
print()
print('10 random samples:')
sample = naukri_probable.sample(min(10, len(naukri_probable)))
for _, row in sample.iterrows():
    print(f'- {row["job_title"]} @ {row["company_name"]}')
    print(f'  role_family: {row["__role_family"]}')
    print()
