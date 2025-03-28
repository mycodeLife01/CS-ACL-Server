data = None
bomb_state = -1
bomb_state_msg = {
    0:'bomb is planting',
    1:'bomb is planted',
    2:'bomb is exploded',
    3:'bomb is defusing',
    4:'bomb is defused',
    5:'bomb is carried',
    6:'bomb is dropped'
}
bomb_state_map = {
    'planting': 0,
    'planted': 1,
    'exploded': 2,
    'defusing': 3,
    'defused': 4,
    'carried': 5,
    'dropped': 6                                                                                        
    }
round = 0