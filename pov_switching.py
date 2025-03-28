from flask import Flask,jsonify
from gsi import server
import global_data
import time
import threading
import  json
import requests

myServer = server.GSIServer(('127.0.0.1',3000),'vspo')
myServer.start_server()

#读取赛前预录选手信息，包括选手名，战队名和舞台位置
player_info_json = "player_info.json"
with open(player_info_json, "r", encoding="utf-8") as f:
    player_info = json.load(f)

pov_on_url = 'http://192.168.15.19:8088/api/?Function=OverlayInput1In&Input='
pov_off_url = 'http://192.168.15.19:8088/API/?Function=OverlayInput1Off'

def pov_switching():
    if 'player' in global_data.data and "steamid" in global_data.data['player']:
        ob_player_info = player_info[global_data.data['player']['steamid']]
        player_seat = str(ob_player_info['player_seat'])
        send_url = pov_on_url+player_seat
        requests.get(send_url)
        #发送vMix请求
        #http://192.168.15.19:8088/api/?Function=OverlayInput1In&Input=
        print(ob_player_info, send_url)
    else:
        #下POV，camera off
        requests.get(pov_off_url)
        print("POV OFF!")
    

while True:
    pov_switching()
    time.sleep(0.2)