from flask import Flask, jsonify
from flask_cors import CORS
from analyse import (
    analyse_map_pool,
    analyse_pistol_round,
    analyse_player,
    analyse_side_win_rate,
)
import logging
from sqlalchemy.orm import sessionmaker
from models import *

app = Flask(__name__)
CORS(app)

SessionLocal = sessionmaker(
    bind=ENGINELocal, autoflush=False, autocommit=False, expire_on_commit=False
)


@app.route("/player-compare")
def get_player_compare():
    Session = sessionmaker(bind=ENGINELocal, autocommit=False)
    session = Session()
    try:
        p1, p2 = (
            session.query(CpPlayer.player_name_1, CpPlayer.player_name_2)
            .filter(CpPlayer.select == 1)
            .first()
        )
    except Exception as e:
        logging.error(f"获取当前选择的选手cp错误:{e}", exc_info=True)
    try:
        p1_stats = analyse_player(p1)
        p2_stats = analyse_player(p2)
        result = {"player_1": p1_stats, "player_2": p2_stats}

        return jsonify({"message": "success", "data": result, "code": 200})
    except Exception as e:
        logging.error(f"处理选手对比错误:{e}", exc_info=True)
        return jsonify({"message": "error"})


all_map = [
    "de_ancient",
    "de_anubis",
    "de_dust2",
    "de_inferno",
    "de_mirage",
    "de_nuke",
    "de_train",
]

mapname_index_dict = {
    "de_ancient": 0,
    "de_anubis": 1,
    "de_dust2": 2,
    "de_inferno": 3,
    "de_mirage": 4,
    "de_nuke": 5,
    "de_train": 6,
}


@app.route("/team-compare-map")
def get_team_compare_map():
    session = SessionLocal()
    try:
        cp = session.query(CpTeam).filter(CpTeam.select == 1).first()
        team_1 = cp.team_1
        team_2 = cp.team_2
    except Exception as e:
        logging.error(f"获取当前选择的队伍cp错误:{e}", exc_info=True)
    try:
        team_map_info = analyse_map_pool([team_1, team_2])
        result = []
        for each_map in all_map:
            result.append(
                {
                    "map_name": each_map,
                    "left": {"wins": 0, "losses": 0, "team_id": team_1},
                    "right": {"wins": 0, "losses": 0, "team_id": team_2},
                }
            )
        for each_team in team_map_info:
            map_pool = each_team["map_pool"]
            team_id = each_team["team"]
            for map_name, win_loss_list in map_pool.items():
                if team_id == team_1:
                    result[mapname_index_dict[map_name]]["left"]["wins"] = (
                        win_loss_list[0]
                    )
                    result[mapname_index_dict[map_name]]["left"]["losses"] = (
                        win_loss_list[1]
                    )
                elif team_id == team_2:
                    result[mapname_index_dict[map_name]]["right"]["wins"] = (
                        win_loss_list[0]
                    )
                    result[mapname_index_dict[map_name]]["right"]["losses"] = (
                        win_loss_list[1]
                    )
        return jsonify({"message": "success", "data": result, "code": 200})
    except Exception as e:
        logging.error(f"处理图池对比错误:{e}", exc_info=True)
        return jsonify({"message": "error"})
    finally:
        session.close()


@app.route("/team-compare-pistol")
def get_team_compare_pistol():
    Session = sessionmaker(bind=ENGINELocal, autocommit=False)
    session = Session()
    try:
        cp = session.query(CpTeam).filter(CpTeam.select == 1).first()
        team_1 = cp.team_1
        team_2 = cp.team_2
    except Exception as e:
        logging.error(f"获取当前选择的队伍cp错误:{e}", exc_info=True)
    try:
        result = analyse_pistol_round([team_1, team_2])
        return jsonify({"message": "success", "data": result, "code": 200})
    except Exception as e:
        logging.error(f"处理手枪局对比错误:{e}", exc_info=True)
        return jsonify({"message": "error"})


@app.route("/team-compare-side")
def get_team_compare_side():
    Session = sessionmaker(bind=ENGINELocal, autocommit=False)
    session = Session()
    try:
        cp = session.query(CpTeam).filter(CpTeam.select == 1).first()
        team_1 = cp.team_1
        team_2 = cp.team_2
    except Exception as e:
        logging.error(f"获取当前选择的队伍cp错误:{e}", exc_info=True)
    try:
        result = analyse_side_win_rate([team_1, team_2])
        return jsonify({"message": "success", "data": result, "code": 200})
    except Exception as e:
        logging.error(f"处理手枪局对比错误:{e}", exc_info=True)
        return jsonify({"message": "error"})


@app.route("/player-performance")
def get_player_performance():
    Session = sessionmaker(bind=ENGINELocal, autocommit=False)
    session = Session()
    try:
        player_name_list = [
            item[0]
            for item in session.query(PlayerShow.player_name)
            .filter(PlayerShow.select == 1)
            .all()
        ]
    except Exception as e:
        logging.error(f"获取当前选择的Player错误:{e}", exc_info=True)
    try:
        result = []
        for player in player_name_list:
            result.append(analyse_player(player))
        return jsonify({"message": "success", "data": result, "code": 200})
    except Exception as e:
        logging.error(f"处理Player Performance错误:{e}", exc_info=True)
        return jsonify({"message": "error"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=1236)
