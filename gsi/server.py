from http.server import BaseHTTPRequestHandler, HTTPServer
from operator import attrgetter
from threading import Thread
import json
import time
from . import gamestate
from . import payloadparser
import global_data

gameover_flag = 0


class GSIServer(HTTPServer):
    def __init__(self, server_address, auth_token):
        super(GSIServer, self).__init__(server_address, RequestHandler)

        self.auth_token = auth_token
        self.gamestate = gamestate.GameState()
        self.parser = payloadparser.PayloadParser()

        self.running = False

    def start_server(self):
        try:
            thread = Thread(target=self.serve_forever)
            thread.start()
            first_time = True
            while self.running == False:
                if first_time == True:
                    print("CS:GO GSI Server starting..")
                first_time = False
        except:
            print("Could not start server.")

    def get_info(self, target, *argv):
        try:
            if len(argv) == 0:
                state = attrgetter(f"{target}")(self.gamestate)
            elif len(argv) == 1:
                state = attrgetter(f"{target}.{argv[0]}")(self.gamestate)
            elif len(argv) == 2:
                state = attrgetter(f"{target}.{argv[0]}")(self.gamestate)[f"{argv[1]}"]
            else:
                print("Too many arguments.")
                return False
            if "object" in str(state):
                return vars(state)
            else:
                return state
        except Exception as E:
            print(E)
            return False


class RequestHandler(BaseHTTPRequestHandler):
    # last_request_time = time.time()
    def do_POST(self):
        global gameover_flag
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body)
        # 设置全局变量
        global_data.data = payload
        # print(global_data.data)
        # time.sleep(2)
        # print(f'--------------ct是:{global_data.data["map"]["team_ct"]}, t是:{global_data.data["map"]["team_t"]}------------------')
        # with open("gsi_data.json", "w", encoding="utf-8") as f:
        #     json.dump(payload, f, ensure_ascii=False, indent=4)
        if payload["map"]["phase"] == "gameover" and gameover_flag == 0:
            with open("player_info.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            data["is_over"] = "1"

            with open("player_info.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            with open("gsi_data.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=4)
            gameover_flag += 1
            # print(global_data.data)
            # print(global_data.bomb_state)
        if not self.authenticate_payload(payload):
            print("auth_token does not match.")
            return False
        else:
            self.server.running = True
        self.server.parser.parse_payload(payload, self.server.gamestate)

    def authenticate_payload(self, payload):
        if "auth" in payload and "token" in payload["auth"]:
            return payload["auth"]["token"] == self.server.auth_token
        else:
            return False
