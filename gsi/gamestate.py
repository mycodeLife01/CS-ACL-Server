from . import information
# from . import config
class GameState:
    def __init__(self):
        self.player = information.Player()
        self.map = information.Map()
        self.provider = information.Provider()
        self.phase_countdowns = information.PhaseCountdowns()
        self.bomb = information.Bomb()
        self.round = information.Round()
        self.allplayers = information.Allplayers()
        self.team = information.Team()
