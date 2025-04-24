from sqlalchemy.orm import sessionmaker
from models import *
from contextlib import contextmanager
from sqlalchemy import and_, or_, func
import pandas as pd
from datetime import datetime

SessionLocal = sessionmaker(
    bind=ENGINELocal, autoflush=False, autocommit=False, expire_on_commit=False
)

team_id_list = [
    "CTG",
    "CW",
    "EXU",
    "GTR",
    "JJH",
    "JS",
    "NJ",
    "NMDS",
    "OOW",
    "RA",
    "RSG",
    "XDM",
]

output_path = f"analyse_out/analyse_{datetime.now().date()}.xlsx"


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    except:
        db.rollback()
        raise
    finally:
        db.close()


def analyse_map_pool(team_ids: list[str] = None) -> list:
    if not team_id_list:
        return []
    with get_db() as db:
        result = []
        for team_id in team_ids:
            schedule_ids = [
                item[0]
                for item in db.query(Schedule.schedule_id).filter(
                    and_(
                        or_(Schedule.team_1 == team_id, Schedule.team_2 == team_id),
                        Schedule.stage_id.notin_([0, 5, 6]),
                        Schedule.schedule_status == 3,
                    )
                )
            ]
            matches = db.query(Match).filter(Match.schedule_id.in_(schedule_ids)).all()
            if matches:
                map_pool = {}
                for match in matches:
                    game_map = match.map
                    winner = match.winner
                    if game_map not in map_pool:
                        map_pool.update({game_map: [0, 0]})
                    if team_id == winner:
                        map_pool[game_map][0] += 1
                    if team_id != winner:
                        map_pool[game_map][1] += 1
                result.append({"team": team_id, "map_pool": map_pool})
        return result


def analyse_pistol_round(team_ids: list[str]) -> list:
    if not team_ids:
        return []
    with get_db() as db:
        result = []
        for team_id in team_ids:
            t_total = 0
            ct_total = 0
            t_wins = 0
            ct_wins = 0
            pistol_rounds = (
                db.query(DataRoundTeam)
                .filter(
                    and_(
                        or_(
                            DataRoundTeam.team_1 == team_id,
                            DataRoundTeam.team_2 == team_id,
                        ),
                        DataRoundTeam.round.in_([1, 13]),
                    )
                )
                .all()
            )
            for each_round in pistol_rounds:
                win_team = each_round.win_team
                win_result = each_round.win_result
                if win_team == team_id:
                    if win_result.startswith("t"):
                        t_wins += 1
                        t_total += 1
                    else:
                        ct_wins += 1
                        ct_total += 1
                else:
                    if win_result.startswith("t"):
                        ct_total += 1
                    else:
                        t_total += 1
            t_win_rate = str(round((t_wins / t_total) * 100, 2)) + "%"
            ct_win_rate = str(round((ct_wins / ct_total) * 100, 2)) + "%"
            result.append(
                {"team": team_id, "t_win_rate": t_win_rate, "ct_win_rate": ct_win_rate}
            )
        return result


def analyse_player(player_name: str = None) -> dict:
    if not player_name:
        return {}
    with get_db() as db:
        record = (
            db.query(DataGame.player_name)
            .filter(DataGame.player_name == player_name)
            .limit(1)
            .first()
        )
        if record:
            rating, adr = (
                db.query(
                    func.avg(DataGame.rating),
                    func.avg(DataGame.adr),
                )
                .filter(DataGame.player_name == player_name, DataGame.is_delete == 0)
                .first()
            )
            kpr = (
                db.query(func.avg(DataRound.round_kills).label("kpr"))
                .filter(DataRound.player_name == player_name)
                .scalar()
            )
            team = (
                db.query(PlayerList.team)
                .filter(
                    and_(PlayerList.player_name == player_name, PlayerList.offline == 1)
                )
                .scalar()
            )
            result = {
                "name": player_name,
                "team": team,
                "rating": round(float(rating), 2),
                "adr": round(float(adr), 2),
                "kpr": round(float(kpr), 2),
            }
            return result
        return {}


def get_all_player_stats():
    with get_db() as db:
        player_names = [
            item[0]
            for item in db.query(PlayerList.player_name)
            .filter(PlayerList.team.in_(team_id_list), PlayerList.offline == 1)
            .all()
        ]
        result = []
        for player in player_names:
            p_stats = analyse_player(player)
            if p_stats:
                result.append(p_stats)
        result.sort(key=lambda player: player["team"])
    return result


def analyse_to_excel():
    map_pool_raw = analyse_map_pool(team_id_list)
    pistol_round_raw = analyse_pistol_round(team_id_list)
    players_raw = get_all_player_stats()
    map_rows = []
    for each_team in map_pool_raw:
        team = each_team["team"]
        map_pool = each_team["map_pool"]
        for map_name, (wins, losses) in map_pool.items():
            map_rows.append(
                {"team": team, "map": map_name, "wins": wins, "losses": losses}
            )
    df_map = pd.DataFrame(map_rows)
    pistol_round_rows = []
    for each_team in pistol_round_raw:
        pistol_round_rows.append(
            {
                "team": each_team["team"],
                "t_win_rate": each_team["t_win_rate"],
                "ct_win_rate": each_team["ct_win_rate"],
            }
        )
    df_pistol = pd.DataFrame(pistol_round_rows)
    players_rows = []
    for each_player in players_raw:
        players_rows.append(
            {
                "name": each_player["name"],
                "team": each_player["team"],
                "rating": each_player["rating"],
                "adr": each_player["adr"],
                "kpr": each_player["kpr"],
            }
        )
    df_players = pd.DataFrame(players_rows)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_map.to_excel(writer, sheet_name="Map Pool", index=False)
        df_pistol.to_excel(writer, sheet_name="Pistol Round", index=False)
        df_players.to_excel(writer, sheet_name="Player Stats", index=False)
    print(f"分析结果已导出至: {output_path}")


if __name__ == "__main__":
    analyse_to_excel()
