/*
    mart_referee_stats — per-referee career stats.

    Cards per game, goals per game, home win bias — the kind of
    analysis that's fun to explore and makes a good dashboard panel.
*/

with results as (
    select * from {{ ref('int_match_results') }}
    where referee is not null
      and referee != ''
      and venue = 'home'  -- one row per match (avoid double-counting)
),

matches as (
    select * from {{ ref('stg_matches') }}
    where referee is not null
      and referee != ''
)

select
    m.referee,
    count(*)                                                    as matches_officiated,
    count(distinct m.league_code)                               as leagues,
    count(distinct m.season_code)                               as seasons,
    min(m.match_date)                                           as first_match,
    max(m.match_date)                                           as last_match,

    -- Goals
    round(avg(m.home_goals_ft + m.away_goals_ft), 2)           as avg_goals_per_match,

    -- Cards
    round(avg(m.home_yellows + m.away_yellows), 2)             as avg_yellows_per_match,
    round(avg(m.home_reds + m.away_reds), 2)                   as avg_reds_per_match,
    sum(m.home_yellows + m.away_yellows)                        as total_yellows,
    sum(m.home_reds + m.away_reds)                              as total_reds,

    -- Fouls
    round(avg(m.home_fouls + m.away_fouls), 2)                 as avg_fouls_per_match,

    -- Home bias
    round(
        sum(case when m.result_ft = 'H' then 1 else 0 end) * 100.0 
        / count(*), 1
    ) as home_win_pct,
    round(
        sum(case when m.result_ft = 'D' then 1 else 0 end) * 100.0 
        / count(*), 1
    ) as draw_pct,
    round(
        sum(case when m.result_ft = 'A' then 1 else 0 end) * 100.0 
        / count(*), 1
    ) as away_win_pct

from matches m
group by m.referee
having matches_officiated >= 10
