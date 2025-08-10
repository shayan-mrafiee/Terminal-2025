import gamelib
import random
import math
import warnings
from sys import maxsize
import json


"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP, send_scouts
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0

        # This is a good place to do initial setup
        self.scored_on_locations = []
        self.send_scouts = False
        self.scout_spawn_location = []
        self.clear_locations = []

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        #game_state.suppress_warnings(True)  #Comment or remove this locations to enable warnings.

        self.strategy(game_state)

        game_state.submit_turn() # Do not delete 


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def strategy(self, game_state):
        self.build_defense(game_state, self.clear_locations)
        if self.send_scouts:
            self.build_supports(game_state)
            self.spam_scouts(game_state, self.scout_spawn_location)
            self.send_scouts = False
            self.clear_locations = []
        elif game_state.get_resources()[MP] > 13:
            self.send_scouts = True
            self.scout_spawn_location = [1, 13]
            self.clear_path(game_state)
            
            
    def clear_path(self, game_state):
        self.clear_locations = []
        if self.scout_spawn_location == [1, 13]:
            for y in range(14):
                if [13 - y, y] != [0, 13]:
                    self.clear_locations.append([13 - y, y])
                self.clear_locations.append([14 - y, y])
        else:
            for y in range(14):
                self.clear_locations.append([y + 14, y])
                self.clear_locations.append([y + 13, y])

        game_state.attempt_remove(self.clear_locations)


    def build_defense(self, game_state, exclude = []):
        """
        Make sure our turrets and walls still holds
        """
        wall_locations = [[0, 13], [27, 13]]

        for location in wall_locations:
            if location not in exclude:
                game_state.attempt_spawn(WALL, location)
                game_state.attempt_upgrade(location)
            if game_state.game_map[location] and game_state.game_map[location][0].health <= 60:
                game_state.attempt_spawn(WALL, location)
                game_state.attempt_upgrade(location)

        groups = [[[int(i), 13] for i in range(1, 27)], 
                     [[int(i), 12] for i in range(1, 3)],
                     [[int(i), 12] for i in range(25, 27)]]
        
        for locations in groups:
            for location in locations:
                if location not in exclude:
                    game_state.attempt_spawn(TURRET, location)
                if game_state.game_map[location] and game_state.game_map[location][0].health <= 37.5:
                    game_state.attempt_remove(location)
    
    def build_supports(self, game_state):
        """
        Keep making supports and upgrading them
        """
        for i in range(13, 4, -1):
            if game_state.get_resources()[SP] < 4:
                break
            game_state.attempt_spawn(SUPPORT, [i, 12])
            game_state.attempt_upgrade([i, 12])
        

    def build_reactive_defense(self, game_state):
        """
        This function builds reactive defenses based on where the enemy scored on us from.
        We can track where the opponent scored by looking at events in action frames 
        as shown in the on_action_frame function
        """
        
        for location in self.scored_on_locations:
            # Build turret one space above so that it doesn't block our own edge spawn locations
            build_location = [location[0], location[1]+1]
            game_state.attempt_spawn(TURRET, build_location)

    def spam_scouts(self, game_state, spawn_location):
        for i in range(5):
            game_state.attempt_spawn(SCOUT, [12, 1])
        while(game_state.get_resources()[MP] >= 1):
            game_state.attempt_spawn(SCOUT, [14, 0])

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
            damages.append(damage)
        
        # Now just return the location that takes the least damage
        return location_options[damages.index(min(damages))]

    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units
        
    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        """# Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))"""


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
