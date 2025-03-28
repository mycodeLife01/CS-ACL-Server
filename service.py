import global_data


def overall_bar() -> dict:
    gsi_data = global_data.data

    ct_name = gsi_data["map"]["team_ct"]["name"]
    t_name = gsi_data["map"]["team_t"]["name"]
    ct_score = gsi_data["map"]["team_ct"]["score"]
    t_score = gsi_data["map"]["team_tt"]["score"]
    round = gsi_data["map"]["round"]

    if round <= 24:
        timeout_all = 3
    else:
        timeout_all = 1
    ct_timeout_used = timeout_all - gsi_data["map"]["team_ct"]["timeout_remaining"]
    t_timeout_used = timeout_all - gsi_data["map"]["team_t"]["timeout_remaining"]

    loss_bonus_dict = {0: 1400, 1: 1900, 2: 2400, 3: 2900, 4: 3400}
    ct_loss_bonus = loss_bonus_dict[
        gsi_data["map"]["team_ct"]["consecutive_round_losses"]
    ]
    t_loss_bonus = loss_bonus_dict[
        gsi_data["map"]["team_t"]["consecutive_round_losses"]
    ]

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
        "timeout": (
            f"{ct_timeout_used}/{timeout_all}"
            if gsi_data["phase_countdowns"]["phase"] == "timeout_ct"
            else f"{t_timeout_used}/{timeout_all}"
        ),
    }

    ct_player_data = []
    t_player_data = []
    for steam_id, player in gsi_data["allplayers"].values():
        name = player["name"]
        money = player["state"]["money"]
        weapons = {}
        for weapon in player["weapons"].values():
            if weapon["type"] == "Knife":
                weapons.update({"Knife": weapon["name"]})
            elif weapon["type"] == "Pistol":
                weapons.update({"Pistol": weapon["name"]})
            elif weapon["type"] == "Rifle":
                weapons.update({"Rifle": weapon["name"]})
            elif weapon["type"] == "SniperRifle":
                weapons.update({"SniperRifle": weapon["name"]})
            elif weapon["type"] == "Grenade":
                grenade_list = weapons.get("Grenade")
                if grenade_list:
                    grenade_list.append(weapon["name"])
                    weapons.update({"Grenade": grenade_list})
                else:
                    weapons.update(
                        {
                            "Grenade": [
                                weapon["name"],
                            ]
                        }
                    )
        for weapon_type, weapon_name in weapons.items():
            if weapon_type == "Rifle":
                weapon_show = weapon_name
                break
            elif weapon_type == "SniperRifle":
                weapon_show = weapon_name
                break
            elif weapon_type == "Pistol":
                weapon_show = weapon_name
                break
            elif weapon_type == "Knife":
                weapon_show = weapon_name

        defuse_kit = 1 if player["state"]["defusekit"] else 0
        bomb_info = gsi_data["bomb"]
        if bomb_info["state"] == "carried" and bomb_info["player"] == steam_id:
            bomb = 1

        if not (player["state"]["armor"] > 0  or player["state"]["helmet"]):
            defensekit = 0
        elif player["state"]["armor"] and not player["state"]["helmet"]:
            defensekit = 1
        else:
            defensekit = 2
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
            "defensekit": defensekit,
        }
        if player["team"] == "CT":
            p_data.update({"defusekit": defuse_kit})
            ct_player_data.append(p_data)
        else:
            p_data.update({"bomb": bomb})
            t_player_data.append(p_data)

    return {"mid_board": mid_board, "team_info": [ct_player_data, t_player_data]}
