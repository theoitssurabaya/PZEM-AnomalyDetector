import pandas as pd

df = pd.read_csv("dataset_finalbanget.csv")

df = df.rename(columns={
    "power_watt": "power",
    "power_factor": "powerFactor",
    "energy_kwh": "energy"
})

df.to_csv("dataset_finalterakhir.csv", index=False)
print(df.columns)
