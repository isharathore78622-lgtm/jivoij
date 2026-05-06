import pandas as pd
import os

# File paths (since Fake.csv and True.csv are directly under data/)
fake_path = os.path.join("data", "Fake.csv")
true_path = os.path.join("data", "True.csv")

# Read files
fake = pd.read_csv(fake_path)
true = pd.read_csv(true_path)

# Add labels
fake['label'] = 'FAKE'
true['label'] = 'REAL'

# Combine and shuffle
df = pd.concat([fake, true], axis=0)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

# Keep useful columns
if 'title' in df.columns and 'text' in df.columns:
    df = df[['title', 'text', 'label']]
elif 'text' in df.columns:
    df = df[['text', 'label']]

# Save merged file
output_path = os.path.join("data", "fakenews_combined.csv")
df.to_csv(output_path, index=False)

print(f"✅ Combined dataset saved at: {output_path}")
print(f"Total records: {len(df)}")
print(df.head())