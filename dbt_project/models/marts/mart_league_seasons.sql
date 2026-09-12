/*
    mart_league_seasons — reconstructed final league table for every
    league-season combination.
    
    Ranks teams by points (then goal difference, then goals scored)
    to reproduce the actual final standings. Adds promotion/relegation
    zone flags based on position.
*/

with team_seasons as (
    select * from {{ ref('mart_team_seasons') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by league_code, season_code
            order by 
                total_points desc,
                goal_difference desc,
                goals_for desc,
                team asc
        ) as position,
        count(*) over (
            partition by league_code, season_code
        ) as teams_in_league
    from team_seasons
)

select
    *,
    case
        when position <= 4 and league_code in ('E0','SP1','D1','I1','F1')
            then 'Champions League'
        when position <= 3 and league_code in ('N1','P1','B1','T1','G1','SC0')
            then 'Champions League'
        when position <= 6 and league_code in ('E0','SP1','D1','I1','F1')
            then 'Europa League'
        when position >= teams_in_league - 2
            then 'Relegation'
        else 'Mid-table'
    end as zone

from ranked
