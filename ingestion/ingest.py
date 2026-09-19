"""
Ingest historical football CSVs from football-data.co.uk into Snowflake.

ELT pattern: load raw data as-is, let dbt handle transforms.
"""

import os
import io
import logging
import time
from datetime import datetime

import requests
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Main European leagues — data back to 1993/94, stats from 2000/01
MAIN_LEAGUES = {
    # England
    "E0": "England - Premier League",
    "E1": "England - Championship",
    "E2": "England - League One",
    "E3": "England - League Two",
    "EC": "England - Conference",
    # Scotland
    "SC0": "Scotland - Premiership",
    "SC1": "Scotland - Championship",
    "SC2": "Scotland - League One",
    "SC3": "Scotland - League Two",
    # Major European
    "D1": "Germany - Bundesliga",
    "D2": "Germany - 2. Bundesliga",
    "I1": "Italy - Serie A",
    "I2": "Italy - Serie B",
    "SP1": "Spain - La Liga",
    "SP2": "Spain - Segunda Division",
    "F1": "France - Ligue 1",
    "F2": "France - Ligue 2",
    # Other European
    "N1": "Netherlands - Eredivisie",
    "B1": "Belgium - Jupiler League",
    "P1": "Portugal - Liga",
    "T1": "Turkey - Super Lig",
    "G1": "Greece - Super League",
}

# Extra worldwide leagues — data from ~2012/13
EXTRA_LEAGUES = {
    "ARG": "Argentina - Primera Division",
    "AUT": "Austria - Bundesliga",
    "BRA": "Brazil - Serie A",
    "CHN": "China - Super League",
    "DNK": "Denmark - Superliga",
    "FIN": "Finland - Veikkausliiga",
    "IRL": "Ireland - Premier Division",
    "JPN": "Japan - J-League",
    "MEX": "Mexico - Liga MX",
    "NOR": "Norway - Eliteserien",
    "POL": "Poland - Ekstraklasa",
    "ROU": "Romania - Liga 1",
    "RUS": "Russia - Premier League",
    "SWE": "Sweden - Allsvenskan",
    "SWI": "Switzerland - Super League",
    "USA": "USA - MLS",
}

BASE_URL = "https://www.football-data.co.uk"


def generate_season_codes(start_year: int = 1993, end_year: int = 2025) -> list[str]:
    """Generate season codes like '9394', '0001', '2425'."""
    codes = []
    for y in range(start_year, end_year):
        s = f"{y % 100:02d}{(y + 1) % 100:02d}"
        codes.append(s)
    return codes


def download_csv(league_code: str, season_code: str, is_extra: bool = False) -> pd.DataFrame | None:
    """
    Download a single CSV from football-data.co.uk.
    
    Main leagues:  /mmz4281/{season}/{league}.csv
    Extra leagues:  /new/{league}.csv  (single file per league, all seasons)
    """
    if is_extra:
        url = f"{BASE_URL}/new/{league_code}.csv"
    else:
        url = f"{BASE_URL}/mmz4281/{season_code}/{league_code}.csv"

    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        # Some files have encoding issues
        content = resp.content.decode("utf-8", errors="replace")
        df = pd.read_csv(io.StringIO(content), on_bad_lines="skip")

        # Drop completely empty rows (common at end of files)
        df = df.dropna(how="all")

        if df.empty:
            return None

        # Tag with metadata
        df["_league_code"] = league_code
        df["_season_code"] = season_code
        df["_source_url"] = url
        df["_loaded_at"] = datetime.utcnow().isoformat()

        return df

    except Exception as e:
        logger.warning(f"Failed to download {url}: {e}")
        return None


def get_snowflake_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "FOOTBALL_WAREHOUSE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA", "RAW"),
        role=os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
    )


def setup_snowflake(conn):
    """Create database, schemas, and raw landing table."""
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS FOOTBALL_WAREHOUSE")
    cur.execute("USE DATABASE FOOTBALL_WAREHOUSE")
    cur.execute("CREATE SCHEMA IF NOT EXISTS RAW")
    cur.execute("CREATE SCHEMA IF NOT EXISTS STAGING")
    cur.execute("CREATE SCHEMA IF NOT EXISTS ANALYTICS")
    cur.execute("USE SCHEMA RAW")

    # Raw landing table — VARIANT column for schema flexibility
    # Different leagues/seasons have different column sets
    cur.execute("""
        CREATE TABLE IF NOT EXISTS RAW_MATCHES (
            league_code     VARCHAR(10),
            league_name     VARCHAR(100),
            season_code     VARCHAR(10),
            source_url      VARCHAR(500),
            loaded_at       TIMESTAMP_NTZ,
            raw_data        VARIANT
        )
    """)

    # Also create a flat CSV landing table for direct loads
    # (columns vary by file, so we use a wide nullable schema)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS RAW_MATCHES_FLAT (
            -- Identity
            league_code     VARCHAR(10),
            season_code     VARCHAR(10),
            source_url      VARCHAR(500),
            loaded_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            
            -- Match info
            div             VARCHAR(10),
            date            VARCHAR(20),
            time            VARCHAR(10),
            hometeam        VARCHAR(100),
            awayteam        VARCHAR(100),
            
            -- Scores
            fthg            INTEGER,        -- full time home goals
            ftag            INTEGER,        -- full time away goals
            ftr             VARCHAR(5),     -- full time result (H/D/A)
            hthg            INTEGER,        -- half time home goals
            htag            INTEGER,        -- half time away goals
            htr             VARCHAR(5),     -- half time result
            
            -- Match stats
            referee         VARCHAR(100),
            hs              INTEGER,        -- home shots
            as_             INTEGER,        -- away shots (as is reserved)
            hst             INTEGER,        -- home shots on target
            ast             INTEGER,        -- away shots on target
            hf              INTEGER,        -- home fouls
            af              INTEGER,        -- away fouls
            hc              INTEGER,        -- home corners
            ac              INTEGER,        -- away corners
            hy              INTEGER,        -- home yellows
            ay              INTEGER,        -- away yellows
            hr              INTEGER,        -- home reds
            ar              INTEGER,        -- away reds
            
            -- Betting odds (major bookmakers)
            b365h           FLOAT,          -- Bet365 home
            b365d           FLOAT,          -- Bet365 draw
            b365a           FLOAT,          -- Bet365 away
            bwh             FLOAT,          -- Betway home
            bwd             FLOAT,          -- Betway draw
            bwa             FLOAT,          -- Betway away
            iwh             FLOAT,          -- Interwetten home
            iwd             FLOAT,          -- Interwetten draw
            iwa             FLOAT,          -- Interwetten away
            psh             FLOAT,          -- Pinnacle home
            psd             FLOAT,          -- Pinnacle draw
            psa             FLOAT,          -- Pinnacle away
            whh             FLOAT,          -- William Hill home
            whd             FLOAT,          -- William Hill draw
            wha             FLOAT,          -- William Hill away
            vch             FLOAT,          -- VC Bet home
            vcd             FLOAT,          -- VC Bet draw
            vca             FLOAT,          -- VC Bet away
            
            -- Aggregated odds
            maxh            FLOAT,
            maxd            FLOAT,
            maxa            FLOAT,
            avgh            FLOAT,
            avgd            FLOAT,
            avga            FLOAT,
            
            -- Over/Under 2.5
            bts_over_2_5    FLOAT,
            bts_under_2_5   FLOAT,
            
            -- Catch-all for extra columns
            _extra_columns  VARIANT
        )
    """)
    cur.close()
    logger.info("Snowflake schemas and tables ready")


def load_batch_to_snowflake(conn, batch: pd.DataFrame, league_name: str):
    """
    Load a pandas DataFrame into RAW_MATCHES_FLAT.
    
    Normalises column names and maps known columns to the schema.
    Unknown columns go into _extra_columns as JSON.
    """
    if batch.empty:
        return 0

    # Normalise column names
    batch.columns = [c.strip().lower().replace(" ", "_") for c in batch.columns]

    # Known columns that map to our schema
    known_cols = {
        "div", "date", "time", "hometeam", "awayteam",
        "fthg", "ftag", "ftr", "hthg", "htag", "htr",
        "referee", "hs", "as", "hst", "ast", "hf", "af",
        "hc", "ac", "hy", "ay", "hr", "ar",
        "b365h", "b365d", "b365a", "bwh", "bwd", "bwa",
        "iwh", "iwd", "iwa", "psh", "psd", "psa",
        "whh", "whd", "wha", "vch", "vcd", "vca",
        "maxh", "maxd", "maxa", "avgh", "avgd", "avga",
        "_league_code", "_season_code", "_source_url", "_loaded_at",
    }

    # Rename 'as' → 'as_' (reserved keyword)
    if "as" in batch.columns:
        batch = batch.rename(columns={"as": "as_"})
        known_cols.discard("as")
        known_cols.add("as_")

    # Separate known vs extra columns
    present_known = [c for c in batch.columns if c in known_cols]
    extra = [c for c in batch.columns if c not in known_cols]

    # Build extra columns JSON
    if extra:
        batch["_extra_columns"] = batch[extra].apply(
            lambda row: row.dropna().to_dict() or None, axis=1
        )
    else:
        batch["_extra_columns"] = None

    # Rename metadata columns
    col_map = {
        "_league_code": "league_code",
        "_season_code": "season_code",
        "_source_url": "source_url",
        "_loaded_at": "loaded_at",
    }
    batch = batch.rename(columns=col_map)

    # Select only schema columns
    schema_cols = [
        "league_code", "season_code", "source_url", "loaded_at",
        "div", "date", "time", "hometeam", "awayteam",
        "fthg", "ftag", "ftr", "hthg", "htag", "htr",
        "referee", "hs", "as_", "hst", "ast", "hf", "af",
        "hc", "ac", "hy", "ay", "hr", "ar",
        "b365h", "b365d", "b365a", "bwh", "bwd", "bwa",
        "iwh", "iwd", "iwa", "psh", "psd", "psa",
        "whh", "whd", "wha", "vch", "vcd", "vca",
        "maxh", "maxd", "maxa", "avgh", "avgd", "avga",
        "_extra_columns",
    ]

    for col in schema_cols:
        if col not in batch.columns:
            batch[col] = None

    out = batch[schema_cols].copy()
    out.columns = [c.upper() for c in out.columns]

    # Convert _EXTRA_COLUMNS dict to JSON string for VARIANT
    import json
    out["_EXTRA_COLUMNS"] = out["_EXTRA_COLUMNS"].apply(
        lambda x: json.dumps(x) if isinstance(x, dict) else None
    )

    success, nchunks, nrows, _ = write_pandas(
        conn, out, "RAW_MATCHES_FLAT",
        database="FOOTBALL_WAREHOUSE",
        schema="RAW",
    )

    if success:
        logger.info(f"  Loaded {nrows} rows ({nchunks} chunks)")
    else:
        logger.error(f"  write_pandas failed")

    return nrows if success else 0


def ingest_main_leagues(conn):
    """Download and load all main European league CSVs."""
    seasons = generate_season_codes(1993, 2026)
    total = 0

    for league_code, league_name in MAIN_LEAGUES.items():
        logger.info(f"\n{'='*40}")
        logger.info(f"League: {league_name} ({league_code})")

        for season in seasons:
            df = download_csv(league_code, season, is_extra=False)
            if df is None:
                continue

            logger.info(f"  {season}: {len(df)} matches")
            loaded = load_batch_to_snowflake(conn, df, league_name)
            total += loaded

            # Be polite to the server
            time.sleep(0.5)

    return total


def ingest_extra_leagues(conn):
    """Download and load extra worldwide league CSVs."""
    total = 0

    for league_code, league_name in EXTRA_LEAGUES.items():
        logger.info(f"\n{'='*40}")
        logger.info(f"League: {league_name} ({league_code})")

        # Extra leagues use a different URL pattern and contain all seasons
        df = download_csv(league_code, "all", is_extra=True)
        if df is None:
            logger.warning(f"  No data found for {league_code}")
            continue

        logger.info(f"  {len(df)} total matches")
        loaded = load_batch_to_snowflake(conn, df, league_name)
        total += loaded
        time.sleep(0.5)

    return total


def main():
    logger.info("=" * 60)
    logger.info("FOOTBALL HISTORICAL DATA INGESTION → SNOWFLAKE")
    logger.info(f"Started: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    conn = get_snowflake_connection()

    try:
        setup_snowflake(conn)

        main_total = ingest_main_leagues(conn)
        logger.info(f"\nMain leagues total: {main_total:,} rows")

        extra_total = ingest_extra_leagues(conn)
        logger.info(f"Extra leagues total: {extra_total:,} rows")

        grand_total = main_total + extra_total
        logger.info(f"\n{'='*60}")
        logger.info(f"INGESTION COMPLETE — {grand_total:,} total rows loaded")
        logger.info(f"{'='*60}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
