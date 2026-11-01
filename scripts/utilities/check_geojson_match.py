import json
import duckdb


# Rename-only aliases whose bundled GeoJSON polygons are valid
# equivalents for map-display purposes. Analytical FIPS remain unchanged.
COUNTY_MAP_FIPS_ALIASES = {
    "02158": "02270",  # Kusilvak -> former Wade Hampton geometry
    "46102": "46113",  # Oglala Lakota -> former Shannon geometry
}


# Analytical geographies for which the bundled GeoJSON does not provide
# a valid one-to-one polygon. These remain available analytically but are
# intentionally not drawn on the county map.
EXPECTED_NON_MAP_FIPS = {
    "02010",  # Aleutian Islands Census Area
    "02063",  # Chugach Census Area - split successor
    "02066",  # Copper River Census Area - split successor
    "02140",  # Kobuk Census Area
    "02201",  # Prince of Wales-Outer Ketchikan Census Area
    "02231",  # Skagway-Yakutat-Angoon Census Area
    "02232",  # Skagway-Hoonah-Angoon Census Area
    "02280",  # Wrangell-Petersburg Census Area
    "30113",  # Yellowstone National Park county equivalent
    "46131",  # Washabaugh County
    "51560",  # Clifton Forge city
    "51780",  # South Boston city
}


# Load explicitly supplied/bundled GeoJSON.
with open(
    r"app\assets\geojson\counties.geojson",
    encoding="utf-8",
) as f:
    geo = json.load(f)

geo_fips = {
    str(feature["id"]).zfill(5)
    for feature in geo["features"]
}


# Load analytical county universe.
con = duckdb.connect(
    r"database\countyhealth.duckdb",
    read_only=True,
)

db_fips = {
    str(row[0]).zfill(5)
    for row in con.execute("""
        SELECT DISTINCT fips
        FROM analytics.vw_current_county_lookup
        WHERE fips IS NOT NULL
    """).fetchall()
}

con.close()


raw_database_only = db_fips - geo_fips

alias_sources_present = {
    fips
    for fips in db_fips
    if fips in COUNTY_MAP_FIPS_ALIASES
}

alias_targets_missing = {
    source: target
    for source, target in COUNTY_MAP_FIPS_ALIASES.items()
    if source in db_fips and target not in geo_fips
}

expected_non_map_present = db_fips & EXPECTED_NON_MAP_FIPS

resolved_database_fips = {
    COUNTY_MAP_FIPS_ALIASES.get(fips, fips)
    for fips in db_fips
    if fips not in EXPECTED_NON_MAP_FIPS
}

unresolved = resolved_database_fips - geo_fips

unexpected_raw_database_only = (
    raw_database_only
    - set(COUNTY_MAP_FIPS_ALIASES)
    - EXPECTED_NON_MAP_FIPS
)

missing_expected_non_map = EXPECTED_NON_MAP_FIPS - db_fips


print("=" * 60)
print("GeoJSON polygons       :", len(geo_fips))
print("Analytical geographies :", len(db_fips))
print("Raw database-only FIPS :", len(raw_database_only))
print("Validated aliases      :", len(alias_sources_present))
print("Expected non-map FIPS  :", len(expected_non_map_present))
print("Resolved map coverage  :", len(db_fips) - len(expected_non_map_present))
print("=" * 60)

print("\nValidated rename-only aliases:")
for source in sorted(alias_sources_present):
    print(
        source,
        "->",
        COUNTY_MAP_FIPS_ALIASES[source],
    )

print("\nExpected analytical geographies not drawn:")
for fips in sorted(expected_non_map_present):
    print(fips)

if alias_targets_missing:
    print("\nERROR: alias targets missing from GeoJSON:")
    for source, target in sorted(alias_targets_missing.items()):
        print(source, "->", target)

if unexpected_raw_database_only:
    print("\nERROR: unexpected database-only FIPS:")
    for fips in sorted(unexpected_raw_database_only):
        print(fips)

if unresolved:
    print("\nERROR: unresolved analytical map FIPS:")
    for fips in sorted(unresolved):
        print(fips)

if missing_expected_non_map:
    print("\nERROR: expected non-map contract drift:")
    for fips in sorted(missing_expected_non_map):
        print(fips)


if (
    alias_targets_missing
    or unexpected_raw_database_only
    or unresolved
    or missing_expected_non_map
):
    raise SystemExit(1)


print("\nPASS: analytical geography-to-GeoJSON contract validated.")
