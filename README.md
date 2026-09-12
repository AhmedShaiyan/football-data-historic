# Football Historical Data Warehouse

A modern ELT pipeline that ingests 30+ years of football match data across 38 league divisions into Snowflake, with dbt transforming raw CSVs into analytical models.

## Architecture

```
football-data.co.uk (free CSVs)
        │
        │  Python ingestion script
        │  (~250k matches, 38 leagues, 1993–present)
        ▼
┌─────────────────────────────┐
│  Snowflake: RAW schema      │  ← raw_matches_flat (as-is from CSVs)
│                             │
│  dbt: STAGING schema        │  ← stg_matches (cleaned, typed, deduped)
│                             │     int_match_results (unpivoted per-team view)
│                             │
│  dbt: ANALYTICS schema      │  ← mart_team_seasons (season aggregates)
│                             │     mart_league_seasons (final tables + zones)
│                             │     mart_head_to_head (rivalry records)
│                             │     mart_referee_stats (official analysis)
└─────────────────────────────┘
        │
        ▼
   Dashboard (Snowsight / Power BI / Preset)
```

## Data

Source: [football-data.co.uk](https://www.football-data.co.uk/data.php) — free, no API key required.

| Metric | Volume |
|---|---|
| Leagues | 38 divisions across 27 countries |
| Seasons | Up to 31 (1993/94 – 2025/26) |
| Matches | ~250,000 |
| Columns per match | 40-100 (results, stats, betting odds) |
| Raw data size | ~120 MB CSV |

## Why Snowflake + dbt (and not PySpark + Postgres)

| Concern | PySpark + Postgres | Snowflake + dbt |
|---|---|---|
| Transform layer | Python code, opaque to analysts | SQL models, version-controlled, testable |
| Schema evolution | Manual migration scripts | dbt handles it; raw VARIANT absorbs new columns |
| Data testing | Custom validators | dbt tests: unique, not_null, expression checks |
| Documentation | README + comments | `dbt docs generate` → browsable lineage graph |
| Scale | Bound by single Postgres instance | Snowflake auto-scales compute independently |
| Collaboration | "Run this script" | `dbt run` — anyone with SQL can contribute models |

## Setup

### 1. Snowflake account

Sign up for the [30-day free trial](https://signup.snowflake.com/) ($400 in credits, no card required).

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure credentials

```bash
cp .env.example .env
# Edit .env with your Snowflake account details
```

### 4. Run ingestion

```bash
cd ingestion
python ingest.py
```

This downloads all CSVs and loads them into `FOOTBALL_WAREHOUSE.RAW.RAW_MATCHES_FLAT`.
Takes ~15-20 minutes (polite 0.5s delay between requests).

### 5. Run dbt

```bash
cd dbt_project
dbt deps          # install dbt_utils
dbt seed          # load league_codes.csv
dbt run           # build all models
dbt test          # run schema + expression tests
dbt docs generate # generate documentation site
dbt docs serve    # browse lineage graph locally
```

## dbt model lineage

```
raw_matches_flat (source)
    └── stg_matches (staging: clean + type + dedup)
            ├── int_match_results (intermediate: unpivot home/away)
            │       ├── mart_team_seasons (per team per season aggregates)
            │       │       └── mart_league_seasons (final tables + zones)
            │       └── mart_referee_stats (per referee career stats)
            └── mart_head_to_head (pair-wise rivalry records)
```

## Example queries

```sql
-- Premier League all-time points-per-game leaders
SELECT team, sum(total_points) as career_pts, sum(played) as career_games,
       round(career_pts / career_games, 2) as ppg
FROM ANALYTICS.MART_TEAM_SEASONS
WHERE league_code = 'E0'
GROUP BY team
ORDER BY ppg DESC
LIMIT 10;

-- El Clasico head-to-head
SELECT * FROM ANALYTICS.MART_HEAD_TO_HEAD
WHERE team_1 = 'Barcelona' AND team_2 = 'Real Madrid';

-- Strictest referees (most cards per game, min 50 matches)
SELECT referee, matches_officiated, avg_yellows_per_match, avg_reds_per_match
FROM ANALYTICS.MART_REFEREE_STATS
WHERE matches_officiated >= 50
ORDER BY avg_yellows_per_match DESC
LIMIT 15;
```

## Project structure

```
football-historical-warehouse/
├── ingestion/
│   └── ingest.py              # Download CSVs → Snowflake RAW
├── dbt_project/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── packages.yml
│   ├── seeds/
│   │   └── league_codes.csv   # League code → readable name mapping
│   ├── models/
│   │   ├── staging/
│   │   │   ├── sources.yml
│   │   │   └── stg_matches.sql
│   │   ├── intermediate/
│   │   │   └── int_match_results.sql
│   │   └── marts/
│   │       ├── mart_team_seasons.sql
│   │       ├── mart_league_seasons.sql
│   │       ├── mart_head_to_head.sql
│   │       └── mart_referee_stats.sql
│   └── schema.yml
├── requirements.txt
└── .env.example
```
