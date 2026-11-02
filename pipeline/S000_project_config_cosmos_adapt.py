"""
S000_project_config_cosmos_adapt.py
breguero@ucsc.edu  12/10/2025

Project-wide constants and helpers for the COSMOS-Adapt damage workflow.
Import with: from S000_project_config_cosmos_adapt import *
"""

from pathlib import Path
import numpy as np

# ---------------------------------------------------------------------------
# Root directory (tries network drive, then fallbacks)
# ---------------------------------------------------------------------------
_candidates = [Path('/cccr-lab'), Path('J:/'), Path('C:/temp/fake_jamaica'), Path('/Volumes/cccr-lab')]
for _d in _candidates:
    if _d.exists():
        root_directory = _d
        break
else:
    raise FileNotFoundError(f'No valid project directory found. Tried: {_candidates}')

project_root_directory = root_directory / '001_projects' / '003_cosmos-adapt'

# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------
database_directory     = project_root_directory / '000_Data'
datadir_damages        = project_root_directory / '010_DAMAGES_INPUT'
damage_table_directory = database_directory / '001_DAMAGE_TABLES'
damage_folder_outputs  = '011_DAMAGES_results_final'

indirectdamages_max_recovery_time_directory = database_directory / '020_INDIRECTDAMAGES_MAX_RECOVERY_TIME'
indirectdamages_multiplier_directory        = database_directory / '021_INDIRECTDAMAGES_MULTIPLIERS'
indirectdamages_zillow_directory            = database_directory / '022_INDIRECTDAMAGES_ZILLOWRENT'
indirect_damages_input_directory            = '003_INDIRECT_DAMAGES_INPUT'

# ---------------------------------------------------------------------------
# Indirect-damage parameters
# ---------------------------------------------------------------------------

# Monthly rent-to-price ratios
rpr_ret = 0.08613862058 / 12
rpr_off = 0.02502692786 / 12
rpr_ind = 0.07381495149 / 12

# Rent-to-revenue ratios
rr_ret  = 0.075   # Retail
rr_off  = 0.055   # Office
rr_rest = 0.08    # Restaurants
rr_ind  = 0.04    # Industrial

# Blended ratios
rr_ret_rest = np.mean([rr_ret, rr_rest])
rr_ret_off  = np.mean([rr_ret, rr_off])
rpr_ret_off = np.mean([rpr_ret, rpr_off])

# ---------------------------------------------------------------------------
# Road damage constants
# ---------------------------------------------------------------------------
road_damage_value_per_mile  = 1_358_000          # 2025 USD/mile
road_damage_value_per_meter = road_damage_value_per_mile / 1609.34

# ---------------------------------------------------------------------------
# CBA parameters
# ---------------------------------------------------------------------------
NYR            = 30
DISCOUNT_RATES = np.array([3, 7]) / 100
USD_VALUE_UPDATE = 1.19   # NSI is 2021 USD; factor converts to 2025 USD

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
meters_to_feet = 3.28084
FACTOR_RECONSTRUCTION_DUNES = 0.5  # fraction of adaptation cost to rebuild lost dune volume

# ---------------------------------------------------------------------------
# Scenario lists
# ---------------------------------------------------------------------------
RP_list  = [5, 20, 50, 100]                      # return periods (years)
DEM_list = ['dem020', 'dem050', 'dem080']         # sea-level scenarios

dem_year_dict = {20: 2025, 50: 2055, 80: 2085}   # integer code → year

dem_year_map = {
    'dem020': 2025,
    'dem050': 2055,
    'dem080': 2085,
}

# Normalise any dem representation to the canonical string 'dem020' / 'dem050' / 'dem080'
_DEM_NORMALISE = {
    # integer codes
    20: 'dem020', 50: 'dem050', 80: 'dem080',
    # string integer codes
    '20': 'dem020', '50': 'dem050', '80': 'dem080',
    # years
    2025: 'dem020', 2055: 'dem050', 2085: 'dem080',
    '2025': 'dem020', '2055': 'dem050', '2085': 'dem080',
    # already canonical
    'dem020': 'dem020', 'dem050': 'dem050', 'dem080': 'dem080',
}

def normalize_dem(value) -> str:
    """
    Convert any dem representation to the canonical string form used throughout
    the workflow ('dem020', 'dem050', 'dem080').

    Accepted input forms: 20/50/80, '20'/'50'/'80', 2025/2055/2085,
    '2025'/'2055'/'2085', or the canonical strings themselves.

    Usage on a DataFrame column:
        df['dem'] = df['dem'].map(normalize_dem)
    """
    result = _DEM_NORMALISE.get(value)
    if result is None:
        raise ValueError(
            f"Unknown dem value {value!r}. "
            f"Accepted values: {list(_DEM_NORMALISE.keys())}"
        )
    return result

# ---------------------------------------------------------------------------
# Adaptation scenario mapping (per site)
# ---------------------------------------------------------------------------
# site001_santacruz and site001_santacruz2 share the same adaptation keys
_SITE001_ADAPT = {
    '000': 'no_adaptation',
    '014': 'seawall',
    '023': 'reef',
    '031': 'dune',
}

_ADAPT_BY_SITE = {
    'site001_santacruz':  _SITE001_ADAPT,
    'site001_santacruz2': _SITE001_ADAPT,
    'site002_halfmoonbay': {
        '000': 'no_adaptation',
        '010': 'seawall',
        '020': 'reef',
    },
    'site003_venturanorth': {
        '000': 'no_adaptation',
        '010': 'seawall',
        '020': 'reef',
        '030': 'dune',
    },
    'site004_venturanorth2': {
        '000': 'no_adaptation',
        '010': 'seawall',
        '020': 'reef',
        '030': 'dune',
    },
}

VALID_SITES = list(_ADAPT_BY_SITE.keys())


def get_adaptation_names(site: str) -> dict:
    """
    Return a dict mapping zero-padded adapt keys to human-readable names
    for the given site, e.g. {'000': 'no_adaptation', '014': 'seawall', ...}.

    Raises ValueError for unknown sites.
    """
    if site not in _ADAPT_BY_SITE:
        raise ValueError(
            f"Unknown site '{site}'. Valid options: {VALID_SITES}"
        )
    return _ADAPT_BY_SITE[site]
