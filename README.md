# football-data-historic

Pulls match data from football-data.co.uk into Snowflake and models it with dbt. Dataset consists of 38 leagues, From 1993 to 2025 (~300k matches).

## Setup

`.env`:

```
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=FOOTBALL_WAREHOUSE
SNOWFLAKE_SCHEMA=RAW
SNOWFLAKE_ROLE=SYSADMIN
```

```
pip install requests pandas python-dotenv snowflake-connector-python dbt-snowflake
python ingestion/ingest.py

cd dbt_project
dbt deps --profiles-dir .
dbt seed --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .
```

## Structure

`ingestion/ingest.py` loads raw CSVs into `RAW.RAW_MATCHES_FLAT`. dbt takes it from there: staging cleans it up, intermediate unpivots matches into per-team rows, marts aggregate into team seasons, league tables, head-to-head records, and referee stats.
