from flask import Flask, jsonify
from gsi import server
from datetime import datetime
from models import *
from sqlalchemy import and_, or_
from all_api import after_game_score
from service import *
from functools import reduce, lru_cache
from operator import add
import global_data
import time
import threading
import json
import requests
import os
import logging
import traceback

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

previous_bomb_state = -1
current_bomb_state = -1
isFirstPlanted = True
is_initalize = False
check_current_round = 0
round_wins_count = 0
flag = 0
c4_planted_url = "http://192.168.15.235:8000/api/location/2/0/1/press"
c4_defused_url = "http://192.168.15.235:8000/api/location/2/1/1/press"
c4_exploded_url = "http://192.168.15.235:8000/api/location/2/2/1/press"
c4_all_off = "http://192.168.15.235:8000/api/location/2/0/2/press"

left_win = "http://192.168.15.235:8000/api/location/2/0/3/press"
right_win = "http://192.168.15.235:8000/api/location/2/1/3/press"

phase_off = ["timeout_ct", "timeout_t", "paused", "freezetime"]
phase_music_off = []
C4_OFF = False

last_phase = ""
over_count = 0

paused_bgm_url = "http://192.168.200.49:8000/api/location/1/0/1/press"
halfgame_bgm_url = "http://192.168.200.49:8000/api/location/1/0/3/press"
win_bgm_url = "http://192.168.200.49:8000/api/location/1/0/2/press"
turnoff_bgm_url = "http://192.168.200.49:8000/api/location/1/0/4/press"

# 读取赛前预录选手信息，包括选手名，战队名和舞台位置
player_info_json = "player_info.json"
player_info = None
with open(player_info_json, "r", encoding="utf-8") as f:
    player_info = json.load(f)

# 获取全称
left_team = player_info["teams"]["left"]["fullname"]
right_team = player_info["teams"]["right"]["fullname"]
left_team_short = player_info["teams"]["left"]["shortname"]
right_team_short = player_info["teams"]["right"]["shortname"]


def initalizeRound():
    global round_wins_count, isFirstPlanted, previous_bomb_state, is_initalize, current_bomb_state
    if not is_initalize:
        round_wins_count = (
            global_data.data["map"]["round"]
            if "round_wins" in global_data.data["map"]
            else 0
        )
        previous_bomb_state = (
            global_data.bomb_state_map.get(global_data.data["bomb"]["state"])
            if "bomb" in global_data.data
            else -1
        )
        global_data.bomb_state = previous_bomb_state
        # print('previous_bomb_state', previous_bomb_state)
        is_initalize = True


# checkGlobalData:用于刷新全局
def checkGlobalData():
    global isFirstPlanted, round_wins_count, left_team, right_team, side_swaped, t_name_firsthalf, ct_name_firsthalf
    # 检查队名是否输入正确
    # gsi_team_names = {
    #     global_data.data["map"]["team_ct"]["name"],
    #     global_data.data["map"]["team_t"]["name"],
    # }
    # if {left_team, right_team} != gsi_team_names:
    #     print("配置文件队名输入有误！")
    #     raise SystemExit
    # print(f'ct timeouts remaining: {global_data.data["map"]["team_ct"]["timeouts_remaining"]}')
    # print(f't timeouts remaining: {global_data.data["map"]["team_t"]["timeouts_remaining"]}')
    # time.sleep(5)
    current_round = global_data.data["map"]["round"]
    # 输出bomb状态，在当前回合内判断，若current_round!=global_data.round，则更新current_round后再取bomb状态
    if current_round == global_data.round:
        # 有时候bomb里取不到state，需要从round取
        if "bomb" in global_data.data:
            bomb_state_str = global_data.data["bomb"]["state"]
        elif "round" in global_data.data:
            bomb_state_str = global_data.data["round"]["bomb"]
        else:
            # 若都没有，打印当前全部数据检查
            # print(global_data.data)
            pass
        # 更新全局bomb状态
        global_data.bomb_state = global_data.bomb_state_map.get(bomb_state_str)
    else:
        global_data.round = current_round
        isFirstPlanted = True
        print("回合更新，重置了一次!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    # 输出队伍胜利，根据round_wins长度增加触发
    if "round_wins" in global_data.data["map"]:
        round_wins = global_data.data["map"]["round_wins"]
    else:
        # 第一回合没有roundwins
        round_wins = {}

    team_t = global_data.data["map"]["team_t"]["name"]
    team_ct = global_data.data["map"]["team_ct"]["name"]
    current_round_wins_count = len(round_wins)

    if current_round_wins_count != round_wins_count and is_initalize:
        round_result = list(round_wins.values())
        if len(round_result) > 0:
            latest_winner = round_result[-1]
        else:
            latest_winner = "n"
        if latest_winner[0] == "t":
            if team_t == left_team:
                print(f"Team{team_t} won!!! Left")
                # requests.post(left_win)
            else:
                print(f"Team{team_t} won!!! Right")
                # requests.post(right_win)
        elif latest_winner[0] == "c":
            if team_ct == left_team:
                print(f"Team{team_ct} won!!! Left")
                # requests.post(left_win)
            else:
                print(f"Team{team_ct} won!!! Right")
                # requests.post(right_win)
        round_wins_count = current_round_wins_count

    # print(global_data.data['map']['round'])
    # print(f"round:{global_data.data['map']['round']}, phase:{global_data.data['phase_countdowns']['phase']}")
    if (
        global_data.data["map"]["round"] == 12
        and side_swaped == False
        and global_data.data["phase_countdowns"]["phase"] == "freezetime"
    ):
        print("换边成功")
        t_name_firsthalf, ct_name_firsthalf = ct_name_firsthalf, t_name_firsthalf
        side_swaped = True


def sendEventMsg():
    global previous_bomb_state, isFirstPlanted, current_bomb_state, C4_OFF, last_phase, over_count
    phase = global_data.data["round"]["phase"]
    round = global_data.data["map"]["round"]
    map_phase = global_data.data["map"]["phase"]
    # print(round)
    if is_initalize:
        bomb_state = global_data.bomb_state
        # print(bomb_state)
        # 判断炸弹状态是否改变，无改变不打印
        current_bomb_state = bomb_state
    if previous_bomb_state != current_bomb_state:
        # 只有phase在Live时，埋包才有必要发送请求
        if bomb_state == 1 and phase == "live" and isFirstPlanted:
            # requests.post(c4_planted_url)
            print(global_data.bomb_state_msg[bomb_state])

            isFirstPlanted = False
        # 只要包爆炸了或者被拆了，都需要发送请求
        # 拆
        elif bomb_state == 4:
            # requests.post(c4_defused_url)
            print(global_data.bomb_state_msg[bomb_state])
        # 炸
        elif bomb_state == 2:
            # requests.post(c4_exploded_url)
            print(global_data.bomb_state_msg[bomb_state])
        # 其他情况都不发送请求

        previous_bomb_state = current_bomb_state

    phase_flag = global_data.data["phase_countdowns"]["phase"]

    # print(phase_flag)
    # seconds = global_data.data["phase_countdowns"]["phase_ends_in"]
    # print(seconds)
    # print(f"当前的phase是:{phase_flag}")
    if phase_flag in phase_off and not C4_OFF:
        # C4 ALL OFF
        # requests.post(c4_all_off)
        C4_OFF = True
        print("C4 ALL OFF!!!!!!!!!!")
    elif (
        phase_flag in ("timeout_ct", "timeout_t", "paused")
        and phase_flag != last_phase
        and round != 12
    ):
        print("播放暂停音乐")
        # requests.post(paused_bgm_url)
    elif phase_flag == "over" and round == 12 and phase_flag != last_phase:
        print("播放半场暂停音乐")
        # requests.post(halfgame_bgm_url)
    # elif phase_flag == 'freezetime' and last_phase in ("timeout_ct", "timeout_t", "paused"):
    #     print('播放暂停音乐')
    # elif phase_flag == 'freezetime' and last_phase in ("timeout_ct", "timeout_t", "paused") and seconds in ("3.9","3.8","3.7","3.6","3.5","3.4","3.3","3.2","3.1","3.0"):
    #     print('关闭暂停音乐')
    elif phase_flag == "live" and last_phase == "freezetime":
        print("关闭暂停音乐")
        # requests.post(turnoff_bgm_url)
    elif map_phase == "gameover" and over_count == 0:
        print("播放结束音乐")
        # requests.post(win_bgm_url)
        # print(over_count)
        over_count += 1
    elif phase_flag == "live":
        C4_OFF = False
    last_phase = phase_flag
    # print(f"已更新上个phase为:{last_phase}")


def save_round_data():
    # 用于判断游戏是否结束
    global flag
    # current_round = global_data.data['map']['round']
    # 在一回合结束后导出本局json数据
    if global_data.data["phase_countdowns"]["phase"] == "over":
        current_round = global_data.data["map"]["round"]
        # 储存本回合adr json数据
        adr_data = {}
        for player_id, player_data in global_data.data["allplayers"].items():
            adr_data[player_id] = player_data["state"]["round_totaldmg"]
        folder_path = "./adr_json"
        round_data = os.path.join(folder_path, f"round_{current_round}_data")
        # print('adr_data', adr_data)
        with open(round_data, "w", encoding="utf-8") as file:
            json.dump(adr_data, file, ensure_ascii=False, indent=4)
    # 在游戏结束时，储存最后一回合的json数据
    elif global_data.data["map"]["phase"] == "gameover" and flag == 0:
        current_round = global_data.data["map"]["round"]
        # 储存本回合adr json数据
        adr_data = {}
        for player_id, player_data in global_data.data["allplayers"].items():
            adr_data[player_id] = player_data["state"]["round_totaldmg"]
        folder_path = "./adr_json"
        round_data = os.path.join(folder_path, f"round_{current_round}_data")
        # print('adr_data', adr_data)
        with open(round_data, "w", encoding="utf-8") as file:
            json.dump(adr_data, file, ensure_ascii=False, indent=4)
        flag += 1


def backgroundProcess():
    while True:
        try:
            checkGlobalData()
            sendEventMsg()
            store_round_data()
            # store_real_time_data()
        except Exception as e:
            logging.error(f"发生错误{e}", exc_info=True)


@app.route("/allPlayerState")
def allPlayerState():
    res = {"players": [], "left_team_timeout": 0, "right_team_timeout": 0, "boom": 0}
    try:
        all_players_data = global_data.data["allplayers"]
        for key, player_data in all_players_data.items():
            steam_ids_record = list(player_info["player"].keys())
            if key not in steam_ids_record:
                continue
            # 取到选手预录信息
            this_player_info = player_info["player"][str(key)]
            # 选手本场比赛数据
            this_player_data = player_data["match_stats"]
            # 判断选手是否存活
            is_dead = 0 if player_data["state"]["health"] > 0 else 1
            res["players"].append(
                {
                    "player_name": this_player_info["player_name"],
                    "player_name_with_team": this_player_info["team_name"]
                    + "_"
                    + this_player_info["player_name"],
                    "team_name": this_player_info["team_name"],
                    "seat": this_player_info["player_seat"],
                    "K": this_player_data["kills"],
                    "D": this_player_data["deaths"],
                    "A": this_player_data["assists"],
                    "KDA": str(this_player_data["kills"])
                    + "/"
                    + str(this_player_data["deaths"])
                    + "/"
                    + str(this_player_data["assists"]),
                    "is_dead": is_dead,
                }
            )
        side = None
        phase = global_data.data["phase_countdowns"]["phase"]

        if phase == "timeout_ct":
            side = "team_ct"
        elif phase == "timeout_t":
            side = "team_t"

        if side:
            # res["timeout_team"] = global_data.data["map"][side]["name"]
            team = global_data.data["map"][side]["name"]
            teams_config = list(player_info["teams"].values())
            # res["timeout_team"] = next(
            #     (t["shortname"] for t in teams_config if t["fullname"] == team)
            # )
            timeout_team_name = next(
                (t["shortname"] for t in teams_config if t["fullname"] == team)
            )
            if timeout_team_name == left_team:
                res["left_team_timeout"] = 1
            else:
                res["right_team_timeout"] = 1

        boom = 0
        planting = 0
        if (
            "bomb" in global_data.data
            and global_data.data["bomb"]["state"] == "exploded"
        ):
            boom = 1
        elif (
            "bomb" in global_data.data
            and global_data.data["bomb"]["state"] == "planting"
        ):
            planting = 1
        res["boom"] = boom
        res["planting"] = planting
        res["players"].sort(key=lambda a: a["seat"])
        return jsonify({"msg": "succeed", "data": res})

    except Exception as e:
        logging.error(f"all player error:{e}", exc_info=True)
        return jsonify({"msg": "Error...", "data": []})


# 目前ob的选手数据
@app.route("/observedPlayer")
def observedPlayer():
    res = {}
    try:
        data = global_data.data["player"]
        player_name = data["name"]
        allplayers = allPlayerState()["data"]
        # for player in allplayers:
        #     if allplayers[player]['name'] == player_name:
        #         data['adr'] = adr[player]
        res = data
        return jsonify({"msg": "请求成功", "data": res})
    except Exception as e:
        print(f"发生错误：{e}")
        return jsonify({"msg": "内部异常...", "data": {}})


t_name_firsthalf = ""
ct_name_firsthalf = ""
# 选边初始化标志
side_initialized = False
# 换边标志
side_swaped = False
# t和ct上半场的分数
t_wins_firsthalf = 0
ct_wins_firsthalf = 0


def initializeSide():
    global side_initialized, t_name_firsthalf, ct_name_firsthalf, t_wins_firsthalf, ct_wins_firsthalf
    round = global_data.data["map"]["round"]
    if not side_initialized and round >= 12:
        round_wins_values = list(global_data.data["map"]["round_wins"].values())
        t_wins, ct_wins = 0, 0
        for result in round_wins_values[0:12]:
            if result[0] == "c":
                ct_wins += 1
            else:
                t_wins += 1
            t_wins_firsthalf = t_wins
            ct_wins_firsthalf = ct_wins
    ct_name_firsthalf = global_data.data["map"]["team_ct"]["name"]
    t_name_firsthalf = global_data.data["map"]["team_t"]["name"]
    side_initialized = True


# teamnames = {"wolfesport": "WF", "Beer": "BEER"}


def real_time_score():
    global left_team, right_team, t_wins_firsthalf, ct_wins_firsthalf
    try:
        ct_wins = 0
        t_wins = 0
        # 如果加时，用另一套逻辑
        if global_data.data["map"]["round"] >= 24:
            print("加时比分")
            t_data = global_data.data["map"]["team_t"]
            ct_data = global_data.data["map"]["team_ct"]
            if t_data["name"] == left_team:
                return {
                    "left": t_data["score"],
                    "left_team": left_team_short,
                    "right": ct_data["score"],
                    "right_team": right_team_short,
                }
            else:
                return {
                    "left": ct_data["score"],
                    "left_team": left_team_short,
                    "right": t_data["score"],
                    "right_team": right_team_short,
                }
        if "round_wins" in global_data.data["map"]:
            round_wins = global_data.data["map"]["round_wins"]
            for result in round_wins.values():
                if result[0] == "c":
                    ct_wins += 1
                else:
                    t_wins += 1
            # 换边之后，记录上半场比分
            if (
                global_data.data["map"]["round"] == 12
                and global_data.data["phase_countdowns"]["phase"] == "freezetime"
            ):
                t_wins_firsthalf = t_wins
                ct_wins_firsthalf = ct_wins

            if left_team == ct_name_firsthalf:
                left_score = ct_wins - ct_wins_firsthalf + t_wins_firsthalf
                right_score = t_wins - t_wins_firsthalf + ct_wins_firsthalf
            else:
                left_score = t_wins - t_wins_firsthalf + ct_wins_firsthalf
                right_score = ct_wins - ct_wins_firsthalf + t_wins_firsthalf

            left_team_player_info = []
            right_team_player_info = []
            t_fullname = global_data.data["map"]["team_t"]["name"]
            ct_fullname = global_data.data["map"]["team_ct"]["name"]
            match_id = player_info["match_id"]

            for player_data in global_data.data["allplayers"].values():
                side = player_data["team"]  # t/ct
                match_stats = player_data["match_stats"]
                adr_dict = get_players_adr(match_id)
                adr = int(adr_dict[player_data["name"]]) if adr_dict is not None else 0
                data = {
                    "player_name": player_data["name"],
                    "kills": match_stats["kills"],
                    "deaths": match_stats["deaths"],
                    "assists": match_stats["assists"],
                    "adr": adr,
                }
                if (side == "T" and t_fullname == left_team) or (
                    side == "CT" and ct_fullname == left_team
                ):
                    left_team_player_info.append(data)
                elif (side == "T" and t_fullname == right_team) or (
                    side == "CT" and ct_fullname == right_team
                ):
                    right_team_player_info.append(data)

            res = {
                "left": left_score,
                "right": right_score,
                "left_team": left_team_short,
                "right_team": right_team_short,
                "left_team_info": left_team_player_info,
                "right_team_info": right_team_player_info,
            }
        else:
            res = {
                "left": 0,
                "right": 0,
                "left_team": left_team_short,
                "right_team": right_team_short,
                "left_team_info": [],
                "right_team_info": [],
            }
        res["left_team_info"].sort(key=lambda player: player["adr"], reverse=True)
        res["right_team_info"].sort(key=lambda player: player["adr"], reverse=True)
        # print(res)
        return res
    except Exception as e:
        print(f"发生错误：{e},在第{e.__traceback__.tb_lineno}行")
        traceback.print_exc()
        return None

    # def get_players_adr(match_id):
    Session = sessionmaker(bind=ENGINELocal, autocommit=False)
    session = Session()
    res = {}
    try:
        all_players = [
            p[0]
            for p in session.query(DataRound.player_name)
            .filter(DataRound.match_id == match_id)
            .distinct()
            .all()
        ]
        round_count = (
            session.query(DataRound.round)
            .order_by(DataRound.round.desc())
            .limit(1)
            .scalar()
        )
        if (all_players == [] or all_players is None) or round_count is None:
            return None

        # dmg_list = [
        #         (item[0], item[1])
        #         for item in session.query(DataRound.player_name, DataRound.round_totaldmg)
        #         .filter(
        #             DataRound.match_id == match_id
        #         )
        #         .all()
        #     ]
        for player in all_players:
            dmg_list = [
                item[0]
                for item in session.query(DataRound.round_totaldmg)
                .filter(
                    and_(
                        DataRound.player_name == player, DataRound.match_id == match_id
                    )
                )
                .all()
            ]
            res[player] = reduce(add, dmg_list) / round_count
        return res
    except Exception as e:
        logging.error(f"获取比赛基本信息错误: {e}", exc_info=True)
        return None


def get_players_adr(match_id):
    try:
        Session = sessionmaker(bind=ENGINELocal, autocommit=False)
        session = Session()
        round_count = (
            session.query(func.max(DataRound.round))
            .filter(DataRound.match_id == match_id)
            .scalar()
        )
        if not round_count:
            return None
        player_adr_dict = {
            player_name: total_dmg / round_count
            for player_name, total_dmg in session.query(
                DataRound.player_name,
                func.sum(DataRound.round_totaldmg).label("total_dmg"),
            )
            .filter(DataRound.match_id == match_id)
            .group_by(DataRound.player_name)
            .all()
        }
        return player_adr_dict
    except Exception as e:
        logging.error(f"处理adr时发生错误{e}", exc_info=True)
        return None


@app.route("/scores")
def scores():
    try:
        scores = real_time_score()
        if scores is None:
            return jsonify({"message": "获取比分失败", "data": {}})
        return jsonify({"message": "获取比分成功", "data": scores})
    except Exception as e:
        print(f"发生错误：{e},在第{e.__traceback__.tb_lineno}行")
        return jsonify({"message": "获取比分失败", "data": {}})


@app.route("/scoreboard")
def scoreboard():
    res = {}
    res["left_team"], res["right_team"] = [], []
    try:
        # 获取本局结算数据
        with open("gsi_data.json", "r", encoding="utf-8") as file:
            all_players_data = json.load(file)
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
            if this_player_info["team_name"] == left_team:
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

        return jsonify({"msg": "succeed", "data": res})

    except Exception as e:
        print(f"发生错误：{e}")
        print(e.__traceback__.tb_lineno)
        return jsonify({"msg": "内部异常...", "data": {}})


result_written = False


def store_real_time_data():
    global result_written
    Session = sessionmaker(bind=ENGINELocal, autocommit=False)
    session = Session()
    # 获取配置文件信息
    try:
        match_id = player_info["match_id"]
        schedule_id = player_info["schedule_id"]
        team_1 = player_info["teams"]["left"]["shortname"]
        team_2 = player_info["teams"]["right"]["shortname"]
    except Exception as e:
        logging.error(f"获取比赛基本信息错误: {e}", exc_info=True)
        return
    # 更新match和schedule状态
    try:
        schedule_status = (
            session.query(Schedule.schedule_status)
            .filter(Schedule.schedule_id == schedule_id)
            .scalar()
        )
        match_status = (
            session.query(Match.match_status)
            .filter(Match.match_id == match_id)
            .scalar()
        )
        if schedule_status == 1 and match_status == 1:
            session.query(Schedule).filter(Schedule.schedule_id == schedule_id).update(
                {
                    "schedule_status": 2,
                    "schedule_real_start_time": int(time.time() * 1000),
                }
            )
            session.query(Match).filter(Match.match_id == match_id).update(
                {
                    "match_status": 2,
                    "match_real_start_time": int(time.time() * 1000),
                }
            )
        elif schedule_status == 2 and match_status == 1:
            session.query(Match).filter(Match.match_id == match_id).update(
                {
                    "match_status": 2,
                    "match_real_start_time": int(time.time() * 1000),
                }
            )
    except Exception as e:
        logging.error(f"更新status和start_time时发生错误: {e}", exc_info=True)
        session.rollback()
        session.close()
        return

    # 1. 保存正在进行的match的基本信息
    try:
        exists = (
            session.query(RealTimeMatch)
            .filter(RealTimeMatch.match_id == match_id)
            .first()
            is not None
        )
        if not exists:
            real_time_match = RealTimeMatch(
                match_id=match_id,
                team_1=team_1.upper(),
                team_2=team_2.upper(),
                team_1_score=0,
                team_2_score=0,
            )
            session.add(real_time_match)
    except Exception as e:
        logging.error(f"插入新的real_time_match时发生错误: {e}", exc_info=True)
        session.rollback()
        session.close()
        return

    # 2. 保存比分信息
    try:
        score_info = real_time_score()
        session.query(RealTimeMatch).filter(RealTimeMatch.match_id == match_id).update(
            {"team_1_score": score_info["left"], "team_2_score": score_info["right"]}
        )
    except Exception as e:
        logging.error(f"更新比分时发生错误: {e}", exc_info=True)
        session.rollback()
        session.close()
        return

    # 3. 保存选手信息
    try:
        for steam_id, data in global_data.data["allplayers"].items():
            # print(global_data.data["allplayers"])
            # time.sleep(10)
            in_game_name = data["name"]
            steam_ids_record = player_info["player"].keys()
            if steam_id not in steam_ids_record:
                continue
            player_name, team = (
                session.query(PlayerList.player_name, PlayerList.team)
                .filter(PlayerList.nickname == in_game_name, PlayerList.offline == 1)
                .first()
            )
            # print(player_name)
            kills = data["match_stats"]["kills"]
            deaths = data["match_stats"]["deaths"]
            assists = data["match_stats"]["assists"]
            # 若当前比赛的实时选手数据不存在，则插入
            if (
                session.query(RealTimePlayer)
                .filter(
                    and_(
                        RealTimePlayer.match_id == match_id,
                        RealTimePlayer.steam_id == steam_id,
                    )
                )
                .first()
                is None
            ):
                real_time_player = RealTimePlayer(
                    match_id=match_id,
                    steam_id=steam_id,
                    player_name=player_name,
                    kills=kills,
                    deaths=deaths,
                    assists=assists,
                    team=team,
                )
                session.add(real_time_player)
            # 若存在，则更新
            # old_damage = (
            #     session.query(RealTimePlayer.damage)
            #     .filter(
            #         and_(
            #             RealTimePlayer.match_id == match_id,
            #             RealTimePlayer.steam_id == steam_id,
            #         )
            #     )
            #     .scalar()
            # )
            session.query(RealTimePlayer).filter(
                and_(
                    RealTimePlayer.match_id == match_id,
                    RealTimePlayer.steam_id == steam_id,
                )
            ).update(
                {
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists,
                }
            )
    except Exception as e:
        logging.error(f"更新选手信息时时发生错误: {e}", exc_info=True)
        session.rollback()
        session.close()
        return
    # 游戏结束时，把状态改成3，已结束,并更新比分和真实结束时间
    try:
        with open("player_info.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if data["is_over"] == "1" and not result_written:
            game_result = after_game_score()
            winner = (
                game_result["left_team"]
                if game_result["left"] > game_result["right"]
                else game_result["right_team"]
            )
            schedule = (
                session.query(Schedule)
                .filter(Schedule.schedule_id == schedule_id)
                .first()
            )
            team_score_field_str = (
                "team_1_score" if schedule.team_1 == winner else "team_2_score"
            )
            session.query(Schedule).filter(Schedule.schedule_id == schedule_id).update(
                {
                    team_score_field_str: getattr(schedule, team_score_field_str) + 1,
                }
            )
            session.query(Match).filter(Match.match_id == match_id).update(
                {
                    "match_status": 3,
                    "match_real_end_time": int(time.time() * 1000),
                    "winner": winner,
                }
            )
            # 判断大场是否已结束
            team_1_score, team_2_score, schedule_type = (
                session.query(
                    Schedule.team_1_score, Schedule.team_2_score, Schedule.schedule_type
                )
                .filter(Schedule.schedule_id == schedule_id)
                .first()
            )
            schedule_over = (
                True
                if (
                    (team_1_score == 2 or team_2_score == 2) and schedule_type == 2
                )  # bo3
                or (
                    (team_1_score == 1 or team_2_score == 1) and schedule_type == 1
                )  # bo1
                or (
                    (team_1_score == 3 or team_2_score == 3) and schedule_type == 3
                )  # bo5
                else False
            )
            if schedule_over:
                session.query(Schedule).filter(
                    Schedule.schedule_id == schedule_id
                ).update(
                    {
                        "schedule_status": 3,
                        "schedule_real_end_time": int(time.time() * 1000),
                    }
                )
            result_written = True
    except Exception as e:
        logging.error(f"更新schedule,match结束状态时发生错误: {e}", exc_info=True)
        session.rollback()
        session.close()
        return
    # 存库
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logging.error(f"保存信息到数据库时发生错误: {e}", exc_info=True)
    finally:
        session.close()


timeout_url = ""
timeout_flag = True


def check_timeout() -> None:
    global timeout_flag
    phase = global_data.data["phase_countdowns"]["phase"]
    if phase in ("timeout_ct", "timeout_t") and timeout_flag:
        print("--------------------Timout--------------------")
        # requests.post(timeout_url)
        timeout_flag = False
    elif phase not in ("timeout_ct", "timeout_t") and not timeout_flag:
        timeout_flag = True


def store_round_data():
    gsi = global_data.data
    Session = sessionmaker(bind=ENGINELocal, autocommit=False)
    session = Session()
    round = gsi["map"]["round"]
    win_result = list(gsi["map"]["round_wins"].values())[-1]
    win_team = (
        gsi["map"]["team_ct"]["name"]
        if win_result[0] == "c"
        else gsi["map"]["team_t"]["name"]
    )
    match_id = player_info["match_id"]
    count = (
        session.query(DataRound)
        .filter(and_(DataRound.round == round, DataRound.match_id == match_id))
        .count()
    )

    phase = gsi["phase_countdowns"]["phase"]

    if phase == "over" and count < 10:
        try:
            player_stats = [
                {
                    "steam_id": steam_id,
                    "player_name": p["name"],
                    "round_kills": p["state"]["round_kills"],
                    "round_killhs": p["state"]["round_killhs"],
                    "round_totaldmg": p["state"]["round_totaldmg"],
                }
                for steam_id, p in list(gsi["allplayers"].items())
            ]

            for player in player_stats:
                data_round = DataRound(
                    steam_id=player["steam_id"],
                    player_name=player["player_name"],
                    round_kills=player["round_kills"],
                    round_killhs=player["round_killhs"],
                    round_totaldmg=player["round_totaldmg"],
                    round=round,
                    match_id=match_id,
                )
                session.add(data_round)
            # 保存round赛果
            data_round_team = DataRoundTeam(
                match_id=match_id, round=round, win_team=win_team, win_result=win_result
            )
            session.add(data_round_team)
        except Exception as e:
            logging.error(f"保存round data到数据库时发生错误: {e}", exc_info=True)
            session.rollback()
            session.close()
        finally:
            logging.info(f"round{round}数据保存成功！")
            session.commit()
            session.close()


@app.route("/overallBoard")
def overall_board():
    board = get_overall_board()
    if board:
        return jsonify({"message": "success", "data": board, "code": 200})
    return jsonify({"message": "error"})


@app.route("/slideBar")
def slide_bar():
    bar = get_slide_bar()
    if bar:
        return jsonify({"message": "success", "data": bar, "code": 200})
    return jsonify({"message": "error"})


def compare_map_pool(team_1, team_2):
    try:
        Session = sessionmaker(bind=ENGINELocal, autocommit=False)
        session = Session()
        # 查询所有team1参加过的赛程
        schedule_ids_team1_query = (
            session.query(Schedule.schedule_id)
            .filter(
                and_(or_(Schedule.team_1 == team_1, Schedule.team_2 == team_1)),
                Schedule.stage_id.notin_(["0", "5"]),
            )
            .all()
        )
        schedule_ids_team1 = [item[0] for item in schedule_ids_team1_query]
        # 查询所有team2参加过的赛程
        schedule_ids_team2_query = (
            session.query(Schedule.schedule_id)
            .filter(
                and_(or_(Schedule.team_1 == team_2, Schedule.team_2 == team_2)),
                Schedule.stage_id.notin_(["0", "5"]),
            )
            .all()
        )
        schedule_ids_team2 = [item[0] for item in schedule_ids_team2_query]
        matches_with_team1 = (
            session.query(Match).filter(Match.schedule_id.in_(schedule_ids_team1)).all()
        )
        matches_with_team2 = (
            session.query(Match).filter(Match.schedule_id.in_(schedule_ids_team2)).all()
        )
        team1_map = {}
        team2_map = {}
        for match in matches_with_team1:
            map = match.map
            win_team = match.winner
            if map not in team1_map:
                team1_map.update({map: {"win": 0, "lose": 0}})
            if win_team == team_1:
                team1_map[map]["win"] += 1
            else:
                team1_map[map]["lose"] += 1
        for match in matches_with_team2:
            map = match.map
            win_team = match.winner
            if map not in team2_map:
                team2_map.update({map: {"win": 0, "lose": 0}})
            if win_team == team_1:
                team2_map[map]["win"] += 1
            else:
                team2_map[map]["lose"] += 1
        common_maps = list(set(team1_map.keys()) & set(team2_map.keys()))
        result = []
        for map in common_maps:
            map_info_team1 = team1_map[map]
            map_info_team2 = team2_map[map]
            result.append(
                {
                    "map": map,
                    "team1": team_1,
                    "team2": team_2,
                    "map_info_team1": map_info_team1,
                    "map_info_team2": map_info_team2,
                }
            )
        return result
    except Exception as e:
        logging.error(f"compare_map_pool错误:{e}", exc_info=True)


@app.route("/team_compare")
def get_team_compare():
    try:
        Session = sessionmaker(bind=ENGINELocal, autocommit=False)
        session = Session()
        cp = session.query(CpTeam).filter(CpTeam.select == 1).first()
        team_1 = cp.team_1
        team_2 = cp.team_2
        map_cp = compare_map_pool(team_1, team_2)
        return jsonify({"message": "success", "data": map_cp, "code": 200})
    except Exception as e:
        logging.error(f"get team compare错误:{e}", exc_info=True)
        return jsonify({"message": "error"})


if __name__ == "__main__":
    # myServer = server.GSIServer(("127.0.0.1", 3000), "vspo")
    # myServer.start_server()
    # initalizeRound()
    # initializeSide()
    # thread = threading.Thread(target=backgroundProcess)
    # thread.daemon = True
    # thread.start()
    app.run(host="0.0.0.0", port=1234, debug=False)
