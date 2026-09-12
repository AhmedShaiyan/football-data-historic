/*
    int_match_results — one row per team per match.
    
    Unpivots the home/away structure so every team gets a row
    for every game, tagged with venue (home/away) and result
    from their perspective. This is the shape that makes
    aggregations like "wins at home" and "goals per game" trivial.
*/

with matches as (
    select * from {{ ref('stg_matches') }}
),

home as (
    select
        match_id,
        match_date,
        league_code,
        season_code,
        home_team        as team,
        away_team        as opponent,
        'home'           as venue,
        home_goals_ft    as goals_scored,
        away_goals_ft    as goals_conceded,
        home_goals_ft - away_goals_ft as goal_difference,
        case result_ft
            when 'H' then 'W'
            when 'D' then 'D'
            when 'A' then 'L'
        end as result,
        case result_ft
            when 'H' then 3
            when 'D' then 1
            else 0
        end as points,

        -- Stats from this team's perspective
        home_shots              as shots,
        away_shots              as shots_against,
        home_shots_on_target    as shots_on_target,
        away_shots_on_target    as shots_on_target_against,
        home_fouls              as fouls,
        away_fouls              as fouls_against,
        home_corners            as corners,
        away_corners            as corners_against,
        home_yellows            as yellows,
        away_yellows            as yellows_against,
        home_reds               as reds,
        away_reds               as reds_against,

        -- Odds
        odds_home_b365          as odds_win_b365,
        odds_draw_b365,
        odds_away_b365          as odds_lose_b365,
        odds_home_pinnacle      as odds_win_pinnacle,
        odds_draw_pinnacle,
        odds_away_pinnacle      as odds_lose_pinnacle,
        odds_home_avg           as odds_win_avg,
        odds_draw_avg,
        odds_away_avg           as odds_lose_avg,

        referee

    from matches
),

away as (
    select
        match_id,
        match_date,
        league_code,
        season_code,
        away_team        as team,
        home_team        as opponent,
        'away'           as venue,
        away_goals_ft    as goals_scored,
        home_goals_ft    as goals_conceded,
        away_goals_ft - home_goals_ft as goal_difference,
        case result_ft
            when 'A' then 'W'
            when 'D' then 'D'
            when 'H' then 'L'
        end as result,
        case result_ft
            when 'A' then 3
            when 'D' then 1
            else 0
        end as points,

        away_shots              as shots,
        home_shots              as shots_against,
        away_shots_on_target    as shots_on_target,
        home_shots_on_target    as shots_on_target_against,
        away_fouls              as fouls,
        home_fouls              as fouls_against,
        away_corners            as corners,
        home_corners            as corners_against,
        away_yellows            as yellows,
        home_yellows            as yellows_against,
        away_reds               as reds,
        home_reds               as reds_against,

        odds_away_b365          as odds_win_b365,
        odds_draw_b365,
        odds_home_b365          as odds_lose_b365,
        odds_away_pinnacle      as odds_win_pinnacle,
        odds_draw_pinnacle,
        odds_home_pinnacle      as odds_lose_pinnacle,
        odds_away_avg           as odds_win_avg,
        odds_draw_avg,
        odds_home_avg           as odds_lose_avg,

        referee

    from matches
),

unioned as (
    select * from home
    union all
    select * from away
)

select * from unioned
