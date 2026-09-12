/*
    stg_matches — clean, typed, deduplicated match data.
    
    This is the first transform layer. It:
    - Parses the messy date strings into proper DATEs
    - Casts numeric columns from VARCHAR
    - Generates a surrogate key
    - Deduplicates (some CSVs overlap at season boundaries)
*/

with source as (
    select * from {{ source('raw', 'raw_matches_flat') }}
),

cleaned as (
    select
        -- Surrogate key: league + date + home + away is unique per match
        {{ dbt_utils.generate_surrogate_key([
            'league_code', 'date', 'hometeam', 'awayteam'
        ]) }} as match_id,

        -- League info
        league_code,
        season_code,
        div,

        -- Parse date — football-data.co.uk uses DD/MM/YYYY or DD/MM/YY
        case
            when length(date) = 10 then try_to_date(date, 'DD/MM/YYYY')
            when length(date) = 8  then try_to_date(date, 'DD/MM/YY')
            else null
        end as match_date,

        time as kick_off_time,

        -- Teams
        trim(hometeam) as home_team,
        trim(awayteam) as away_team,

        -- Scores
        fthg as home_goals_ft,
        ftag as away_goals_ft,
        ftr  as result_ft,
        hthg as home_goals_ht,
        htag as away_goals_ht,
        htr  as result_ht,

        -- Match stats
        trim(referee) as referee,
        hs   as home_shots,
        as_  as away_shots,
        hst  as home_shots_on_target,
        ast  as away_shots_on_target,
        hf   as home_fouls,
        af   as away_fouls,
        hc   as home_corners,
        ac   as away_corners,
        hy   as home_yellows,
        ay   as away_yellows,
        hr   as home_reds,
        ar   as away_reds,

        -- Betting odds (Bet365 as primary, Pinnacle as sharp)
        b365h as odds_home_b365,
        b365d as odds_draw_b365,
        b365a as odds_away_b365,
        psh   as odds_home_pinnacle,
        psd   as odds_draw_pinnacle,
        psa   as odds_away_pinnacle,

        -- Market averages
        avgh  as odds_home_avg,
        avgd  as odds_draw_avg,
        avga  as odds_away_avg,
        maxh  as odds_home_max,
        maxd  as odds_draw_max,
        maxa  as odds_away_max,

        -- Metadata
        loaded_at

    from source
    where hometeam is not null      -- drop empty trailing rows
      and awayteam is not null
      and fthg is not null          -- must have a result
),

deduplicated as (
    select *,
        row_number() over (
            partition by match_id
            order by loaded_at desc
        ) as _rn
    from cleaned
)

select * exclude (_rn)
from deduplicated
where _rn = 1
