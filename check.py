import json
import logging
from sqlalchemy.orm import sessionmaker
from models import *
from sqlalchemy import and_, or_

SessionLocal = sessionmaker(bind=ENGINELocal, autocommit=False)


def check_steam_id(team_ids: list) -> bool:
    try:
        db = SessionLocal()
        steam_ids_cfg = set()
        with open("player_info/HF_GL.json", "r", encoding="utf-8") as f:
            steam_ids_cfg = set(list(json.load(f)["player"].keys()))
        steam_ids_db = set(
            [
                item[0]
                for item in db.query(PlayerList.steam_id)
                .filter(
                    and_(PlayerList.team.in_(team_ids), PlayerList.offline == 1)
                )
                .all()
            ]
        )
        return steam_ids_cfg <= steam_ids_db
    except Exception as e:
        logging.error(
            f"Error checking steam id config, query teams ({team_ids}): {e}",
            exc_info=True,
        )
        raise
    finally:
        db.close()

if check_steam_id(['HF', 'GL']):
    print('match')
else:
    print('mismatch')
