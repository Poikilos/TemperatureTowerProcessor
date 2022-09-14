#!/usr/bin/env python3
from __future__ import print_function
from __future__ import division

'''
This program changes and inserts temperatures into gcode that builds a
temperature tower.
Copyright (C) 2019  Jake "Poikilos" Gustafson
'''
import sys
import os
import copy
import shutil
import json
import decimal
import inspect
import math

from decimal import Decimal

CLI_HELP = '''

Usage
(where command is TemperatureConfiguration.pyw or
TemperatureConfigurationCLI.py):
command [filename] [<temperature1> <temperature2>] [optional arguments]

Sequential arguments:
filename -- Provide a path to a gcode file.
temperatures -- Provide a minimum and maximum temperature. You must
    provide 0 or 2 temperatures, otherwise a ValueError will occur in
    main(). If you provide filename, temperatures must come after
    the filename

Optional arguments:
--verbose -- Set whether to show additional messages.
'''

'''
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''


verbosity = 0
for argI in range(1, len(sys.argv)):
    arg = sys.argv[argI]
    if arg.startswith("--"):
        if arg == "--verbosity":
            verbosity = 1
        elif arg == "--debug":
            verbosity = 2


def debug(*args, **kwargs):
    '''
    The Main class should override this and use its own verbose setting
    (See Main class code:
    global debug
    debug = self.debug
    )
    '''
    print(*args, file=sys.stderr, **kwargs)
    return True


def echo0(*args, **kwargs):  # formerly error
    print(*args, file=sys.stderr, **kwargs)
    return True


def echo1(*args, **kwargs):
    global verbosity
    if verbosity < 1:
        return False
    print(*args, file=sys.stderr, **kwargs)
    return True


def echo2(*args, **kwargs):
    global verbosity
    if verbosity < 2:
        return False
    print(*args, file=sys.stderr, **kwargs)
    return True


def usage():
    # print(CLI_HELP)
    print(GCodeFollower.getDocumentation())
    GCodeFollower.printSettingsDocumentation()
    print("")


def show_fewest(n):
    '''
    Display only decimal places that are not 0.

    Sequential arguments:
    n -- a float/Decimal value.
    '''
    s = "{}".format(n)
    while s.endswith(".0") or s.endswith("0"):
        s = s[:-1]
    return s



python_round = round


def round_nearest_d(*args):
    '''
    This is a Decimal version of round_nearest. See round_nearest for
    documentation.
    '''
    if len(args) == 1:
        x = args[0]
        i, f = divmod(x, 1)
        return int(i + ((f >= 0.5) if (x > 0) else (f > 0.5)))
    elif len(args) == 2:
        precision = args[1]
        # return python_round(args[0], precision)
        multiplier = Decimal(10 ** precision)
        increased = Decimal(args[0] * multiplier)
        return Decimal(round_nearest_d(increased)) / Decimal(multiplier)
    else:
        ValueError(
            "round_nearest only takes 1 or 2 arguments:"
            " (value [, precision])"
        )


def round_nearest(*args):
    '''
    This function circumvents the new Python 3 behavior where round uses
    "banker's rounding" to "limit the accumulation of errors when
    summing a list of rounded integers" (according to remi.lapeyre on
    <https://bugs.python.org/issue36082>).
    - The result of banker's rounding is that round(1.5) is 2 and
      round(2.5) is 2 and round(2.51) is 3. Rounding even numbers
      differs since the rounding is toward (but not all the way to) the
      nearest even number.
    - To monkey patch Python 3 to do rounding the "school" way (such as
      rounding 2.5 to 3), do:
      round = round_nearest

    This function is based on E. Zeytinci's Nov 13, 2019 answer
    <https://stackoverflow.com/a/58839239> on
    <https://stackoverflow.com/questions/58838995/how-to-switch-off-
    bankers-rounding-in-python>.

    However, this version skips the procedure if a second sequential
    argument is given.

    Sequential arguments:
    value -- a float value to round.
    precision (optional) -- the number of decimal places to keep (uses
        Python's builtin round function which uses banker's rounding in
        Python 3). If not provided, value is rounded to a whole number
        manually (without Python's builtin round function).
    '''
    if len(args) == 1:
        x = args[0]
        i, f = divmod(x, 1)
        return int(i + ((f >= 0.5) if (x > 0) else (f > 0.5)))
    elif len(args) == 2:
        precision = args[1]
        # return python_round(args[0], precision)
        multiplier = 10 ** precision
        increased = args[0] * multiplier
        return round_nearest(increased) / multiplier
    else:
        ValueError(
            "round_nearest only takes 1 or 2 arguments:"
            " (value [, precision])"
        )

round = round_nearest


def getHMSFromS(estSec):
    estLeft = estSec
    estHr = estLeft // 3600
    estLeft -= float(estHr) * 3600.0
    estMin = estLeft // 60
    estLeft -= float(estMin) * 60.0
    estLeft = round(estLeft)
    return int(estHr), int(estMin), round(estLeft)


def getHMSMessageFromS(estSec):
    h, m, s = getHMSFromS(estSec)
    return "{}h{}m{}s".format(h, m, s)


def encVal(v):
    '''
    Get the encoded value as would appear in Python code.
    '''
    if v is None:
        return "None"
    if v is True:
        return "True"
    if v is False:
        return "False"
    elif isinstance(v, str):
        return '"{}"'.format(v)
    return str(v)


def modify_cmd_meta(meta, key, value, precision=5):
    for pair in meta:
        if pair[0] != key:
            continue
        if len(pair) < 2:
            raise ValueError(
                "The key has no param in the original command `{}`,"
                " so the key '{}' was left unchanged for safety."
                "".format(cmd, key)
            )
        if isinstance(value, float) or isinstance(value, Decimal):
            # decimal_format = "{:."+str(precision)+"f}"
            # pair[1] = decimal_format.format(round(value, precision))
            pair[1] = show_fewest(round(value, precision))
            # pair[1] = show_fewest(value)
        else:
            pair[1] = "{}".format(value)
        return True
    return False


def meta_to_cmd(meta):
    '''
    Transform a list of key-value pairs (2-long tuples or lists) into a
    single g-code command string.
    '''
    result = ""
    prefix = ""
    for pair in meta:
        result += prefix
        if len(pair) != 2:
            raise ValueError(
                "Each list in meta from get_cmd_meta should be a pair,"
                " but there is a different number of parts in: {}"
                "".format(pair)
            )
        for part in pair:
            result += "{}".format(part)
        prefix = " "
    return result


def changed_cmd(cmd, key, value, precision=5):
    '''
    Parse the g-code command and after key, change the number to value.
    If value is a float or decimal, format it to the number of places
    specified by precision.
    Otherwise, format it directly (assume it is a string with the
    correct number of decimal places or an int that should have no
    decimal places).
    '''
    meta = get_cmd_meta(cmd)
    result = modify_cmd_meta(meta, key, value, precision=precision)
    if not result:
        return cmd
    return meta_to_cmd(meta)


def get_cmd_meta(cmd):
    '''
    Parse the g-code command to a set of lists such as:
    [['G', '1'], ['X', '110'], ['E', '45'], ['F', '500.0']]
    [['M', '117'], ['', 'Some message']]
    '''
    comment_i = None
    '''
    commentMarks = [";", "//"]
    for commentMark in commentMarks:
      tryI = cmd.find(commentMark)
      if tryI >= 0:
          if (comment_i is None) or (tryI < comment_i):
              comment_i = tryI
    '''
    tryI = cmd.find(";")
    if tryI >= 0:
        # if (comment_i is None) or (tryI < comment_i):
        comment_i = tryI
    if cmd.strip().startswith("/"):
        # ^ as per <https://www.cnccookbook.com/
        #   g-code-basics-program-format-structure-blocks/>
        # (also takes care of non-standard // comments)
        comment_i = cmd.find("/")
    if comment_i is not None:
        cmd = cmd[0:comment_i]

    cmd = cmd.strip()
    # print("cmd={}".format(cmd))
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
    functionStr = None
    for i in range(len(parts)):
        arg = parts[i].strip()
        if functionStr is None:
            if len(arg) < 1:
                functionStr = ""
            else:
                functionStr = arg
        if len(arg) > 1:
            k, v = arg[0], arg[1:]
            if functionStr == "M117":
                displayStr = " ".join(parts[1:])
                cmd_meta.append([k, v])
                cmd_meta.append(['', displayStr])
                # ^ See M117 in docstring
                break
            try:
                fv = float(v)
            except ValueError as ex:
                echo0('WARNING: "{}" is not a number in "{}"'
                      ''.format(v, cmd))
            cmd_meta.append([k, v])
        else:
            # no value (such as: To home X, nothing is after 'G1 X'):
            cmd_meta.append([arg[0]])
    return cmd_meta


def cmd_meta_dict(cmd_meta):
    '''
    Change results of get_cmd_meta like
    [['G', '1'], ['X', '110'], ['E', '45'], ['F', '500.0']]
    to a dictionary like:
    {'function': 'G1', 'G': '1', 'X': '110', 'E': '45', 'F': '500.0'}
    '''
    if cmd_meta is None:
        return None
    metaD = {}
    for pair in cmd_meta:
        if metaD.get('function') is None:
            if len(pair) != 2:
                echo0("WARNING: The G-code command doesn't have"
                      " 2 parts: {} in {}"
                      "".format(pair, cmd_meta))
                metaD['function'] = ''  # prevent gathering it again
            else:
                metaD['function'] = ''.join(pair)
        if len(pair) == 2:
            k, v = pair
        elif len(pair) == 1:
            k, v = pair[0], None
        else:
            k, v = pair[0], pair[1:]
        metaD[k] = v
    return metaD


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


class GCodeFollowerArgParser():
    '''
    The run arguments are parsed here in case you want to change them
    via the GUI. They are parsed once and for all to avoid late parsing
    as long as you only make one instance of this class!

    '''
    def __init__(self):
        '''
        This uses sys.argv! See usage for documentation.
        '''
        global verbosity
        self.verbose = False if verbosity < 1 else True
        self.temperatures = None
        self.template_gcode_path = None
        self.help = False
        seqArgs = []

        for argI in range(1, len(sys.argv)):
            arg = sys.argv[argI]
            if arg == "--verbose":
                self.verbose = True
                echo0("* Verbose mode is enabled.")
            elif arg == "--help":
                self.help = True
            elif arg.startswith("--"):
                raise ValueError("The argument {} is invalid."
                                 "".format(arg))
            else:
                seqArgs.append(arg)

        if (len(seqArgs) == 1) or (len(seqArgs) == 3):
            self.template_gcode_path = seqArgs[0]
        if len(seqArgs) == 3:
            self.temperatures = [seqArgs[1], seqArgs[2]]
        elif len(seqArgs) == 2:
            self.temperatures = [seqArgs[0], seqArgs[1]]
        if len(seqArgs) > 3:
            usage()
            raise ValueError("Error: There were too many arguments.")

        if self.verbose:
            print("seqArgs: {}".format(seqArgs))
            print("template_gcode_path: {}".format(self.template_gcode_path))
            print("temperatures: {}".format(self.temperatures))


class GCodeFollower:
    '''

    Public properties:
    desired_temperatures -- The user wants this list temperatures. It
        usually differs from the number of levels in the tower.

    emuState --  Gather and store the projected state of the hardware.
        The state is reset on _generateTower since it calls
        resetEmuState.
        State variables:
        - 'position' is a 3D position of the current tool (a list or
          tuple of 3 floats). It doesn't need to be stored separately
          in each tool because the a head with all tools on the same
          carriage is the only arrangement that is emulated.
        - 'tool' is the current tool string such as 'T0' by default.
        - 'tools' is a dictionary of tool states where 'tool' is the
          key. Obtain the current tool's state safely with getToolState.
          Example tools:
          - 'T0' (and others) is a dict containing tool information.
            - 'temperature' is the projected temperature (starting at
              self.roomTemperature).
            - There is no position. The global position is used.
        - 'servos' is a dictionary of servo states where 'extruder' is
          the key. Obtain the servos's state safely with getEPos.
          Example servos:
          - 'E0' (and others) is a dict containing servo information.
            - 'position' is a 1D (float, not list) position.
    '''
    _towerName = ("the mesh (such as STL) from Python GUI for"
                  " Configurable Temperature Tower")
    _downloadPageURLs = [
        "https://www.thingiverse.com/thing:4068975",
        "https://github.com/poikilos/TemperatureTowerProcessor"
    ]
    # The old one is thing:2092820 but that is not very tall, and has
    # some mesh issues.

    _end_retraction_flag = "filament slightly"
    _rangeNames = ["min", "max"]
    _settingsDocPath = "settings descriptions.txt"
    _settingsPath = "settings.json"
    _settings_types = {}
    _settings_descriptions = {}

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

    def __init__(self, echo_callback=None, enable_ui_callback=None,
                 verbose=False, autoHomeToolTemperature=200.0,
                 autoHomeBedTemperature=60.0, autoHomeMoveTime=51.0,
                 roomTemperature=20):
        """
        Change settings via setVar and self.getVar. Call
        "getSettingsNames" to get a list of all settings. Call "getHelp"
        to see the documentation for each setting, preceded by the type
        in parenthesis.

        Keyword arguments:
        echo_callback -- Whatever function you provide must accept a
            string. It will be called whenever status should be shown.
        enable_ui_callback -- Whatever function you provide must accept
            a boolean. It will be called with false whenever a process
            starts and true whenever a process ends.
        autoHomeBedTemperature -- Assume this temperature has to be
            reached before G28 will start (If not None, add a
            significant delay to G28)
        autoHomeToolTemperature -- Assume this temperature has to be
            reached before G28 will start (If not None, add a
            significant delay to G28)
        autoHomeMoveTime -- Assume that G28 takes this long even if the
            temperature is reached (A longer time like 90.0 is
            recommended if using a touch sensor with a repeatability
            test enabled).
        roomTemperature -- Set the temperature of the room.
        """
        self._verbose = (verbose is True)
        global debug
        debug = self.debug
        self._estS = 0.0
        self._extrudeS = None
        self._settings = {}

        self.stats = {}
        self._createVar("template_gcode_path", None, "str",
                        "Look here for the source gcode of the"
                        " temperature tower.")
        self._createVar("default_path", "tower.gcode", "str",
                        "Look here if template_gcode_path is not"
                        " specified.")
        self._createVar("level_count", 10, "int",
                        "This is how many levels are in the source"
                        " gcode file.")
        self._createVar("level_height", "10.0", "Decimal",
                        "The height of each level excluding levels"
                        " (special_heights can override this for"
                        " individual levels of the tower).")
        self._createVar("special_heights[0]", "12.8", "Decimal",
                        "This is the height of the first floor and any"
                        " other floors that don't match level_height"
                        " (must be consecutive).")
        self._createVar("temperature_step", "5", "int",
                        "Change this many degrees at each level.")
        self._createVar("max_z_build_movement", "1.20", "Decimal",
                        "This Z distance or less is counted as a build"
                        " movement, and is eliminated after the tower"
                        " is truncated (after there are no more"
                        " temperature steps in the range and the next"
                        " level would start).")
        self._createVar(self.getRangeVarName("temperature", 0), None,
                        "int", ("The first level of the temperature"
                                " tower should be printed at this"
                                " temperature (C)."))
        self._createVar(self.getRangeVarName("temperature", 1), None,
                        "int", ("After incrementing each level of the"
                                " tower by temperature_step, finish the"
                                " level that is this temperature then"
                                " stop printing."))
        self._stop_building_msg = ("; GCodeFollower says: stop_building"
                                   " (additional build-related codes"
                                   " that were below will be excluded)")
        self.fwDefaultPositionMode = 'absolute'
        self.autoHomeBedTemperature = autoHomeBedTemperature
        self.autoHomeToolTemperature = autoHomeToolTemperature
        self.autoHomeMoveTime = autoHomeMoveTime
        self.roomTemperature = roomTemperature
        # ^ The default *can* be absolute if set in Marlin
        #   configuration_adv.h (See
        #   <https://reprap.org/forum/read.php?262,193749>).
        # Initialize emuState (requires self.fwDefaultPositionMode):
        self.resetEmuState()
        # self._insert_msg = "; GCodeFollower."
        self.dirStep = None

        # region checkSettings sets this.
        self.max_temperature = None
        self.min_temperature = None
        self.heights = None
        self.temperatures = None
        self.desired_temperatures = None
        # endregion checkSettings sets this.

        if echo_callback is not None:
            self.echo = echo_callback

        if enable_ui_callback is not None:
            self.enableUI = enable_ui_callback

        # The first (minimum) value is at Z0:
        # self.setRangeVars("temperature", name, 240, 255)
        # self.setRangeVars("temperature", name, 190, 210)
        # NOTE: [Hatchbox
        # PLA](https://www.amazon.com/gp/product/B00J0GMMP6)
        # has the temperature 180-210, but 180 underextrudes unusably
        # (and doesn't adhere to the bed well [even 60C black diamond]).

        # G-Code reference:
        # - Marlin (or Sprinter):
        #   http://marlinfw.org/docs/gcode/G000-G001.html
        self.commands = {}
        self.params = {}

        # commands with known params:
        self.commands['fast_move'] = 'G0'  # usually without extrude
        self.commands['move'] = 'G1'  # move (and usually extrude)
        self.commands['set temperature and wait'] = 'M109'
        self.commands['set fan speed'] = 'M106'
        self.commands['set position'] = 'G92'
        self.commands['fan off'] = 'M107'
        # commands with no known params:
        # - G92.1 <http://marlinfw.org/docs/gcode/G092.html>:
        self.commands['Reset selected workspace to 0, 0, 0'] = 'G92.1'

        # params:
        self.params['fast_move'] = ['X', 'Y', 'Z', 'F', 'E']
        # NOTE: Using G0 for moves only (not extrusions) is a convention
        # (also, doing so helps with compatibility with devices that are
        # not 3D printers--see
        # http://marlinfw.org/docs/gcode/G000-G001.html).
        self.params['move'] = ['X', 'Y', 'Z', 'F', 'E']
        self.params['set temperature and wait'] = ['S']
        self.params['set fan speed'] = ['S']
        self.params['set position'] = ['E', 'X', 'Y', 'Z']
        self.params['fan off'] = ['P']
        self.param_names = {}
        self.param_names["E"] = "extrude (mm)"
        # E extrudes that many mm of filament (+/-, relative of course)
        self.param_names["F"] = "speed (mm/minute)"
        self.param_names["P"] = "index"  # such as fan# (default 0)

        self.code_numbers = {}
        for k, v in self.commands.items():
            self.code_numbers[k] = Decimal(v[1:])

        self.debuggedLengths = []

    def saveDocumentationOnce(self):
        if not os.path.isfile(GCodeFollower._settingsDocPath):
            self.saveDocumentation()
            print(
                "* an explanation of settings has been written to"
                " '{}'.".format(GCodeFollower._settingsDocPath)
            )
        else:
            print(
                "* an explanation of settings was previously saved to"
                " '{}'.".format(GCodeFollower._settingsDocPath)
            )

    def getToolPos(self):
        return [
            self.emuState['position'][0],
            self.emuState['position'][1],
            self.emuState['position'][2]
        ]

    def setExtruder(self, extruder):
        '''
        Sequential arguments:
        extruder -- The name of an extruder such as E0
        '''
        if not extruder.startswith('E'):
            raise ValueError("extruder must start with 'E' but is {}"
                             "".format(extruder))
        self.emuState['extruder'] = extruder
        if self.emuState['servos'].get(extruder) is None:
            self.emuState['servos'][extruder] = {
                'position': 0.0,
                'position_mode': self.fwDefaultPositionMode,
            }

    def getEPos(self):
        servo = self.emuState['extruder']
        servoState = self.emuState['servos'].get(servo)
        if servoState is None:
            return None
        return servoState.get('position')

    def setEPos(self, ePos):
        ePos = float(ePos)
        # ^ Ensure that a bad value raises ValueError.
        servo = self.emuState['extruder']
        if self.emuState['servos'].get(servo) is None:
            self.emuState['servos'][servo] = {}
        self.emuState['servos'][servo]['position'] = ePos

    def getToolTemperature(self):
        toolState = self.getToolState()
        temperature = None
        if toolState is not None:
            temperature = toolState.get('temperature')
        return temperature

    def setToolTemperature(self, temperature):
        temperature = float(temperature)
        # ^ Ensure that a bad value raises ValueError.
        tool = self.emuState['tool']
        if self.emuState['tools'].get(tool) is None:
            self.emuState['tools'][tool] = {}
        self.emuState['tools'][tool]['temperature'] = temperature

    def setToolToRoomTemperature(self):
        self.setToolTemperature(self.roomTemperature)

    def setToolToAmbientTemperature(self):
        self.setToolToRoomTemperature()

    def getBedTemperature(self):
        temperature = self.emuState.get('bed_temperature')
        return temperature

    def setBedTemperature(self, temperature):
        temperature = float(temperature)
        # ^ Ensure that a bad value raises ValueError.
        self.emuState['bed_temperature'] = temperature

    def setBedToRoomTemperature(self):
        self.setBedTemperature(self.roomTemperature)

    def setBedToAmbientTemperature(self):
        self.setBedToRoomTemperature()

    def getToolState(self):
        '''
        Get a tool state dict guaranteed to never be None. See the
        GCodeFollower documentation for descriptions of tool state
        entries.
        '''
        tool = self.emuState['tool']
        toolState = self.emuState['tools'].get(tool)
        if toolState is None:
            return {}
        return toolState

    def setTool(self, tool):
        if not tool.startswith('T'):
            raise ValueError("tool should start with 'T' but is {}"
                             "".format(tool))
        self.emuState['tool'] = tool
        if self.emuState['tools'].get(tool) is None:
            self.emuState['tools'][tool] = {
                'offsets': (0.0, 0.0, 0.0),
            }

    def resetEmuState(self):
        self.emuState = {
            'tools': {
            },
            'servos': {
            },
            'position': (0.0, 0.0, 0.0),
            'position_mode': self.fwDefaultPositionMode,
        }
        self.setBedToAmbientTemperature()
        self.setTool('T0')
        self.setToolToAmbientTemperature()
        self.setExtruder('E0')

    def saveDocumentation(self):
        try:
            with open(GCodeFollower._settingsDocPath, 'w') as outs:
                self.saveDocumentationTo(outs)
        except e:
            os.remove(GCodeFollower._settingsDocPath)
            raise e

    @staticmethod
    def saveDocumentationTo(stream):
        stream.write(GCodeFollower.getDocumentation() + "\n")

        def _saveLine(line):
            stream.write(line + "\n")
        # _saveLine("Writing settings:")
        GCodeFollower.printSettingsDocumentation(print_callback=_saveLine)

    @staticmethod
    def printSettingsDocumentation(print_callback=echo0):
        print_callback(
            "You can edit \"{}\" to change settings".format(
                GCodeFollower._settingsPath
            )
        )
        # being careful to maintain the JSON format properly (try
        # pasting your settings into https://jsonlint.com/ if you're
        # not sure, then copy from there)."
        # "".format(GCodeFollower._settingsPath)
        # print("If you write a Python program that imports"
        #       " GCodeFollower, you can set an individual setting by"
        #       " calling the setVar method on a GCodeFollower object"
        #       " before calling calling its generateTower"
        #       " method.")
        print_callback("")
        print_callback("Settings:")
        names = GCodeFollower.getSettingsNames()
        if len(names) < 1:
            raise RuntimeError("printSettingsDocumentation must be"
                               " called after an instance defines"
                               " variables.")
        for name in names:
            print_callback("- " + name + ": "
                           + GCodeFollower.getHelp(name))

    def setVar(self, name, value):
        """
        Automatically set the variable to the proper type, or raise
        ValueError if that is not possible.
        """
        if name not in self._settings:
            raise KeyError("{} is not a valid setting.".format(name))
        if value is not None:
            python_type = GCodeFollower._settings_types[name]
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
        if self._verbose:
            echo0("  * {} set {} to {}"
                  "".format(inspect.stack()[1][3], name,
                            self.getVar(name)))

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
        return cast_by_type_string(value, GCodeFollower._settings_types[name])

    def getVar(self, name, prevent_exceptions=False):
        # if prevent_exceptions:
        #     result = self._settings.get(name)
        #     if result is not None:
        #         return self.castVar(name, result)
        #     else:
        #         return None
        # return self.castVar(name, self._settings[name])
        result = self._settings.get(name)
        if prevent_exceptions:
            if result is None:
                return None
        # echo0(json.dumps(self._settings))
        return cast_by_type_string(result, GCodeFollower._settings_types[name])

    def getRangeVar(self, name, i):
        return self.getVar(self.getRangeVarName(name, i))

    def getRangeVarLen(self, name):
        return len(self.getRangeVars(name))

    def getRangeVars(self, name):
        results = []
        got = True
        count = 0
        while True:
            try:
                got = self.getVar(self.getRangeVarName(name, count),
                                  prevent_exceptions=True)
            except IndexError:
                # ^ getRangeVarName can still throw an exception
                got = None
            if got is None:
                break
            count += 1
            results.append(got)
        return results

    def _createVar(self, name, value, python_type, description):
        self._settings[name] = cast_by_type_string(value, python_type)
        GCodeFollower._settings_types[name] = python_type
        GCodeFollower._settings_descriptions[name] = description

    def getListVar(self, name, i, prevent_exceptions=True):
        return self.getVar(name + "[" + str(i) + "]",
                           prevent_exceptions=prevent_exceptions)

    def setListVar(self, name, i, value):
        self.setVar(name + "[" + str(i) + "]", value)

    @staticmethod
    def getHelp(name):
        """
        Get the documentation for a setting, preceded by the type in
        parenthesis.
        """
        return ("(" + GCodeFollower._settings_types[name] + ") "
                + GCodeFollower._settings_descriptions[name])

    @staticmethod
    def getSettingsNames():
        return GCodeFollower._settings_types.keys()

    def saveSettings(self):
        serializable_settings = {}
        for k, v in self._settings.items():
            if type(v).__name__ == "Decimal":
                serializable_settings[k] = str(v)
            else:
                serializable_settings[k] = v
        with open(GCodeFollower._settingsPath, 'w') as outs:
            json.dump(serializable_settings, outs, indent=4)
            # sort_keys=True)

    def loadSettings(self):
        echo0("Loading settings...")
        self.error = None
        with open(GCodeFollower._settingsPath) as ins:
            tmp_settings = json.load(ins)
            # Use a temp file in case the file is missing any settings.
            for k, originalV in tmp_settings.items():
                v = originalV
                if k in self._settings:
                    if v == "None":
                        v = None
                    self._settings[k] = self.castVar(k, v)
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

    def enableUI(self, enable):
        if enable:
            print("")
            print("The process completed.")
            print("")
        else:
            print("")
            print("Please wait...")

    def pushLimits(self, value):
        '''
        Push min & max to contain value.
        If either is None, they also take the value.
        '''
        if ((self.min_temperature is None)
                or (value < self.min_temperature)):
            self.min_temperature = value
        if ((self.max_temperature is None)
                or (value > self.max_temperature)):
            self.max_temperature = value

    def checkSettings(self):
        """

        Ensure that everything in the settings dictionary is
        correct. Call self.enableUI(True) if it fails, since this is
        not guaranteed to do that.

        Before calling this, set self.echo or set echo_callback using
        the constructor if you want messages to be shown back to the
        caller.

        The following are the values checked:
        template_gcode_path -- If None, default_path is used.
        temperature -- This must be a list of 2 temperatures, otherwise
            ValueError is raised.


        Incorrect setting(s) will cause the following:
        - raise ValueError if max_temperature or min_temperature are not
          present or not set properly.
        - raise FileNotFoundError if src_path is missing.

        Returns: a tuple (is_good, err_or_None).
        """
        verbose = self._verbose
        getV = self.getVar
        self.error = None

        if self.getVar("template_gcode_path") is not None:
            if verbose:
                print(
                    '* using template_gcode_path from settings: {}...'
                    ''.format(encVal(getV("template_gcode_path")))
                )
        else:
            self.setVar("template_gcode_path", getV("default_path"))
            if verbose:
                print('* checking for {}...'
                      ''.format(encVal(getV("template_gcode_path"))))
                print("")

        notePath = getV("template_gcode_path") + " is missing.txt"
        if not os.path.isfile(getV("template_gcode_path")):
            if verbose:
                print("")
                print(
                    "{} does not exist.".format(
                        encVal(getV("template_gcode_path"))
                    )
                )
            msg = ("You must slice " + GCodeFollower._towerName
                   + " from:")
            for thisURL in GCodeFollower._downloadPageURLs:
                msg += "\n- " + thisURL
            msg += "\nas {}".format(getV("template_gcode_path"))
            notePathMsg = ""
            if getV("template_gcode_path") == getV("default_path"):
                notePathMsg = ""
                exMessage = ""
                try:
                    with open(notePath, 'w') as outs:
                        outs.write(msg)
                    notePathMsg = ". See 'README.md'."
                    # See '" + os.path.abspath(notePath) + "'
                except e:
                    exType, exMessage, exTraceback = sys.exc_info()
                    if verbose:
                        print(exMessage)
                    notePathMsg = (" Writing '" +
                                   os.path.abspath(notePath)
                                   + "' failed: " + exMessage)
            # if verbose:
            self.echo(msg + notePathMsg)
            if verbose:
                print("")
            self.enableUI(True)
            raise FileNotFoundError(msg + notePathMsg)
            # return False, msg + notePathMsg
        else:
            if os.path.isfile(notePath):
                os.remove(notePath)

        for i in range(2):
            if self.getRangeVar("temperature", i) is None:
                self.enableUI(True)
                raise ValueError(
                    (self.getRangeVarName("temperature", i)
                     + " is missing.")
                )

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
        for i in range(getV("level_count")):
            this_level_height = getV("level_height")
            if (special_heights is not None) and (i < len(special_heights)):
                if special_heights[i] is not None:
                    # if verbose:
                    #     print("special_heights[" + str(i) + "]: "
                    #           + type(special_heights[i]).__name__)
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

        self.max_temperature = None
        self.min_temperature = None
        # ^ These are set automatically by self.pushLimits depending
        #   upon how many steps between all levels or how many
        #   temperatures are available (the smallest of the two).
        height_i = 0
        # height = Decimal("0.00")
        self.temperatures = []
        self.desired_temperatures = []
        self.dirStep = getV("temperature_step") * -1
        if self.dirStep == 0:
            raise ValueError("The step (per floor) should not be 0.")
        temps = self.getRangeVars("temperature")
        print("* Each new floor steps by: {} C".format(self.dirStep))
        this_temperature = temps[0]
        if self.dirStep < 1:
            this_temperature = temps[-1]
        # if verbose:
        #     print("this_temperature: "
        #           + type(this_temperature).__name__)
        # if this_temperature is None:
        #     self.enableUI(True)
        #     raise ValueError("The settings value '"
        #                      + self.getRangeVarName("temperature", 0)
        #                      + "' is missing (you must set this).")
        # if self.getRangeVar("temperature", 1) is None:
        #     self.enableUI(True)
        #     raise ValueError("The settings value '"
        #                      + self.getRangeVarName("temperature", 1)
        #                      + "' is missing (you must set this).")

        prevTemp = None
        for thisTemp in temps:
            if (prevTemp is not None) and (thisTemp < prevTemp):
                # self.dirStep *= 1
                raise ValueError("The steps must be in order"
                                 " from lowest to highest.")
            prevTemp = thisTemp
        temps = list(reversed(temps))
        print("* temperatures (max 1st usually): {}".format(temps))
        while True:
            if height_i < len(self.heights):
                # height = self.heights[height_i]
                # if verbose:
                #    print("* adding level {} ({} C) at"
                #           " {}mm".format(height_i,
                #                          this_temperature, height))
                self.temperatures.append(this_temperature)
                self.pushLimits(this_temperature)
                # ^ sets min_temperature and max_temperature
            self.desired_temperatures.append(this_temperature)
            # if verbose:
            #     print("temperature_step: "
            #           + type(getV("temperature_step")).__name__)
            this_temperature += self.dirStep
            if (self.dirStep > 0) and (this_temperature > temps[-1]):
                this_temperature -= self.dirStep
                break
            elif (self.dirStep < 0) and (this_temperature < temps[-1]):
                this_temperature -= self.dirStep
                break
            height_i += 1
        this_temperature = None
        self.echo("")
        ls = ["{:<9}".format(i) for i in range(len(self.temperatures))]
        self.echo("level:       " + "".join(ls))
        ts = ["{:<9}".format(t) for t in self.temperatures]
        self.echo("temperature: " + "".join(ts))
        hs = ["{:>8.3f}mm".format(t) for t in self.heights]
        self.echo("height:     " + "".join(hs))
        self.echo("")
        if (self.min_temperature > temps[-1]) and (self.dirStep < 0):
            self.echo(
                "INFO: The min_temperature {} didn't reach the last."
                " Only {} floors will be present since the"
                " number of desired temperatures to min is greater than"
                " the available {} floors in the model"
                " (counting by {} C).".format(self.min_temperature,
                                              len(self.temperatures),
                                              len(self.heights),
                                              getV("temperature_step"))
            )
        elif (self.max_temperature < temps[-1]) and (self.dirStep > 0):
            self.echo(
                "INFO: The max_temperature {} didn't reach the last."
                " Only {} floors will be present since the"
                " number of desired temperatures is greater than"
                " the available {} floors in the model"
                " (counting by {} C).".format(self.min_temperature,
                                              len(self.temperatures),
                                              len(self.heights),
                                              getV("temperature_step"))
            )
        elif len(self.temperatures) < len(self.heights):
            self.echo("INFO: Only {} floors ({}) will be present since"
                      " the temperature range ({} counting by {}) has"
                      " fewer steps than the {}-floor tower"
                      " model.".format(len(self.temperatures),
                                       self.temperatures,
                                       temps,
                                       getV("temperature_step"),
                                       len(self.heights)))
        return True, None

    def getRangeString(self, name):
        temps = self.getRangeVars(name)
        if self.dirStep < 0:
            return "{}-{}".format(temps[-1], temps[0])
        return "{}-{}".format(temps[0], temps[-1])

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
                total_name = "net_" + name + "_before_stop_building"
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

    def generateTower(self):
        try:
            self._generateTower()
        except Exception as ex:
            self.enableUI(True)
            raise ex

    def getToolSecRelTemp(self, S):
        '''
        Get an estimated time it takes to reach temperature S from the
        estimated current temperature.
        - If the current temperature is None,
          setToolToAmbientTemperature is called.
        '''
        temperature = self.getToolTemperature()
        if temperature is None:
            self.setToolToAmbientTemperature()
            temperature = self.getToolTemperature()
        diff = abs(S - temperature)
        toolSecPerDegree = 109.0 / 188.0
        # It took R2X 14T with FlexionHT about 1m49s to get from
        # room temperature of about 22C to 210C: 109s/188degrees
        # = 0.57978723404255319149 sec/deg
        return float(diff) * toolSecPerDegree

    def debug(self, msg):
        if not self._verbose:
            return
        echo0("[debug] {}".format(msg))

    def getBedSecRelTemp(self, S):
        '''
        Get an estimated time it takes to reach temperature S from the
        estimated current temperature.
        - If the current temperature is None, setBedToAmbientTemperature
          is called.
        '''
        temperature = self.getBedTemperature()
        if temperature is None:
            self.setBedToAmbientTemperature()
            temperature = self.getBedTemperature()
        diff = abs(S - temperature)
        bedSecPerDegree = 213.0 / 36.0
        # It took R2X 14T with stock z axis about 3m33s to get from
        # room temperature of about 22C to 58C: 213s/36degrees
        # = 5.91666666666666666667 sec/deg
        return float(diff) * bedSecPerDegree

    def addSec(self, gcodeLine):
        '''
        Analyze the gcode line and add seconds to self._estS based on
        the travel speed and distance.
        '''
        gcodeLine = gcodeLine.strip()
        cmd_meta = get_cmd_meta(gcodeLine)
        meta = cmd_meta_dict(cmd_meta)
        if meta is None:
            lenMsg = "{}(string[{}])".format(meta, 0)
        else:
            lenMsg = "{}(string[{}])".format(cmd_meta[0], len(meta))
        if lenMsg not in self.debuggedLengths:
            # Show unique command structures (Where the combination
            # of the G-code name and the parameter count is unique).
            self.debuggedLengths.append(lenMsg)
            debug("* found first instance of a command like: {}"
                  "".format(meta))
        if meta is None:
            return
        f = meta.get('function')
        if f is None:
            f = ""
        if f.startswith("T"):
            # Choose tool
            # such as {'T': '0'}
            self.setTool(f)
        elif f == "M104":
            # Set hotend temperature
            # such as {'M': '104', 'S': '210'}
            S = meta.get('S')
            if S is None:
                echo0('WARNING: S is None in "{}"'
                      ''.format(cmd_meta))
            else:
                S = float(S)
                self.setToolTemperature(S)
        elif f == "M105":
            # Report temperatures
            # Usage: M105 [R] [T<index>]
            # such as {'M': '105'}
            pass
        elif f == "M109":
            # Wait for hotend temperature
            # Usage:
            # M109 [B<temp>] [F<flag>] [I<index>] [R<temp>] [S<temp>] [T<index>]
            # such as {'M': '109', 'S': '210'}
            S = meta.get('S')
            if S is None:
                echo0('WARNING: S is None in "{}"'
                      ''.format(cmd_meta))
            else:
                S = float(S)
                heatupTime = self.getToolSecRelTemp(S)
                self._estS += heatupTime
                oldS = self.getToolTemperature()
                debug("_estSec += {} tool heatup time from {} to {}"
                      "".format(heatupTime, oldS, S))
                self.setToolTemperature(S)
        elif f == "M82":
            # Set extrusion to absolute mode
            # such as {'M': '82'}
            pass
        elif f == "M280":
            # Set a servo position
            # Usage: M280 P<index> S<pos>
            # such as {'M': '280', 'P': '0', 'S': '160'}
            pass
        elif f == "G4":
            # Dwell
            # Usage: G4 [P<time (ms)>] [S<time (sec)>]
            # such as {'G': '4', 'P': '100'}
            S = meta.get('S')
            P = meta.get('P')
            if P is not None:
                P = float(P)
            if S is None:
                if P is not None:
                    S = P / 1000.0
            else:
                S = float(S)
            if S is not None:
                self._estS += S
                debug("_estSec += {} dwell".format(S))
            else:
                echo0('WARNING: S & P are None in "{}"'
                      ''.format(cmd_meta))
        elif f == "M420":
            # Get and/or set bed leveling state
            # such as {'M': '420', 'S': '1'}
            pass
        elif f == "G28":
            # Auto-home
            # such as {'G': '28'}
            oldTS = self.getToolTemperature()
            T_S = self.autoHomeToolTemperature
            toolHeatupTime = self.getToolSecRelTemp(T_S)
            self._estS += toolHeatupTime
            debug("_estSec += {} tool heatup time from {} to {} auto"
                  "".format(toolHeatupTime, oldTS, T_S))
            self.setToolTemperature(T_S)
            oldBS = self.getBedTemperature()
            B_S = self.autoHomeBedTemperature
            bedHeatupTime = self.getBedSecRelTemp(B_S)
            self._estS += bedHeatupTime
            debug("  _estSec += {} bed heatup time from {} to {} auto"
                  "".format(bedHeatupTime, oldBS, B_S))
            self.setBedTemperature(B_S)
            self._estS += self.autoHomeMoveTime
            debug("  _estSec += {} autoHomeMoveTime"
                  "".format(self.autoHomeMoveTime))
            # ^ A long time assumes a touch sensor
        elif f == "M190":
            # Wait for bed temperature
            # such as {'M': '190', 'S': '60.0'}
            oldBS = self.getBedTemperature()
            B_S = meta.get('S')
            if B_S is not None:
                B_S = float(B_S)
                bedHeatupTime = self.getBedSecRelTemp(B_S)
                self._estS += bedHeatupTime
                debug("_estSec += {} bed heatup time from {} to {}"
                      "".format(bedHeatupTime, oldBS, B_S))
                self.setBedTemperature(B_S)
            else:
                # TODO: see if self.getBedTemperature differs from the
                # last bed temp command's S.
                pass
        elif f == "M92":
            # Set Axis Steps-per-unit
            # such as {'G': '92', 'E': '0'}
            pass
        elif f in ["G0", "G1", "G92"]:
            # such as:
            # - {'G': '1', 'X': '50', 'Y': '1.5', 'Z': '0.22',
            #    'F': '9000'}
            # - {'G': '1', 'X': '110', 'E': '45', 'F': '500.0'}
            # - {'G': '1', 'Y': '0.0', 'F': '250.0'}
            # Caveats:
            # - "Marlin 2.0 introduces an option to maintain a
            #   separate default feedrate for G0"
            #   -<https://marlinfw.org/docs/gcode/G000-G001.html>
            # - "Coordinates are given in millimeters by default. Units
            #   may be set to inches by G20."
            #   -<https://marlinfw.org/docs/gcode/G000-G001.html>
            oldPos = self.getToolPos()
            newPos = self.getToolPos()
            newPos = [meta.get('X'), meta.get('Y'), meta.get('Z')]
            # ^ Cast to float before using (See the two loops below).
            deltas = [0.0, 0.0, 0.0]
            moveAny = False
            if self.emuState['position_mode'] == 'relative':
                for i in range(len(newPos)):
                    if newPos[i] is None:
                        newPos[i] = 0.0
                    else:
                        newPos[i] = float(newPos[i])
                        moveAny = True
                    deltas[i] = abs(newPos[i])
            else:
                for i in range(len(newPos)):
                    if newPos[i] is None:
                        newPos[i] = oldPos[i]
                    else:
                        moveAny = True
                        newPos[i] = float(newPos[i])
                    deltas[i] = abs(newPos[i]-oldPos[i])
            distance = math.sqrt(
                deltas[0]**2 + deltas[1]**2 + deltas[2]**2
            )
            # elif f == "G0":
            # such as:
            # - {'G': '0', 'F': '4200', 'X': '103.931', 'Y': '57.516',
            #    'Z': '0.32'}
            # - {'G': '0', 'F': '4200', 'X': '103.451', 'Y': '57.996'}
            # - {'G': '0', 'X': '103.251', 'Y': '57.416'}

            F = meta.get('F')  # mm/minute
            tool = self.emuState['tool']
            if F is None:
                oldF = self.emuState['tools'][tool].get('feedrate')
                if oldF is not None:
                    F = oldF
                else:
                    echo0("WARNING: The feedrate is unknown at {}."
                          "".format(cmd_meta))
                return
            else:
                F = float(F)
            feedPerSec = F / 60.0

            if moveAny:
                travelTime = distance / feedPerSec
                self._estS += travelTime
                if travelTime > 6:
                    debug("_estSec += {} travel time ({} / {})"
                          "".format(travelTime, distance, feedPerSec))
                    debug("  oldPos: {}".format(oldPos))
                    debug("  newPos: {}".format(newPos))
                    debug("  deltas: {}".format(deltas))
                    debug("  self.emuState['position_mode']: {}"
                          "".format(self.emuState['position_mode']))
                self.emuState['position'] = newPos
                self.emuState['tools'][tool]['feedrate'] = F
                # ^ A servo feedrate is set below if not returning.
                return
            servo = self.emuState['extruder']
            self.emuState['servos'][servo]['feedrate'] = F

            eDiff = 0.0
            E = meta.get('E')
            if E is not None:
                E = float(E)
                eDiff = abs(self.getEPos() - E)
                feedTime = eDiff / feedPerSec
                self._estS += feedTime
                debug("_estSec += {} feed time ({} / {})"
                      "".format(feedTime, eDiff, feedPerSec))
                self.setEPos(E)
            else:
                echo0('WARNING: Estimating "{}" is not possible since'
                      ' there was no X, Y, Z, nor E movement.'
                      ''.format(cmd_meta))

        elif f == "M107":
            # Fan off
            # such as {'M': '107'}
            pass
        elif f == "M106":
            # Set fan speed
            # such as {'M': '106', 'S': '255'}
            pass
        elif f == "G90":
            self.emuState['position_mode'] = 'absolute'
        elif f == "G91":
            self.emuState['position_mode'] = 'relative'
        elif f == "M140":
            # Set bed temp BUT don't wait.
            pass
        elif f == "M117":
            # Show a message.
            pass
        elif f == "M84":
            # Disable motors.
            pass
        else:
            echo0("WARNING: The command isn't emulated for estimates"
                  " or other uses: {}"
                  "".format(cmd_meta))
        # Additional relevant commands:
        # M209: Set auto retract
        # M141: Set chamber temperature

    def _generateTower(self):
        getV = self.getVar
        getS = self.getStat
        setS = self.setStat
        modS = self._changeStat
        lvl = 0

        def getL():
            return getS("level")

        def modL(delta, line_number):
            global lvl
            self._changeStat("level", delta, line_number)
            lvl = getL()

        def setL(value, line_number):
            global lvl
            setS("level", value, line_number)
            lvl = value

        cn = self.code_numbers
        heights = self.heights
        if self.heights is None:
            raise RuntimeError("Heights were not calculated. You must"
                               " run checkSettings before"
                               " generateTower.")
        echoP = self._echo_progress
        self._estS = 0.0
        start_temperature_found = False
        stw_cmd = self.commands['set temperature and wait']
        stw_param0 = self.params['set temperature and wait'][0]
        tmprs = self.temperatures

        self.clearStats()
        setS("height", Decimal("0.00"), -1)

        setL(0, -1)
        setS("new_line_count", 0, -1)
        setS("stop_building", False, -1)
        last_height = None
        something_printed = False  # Tells the program whether "actual"
        #                          # printing ever occurred yet.
        deltas = {}  # difference from previous (only for keys in
        #            # current line)
        given_values = None  # ONLY values from the current line
        previous_values = {}
        previous_dst_line = None
        previous_src_line = None
        line_number = -1
        try:
            ok, err = self.checkSettings()
            if not ok:
                self.enableUI(True)
                return False
            else:
                print('* saving "{}"...'
                      ''.format(GCodeFollower._settingsPath))
                self.saveSettings()
        except Exception as e:
            self.echo(str(e))
            raise e
        tmp_path = getV("template_gcode_path") + ".tmp"
        dst_path = (self.getRangeString("temperature") + "_"
                    + getV("template_gcode_path"))
        # os.path.splitext(getV("template_gcode_path"))[0]
        # + "_" + range + ".gcode"
        dant_shown = {}  # debug accessing new temperature
        dnlh_shown = {}  # debug next level height
        dnnh_shown = {}  # debug no next height
        dwfnh_shown = {}  # debug wait for height before changing level
        bytes_total = os.path.getsize(getV("template_gcode_path"))
        bytes_count = 0
        setS("progress", "0%", -1)
        prev_line_len = 0
        template_gcode_path = getV("template_gcode_path")
        print("* reading \"{}\"...".format(template_gcode_path))
        with open(template_gcode_path) as ins:
            with open(tmp_path, 'w') as outs:
                line_number = 0
                for original_line in ins:
                    bytes_count += prev_line_len
                    setS(
                        "progress",
                        (str(round(bytes_count/round(bytes_total/100)))
                         + "%"),
                        line_number
                    )
                    prev_line_len = len(original_line)
                    next_l_h = None  # next level's height
                    next_l_t = None  # next level's temperature
                    if getS("level") + 1 < len(heights):
                        next_l_h = heights[getS("level") + 1]
                        if self._verbose:
                            l_str = str(getS("level") + 1)
                            if dnlh_shown.get(l_str) is not True:
                                echoP("* INFO: The next height (for"
                                      " level {}) is"
                                      " {}.".format(l_str, next_l_h))
                                dnlh_shown[l_str] = True
                    else:
                        if self._verbose:
                            l_str = str(getS("level") + 1)
                            if dnnh_shown.get(l_str) is not True:
                                echoP("* INFO: There is no height for"
                                      " the next level"
                                      " ({}).".format(l_str))
                                dnnh_shown[l_str] = True
                    if getS("level") + 1 < len(tmprs):
                        next_l_t = tmprs[getS("level") + 1]
                        if self._verbose:
                            l_str = str(getS("level") + 1)
                            if dant_shown.get(l_str) is not True:
                                echoP("* INFO: A temperature for level"
                                      " {} is being"
                                      " accessed.".format(l_str))
                                dant_shown[l_str] = True
                    if given_values is not None:
                        for k, v in given_values.items():
                            previous_values[k] = v
                    given_values = {}  # This is ONLY for the current
                    #                  # command. Other known (past)
                    #                  # values are in stats.
                    line_number += 1
                    line = original_line.rstrip()
                    double_blank = False
                    if previous_dst_line is not None:
                        if ((len(previous_dst_line) == 0) and
                                (len(line) == 0)):
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
                                continue  # no value; just letter param
                            elif len(cmd_meta[i]) > 2:
                                echoP("Line {}: WARNING: extra param"
                                      " (this should never happen) in"
                                      " '{}'".format(line_number, line))
                            try:
                                setS(cmd_meta[i][0],
                                     Decimal(cmd_meta[i][1]),
                                     line_number)
                                given_values[cmd_meta[i][0]] = Decimal(
                                    cmd_meta[i][1]
                                )
                            except decimal.InvalidOperation as e:
                                if type(e) == decimal.ConversionSyntax:
                                    echoP(
                                        "Line {}: ERROR: Bad"
                                        " conversion syntax:"
                                        " '{}'".format(line_number,
                                                       cmd_meta[i][1])
                                    )
                                else:
                                    echoP(
                                        "Line {}: ERROR: Bad Decimal"
                                        " (InvalidOperation):"
                                        " '{}'".format(line_number,
                                                       cmd_meta[i][1])
                                    )
                                echoP("  cmd_meta: {}".format(cmd_meta))
                        for k, v in given_values.items():
                            previous_v = previous_values.get(k)
                            if previous_v is not None:
                                deltas[k] = v - previous_v
                        if getS("stop_building"):
                            # echoP(str(cmd_meta))
                            if (len(cmd_meta) == 2):
                                if (cmd_meta[1][0] == "F"):
                                    # It ONLY has F param, so it is not
                                    # end gcode.
                                    would_move_for_build = True
                                # elif given_values.get("F")
                                # is not None:
                                #     echoP("Line {}: ERROR: Keeping"
                                #           " unnecessary"
                                #           " F in:"
                                #           " {}".format(line_number,
                                #                        cmd_meta))
                            # else:
                            #     echoP("Line {}: ERROR: Keeping"
                            #           " necessary F"
                            #           " in: {}".format(line_number,
                            #                            cmd_meta))
                    if cmd_meta is None:
                        if ((not getS("stop_building")) or
                                (not double_blank)):
                            self.addSec(original_line)
                            outs.write(
                                (original_line.rstrip("\n").rstrip("\r")
                                 + "\n")
                            )
                            previous_dst_line = line
                        continue
                    # cmdStr ''.join(cmd_meta[0])  # such as "M117"
                    try:
                        code_number = int(cmd_meta[0][1])
                    except ValueError as ex:
                        print("Error in cmd_meta: {}".format(cmd_meta))
                        raise ex

                    if cmd_meta[0][0] == "G":
                        if given_values.get('E') is not None:
                            would_extrude = True
                            # if (comment is not None) or
                            # (GCodeFollower._end_retraction_flag in
                            # comment):
                            if GCodeFollower._end_retraction_flag in line:
                                if Decimal(given_values.get('E')) < 0:
                                    # NOTE: Otherwise includes
                                    # retractions in end gcode
                                    # (negative # after E)
                                    would_extrude = False
                            # Otherwise, discard BOTH negative and
                            # positive filament feeding after tower is
                            # finished.
                        # NOTE: homing is still allowed (values without
                        # params are not in given_values).
                        if given_values.get('X') is not None:
                            if (given_values.get('Y') is not None):
                                would_move_for_build = True
                            elif (given_values.get('Z') is not None):
                                would_move_for_build = True
                            elif given_values.get('X') != Decimal("0.00"):
                                would_move_for_build = True
                            else:
                                # it is homing X, so it isn't building
                                pass
                        # elif given_values.get('Y') is not None:
                            # # NOTE: This can't help but eliminate
                            # # moving the (Prusa-style) bed forward
                            # # for easy removal in end gcode.
                            # would_move_for_build = True
                        delta_z = deltas.get("Z")
                        if (delta_z is not None):
                            if (abs(delta_z) <= getV("max_z_build_movement")):
                                # This is too small to be a necessary
                                # move (it is probably moving to the
                                # next layer)
                                would_move_for_build = True
                            elif (getS("stop_building") and
                                    not would_move_for_build):
                                echoP("Line {}: Moving from {} (from"
                                      " line {}) to {} would"
                                      " move a lot {}"
                                      " (keeping '{}').".format(
                                        line_number,
                                        getS("Z"),
                                        self.getStatLine("Z"),
                                        given_values.get("Z"),
                                        abs(deltas.get("Z")),
                                        line
                                      ))
                        elif (getS("stop_building") and
                                (getS("Z") is None)):
                            echoP("Line {}: ERROR: No recorded z delta"
                                  "but build is"
                                  " over.".format(line_number))

                        would_build = (would_extrude or
                                       would_move_for_build)

                        if (code_number == 1) or (code_number == 0):
                            if getS("stop_building"):
                                if would_build:
                                    # NOTE: this removes any retraction
                                    # (negative value after 'E' param)
                                    # in stop gcode.
                                    continue
                                else:
                                    echoP(
                                        "Line {}: WARNING: Allowing"
                                        " '{}' after stop (z"
                                        " delta {})".format(
                                            line_number,
                                            line,
                                            deltas.get("Z")
                                        )
                                    )
                            self.addSec(line)
                            outs.write(line + "\n")
                            previous_dst_line = line  # It's just a
                            #                         # movement, so
                            #                         # don't edit it.
                            #                         # Insert
                            #                         # temperature
                            #                         # after it if it
                            #                         # is a new level
                            #                         # (below).
                            given_z = given_values.get("Z")
                            z_index = part_indices.get("Z")
                            if z_index is None:
                                continue
                            if len(cmd_meta[z_index]) == 1:
                                setS("height", Decimal("0.00"),
                                     line_number)
                                last_height = getS("height")
                                setL(0, line_number)
                                # echoP("Line {}: Missing value after"
                                #       " '{}'".format(
                                #     line_number,
                                #     cmd_meta[1][0])
                                # )
                                # continue
                                # if len(cmd_meta[1]) == 1:  # already
                                #                            # checked
                                echoP("Line {}: INFO: Homing was"
                                      " detected so"
                                      " level & height were changed"
                                      " to 0...")
                                continue
                            else:
                                # NOTE: already determined to have "Z"
                                #   (See `continue` further up.)
                                # NOTE: len(cmd_meta[z_index]) cannot be
                                #   0 since it is obtained using split.
                                setS("height",
                                     Decimal(cmd_meta[z_index][1]),
                                     line_number)
                                # if self._verbose:
                                #     echoP(
                                #         "* INFO: Z is now {} due to"
                                #         " {}".format(
                                #             cmd_meta[z_index][1],
                                #             cmd_meta
                                #         )
                                #     )
                                last_height = getS("height")
                                lvl = getS("level")
                                h = getS("height")
                                if next_l_h is None:
                                    if not getS("stop_building"):
                                        setS("stop_building", True,
                                             line_number)
                                        estHr, estMin, estLeft = (
                                            getHMSFromS(self._estS)
                                        )
                                        self._estS
                                        print("ESTIMATE: {}s"
                                              "".format(self._estS))
                                        self._extrudeS = self._estS
                                        print("ESTIMATE: {}h{}m{}s"
                                              "".format(estHr,
                                                        estMin,
                                                        estLeft))
                                        # self.addSec(original_line)
                                        outs.write(
                                            (self._stop_building_msg
                                             + "\n")
                                        )
                                        if next_l_t is not None:
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
                                                    getL(),
                                                    h,
                                                    tmprs[getL()]
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
                                                    getL(),
                                                    h,
                                                    tmprs[getL()]
                                                )
                                            )
                                        echoP("  (Future extrusion"
                                              " will be"
                                              " suppressed)")

                                        continue
                                elif h >= next_l_h:
                                    # This code can still be reached if
                                    # not would_extrude:
                                    if next_l_t is None:
                                        if not getS("stop_building"):
                                            setS("stop_building", True,
                                                 line_number)
                                            print("ESTIMATE: {}s"
                                                  "".format(self._estS))
                                            self._extrudeS = (
                                                self._estS
                                            )
                                            estHr, estMin, estLeft = (
                                                getHMSFromS(self._estS)
                                            )
                                            print("ESTIMATE: {}h{}m{}s"
                                                  "".format(estHr,
                                                            estMin,
                                                            estLeft))
                                            # self.addSec(original_line)
                                            outs.write(
                                                (self._stop_building_msg
                                                 + "\n")
                                            )
                                            echoP(
                                                "* Line {}: The tower"
                                                " will be truncated"
                                                " since there is no new"
                                                " temperature available"
                                                " (no level beyond {})"
                                                " at {}".format(
                                                    line_number,
                                                    getL(),
                                                    h
                                                )
                                            )
                                            echoP("  (Future extrusion"
                                                  " will be"
                                                  " suppressed)")
                                        continue
                                    if not start_temperature_found:
                                        # setL("level", 0, line_number)
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
                                                h,
                                                stw_cmd,
                                                getL()
                                            )
                                        )
                                    elif ((len(heights) > lvl + 2) and
                                            (h > heights[lvl + 2])):
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
                                                h,
                                            )
                                        )
                                    else:
                                        # if lvl + 1 < len(tmprs):
                                        # already checked (see this
                                        # clause and the previous `if`
                                        # clause).
                                        modL(1, line_number)
                                        if self._verbose:
                                            echoP(
                                                "Line {}: INFO: "
                                                " **temperature** at"
                                                " height {} will"
                                                " become {} (for"
                                                " level {})".format(
                                                    line_number,
                                                    h,
                                                    tmprs[getL()],
                                                    getL()
                                                )
                                            )
                                        new_line = "{} {}{:.2f}".format(
                                            stw_cmd,
                                            stw_param0,
                                            tmprs[getL()]
                                        )
                                        # echoP(new_line)
                                        self.addSec(new_line)
                                        outs.write(new_line + "\n")
                                        previous_dst_line = new_line
                                        modS("new_line_count", 1,
                                             line_number)
                                        echoP(
                                            "Line {}: Inserted:"
                                            " {}".format(
                                                line_number,
                                                new_line
                                            )
                                        )
                                        echoP("- after"
                                              " '{}'".format(line))
                                        echoP("- new line #: {}".format(
                                            (line_number
                                             + getS("new_line_count"))
                                        ))
                                else:
                                    if self._verbose:
                                        l_str = str(getL() + 1)
                                        if dwfnh_shown.get(l_str) is not True:
                                            # echoP(
                                            #     "* INFO: The next"
                                            #     " height (for level"
                                            #     " {}) of {} has not"
                                            #     " yet been reached"
                                            #     " at {}.".format(
                                            #         l_str,
                                            #         next_l_h,
                                            #         h
                                            #     )
                                            # )
                                            dwfnh_shown[l_str] = True
#
                        else:  # some other G code
                            if getS("stop_building"):
                                if would_build:
                                    continue
                                else:
                                    if code_number == 91:
                                        echoP(
                                            "Line {}: INFO:"
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
                            self.addSec(line)
                            outs.write(line + "\n")
                            previous_dst_line = line

                    elif cmd_meta[0][0] == "M":
                        if line[0:5] == stw_cmd + " ":
                            # ^self.commands['set temperature and wait']
                            #  (usually M109)
                            # (extruder temperature)
                            # d for decimal integer format (with no
                            # decimals):
                            new_line = "{} {}{:d}".format(stw_cmd,
                                                          stw_param0,
                                                          tmprs[getL()])
                            if start_temperature_found:
                                echoP("Line {}: Extra temperature"
                                      " command at {}:"
                                      " {}".format(line_number,
                                                   getS("height"), line)
                                      + "\n- changed to: " + new_line
                                      + "...")
                            else:
                                echoP(
                                    "Line {}: Initial temperature"
                                    " command at {}:"
                                    " {}".format(line_number,
                                                 getS("height"),
                                                 line)
                                    + "\n- changed to: " + new_line
                                    + "..."
                                )
                            self.addSec(new_line)
                            outs.write(new_line + "\n")
                            previous_dst_line = line
                            # if getL() == 0:
                            #     if getL() + 1 < len(tmprs):
                            #         modL(1, line_number)
                            #         # echoP("Level {} is "
                            #         #       "next.".format(
                            #         #         getL())
                            #         #       )
                            start_temperature_found = True
                        elif (getS("stop_building") and
                                (code_number == cn['set fan speed'])):
                            # Do not keep the fan speed line.
                            continue
                        else:
                            self.addSec(line)
                            outs.write(line + "\n")
                            previous_dst_line = line
                    else:
                        self.addSec(line)
                        outs.write(line + "\n")
                        previous_dst_line = line
                        pass
                        # echoP("Unknown command:"
                        #       " {}".format(cmd_meta[0][0]))
        shutil.move(tmp_path, dst_path)
        etaTimeStr = getHMSMessageFromS(self._estS)
        extTimeStr = getHMSMessageFromS(self._extrudeS)
        self.echo("100% (done; saved {};"
                  " estimated print time: {} ({} extrusion))"
                  "".format(dst_path, etaTimeStr, extTimeStr))
        bytes_count = bytes_total
        setS("progress", "100%", line_number)

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
