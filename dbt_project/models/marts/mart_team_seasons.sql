/*
    mart_team_seasons — one row per team per season per league.

    The core analytical table. Aggregates match-level results
    into season summaries: points, wins, goals, form, disciplinary,
    and betting market accuracy.
*/

with results as (
    select * from {{ ref('int_match_results') }}
),

season_stats as (
    select
        team,
        league_code,
        season_code,

        -- Record
        count(*)                                          as played,
        sum(case when result = 'W' then 1 else 0 end)    as wins,
        sum(case when result = 'D' then 1 else 0 end)    as draws,
        sum(case when result = 'L' then 1 else 0 end)    as losses,
        sum(points)                                       as total_points,

        -- Goals
        sum(goals_scored)                                 as goals_for,
        sum(goals_conceded)                               as goals_against,
        sum(goal_difference)                              as goal_difference,
        round(avg(goals_scored), 2)                       as avg_goals_scored,
        round(avg(goals_conceded), 2)                     as avg_goals_conceded,

        -- Home vs away split
        sum(case when venue = 'home' and result = 'W' then 1 else 0 end) as home_wins,
        sum(case when venue = 'away' and result = 'W' then 1 else 0 end) as away_wins,
        sum(case when venue = 'home' then goals_scored else 0 end)       as home_goals_for,
        sum(case when venue = 'away' then goals_scored else 0 end)       as away_goals_for,

        -- Match stats (where available)
        round(avg(shots), 1)                              as avg_shots,
        round(avg(shots_on_target), 1)                    as avg_shots_on_target,
        round(avg(corners), 1)                            as avg_corners,
        round(avg(fouls), 1)                              as avg_fouls,
        sum(yellows)                                      as total_yellows,
        sum(reds)                                         as total_reds,

        -- Clean sheets
        sum(case when goals_conceded = 0 then 1 else 0 end) as clean_sheets,

        -- Betting: how often the market favourite actually won
        sum(case 
            when odds_win_avg is not null 
             and odds_win_avg < odds_lose_avg 
             and result = 'W' 
            then 1 else 0 
        end) as times_favoured_and_won,
        sum(case 
            when odds_win_avg is not null 
             and odds_win_avg < odds_lose_avg 
            then 1 else 0 
        end) as times_favoured,

        min(match_date) as season_start_date,
        max(match_date) as season_end_date

    from results
    group by team, league_code, season_code
)

select
    *,
    round(total_points * 1.0 / nullif(played, 0), 2) as points_per_game,
    round(wins * 100.0 / nullif(played, 0), 1)       as win_pct,
    round(
        times_favoured_and_won * 100.0 / nullif(times_favoured, 0), 1
    ) as favourite_conversion_pct

from season_stats
