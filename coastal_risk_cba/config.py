"""Project configuration: YAML loader, paths, sites, adaptation codes (v1 S000).

breguero@ucsc.edu

    cfg = Config.load()                                   # configs/cosmos_adapts.yaml
    cfg = cfg.with_overrides({"cba.cost_base": "legacy"})
    site = cfg.site("santacruz")                          # alias or full id
    site.adapt_names                                      # {'000': 'no_adaptation', '014': 'seawall', ...}
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "cosmos_adapts.yaml"

CHOICES = {
    "exposure.unit_assignment": {"first", "largest_overlap"},
    "damage.depth_statistic": {"max", "mean"},
    "risk.aeb_method": {"per_rp"},
    "risk.es_tail": {"flat", "truncated"},
    "cba.cost_base": {"all_placed", "portfolio_2025", "legacy"},
    "cba.first_cashflow_year": {0, 1},
}

# Canonical sea-level scenario codes (v1 S000 _DEM_NORMALISE).
_DEM_YEARS = {"dem020": 2025, "dem050": 2055, "dem080": 2085}
_DEM_ALIASES = {}
for _code, _year in _DEM_YEARS.items():
    _n = int(_code[3:])
    for _v in (_code, _n, str(_n), _year, str(_year)):
        _DEM_ALIASES[_v] = _code


def normalize_dem(value) -> str:
    """Canonical 'dem020'/'dem050'/'dem080' from 20, '20', 2025, '2025' or 'dem020'."""
    try:
        return _DEM_ALIASES[value]
    except (KeyError, TypeError):
        raise ValueError(f"unknown dem value {value!r}; accepted: {list(_DEM_ALIASES)}") from None


@dataclass(frozen=True)
class Site:
    id: str                      # e.g. 'site001_santacruz2'
    label: str
    zillow_sheet: str
    adapt_names: dict[str, str]  # zero-padded code -> measure name
    aliases: tuple[str, ...] = ()
    regression_mode: str | None = None
    _cfg: Config | None = field(default=None, repr=False, compare=False)

    @property
    def number(self) -> str:
        """'site001' (flood-map filename prefix)."""
        return self.id.split("_")[0]

    @property
    def measures(self) -> list[str]:
        return [n for n in self.adapt_names.values() if n != "no_adaptation"]

    @property
    def has_dunes(self) -> bool:
        return "dune" in self.adapt_names.values()

    def adapt_code(self, name: str) -> str:
        for code, n in self.adapt_names.items():
            if n == name:
                return code
        raise KeyError(f"{self.id}: no adaptation named {name!r}")

    def flood_map_stem(self, dem, rp: int, adapt: str, mode: str) -> str:
        """v1 flood-map stem, e.g. 'site001_dem020_rp005_adapt000_mode002_hmax'. `adapt` is a code or a name."""
        code = adapt if adapt in self.adapt_names else self.adapt_code(adapt)
        return f"{self.number}_{normalize_dem(dem)}_rp{int(rp):03d}_adapt{code}_mode{mode}_hmax"

    @property
    def input_dir(self) -> Path:
        return self._cfg.inputs_dir / self.id

    @property
    def reference_dir(self) -> Path:
        return self._cfg.reference_dir / self.id

    @property
    def output_dir(self) -> Path:
        return self._cfg.outputs_dir / self.id


class Config:
    def __init__(self, data: dict, source: Path | None = None):
        self.data = data
        self.source = source
        self._validate()
        self._sites = {
            sid: Site(
                id=sid,
                label=s["label"],
                zillow_sheet=s["zillow_sheet"],
                adapt_names={str(k): v for k, v in s["adapt"].items()},
                aliases=tuple(s.get("aliases", ())),
                regression_mode=s.get("regression_mode"),
                _cfg=self,
            )
            for sid, s in data["sites"].items()
        }
        self._alias = {}
        for site in self._sites.values():
            for name in (site.id, *site.aliases):
                if name in self._alias:
                    raise ValueError(f"site name {name!r} used twice")
                self._alias[name] = site.id

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        path = Path(path) if path is not None else DEFAULT_CONFIG
        with open(path) as f:
            return cls(yaml.safe_load(f), source=path)

    def with_overrides(self, overrides: dict) -> Config:
        """Copy with dotted-key overrides, e.g. {'cba.cost_base': 'legacy', 'risk.anchor_rp': 1}."""
        data = copy.deepcopy(self.data)
        for key, value in overrides.items():
            *parents, leaf = key.split(".")
            node = data
            for p in parents:
                node = node[p]
            if leaf not in node:
                raise KeyError(f"unknown config key {key!r}")
            node[leaf] = value
        return Config(data, source=self.source)

    def get(self, key: str):
        """Value at a dotted key, e.g. cfg.get('cba.cost_base')."""
        node = self.data
        for p in key.split("."):
            node = node[p]
        return node

    def _validate(self):
        for key, allowed in CHOICES.items():
            if self.get(key) not in allowed:
                raise ValueError(f"{key} = {self.get(key)!r}; allowed {sorted(allowed, key=str)}")
        if set(self.data["scenarios"]["dems"]) != set(_DEM_YEARS):
            raise ValueError(f"scenarios.dems must be {sorted(_DEM_YEARS)}")
        # Guards against YAML 1.1 reading a bare `off` key as False.
        for key, expected in [("rent_to_price_annual", {"ret", "off", "ind"}),
                              ("rent_to_revenue", {"ret", "off", "rest", "ind"})]:
            if set(self.data["indirect"][key]) != expected:
                raise ValueError(f"indirect.{key} keys must be {sorted(expected)} (quote \"off\")")
        for code in self.data["modes"]:
            if not isinstance(code, str):
                raise ValueError(f"mode codes must be quoted strings, got {code!r}")

    # --- sections -------------------------------------------------------------------------------
    exposure = property(lambda self: self.data["exposure"])
    damage = property(lambda self: self.data["damage"])
    indirect = property(lambda self: self.data["indirect"])
    dunes = property(lambda self: self.data["dunes"])
    costs = property(lambda self: self.data["costs"])
    risk = property(lambda self: self.data["risk"])
    cba = property(lambda self: self.data["cba"])
    modes = property(lambda self: self.data["modes"])

    # --- sites ------------------------------------------------------------------------------------
    @property
    def sites(self) -> dict[str, Site]:
        return dict(self._sites)

    def site(self, name: str) -> Site:
        try:
            return self._sites[self._alias[name]]
        except KeyError:
            raise ValueError(f"unknown site {name!r}; valid: {sorted(self._alias)}") from None

    @property
    def regression_sites(self) -> list[Site]:
        return [s for s in self._sites.values() if s.regression_mode]

    # --- scenarios --------------------------------------------------------------------------------
    @property
    def return_periods(self) -> list[int]:
        return list(self.data["scenarios"]["return_periods"])

    @property
    def dem_year(self) -> dict[str, int]:
        return dict(self.data["scenarios"]["dems"])

    @property
    def dems(self) -> list[str]:
        return list(self.dem_year)

    # --- derived parameters -----------------------------------------------------------------------
    @property
    def road_cost_per_meter(self) -> float:
        return self.damage["road_cost_per_mile"] / self.damage["miles_to_meters"]

    @property
    def rent_ratios(self) -> dict[str, float]:
        """Monthly rent-to-price (rpr_*) and rent-to-revenue (rr_*) ratios incl. v1 blends (S000)."""
        rpr = {f"rpr_{k}": v / 12 for k, v in self.indirect["rent_to_price_annual"].items()}
        rr = {f"rr_{k}": v for k, v in self.indirect["rent_to_revenue"].items()}
        out = {**rpr, **rr}
        out["rr_ret_rest"] = (rr["rr_ret"] + rr["rr_rest"]) / 2
        out["rr_ret_off"] = (rr["rr_ret"] + rr["rr_off"]) / 2
        out["rpr_ret_off"] = (rpr["rpr_ret"] + rpr["rpr_off"]) / 2
        return out

    # --- paths ------------------------------------------------------------------------------------
    @property
    def root(self) -> Path:
        """Lab root: first existing of paths.root_candidates."""
        for c in self.data["paths"]["root_candidates"]:
            if Path(c).exists():
                return Path(c)
        raise FileNotFoundError(f"no lab root found; tried {self.data['paths']['root_candidates']}")

    def _project_path(self, key: str) -> Path:
        return self.project_dir / self.data["paths"][key]

    @property
    def project_dir(self) -> Path:
        """Folder with 000_Data/ and 010_DAMAGES_INPUT/: $COSMOS_DATA_ROOT, else <lab root>/paths.project."""
        if os.environ.get("COSMOS_DATA_ROOT"):
            return Path(os.environ["COSMOS_DATA_ROOT"]).expanduser().resolve()
        return self.root / self.data["paths"]["project"]

    data_dir = property(lambda self: self._project_path("data"))
    inputs_dir = property(lambda self: self._project_path("inputs"))
    damage_tables_dir = property(lambda self: self._project_path("damage_tables"))
    recovery_time_file = property(lambda self: self._project_path("recovery_time"))
    multipliers_file = property(lambda self: self._project_path("multipliers"))
    zillow_file = property(lambda self: self._project_path("zillow"))
    @property
    def reference_dir(self) -> Path:
        """v1 reference outputs (read only): $COSMOS_REFERENCE_DIR, else <project>/paths.reference_outputs."""
        if os.environ.get("COSMOS_REFERENCE_DIR"):
            return Path(os.environ["COSMOS_REFERENCE_DIR"]).expanduser().resolve()
        return self._project_path("reference_outputs")

    @property
    def available_regression_sites(self) -> list[Site]:
        """Regression sites whose reference outputs are reachable."""
        try:
            return [s for s in self.regression_sites if s.reference_dir.is_dir()]
        except FileNotFoundError:
            return []


    @property
    def outputs_dir(self) -> Path:
        """v2 output root; relative paths resolve against the repository. Never the v1 reference."""
        p = Path(self.data["paths"]["outputs"]).expanduser()
        p = p if p.is_absolute() else REPO_ROOT / p
        if Path(self.data["paths"]["reference_outputs"]).name in p.resolve().parts:
            raise ValueError(f"paths.outputs must not be the v1 reference outputs: {p}")
        return p

    def unit_cost_table(self, site: str | Site) -> Path:
        s = site if isinstance(site, Site) else self.site(site)
        return s.input_dir / self.costs["unit_cost_table"].format(site=s.id)

    def dimensions_table(self, site: str | Site, measure: str) -> Path:
        s = site if isinstance(site, Site) else self.site(site)
        return s.input_dir / self.costs["dimensions"].format(site=s.id, measure=measure)
