from flask import Flask, jsonify, request
from gsi import server
from datetime import datetime
import global_data
import time
import threading
import json
import requests
import os
from flask_cors import CORS
from sqlalchemy import and_

import xml.etree.ElementTree as ET
from decimal import Decimal
from models import *

app = Flask(__name__)
# 允许所有域名进行跨域访问
CORS(app)

previous_bomb_state = -1
current_bomb_state = -1
isFirstPlanted = True
is_initalize = False
check_current_round = 0
round_wins_count = 0
flag = 0
mvp_player = ""

# app.json.ensure_ascii = False # 解决中文乱码问题

Session = sessionmaker(bind=ENGINELocal, autocommit=False)
session = Session()

# 读取赛前预录选手信息，包括选手名，战队名和舞台位置
player_info_json = "player_info.json"
with open(player_info_json, "r", encoding="utf-8") as f:
    player_info = json.load(f)

# 获取简称
for key, value in player_info["player"].items():
    if value["player_seat"] == 1:
        left_team = value["team_name"]
    elif value["player_seat"] == 6:
        right_team = value["team_name"]

# 获取全称
left_team_long = player_info["teams"]["left"]["fullname"]
right_team_long = player_info["teams"]["right"]["fullname"]

global_json = {}


def readJsonFile(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return None


left_team_short = player_info["teams"]["left"]["shortname"]
right_team_short = player_info["teams"]["right"]["shortname"]


@app.route("/scores")
def scores_aftergame():
    try:
        scores = after_game_score()
        if scores is None:
            return jsonify({"message": "获取比分失败", "data": {}})
        return jsonify({"message": "获取比分成功", "data": scores})
    except Exception as e:
        print(f"发生错误：{e},在第{e.__traceback__.tb_lineno}行")
        return jsonify({"message": "获取比分失败", "data": {}})


def after_game_score():
    try:
        aftergame_data = readJsonFile("gsi_data.json")
        ct_data = aftergame_data["map"]["team_ct"]
        t_data = aftergame_data["map"]["team_t"]
        res = {
            "left_team": left_team_short,
            "right_team": right_team_short,
            "left": 0,
            "right": 0,
        }
        if ct_data["name"] == left_team_long:
            res["left"] = ct_data["score"]
            res["right"] = t_data["score"]
        else:
            res["left"] = t_data["score"]
            res["right"] = ct_data["score"]

        # res = {
        #     "left_team": 'FDG',
        #     "right_team": 'LSH',
        #     "left": 8,
        #     "right": 13,
        # }
        return res
    except Exception as e:
        print(f"发生错误：{e},在第{e.__traceback__.tb_lineno}行")
        return None


def get_aftergame_board():
    Session = sessionmaker(bind=ENGINELocal, autocommit=False)
    session = Session()
    res = {}
    try:
        match_id = player_info["match_id"]
        match_data = session.query(DataGame).filter(DataGame.match_id == match_id).all()
        player_team_dict = {
            name.split("_")[1]: team
            for name, team in session.query(
                PlayerOffline.char_name, PlayerOffline.team_id
            ).all()
        }
        # print(player_team_dict)
        left_team_info = []
        right_team_info = []
        for each_player in match_data:
            name = each_player.player_name
            team = player_team_dict[name]
            data = {
                "player_name": each_player.player_name,
                "kills": each_player.kills,
                "deaths": each_player.deaths,
                "assists": each_player.assists,
                "adr": each_player.adr,
            }
            if team == left_team_short:
                left_team_info.append(data)
            else:
                right_team_info.append(data)
        res["left_team_info"] = left_team_info
        res["right_team_info"] = right_team_info
        return res
    except Exception as e:
        print(f"发生错误：{e},在第{e.__traceback__.tb_lineno}行")
    finally:
        session.close()


def get_aftergame_slide_bar():
    try:
        aftergame_data = readJsonFile("gsi_data.json")
        round_results = list(aftergame_data["map"]["round_wins"].values())
        n = len(round_results)
        top = [0] * n
        bottom = [0] * n
        for i in range(n):
            result = round_results[i]
            if (i <= 11) or (i >= 24 and i % 2 == 0):
                if result == "t_win_bomb":
                    top[i] = 1
                elif result == "t_win_elimination":
                    top[i] = 2
                elif result == "ct_win_defuse":
                    bottom[i] = 1
                elif result == "ct_win_elimination":
                    bottom[i] = 2
                elif result == "ct_win_time":
                    bottom[i] = 3
            elif (i >= 12 and i <= 23) or (i >= 24 and i % 2 != 0):
                if result == "t_win_bomb":
                    bottom[i] = 1
                elif result == "t_win_elimination":
                    bottom[i] = 2
                elif result == "ct_win_defuse":
                    top[i] = 1
                elif result == "ct_win_elimination":
                    top[i] = 2
                elif result == "ct_win_time":
                    top[i] = 3
        if n > 24:
            top = top[0:23]
            bottom = bottom[0:23]

        return {"top": top, "bottom": bottom}
    except Exception as e:
        print(f"发生错误：{e},在第{e.__traceback__.tb_lineno}行")


@app.route("/aftergameBoard")
def aftergameBoard():
    try:
        data = get_aftergame_board()
        return jsonify({"msg": "请求成功", "data": data})
    except Exception as e:
        print(f"发生错误：{e},在第{e.__traceback__.tb_lineno}行")
        return jsonify({"msg": "error"})


@app.route("/aftergameSlideBar")
def aftergame_slide_bar():
    try:
        data = get_aftergame_slide_bar()
        return jsonify({"msg": "请求成功", "data": data})
    except Exception as e:
        print(f"发生错误：{e},在第{e.__traceback__.tb_lineno}行")
        return jsonify({"msg": "error"})


def parse_scoreboard():
    global global_json
    res = {}
    res["left_team"], res["right_team"] = [], []
    try:
        # 获取本局结算数据
        with open("gsi_data.json", "r", encoding="utf-8") as file:
            all_players_data = json.load(file)
        global_json = all_players_data
        # 获取所有回合adr_json
        folder_path = "./adr_json"
        all_adr_json = []
        for adr_file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, adr_file)
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                all_adr_json.append(data)
        # print('all_adr_json', all_adr_json)
        for key, player_data in all_players_data["allplayers"].items():
            # 取到选手预录信息
            this_player_info = player_info["player"][str(key)]
            # 选手本场比赛数据
            this_player_data = player_data["match_stats"]
            # 判断选手是否存活
            # is_dead = 0 if player_data["state"]["health"]>0 else 1
            player_adr = 0
            matches_number = len(all_adr_json)
            for player in all_adr_json:
                player_adr += player[str(key)]
            if this_player_info["team_name"].strip() == left_team:
                res["left_team"].append(
                    {
                        "player_name": this_player_info["player_name"],
                        "team_name": this_player_info["team_name"],
                        "seat": this_player_info["player_seat"],
                        "K": this_player_data["kills"],
                        "D": this_player_data["deaths"],
                        "A": this_player_data["assists"],
                        "KD": str(this_player_data["kills"])
                        + "/"
                        + str(this_player_data["deaths"]),
                        "ADR": int(player_adr / matches_number),
                        # 'is_dead': is_dead
                    }
                )
            else:
                res["right_team"].append(
                    {
                        "player_name": this_player_info["player_name"],
                        "team_name": this_player_info["team_name"],
                        "seat": this_player_info["player_seat"],
                        "K": this_player_data["kills"],
                        "D": this_player_data["deaths"],
                        "A": this_player_data["assists"],
                        "KD": str(this_player_data["kills"])
                        + "/"
                        + str(this_player_data["deaths"]),
                        "ADR": int(player_adr / matches_number),
                        # 'is_dead': is_dead
                    }
                )
        res["left_team"].sort(key=lambda a: a["ADR"], reverse=True)
        res["right_team"].sort(key=lambda a: a["ADR"], reverse=True)
        # print("---------------------------------scoreboard--------------------", res)
        return res

    except Exception as e:
        print(f"发生错误：{e}")
        print(e.__traceback__.tb_lineno)
        return {}


@app.route("/scoreboard")
def scoreboard():
    res = parse_scoreboard()
    return jsonify({"msg": "请求成功", "data": res})


# 响应mvp页面请求
@app.route("/player_list")
def player_list():
    players = []
    # for player in parse_scoreboard()["left_team"]:
    #     players.append(player["player_name"])
    # for player in parse_scoreboard()["right_team"]:
    #     players.append(player["player_name"])
    try:
        session = Session()
        list = [
            p[0]
            for p in session.query(PlayerList.nickname)
            .filter(and_(PlayerList.starter == 1, PlayerList.team.in_(("UOB", "idfj"))))
            .all()
        ]
        print(f"player_list:{list}")
        # player_info = readJsonFile("player_info.json")
        # players = player_info["player"]
        # player_list = [player["player_name"] for player in players.values()]
        return jsonify({"message": "选手列表获取成功！", "data": list})
    except Exception as e:
        print(f"发生异常：{e}, 在第{e.__traceback__.tb_lineno}行")
        return jsonify({"message": "选手列表获取失败！", "data": []})


# 修改mvp全局变量
@app.route("/setMvp", methods=["POST"])
def setMvp():
    global mvp_player
    mvp = request.form.get("mvp")
    mvp_player = mvp
    print(f"已设置本局mvp为:{mvp_player}")
    return "", 204


# mvp赛后接口
@app.route("/mvp")
def mvp():
    Session = sessionmaker(bind=ENGINELocal, autocommit=False)
    session = Session()
    try:
        match_code = (
            session.query(GameList.match_code)
            .order_by(GameList.create_time.desc())
            .first()[0]
        )
        mvp = None
        team = ""
        name = ""
        players = (
            session.query(DataGame)
            .filter(DataGame.match_code == match_code)
            .order_by(DataGame.rating.desc(), DataGame.adr.desc())
            .all()
        )
        win_team = (
            session.query(GameList.win_team)
            .order_by(GameList.create_time.desc())
            .first()[0]
        )
        for p in players:
            player_info = (
                session.query(PlayerList.team, PlayerList.player_name)
                .filter(PlayerList.nickname == p.player_name)
                .first()
            )
            if player_info[0] == win_team:
                mvp = p
                team = player_info[0].upper()
                name = player_info[1]
                break
        # mvp_info = {
        #     "player_name": "Linz1",
        #     "team": "BEER",
        #     "kills": 19,
        #     "deaths": 12,
        #     "assists": 6,
        #     "adr": 111,
        #     "headshotratio": "50%",
        #     "opening dules": 5,
        #     "muitikills": 8,
        # }
        mvp_info = {
            "player_name": name,
            "team": team,
            "kills": mvp.kills,
            "deaths": mvp.deaths,
            "assists": mvp.assists,
            "headshotratio": float(mvp.headshotratio),
            "adr": mvp.adr,
            "opening dules": mvp.firstkill,
            "firstdeath": mvp.firstdeath,
            "sniperkills": mvp.sniperkills,
            "muitikills": mvp.muitikills,
            "utilitydmg": mvp.utilitydmg,
            "kast": float(mvp.kast),
            "rating": float(mvp.rating),
        }
        return jsonify({"msg": "请求成功", "data": mvp_info})
    except Exception as e:
        print(f"发生异常：{e}, 在第{e.__traceback__.tb_lineno}行")
        return jsonify(
            {"msg": "请求失败", "data": {}, "description": "未查询到匹配的选手！"}
        )


# 手选mvp接口
@app.route("/selectedMVP")
def selectedMVP():
    try:
        match_code = (
            session.query(GameList.match_code)
            .order_by(GameList.create_time.desc())
            .first()[0]
        )
        mvp = (
            session.query(DataGame)
            .filter(
                and_(
                    DataGame.player_name == mvp_player,
                    DataGame.match_code == match_code,
                )
            )
            .first()
        )
        mvp_info = {
            "player_name": mvp.player_name,
            "kills": mvp.kills,
            "deaths": mvp.deaths,
            "assists": mvp.assists,
            "headshotratio": float(mvp.headshotratio),
            "adr": mvp.adr,
            "firstkill": mvp.firstkill,
            "firstdeath": mvp.firstdeath,
            "sniperkills": mvp.sniperkills,
            "muitikills": mvp.muitikills,
            "utilitydmg": mvp.utilitydmg,
            "kast": float(mvp.kast),
            "rating": float(mvp.rating),
        }
        return jsonify({"msg": "请求成功", "data": mvp_info})
    except Exception as e:
        print(f"发生异常：{e}, 在第{e.__traceback__.tb_lineno}行")
        return jsonify(
            {"msg": "请求失败", "data": {}, "description": "未查询到匹配的选手！"}
        )


# 存赛后数据
@app.route("/saveMatchData", methods=["POST"])
def saveMatchData():
    Session = sessionmaker(bind=ENGINELocal, autocommit=False)
    session = Session()

    # 从请求参数中获取 match_code，match_week, match_day, match_num, type, series
    match_code = request.form.get("match_code")
    match_id = request.form.get("match_id")
    if not match_code:
        return jsonify({"error": "缺少 match_code 参数"}), 400

    # 拼接访问的 URL
    url = f"https://mega-tpa.5eplaycdn.com/xml/bracket/tournament/match_xml?match_code={match_code}"

    try:
        response = requests.get(url, proxies={"http": None, "https": None})
        response.raise_for_status()
    except Exception as e:
        print(f"请求数据失败：{str(e)}")
        return jsonify({"error": f"请求数据失败：{str(e)}"}), 500

    # 解析 XML
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        print(f"XML 解析错误：{str(e)}")
        return jsonify({"error": f"XML 解析错误：{str(e)}"}), 500

    # 检查 error 节点
    error_node = root.find("error")
    if error_node is None or error_node.text != "0":
        print("XML 数据返回错误")
        return jsonify({"error": "XML 数据返回错误"}), 400

    data_node = root.find("data")
    if data_node is None:
        print("未找到数据节点")
        return jsonify({"error": "未找到数据节点"}), 400

    # nicknames = [name[0] for name in session.query(PlayerList.nickname).filter(PlayerList.team==win_team).all()]

    # 遍历每个 <item> 节点，解析数据并保存到数据库
    for item in data_node.findall("item"):
        try:
            steamid = item.find("steamid").text.strip()
            # 获取昵称作为玩家名称（也可以使用steamid等其它字段，按实际需求处理）
            nickname = item.find("nickname").text.strip()
            kills = int(item.find("kills").text)

            # headshotratio 带有百分号，需要去除后转换为 Decimal
            headshot_str = item.find("headshotratio").text.strip().replace("%", "")
            headshotratio = Decimal(headshot_str)

            deaths = int(item.find("deaths").text)
            assists = int(item.find("assists").text)
            # adr 字段在 XML 中可能是小数，但数据库定义为 Integer，根据需要可以四舍五入或取整
            adr_value = float(item.find("adr").text)
            adr = int(round(adr_value))

            firstkill = int(item.find("firstkill").text)
            firstdeath = int(item.find("firstdeath").text)
            sniperkills = int(item.find("sniperkills").text)
            muitikills = int(item.find("muitikills").text)
            utilitydmg = int(item.find("utilitydmg").text)

            # kast 带百分号
            kast_str = item.find("kast").text.strip().replace("%", "")
            kast = Decimal(kast_str)

            rating = Decimal(item.find("rating").text)
        except Exception as e:
            # 如果某个节点解析出错，则跳过该项或记录日志
            print(e)
            continue

        # 创建或更新 DataGame 记录（由于主键是 match_code 和 player_name 的组合）
        data_game = DataGame(
            match_code=match_code,
            player_name=nickname,
            kills=kills,
            headshotratio=headshotratio,
            deaths=deaths,
            assists=assists,
            adr=adr,
            firstkill=firstkill,
            firstdeath=firstdeath,
            sniperkills=sniperkills,
            muitikills=muitikills,
            utilitydmg=utilitydmg,
            kast=kast,
            rating=rating,
            match_id=match_id,
        )
        # 使用 merge 可在记录已存在时进行更新，否则插入新记录
        session.merge(data_game)
        # session.query(PlayerList).filter(PlayerList.steam_id == steamid).update(
        #     {PlayerList.nickname: nickname}
        # )
    # 根据5e数据更新player_list

    # 记录本场比赛
    match_week = request.form.get("match_week")
    match_day = request.form.get("match_day")
    match_num = request.form.get("match_num")
    type = request.form.get("type")
    series = request.form.get("series")
    description = request.form.get("description")
    team1 = request.form.get("team1")
    team2 = request.form.get("team2")
    win_team = request.form.get("win_team")

    must_params = [
        match_week,
        match_day,
        match_num,
        type,
        series,
        team1,
        team2,
        win_team,
    ]

    if any(p == "" or p is None for p in must_params):
        return jsonify({"error": "缺少必需参数"}), 400

    game = GameList(
        match_code=match_code,
        match_id=match_id,
        match_week=match_week,
        match_day=match_day,
        match_num=match_num,
        type=type,
        series=series,
        description=description,
        team1=team1,
        team2=team2,
        win_team=win_team,
    )
    session.merge(game)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"数据库保存错误：{str(e)}")
        return jsonify({"error": f"数据库保存错误：{str(e)}"}), 500

    return jsonify({"message": "数据保存成功"}), 200


# 动态显示队名
@app.route("/teamNames")
def get_team_names():
    data = readJsonFile("player_info.json")
    teams = {
        "team1": data["teams"]["left"]["shortname"],
        "team2": data["teams"]["right"]["shortname"],
    }
    return jsonify({"message": "获取队名成功！", "data": teams})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=1111, debug=False)
