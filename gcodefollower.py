#!/usr/bin/env python3

import sys
import os
import copy
import shutil
import json
import decimal
from decimal import Decimal

def get_cmd_meta(cmd):
    comment_i = cmd.find(";")
    if comment_i >= 0:
        cmd = cmd[0:comment_i]
    cmd = cmd.strip()
    if len(cmd) < 1:
        return None
    if cmd[0] == ";":
        # comment
        return None
    while "\t" in cmd:
        cmd = cmd.replace("\t", " ")
    while "  " in cmd:
        cmd = cmd.replace("  ", " ")
    parts = cmd.split(" ")
    cmd_meta = []
    for i in range(len(parts)):
        parts[i] = parts[i].strip()
        if len(parts[i]) > 1:
            cmd_meta.append([parts[i][0], parts[i][1:]])
        else:
            # no value (such as: To home X, nothing is after 'G1 X'):
            cmd_meta.append([parts[i][0]])
    return cmd_meta

def cast_by_type_string(value, type_str):
    if value is None:
        return None
    elif value == "":
        return None
    # NOTE: to reverse this, you'd have to use type(var).__name__
    if type_str == "int":
        return int(value)
    elif type_str == "Decimal":
        return Decimal(value)
    elif type_str == "float":
        return float(value)
    elif type_str == "bool":
        return bool(value)
    else:
        return value

class GCodeFollower:
    _towerName = ("the mesh (such as STL) from Python GUI for"
                  " Configurable Temperature Tower")
    _downloadPageURLs = ["https://www.thingiverse.com/thing:4068975",
                         "https://github.com/poikilos/TemperatureTowerProcessor"]
    # The old one is thing:2092820 but that is not very tall, and has some mesh issues.

    _end_retraction_flag = "filament slightly"
    _rangeNames = ["min", "max"]
    _settingsDescriptionsPath = "settings descriptions.txt"

    def saveDocumentationOnce(self):
        if not os.path.isfile(GCodeFollower._settingsDescriptionsPath):
            self.saveDocumentation()
            print(
                "* an explanation of settings has been written to"
                " '{}'.".format(GCodeFollower._settingsDescriptionsPath)
            )
        else:
            print(
                "* an explanation of settings was previously saved to"
                " '{}'.".format(GCodeFollower._settingsDescriptionsPath)
            )

    def saveDocumentation(self):

        try:
            with open(GCodeFollower._settingsDescriptionsPath, 'w') as outs:
                self.saveDocumentationTo(outs)
        except e:
            os.remove(GCodeFollower._settingsDescriptionsPath)
            raise e

    def saveDocumentationTo(self, stream):
        stream.write(self.getDocumentation() + "\n")
        def _saveLine(line):
            stream.write(line + "\n")
        # _saveLine("Writing settings:")
        self.printSettingsDocumentation(print_callback=_saveLine)

    def printSettingsDocumentation(self, print_callback=print):
        print_callback(
            "You can edit \"{}\" to change settings".format(
                self._settingsPath
            )
        )
        # being careful to maintain the JSON format properly (try
        # pasting your settings into https://jsonlint.com/ if you're
        # not sure, then copy from there).".format(self._settingsPath)
        # print("If you write a Python program that imports"
              # " GCodeFollower, you can set an individual setting by"
              # " calling the setVar method on a GCodeFollower object"
              # " before calling calling its generateTowerThread method.")
        print_callback("")
        print_callback("Settings:")
        names = self.getSettingsNames()
        for name in names:
            print_callback("- " + name + ": "
                           + self.help(name))

    def setVar(self, name, value):
        """
        Automatically set the variable to the proper type, or raise
        ValueError if that is not possible.
        """
        if name not in self._settings:
            raise KeyError("{} is not a valid setting.".format(name))
        if value is not None:
            python_type = self._settings_types[name]
            if type(value).__name__ != "str":
                if python_type == "int":
                    value = int(value)
                elif python_type == "float":
                    value = float(value)
                elif python_type == "Decimal":
                    value = Decimal(value)
                if type(value).__name__ != python_type:
                    raise ValueError("'{}' should be a(n)"
                                     " {}.".format(name, python_type))
        # else: allow setting it to None.
        self._settings[name] = value

    def getRangeVarName(self, name, i):
        return GCodeFollower._rangeNames[i] + "_" + name

    def setRangeVar(self, name, i, value):
        self.setVar(self.getRangeVarName(name, i), value)

    def setRangeVars(self, name, min_value, max_value):
        self.setVar(self.getRangeVarName(name, 0), min_value)
        self.setVar(self.getRangeVarName(name, 1), max_value)

    def castVar(self, name, value):
        if value is None:
            return None
        return cast_by_type_string(self._settings_types[name], value)

    def getVar(self, name, prevent_exceptions=False):
        # if prevent_exceptions:
            # result = self._settings.get(name)
            # if result is not None:
                # return self.castVar(name, result)
            # else:
                # return None
        # return castVar(name, self._settings[name])
        if prevent_exceptions:
            result = self._settings.get(name)
            if result is None:
                return None
            return cast_by_type_string(result, self._settings_types[name])
        return cast_by_type_string(self._settings[name], self._settings_types[name])

    def getRangeVar(self, name, i):
        return self.getVar(self.getRangeVarName(name, i))

    def _createVar(self, name, value, python_type, description):
        self._settings[name] = cast_by_type_string(value, python_type)
        self._settings_types[name] = python_type
        self._settings_descriptions[name] = description

    def getListVar(self, name, i, prevent_exceptions=True):
        return self.getVar(name + "[" + str(i) + "]", prevent_exceptions=prevent_exceptions)

    def setListVar(self, name, i, value):
        self.setVar(name + "[" + str(i) + "]", value)

    def help(self, name):
        """
        Get the documentation for a setting, preceded by the type in
        parenthesis.
        """
        return "(" + self._settings_types[name] + ") " + self._settings_descriptions[name]

    def getSettingsNames(self):
        return self._settings.keys()

    def __init__(self, echo_callback=None, enable_ui_callback=None):
        """
        Change settings via setVar and self.getVar. Call "getSettingsNames" to
        get a list of all settings. Call "help" to see the documentation
        for each setting, preceded by the type in parenthesis.

        Keyword arguments:
        echo_callback -- Whatever function you provide must accept a
            string. It will be called whenever status should be shown.
        enable_ui_callback -- Whatever function you provide must accept a
            boolean. It will be called with false whenever a process starts
            and true whenevere a process ends.
        """
        self._verbose = False
        self._settings = {}
        self._settings_types = {}
        self._settings_descriptions = {}
        self.stats = {}
        self._createVar("template_gcode_path", None, "str", "Look here for the source gcode of the temperature tower.")
        self._createVar("default_path", "tower.gcode", "str", "Look here if template_gcode_path is not specified.")
        self._createVar("level_count", 10, "int", "This is how many levels are in the source gcode file.")
        self._createVar("level_height", "13.500", "Decimal", "The height of each level excluding levels (special_heights can override this for individual levels of the tower).")
        self._createVar("special_heights[0]", "16.201", "Decimal", "This is the level of the first floor and any other floors that don't match level_height (must be consecutive).")
        self._createVar("temperature_step", "5", "int", "Change this many degrees at each level.")
        self._createVar("max_z_build_movement", "1.20", "Decimal", "This Z distance or less is counted as a build movement, and is eliminated after the tower is truncated (after there are no more temperature steps in the range and the next level would start).")
        self._createVar(self.getRangeVarName("temperature", 0), None,
                        "int", "The first level of the temperature tower should be printed at this temperature (C).")
        self._createVar(self.getRangeVarName("temperature", 1), None,
                        "int", "After incrementing each level of the tower by temperature_step, finish the level that is this temperature then stop printing.")
        self._settingsPath = "settings.json"
        self._stop_building_msg = "; GCodeFollower says: stop_building (additional build-related codes that were below will be excluded)"
        # self._insert_msg = "; GCodeFollower."

        self.max_temperature = None  # checkSettings sets this.
        self.heights = None  # checkSettings sets this.
        self.temperatures = None  # checkSettings sets this.
        self.desired_temperatures = None  # checkSettings sets this.
                                          # The user wants this list
                                          # temperatures. It usually
                                          # differs from the number of
                                          # levels in the tower.

        if echo_callback is not None:
            self.echo = echo_callback

        if enable_ui_callback is not None:
            self.enableUI = enable_ui_callback

        # The first (minimum) value is at Z0:
        # self.setRangeVars("temperature", name, 240, 255)
        # self.setRangeVars("temperature", name, 190, 210)
        # NOTE: [Hatchbox PLA](https://www.amazon.com/gp/product/B00J0GMMP6)
        # has the temperature 180-210, but 180 underextrudes unusably
        # (and doesn't adhere to the bed well [even 60C black diamond]).

        # G-Code reference:
        # - Marlin (or Sprinter): http://marlinfw.org/docs/gcode/G000-G001.html
        self.commands = {}
        self.params = {}

        # commands with known params:
        self.commands['move'] = 'G1'  # can also extrude
        self.commands['set temperature and wait'] = 'M109'
        self.commands['set fan speed'] = 'M106'
        self.commands['set position'] = 'G92'
        self.commands['fan off'] = 'M107'
        # commands with no known params:
        self.commands['Reset selected workspace to 0, 0, 0'] = 'G92.1'  # http://marlinfw.org/docs/gcode/G092.html

        # params:
        self.params['move'] = ['X', 'Y', 'Z', 'F', 'E']  # can also extrude
        self.params['set temperature and wait'] = ['S']
        self.params['set fan speed'] = ['S']
        self.params['set position'] = ['E', 'X', 'Y', 'Z']
        self.params['fan off'] = ['P']
        self.param_names = {}
        self.param_names["E"] = "extrude (mm)"
        # E extrudes that many mm of filament (relative of course)
        self.param_names["F"] = "speed (mm/minute)"
        self.param_names["P"] = "index"  # such as fan number (default is 0)

        self.code_numbers = {}
        for k, v in self.commands.items():
            self.code_numbers[k] = Decimal(v[1:])


    def saveSettings(self):
        serializable_settings = {}
        for k, v in self._settings.items():
            if type(v).__name__ == "Decimal":
                serializable_settings[k] = str(v)
            else:
                serializable_settings[k] = v
        with open(self._settingsPath, 'w') as outs:
            json.dump(serializable_settings, outs, indent=4)
            # sort_keys=True)

    def loadSettings(self):
        self.error = None
        with open(self._settingsPath) as ins:
            tmp_settings = json.load(ins)
            # Use a temp file in case the file is missing any settings.
            for k, v in tmp_settings.items():
                if k in self._settings:
                    self._settings[k] = castVar(k, v)
                else:
                    if self.error is None:
                        self.error = ""
                    else:
                        self.error += "; "
                    self.error += k + " is not a valid setting name."
        return self.error is None

    def echo(self, msg):
        print(msg)

    def _echo_progress(self, msg):
        progress = self.getStat("progress")
        if progress is not None:
            self.echo(progress + "  " + msg)
        else:
            self.echo(msg)

    @staticmethod
    def getDocumentation():
        msg = "  Slicer Compatibility:"
        msg += ("\n  - You must put \""
                + GCodeFollower._end_retraction_flag + "\" in"
                " the comment on the same line as any retractions in"
                " your end gcode that you don't want stripped off when"
                " the top of the tower is truncated (to match"
                " GCodeFollower._end_retraction_flag).")
        return msg

    def enableUI(self, enable):
        if enable:
            print("")
            print("The process completed.")
            print("")
        else:
            print("")
            print("Please wait...")

    def checkSettings(self, allow_previous_settings=True, verbose=False):
        """
        This ensures that everything in the settings dictionary is
        correct, and will do the following if not:
        - raise ValueError if max_temperature or min_temperature are not
          present or not set properly.
        - raise FileNotFoundError if src_path is missing.
        """
        self.error = None

        if (len(sys.argv) == 2) or (len(sys.argv) == 4):
            self.setVar("template_gcode_path", sys.argv[1])
            if verbose:
                print("* You set the tower path to '{}'...".format(self.getVar("template_gcode_path")))
        else:
            if verbose:
                print("")
            self.setVar("template_gcode_path", self.getVar("default_path"))
            if verbose:
                print("* checking for '{}'...".format(self.getVar("template_gcode_path")))
                print("")

        notePath = self.getVar("template_gcode_path") + " is missing.txt"
        if not os.path.isfile(self.getVar("template_gcode_path")):
            if verbose:
                print("")
                print("'{}' does not exist.".format(self.getVar("template_gcode_path")))
            msg = "You must slice the Configurable Temperature tower from:"
            for thisURL in GCodeFollower._downloadPageURLs:
                msg += "\n- " + thisURL
            msg += "\nas {}".format(self.getVar("template_gcode_path"))
            if self.getVar("template_gcode_path") == self.getVar("default_path"):
                notePathMsg = ""
                exMessage = ""
                try:
                    with open(notePath, 'w') as outs:
                        outs.write(msg)
                    notePathMsg = ". See 'README.md'."
                    # See '" + os.path.abspath(notePath) + "'
                except:
                    exType, exMessage, exTraceback = sys.exc_info()
                    if verbose:
                        print(exMessage)
                    notePathMsg = (" Writing '" +
                                   os.path.abspath(notePath)
                                   + "' failed: " + exMessage)
            if verbose:
                self.echo(msg + notePathMsg)
            if verbose:
                print("")
            self.enableUI(True)
            raise FileNotFoundError(msg + notePathMsg)
            return False
        else:
            if os.path.isfile(notePath):
                os.remove(notePath)

        if len(sys.argv) == 4:
            self.setRangeVar("temperature", 0, sys.argv[2])
            self.setRangeVar("temperature", 1, sys.argv[3])
        elif len(sys.argv) == 3:
            self.setRangeVar("temperature", 0, sys.argv[1])
            self.setRangeVar("temperature", 1, sys.argv[2])
        else:
            if allow_previous_settings:
                for i in range(2):
                    if self.getRangeVar("temperature", i) is None:
                        self.enableUI(True)
                        raise ValueError(self.getRangeVarName("temperature", i) + " is missing.")
            else:
                self.enableUI(True)
                raise ValueError("You did not set the program parameters as script arguments.")

        # Find these OR the next highest (will differ based on layer
        # height and Slic3r Z offset setting; which may also be
        # negative, but next highest is close enough)
        special_heights = []
        i = 0
        v = self.getListVar("special_heights", i)
        while v is not None:
            special_heights.append(v)
            i += 1
            v = self.getListVar("special_heights", i)

        i = None
        # self.heights = [0, 16.4, 30.16, 43.6, 57.04]
        self.heights = []  # ALWAYS must start with level 0 at 0.00
        total_height = Decimal("0.000")
        for i in range(self.getVar("level_count")):
            this_level_height = self.getVar("level_height")
            if (special_heights is not None) and (i < len(special_heights)):
                if special_heights[i] is not None:
                    # if verbose:
                        # print("special_heights[" + str(i) + "]: " + type(special_heights[i]).__name__)
                    this_level_height = special_heights[i]
            self.heights.append(total_height)
            total_height += this_level_height
        total_height = None

        for i in range(2):
            if verbose:
                print(
                    "You set the {} temperature to {}.".format(
                        GCodeFollower._rangeNames[i],
                        self.getRangeVar("temperature", i)
                    )
                )

        self.max_temperature = None  # This is set automatically
                                     # according to height below.
        this_temperature = self.getRangeVar("temperature", 0)
        # if verbose:
            # print("this_temperature: " + type(this_temperature).__name__)
        # if this_temperature is None:
            # self.enableUI(True)
            # raise ValueError("The settings value '"
                             # + self.getRangeVarName("temperature", 0)
                             # + "' is missing (you must set this).")
        # if self.getRangeVar("temperature", 1) is None:
            # self.enableUI(True)
            # raise ValueError("The settings value '"
                             # + self.getRangeVarName("temperature", 1)
                             # + "' is missing (you must set this).")
        l = 0
        # height = Decimal("0.00")
        self.temperatures = []
        self.desired_temperatures = []
        while True:
            if l < len(self.heights):
                # height = self.heights[l]
               # if verbose:
                   # print("* adding level {} ({} C) at"
                          # " {}mm".format(l, this_temperature, height))
                self.temperatures.append(this_temperature)
                self.max_temperature = this_temperature
            self.desired_temperatures.append(this_temperature)
            # if verbose:
                # print("temperature_step: "
                      # + type(self.getVar("temperature_step")).__name__)
            this_temperature += self.getVar("temperature_step")
            if this_temperature > self.getRangeVar("temperature", 1):
                this_temperature -= self.getVar("temperature_step")
                break
            l += 1
        this_temperature = None
        self.echo("")
        self.echo("level:       " + "".join(["{:<9}".format(i) for i in range(len(self.temperatures))]))
        self.echo("temperature: " + "".join(["{:<9}".format(t) for t in self.temperatures]))
        self.echo("height:     " + "".join(["{:>8.3f}mm".format(t) for t in self.heights]))
        self.echo("")
        if self.max_temperature < self.getRangeVar("temperature", 1):
            self.echo("INFO: Only {} floors will be present since the"
                      " number of desired temperatures is greater than"
                      " the available {} floors in the model"
                      " (counting by {} C).".format(len(self.temperatures),
                                                    len(self.heights),
                                                    self.getVar("temperature_step")))
        elif len(self.temperatures) < len(self.heights):
            self.echo("INFO: Only {} floors will be present since the"
                      " temperature range (counting by {}) has fewer"
                      " steps than the {}-floor tower"
                      " model.".format(len(self.temperatures),
                                       self.getVar("temperature_step"),
                                       len(self.heights)))
        return True

    def getRangeString(self, name):
        return (str(self.getRangeVar(name, 0)) + "-"
                + str(self.getRangeVar(name, 1)))

    def setStat(self, name, value, line_number):
        """
        If you override setStat, you must also override:
        - ...getStat so I can use the variables.
        - ...clearStats so I can clear stats at the start of an
          operation.
        - ...getStatLine so I can provide accurate error output.
        """
        if not self.getStat("stop_building"):
            if name == "E":
                total_name = "total_" + name + "_before_stop_building"
                prev_total = self.stats.get(total_name)
                if prev_total is not None:
                    self.stats[total_name] += Decimal(value)
                else:
                    self.stats[total_name] = Decimal(value)
        self.stats[name] = value
        self.stats_lines[name] = line_number

    def getStat(self, name):
        return self.stats.get(name)

    def _changeStat(self, name, delta, line_number):
        self.setStat(name, self.getStat(name) + delta, line_number)

    def getStatLine(self, name):
        return self.stats_lines.get(name)

    def clearStats(self):
        self.stats = {}  # values known by current OR previous lines
        self.stats_lines = {}  # what line# provides the value of a stat

    def generateTowerThread(self):
        echoP = self._echo_progress
        start_temperature_found = False
        stw_cmd = self.commands['set temperature and wait']
        stw_param0 = self.params['set temperature and wait'][0]

        self.clearStats()
        self.setStat("height", Decimal("0.00"), -1)

        self.setStat("level", 0, -1)
        self.setStat("new_line_count", 0, -1)
        self.setStat("stop_building", False, -1)
        last_height = None
        something_printed = False  # Tells the program whether "actual" printing ever occurred yet.
        deltas = {}  # difference from previous (only for keys in current line)
        given_values = None  # ONLY values from the current line
        previous_values = {}
        previous_dst_line = None
        previous_src_line = None
        line_number = -1
        try:
            if not self.checkSettings():
                self.enableUI(True)
                return False
            else:
                print("* saving '" + self._settingsPath +"'...")
                self.saveSettings()
        except Exception as e:
            self.echo(str(e))
            raise e
        tmp_path = self.getVar("template_gcode_path") + ".tmp"
        dst_path = (self.getRangeString("temperature") + "_"
                         + self.getVar("template_gcode_path"))
        # os.path.splitext(self.getVar("template_gcode_path"))[0]
        # + "_" + range + ".gcode"
        level_t_debug_shown = {}
        level_next_debug_shown = {}
        level_no_next_debug_shown = {}
        level_wait_next_debug_shown = {}
        bytes_total = os.path.getsize(self.getVar("template_gcode_path"))
        bytes_count = 0
        self.setStat("progress", "0%", -1)
        prev_line_len = 0
        with open(self.getVar("template_gcode_path")) as ins:
            with open(tmp_path, 'w') as outs:
                line_number = 0
                for original_line in ins:
                    bytes_count += prev_line_len
                    self.setStat("progress", str(round(bytes_count/round(bytes_total/100))) + "%", line_number)
                    prev_line_len = len(original_line)
                    next_level_height = None
                    next_level_temperature = None
                    if self.getStat("level") + 1 < len(self.heights):
                        next_level_height = self.heights[self.getStat("level") + 1]
                        if self._verbose:
                            l_str = str(self.getStat("level") + 1)
                            if level_next_debug_shown.get(l_str) is not True:
                                echoP("* INFO: The next height (for level {}) is {}.".format(l_str, next_level_height))
                                level_next_debug_shown[l_str] = True
                    else:
                        if self._verbose:
                            l_str = str(self.getStat("level") + 1)
                            if level_no_next_debug_shown.get(l_str) is not True:
                                echoP("* INFO: There is no height for the next level ({}).".format(l_str))
                                level_no_next_debug_shown[l_str] = True
                    if self.getStat("level") + 1 < len(self.temperatures):
                        next_level_temperature = self.temperatures[self.getStat("level") + 1]
                        if self._verbose:
                            l_str = str(self.getStat("level") + 1)
                            if level_t_debug_shown.get(l_str) is not True:
                                echoP("* INFO: A temperature for level {} is being accessed.".format(l_str))
                                level_t_debug_shown[l_str] = True
                    if given_values is not None:
                        for k, v in given_values.items():
                            previous_values[k] = v
                    given_values = {}  # This is ONLY for the current
                                       # command. Other known (past)
                                       # values are in stats.
                    line_number += 1
                    line = original_line.rstrip()
                    double_blank = False
                    if previous_dst_line is not None:
                        if (len(previous_dst_line) == 0) and (len(line) == 0):
                            double_blank = True
                    previous_src_line = line
                    cmd_meta = get_cmd_meta(line)
                    would_extrude = False
                    would_move_for_build = False
                    would_build = False
                    deltas = {}
                    part_indices = {}
                    if cmd_meta is not None:
                        for i in range(1, len(cmd_meta)):
                            part_indices[cmd_meta[i][0]] = i
                            if len(cmd_meta[i]) < 2:
                                continue  # no value; just a letter param
                            elif len(cmd_meta[i]) > 2:
                                echoP("Line {}: WARNING: extra param (this should never happen) in '{}'".format(line_number, line))
                            try:
                                self.setStat(cmd_meta[i][0], Decimal(cmd_meta[i][1]), line_number)
                                given_values[cmd_meta[i][0]] = Decimal(cmd_meta[i][1])
                            except decimal.InvalidOperation as e:
                                if type(e) == decimal.ConversionSyntax:
                                    echoP("Line {}: ERROR: Bad conversion syntax: '{}'".format(line_number, cmd_meta[i][1]))
                                else:
                                    echoP("Line {}: ERROR: Bad Decimal (InvalidOperation): '{}'".format(line_number, cmd_meta[i][1]))
                                echoP("  cmd_meta: {}".format(cmd_meta))
                        for k, v in given_values.items():
                            previous_v = previous_values.get(k)
                            if previous_v is not None:
                                deltas[k] = v - previous_v
                        if self.getStat("stop_building"):
                            # echoP(str(cmd_meta))
                            if (len(cmd_meta) == 2):
                                if (cmd_meta[1][0] == "F"):
                                    # It ONLY has F param, so it is not end gcode
                                    would_move_for_build = True
                                # elif given_values.get("F") is not None:
                                    # echoP("Line {}: ERROR: Keeping"
                                          # " unnecessary"
                                          # " F in:"
                                          # " {}".format(line_number,
                                                       # cmd_meta))
                            # else:
                                # echoP("Line {}: ERROR: Keeping"
                                      # " necessary F"
                                      # " in: {}".format(line_number,
                                                       # cmd_meta))
                    if cmd_meta is None:
                        if (not self.getStat("stop_building")) or (not double_blank):
                            outs.write(original_line.rstrip("\n").rstrip("\r") + "\n")
                            previous_dst_line = line
                        continue
                    code_number = int(cmd_meta[0][1])
                    if cmd_meta[0][0] == "G":
                        if given_values.get('E') is not None:
                            would_extrude = True
                            # if (comment is not None) or (GCodeFollower._end_retraction_flag in comment):
                            if GCodeFollower._end_retraction_flag in line:
                                if Decimal(given_values.get('E')) < 0:
                                    # NOTE: Otherwise includes retractions in end gcode
                                    # (negative # after E)
                                    would_extrude = False
                            # Otherwise, discard BOTH negative and positive
                            # filament feeding after tower is finished.
                        # NOTE: homing is still allowed (values without params
                        # are not in given_values).
                        if given_values.get('X') is not None:
                            if (given_values.get('Y') is not None):
                                # echoP("NOT HOMING: " + str(given_values))
                                would_move_for_build = True
                            elif (given_values.get('Z') is not None):
                                # echoP("NOT HOMING: " + str(given_values))
                                would_move_for_build = True
                            elif given_values.get('X') != Decimal("0.00"):
                                # echoP("NOT HOMING: " + str(given_values))
                                would_move_for_build = True
                            else:
                                # it is homing X, so it isn't building
                                # echoP("HOMING: " + str(given_values))
                                pass
                        # elif given_values.get('Y') is not None:
                            # # NOTE: This can't help but eliminate moving the
                            # # (Prusa-style) bed forward for easy removal in end
                            # # gcode.
                            # would_move_for_build = True
                        delta_z = deltas.get("Z")
                        if (delta_z is not None):
                            if (abs(delta_z) <= self.getVar("max_z_build_movement")):
                                # This is too small to be a necessary move
                                # (it is probably moving to the next layer)
                                would_move_for_build = True
                            elif self.getStat("stop_building") and not would_move_for_build:
                                echoP("Line {}: Moving from {} (from"
                                      " line {}) to {} would"
                                      " move a lot {}"
                                      " (keeping '{}').".format(
                                        line_number,
                                        self.getStat("Z"),
                                        self.getStatLine("Z"),
                                        given_values.get("Z"),
                                        abs(deltas.get("Z")),
                                        line
                                      ))
                        elif self.getStat("stop_building") and (self.getStat("Z") is None):
                            echoP("Line {}: ERROR: No recorded z delta"
                                  "but build is"
                                  " over.".format(line_number))

                        would_build = would_extrude or would_move_for_build

                        if (code_number == 1) or (code_number == 0):
                            if self.getStat("stop_building"):
                                if would_build:
                                    # NOTE: this removes any retraction
                                    # (negative value after 'E' param) in stop
                                    # gcode.
                                    continue
                                else:
                                    echoP("Line {}: WARNING: Allowing '{}'"
                                              " after stop (z delta {})".format(
                                                line_number, line, deltas.get("Z")
                                              ))
                            outs.write(line + "\n")
                            previous_dst_line = line  # It's just a movement,
                                                      # so don't edit it.
                                                      # Insert temperature after
                                                      # it if it is a new level
                                                      # (below).
                            given_z = given_values.get("Z")
                            z_index = part_indices.get("Z")
                            if z_index is None:
                                continue
                            if len(cmd_meta[z_index]) == 1:
                                self.setStat("height", Decimal("0.00"), line_number)
                                last_height = self.getStat("height")
                                self.setStat("level", 0, line_number)
                                # echoP("Line {}: Missing value after"
                                      # " '{}'".format(
                                    # line_number,
                                    # cmd_meta[1][0])
                                # )
                                # continue
                                # if len(cmd_meta[1]) == 1:  # already checked
                                echoP("Line {}: INFO: Homing was"
                                      " detected so"
                                      " level & height were changed"
                                      " to 0...")
                                continue
                            else:
                                # NOTE: already determined to have "Z"
                                #   (See `continue` further up.)
                                # NOTE: len(cmd_meta[z_index]) cannot be 0 since
                                #   it is obtained using split.
                                self.setStat("height", Decimal(cmd_meta[z_index][1]), line_number)
                                # if self._verbose:
                                    # echoP(
                                        # "* INFO: Z is now {} due to"
                                        # " {}".format(
                                            # cmd_meta[z_index][1],
                                            # cmd_meta
                                        # )
                                    # )
                                last_height = self.getStat("height")
                                if next_level_height is None:
                                    if not self.getStat("stop_building"):
                                        self.setStat("stop_building", True, line_number)
                                        outs.write(self._stop_building_msg + "\n")
                                        if next_level_temperature is not None:
                                            echoP(
                                                "* Line {}: The tower"
                                                " ends (there is no"
                                                " level beyond {}) at"
                                                " {} before the"
                                                " temperature range, so"
                                                " there will be no"
                                                " temperature beyond {}"
                                                .format(
                                                    line_number,
                                                    self.getStat("level"),
                                                    self.getStat("height"),
                                                    self.temperatures[self.getStat("level")]
                                                )
                                            )
                                        else:
                                            echoP(
                                                "* Line {}: The tower"
                                                " ends (there is no"
                                                " level beyond {}) at"
                                                " {} nor another level"
                                                " in the temperature"
                                                " range, so there will"
                                                " be no temperature"
                                                " beyond {}"
                                                .format(
                                                    line_number,
                                                    self.getStat("level"),
                                                    self.getStat("height"),
                                                    self.temperatures[self.getStat("level")]
                                                )
                                            )
                                        echoP("  (Future extrusion"
                                                  " will be"
                                                  " suppressed)")

                                        continue
                                elif self.getStat("height") >= next_level_height:
                                    # This code can still be reached if not
                                    # would_extrude:
                                    if next_level_temperature is None:
                                        if not self.getStat("stop_building"):
                                            self.setStat("stop_building", True, line_number)
                                            outs.write(self._stop_building_msg + "\n")
                                            echoP(
                                                "* Line {}: The tower"
                                                " will be truncated"
                                                " since there is no new"
                                                " temperature available"
                                                " (no level beyond {})"
                                                " at {}".format(
                                                    line_number,
                                                    self.getStat("level"),
                                                    self.getStat("height")
                                                )
                                            )
                                            echoP("  (Future extrusion"
                                                  " will be"
                                                  " suppressed)")
                                        continue
                                    if not start_temperature_found: # self.getStat("level") == 0
                                        echoP(
                                            "Line {}: INFO: Splicing"
                                            " temperature at {} will be"
                                            " skipped since the old set"
                                            " temp and wait ({}) wasn't"
                                            " found yet (level is {}),"
                                            " so this is z move is"
                                            " presumably start"
                                            " gcode.".format(
                                                line_number,
                                                self.getStat("height"),
                                                stw_cmd,
                                                self.getStat("level")
                                            )
                                        )
                                    elif ((len(self.heights) > self.getStat("level") + 2)
                                          and (self.getStat("height") > self.heights[self.getStat("level") + 2])):
                                        echoP(
                                            "Line {}: WARNING: Splicing"
                                            " temperature at height"
                                            " {} will be skipped since"
                                            " the height is greater"
                                            " than the next level after"
                                            " the one starting here"
                                            " (since this may"
                                            " be a wait or purge"
                                            " position)".format(
                                                line_number,
                                                self.getStat("height"),
                                            )
                                        )
                                    else:
                                        # if self.getStat("level") + 1 < len(self.temperatures):
                                        # already checked (see this clause and
                                        # the previous if clause).
                                        self._changeStat("level", 1, line_number)
                                        if self._verbose:
                                            echoP("Line {}: INFO: "
                                                " **temperature** at"
                                                " height {} will become"
                                                " {} (for level"
                                                " {})".format(
                                                    line_number,
                                                    self.getStat("height"),
                                                    self.temperatures[self.getStat("level")],
                                                    self.getStat("level")
                                                )
                                            )
                                        new_line = "{} {}{:.2f}".format(
                                            stw_cmd,
                                            stw_param0,
                                            self.temperatures[self.getStat("level")]
                                        )
                                        # echoP(new_line)
                                        outs.write(new_line + "\n")
                                        previous_dst_line = new_line
                                        self.stats["new_line_count"] += 1
                                        echoP(
                                            "Line {}: Inserted:"
                                            " {}".format(
                                                line_number,
                                                new_line
                                            )
                                        )
                                        echoP("- after '{}'".format(line))
                                        echoP("- new line #: {}".format(
                                            line_number+self.stats["new_line_count"]
                                        ))
                                else:
                                    if self._verbose:
                                        l_str = str(self.getStat("level") + 1)
                                        if level_wait_next_debug_shown.get(l_str) is not True:
                                            # echoP("* INFO: The next height (for level {}) of {} has not yet been reached at {}.".format(l_str, next_level_height, self.getStat("height")))
                                            level_wait_next_debug_shown[l_str] = True

                        else:  # some other G code
                            if self.getStat("stop_building"):
                                if would_build:
                                    continue
                                else:
                                    if code_number == 91:
                                        echoP("Line {}: INFO:"
                                            " Allowing '{}'"
                                            " after stop".format(
                                                line_number,
                                                line
                                            )
                                        )
                                    else:
                                        echoP(
                                            "Line {}: WARNING:"
                                            " Allowing '{}'"
                                            " after stop".format(
                                                line_number, line
                                            )
                                        )
                            outs.write(line + "\n")
                            previous_dst_line = line

                    elif cmd_meta[0][0] == "M":
                        if line[0:5] == stw_cmd + " ":  # set temperature & wait
                            # (extruder temperature)
                            # d for decimal integer format (with no decimals):
                            new_line = "{} {}{:d}".format(stw_cmd, stw_param0,
                                                          self.temperatures[self.getStat("level")])
                            if start_temperature_found:
                                echoP("Line {}: Extra temperature command at {}: {}".format(line_number, self.getStat("height"), line)
                                      + "\n- changed to: {}...".format(new_line))
                            else:
                                echoP("Line {}: Initial temperature command at {}: {}".format(line_number, self.getStat("height"), line)
                                      + "\n- changed to: {}...".format(new_line))
                            outs.write(new_line + "\n")
                            previous_dst_line = line
                            # if self.getStat("level") == 0:
                                # if self.getStat("level") + 1 < len(self.temperatures):
                                    # self._changeStat("level", 1, line_number)
                                    # # echoP("Level {} is "
                                            # "next.".format(
                                              # self.getStat("level"))
                                            # )
                            start_temperature_found = True
                        elif self.getStat("stop_building") and (code_number == self.code_numbers['set fan speed']):
                            # Do not keep the fan speed line.
                            continue
                        else:
                            outs.write(line + "\n")
                            previous_dst_line = line
                    else:
                        outs.write(line + "\n")
                        previous_dst_line = line
                        pass
                        # echoP("Unknown command:"
                              # " {}".format(cmd_meta[0][0]))
        shutil.move(tmp_path, dst_path)
        self.echo("100% (done; saved {})".format(dst_path))
        bytes_count = bytes_total
        self.setStat("progress", "100%", line_number)

        # @G1 Z16.40
        # +M104 S240
        # @G1 Z30.16
        # +M104 S245
        # @G1 Z43.60
        # +M104 S250
        # @G1 Z57.04
        # +M104 S255
        self.enableUI(True)
        return True

if __name__ == "__main__":
    print("This is a module. To use it, you must import it into your "
          " program. You probably meant to run TowerConfiguration.py"
          " or TowerConfigurationCLI.py")
