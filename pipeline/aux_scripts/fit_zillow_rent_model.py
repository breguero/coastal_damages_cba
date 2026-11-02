"""Fit the reduced residential rent model used by S021 and write its coefficients.

rent = const + price * val_struct + area_sqft * sqft, one OLS fit per Zillow sheet (site).
S021 reads the coefficients file when zillowrent.xlsx (listings, not redistributed) is absent.

    python fit_zillow_rent_model.py zillowrent.xlsx zillow_rent_ols_coefficients.csv
"""
import sys

import pandas as pd
import statsmodels.api as sm

xlsx, out = sys.argv[1], sys.argv[2]
rows = []
for sheet in ['Santa Cruz', 'Half Moon Bay', 'Ventura county']:
    zil = pd.read_excel(xlsx, sheet_name=sheet)
    y = pd.to_numeric(zil['rent'], errors='coerce')
    X = sm.add_constant(zil[['price', 'area (sq ft)']].copy())
    m = sm.OLS(y, X, missing='drop').fit()
    rows.append({'zillow_sheet': sheet, 'const': m.params['const'], 'price': m.params['price'],
                 'area_sqft': m.params['area (sq ft)'], 'n_obs': int(m.nobs), 'r2': m.rsquared})
df = pd.DataFrame(rows)
df.to_csv(out, index=False, float_format='%.17g')
back = pd.read_csv(out)
assert (back[['const','price','area_sqft']].values == df[['const','price','area_sqft']].values).all()
print(df.to_string())
