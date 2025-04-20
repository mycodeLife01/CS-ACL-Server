import global_data
import logging
import json

player_info = None
with open("player_info.json", "r", encoding="utf-8") as f:
    player_info = json.load(f)


# 战队选手数据版
def get_overall_board() -> dict:
    try:
        gsi_data = global_data.data

        ct_name = gsi_data["map"]["team_ct"]["name"]
        t_name = gsi_data["map"]["team_t"]["name"]
        ct_score = gsi_data["map"]["team_ct"]["score"]
        t_score = gsi_data["map"]["team_t"]["score"]
        round = gsi_data["map"]["round"]

        if round <= 24:
            timeout_all = 3
        else:
            timeout_all = 1
        ct_timeout_used = timeout_all - gsi_data["map"]["team_ct"]["timeouts_remaining"]
        t_timeout_used = timeout_all - gsi_data["map"]["team_t"]["timeouts_remaining"]
        ct_consecutive_round_losses = gsi_data["map"]["team_ct"][
            "consecutive_round_losses"
        ]
        t_consecutive_round_losses = gsi_data["map"]["team_t"][
            "consecutive_round_losses"
        ]

        gsi_data["map"]["team_t"]["consecutive_round_losses"]

        loss_bonus_dict = {0: 1400, 1: 1900, 2: 2400, 3: 2900, 4: 3400}

        ct_loss_bonus = (
            loss_bonus_dict[ct_consecutive_round_losses]
            if ct_consecutive_round_losses <= 4
            else 3400
        )
        t_loss_bonus = (
            loss_bonus_dict[t_consecutive_round_losses]
            if t_consecutive_round_losses <= 4
            else 3400
        )

        ct_equip_value = sum(
            [
                p["state"]["equip_value"]
                for p in gsi_data["allplayers"].values()
                if p["team"] == "CT"
            ]
        )
        t_equip_value = sum(
            [
                p["state"]["equip_value"]
                for p in gsi_data["allplayers"].values()
                if p["team"] == "T"
            ]
        )

        mid_board = {
            "left_team": ct_name,
            "right_team": t_name,
            "left_score": ct_score,
            "right_score": t_score,
            "left_loss_bonus": ct_loss_bonus,
            "right_loss_bonus": t_loss_bonus,
            "left_equip_value": ct_equip_value,
            "right_equip_value": t_equip_value,
            "timeout_left": f"{ct_timeout_used}/{timeout_all}",
            "timeout_right": f"{t_timeout_used}/{timeout_all}",
        }

        ct_player_data = []
        t_player_data = []
        for steam_id, player in gsi_data["allplayers"].items():
            steam_ids_record = player_info["player"].keys()
            if steam_id not in steam_ids_record:
                continue
            name = player["name"]
            money = player["state"]["money"]
            weapons = {}
            # 遍历武器并分类
            for weapon in player["weapons"].values():
                if weapon.get("type", "") in [
                    "Knife",
                    "Pistol",
                    "Rifle",
                    "SniperRifle",
                    "Submachine Gun",
                    "Machine Gun",
                    "Shotgun",
                ]:
                    weapons[weapon["type"]] = weapon["name"]
                elif weapon.get("type", "") == "Grenade":
                    grenade_list = weapons.get("Grenade", [])
                    grenade_list.append(weapon["name"])
                    weapons["Grenade"] = grenade_list

            # 根据武器类型优先级选择 weapon_show
            weapon_show = None
            for weapon_type in [
                "Rifle",
                "SniperRifle",
                "Submachine Gun",
                "Machine Gun",
                "Shotgun",
                "Pistol",
                "Knife",
            ]:
                if weapon_type in weapons:
                    weapon_show = weapons[weapon_type]
                    break

            if player["state"].get("defusekit"):
                defuse_kit = 1
            else:
                defuse_kit = 0

            bomb_info = gsi_data["bomb"]
            if bomb_info["state"] == "carried" and bomb_info["player"] == steam_id:
                bomb = 1
            else:
                bomb = 0

            if not (player["state"]["armor"] > 0 or player["state"]["helmet"]):
                armor = 0
                helmet = 0
            elif player["state"]["armor"] > 0 and not player["state"]["helmet"]:
                armor = 1
                helmet = 0
            else:
                armor = 1
                helmet = 1
            grenade = weapons.get("Grenade")
            if not grenade:
                grenade = ["-", "-", "-", "-"]
            elif len(grenade) == 1:
                grenade.extend(["-", "-", "-"])
            elif len(grenade) == 2:
                grenade.extend(["-", "-"])
            elif len(grenade) == 3:
                grenade.extend(["-"])
            p_data = {
                "name": name,
                "money": money,
                "weapon_show": weapon_show,
                "grenade": grenade,
                "armor": armor,
                "helmet": helmet,
            }
            if player["team"] == "CT":
                p_data.update({"defusekit": defuse_kit})
                ct_player_data.append(p_data)
            else:
                p_data.update({"bomb": bomb})
                t_player_data.append(p_data)
        tag = (
            "Timeouts"
            if gsi_data["phase_countdowns"]["phase"] in ("timeout_ct", "timeout_t")
            else ""
        )
        return {
            "mid_board": mid_board,
            "team_info": {"left_team": ct_player_data, "right_team": t_player_data},
            "tag": tag,
        }
    except Exception as e:
        logging.error(f"处理overallBorad时发生错误:{e}", exc_info=True)
        return {}


# 每回合胜利方式侧边栏
def get_slide_bar():
    try:
        gsi_data = global_data.data
        round_wins = gsi_data["map"].get("round_wins", None)
        res_regulation = {"phase": "", "left": [0] * 12, "right": [0] * 12}
        res_overtime = {"phase": "", "left": [0] * 6, "right": [0] * 6}
        current_round = gsi_data["map"]["round"]

        if not round_wins and current_round >= 24:
            res_overtime["phase"] = "OVERTIME"
            return res_overtime
        if not round_wins and current_round == 0:
            res_regulation["phase"] = "1ST HALF"
            return res_regulation

        part_round_wins = []
        overtime = False
        sec_half = False
        if current_round >= 12 and current_round < 24:
            sec_half = True
            part_round_wins = list(round_wins.items())[12:]
            res_regulation["phase"] = "2ND HALF"
        elif current_round < 12:
            part_round_wins = list(round_wins.items())[0:]
            res_regulation["phase"] = "1ST HALF"
        else:
            overtime = True
            part_round_wins = list(round_wins.items())[0:]
            res_overtime["phase"] = "OVERTIME"
        # print(part_round_wins)
        for round, result in part_round_wins:

            round_num = int(round)

            if not overtime and not sec_half:
                if result == "t_win_bomb":
                    res_regulation["right"][round_num - 1] = 1

                elif result == "t_win_elimination":
                    res_regulation["right"][round_num - 1] = 2

                elif result == "ct_win_defuse":
                    res_regulation["left"][round_num - 1] = 1

                elif result == "ct_win_elimination":
                    res_regulation["left"][round_num - 1] = 2
                elif result == "ct_win_time":
                    res_regulation["left"][round_num - 1] = 3

            elif not overtime and sec_half:
                if result == "t_win_bomb":
                    res_regulation["right"][round_num - 13] = 1

                elif result == "t_win_elimination":
                    res_regulation["right"][round_num - 13] = 2

                elif result == "ct_win_defuse":
                    res_regulation["left"][round_num - 13] = 1

                elif result == "ct_win_elimination":
                    res_regulation["left"][round_num - 13] = 2
                elif result == "ct_win_time":
                    res_regulation["left"][round_num - 13] = 3

            else:
                if result == "t_win_bomb":
                    res_overtime["right"][round_num - 1] = 1

                elif result == "t_win_elimination":
                    res_overtime["right"][round_num - 1] = 2

                elif result == "ct_win_defuse":
                    res_overtime["left"][round_num - 1] = 1

                elif result == "ct_win_elimination":
                    res_overtime["left"][round_num - 1] = 2
                elif result == "ct_win_time":
                    res_overtime["left"][round_num - 1] = 3

        if not overtime:
            return res_regulation
        return res_overtime

    except Exception as e:
        logging.error(f"处理slideBar时发生错误:{e}", exc_info=True)
        return {}
