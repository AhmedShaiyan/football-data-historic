/*
    mart_head_to_head — historical record between every pair of teams.

    One row per team-pair per league, aggregating all meetings.
    Useful for rivalry analysis, pre-match research, and dashboards
    showing "last 10 meetings" style stats.
*/

with matches as (
    select * from {{ ref('stg_matches') }}
),

directional as (
    select
        league_code,
        home_team as team_a,
        away_team as team_b,
        match_date,
        season_code,
        home_goals_ft as team_a_goals,
        away_goals_ft as team_b_goals,
        result_ft,
        case result_ft
            when 'H' then home_team
            when 'A' then away_team
            else 'Draw'
        end as winner
    from matches
),

-- Normalise so team_a is always alphabetically first
normalised as (
    select
        league_code,
        case when team_a < team_b then team_a else team_b end as team_1,
        case when team_a < team_b then team_b else team_a end as team_2,
        match_date,
        season_code,
        case when team_a < team_b then team_a_goals else team_b_goals end as team_1_goals,
        case when team_a < team_b then team_b_goals else team_a_goals end as team_2_goals,
        winner
    from directional
)

select
    team_1,
    team_2,
    league_code,
    count(*)                                                     as total_meetings,
    sum(case when winner = team_1 then 1 else 0 end)             as team_1_wins,
    sum(case when winner = team_2 then 1 else 0 end)             as team_2_wins,
    sum(case when winner = 'Draw' then 1 else 0 end)             as draws,
    sum(team_1_goals)                                            as team_1_total_goals,
    sum(team_2_goals)                                            as team_2_total_goals,
    round(avg(team_1_goals + team_2_goals), 2)                   as avg_goals_per_match,
    min(match_date)                                              as first_meeting,
    max(match_date)                                              as last_meeting,
    count(distinct season_code)                                  as seasons_as_rivals

from normalised
group by team_1, team_2, league_code
having total_meetings >= 2
