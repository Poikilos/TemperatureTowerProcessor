#!/usr/bin/env python3

# This program changes and inserts temperatures into gcode that builds a
# temperature tower.
# Copyright (C) 2019  Jake Gustafson

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
import os
import decimal
from decimal import Decimal
import copy
import shutil

towerName = "the STL from Python GUI for Configurable Temperature Tower"
downloadPageURL = "https://www.thingiverse.com/thing:4068975"

def usage():
    print("  Examples:")
    print("  " + sys.argv[0] + " 190 210")
    # print(sys.argv[0] + " tower.gcode")
    print("  " + sys.argv[0] + " tower.gcode 190 210")
    print("")

end_retraction_flag = "retract filament slightly"
# Usage:
# - You must put "retract filament slightly" in the comment on the same
#   line as any retractions in end gcode that you don't want stripped
#   off when the top of the tower is truncated.
# find these OR the next highest (will differ based on layer height and
# Slic3r Z offset setting; which may also be negative, but next highest
# is close enough)
special_heights = [Decimal("16.201")]  # level[index] is this height
level_height = Decimal("13.500")
# heights = [0, 16.4, 30.16, 43.6, 57.04]
heights = []  # ALWAYS must start with level 0 at 0.00
level_count = 10
total_height = Decimal("0.000")
for i in range(level_count):
    this_level_height = level_height
    if (special_heights is not None) and (i < len(special_heights)):
        if special_heights[i] is not None:
            this_level_height = special_heights[i]
    heights.append(total_height)
    total_height += this_level_height
total_height = None
level = 0
# temperature_range = [240, 255]
temperature_range = [190, 210]  # first one is at 0 on Z axis.
# NOTE: [Hatchbox PLA](https://www.amazon.com/gp/product/B00J0GMMP6)
# has the temperature 180-210, but 180 underextrudes unusably.
temperatures = []
temperature_step = 5
max_z_build_movement = Decimal("1.20")  # maximum distance that counts as building

# G-Code reference:
# - Marlin (or Sprinter): http://marlinfw.org/docs/gcode/G000-G001.html

commands = {}
params = {}

# commands with known params:
commands['move'] = 'G1'  # can also extrude
commands['set temperature and wait'] = 'M109'
commands['set fan speed'] = 'M106'
commands['set position'] = 'G92'
commands['fan off'] = 'M107'
# commands with no known params:
commands['Reset selected workspace to 0, 0, 0'] = 'G92.1'  # http://marlinfw.org/docs/gcode/G092.html

# params:
params['move'] = ['X', 'Y', 'Z', 'F', 'E']  # can also extrude
params['set temperature and wait'] = ['S']
params['set fan speed'] = ['S']
params['set position'] = ['E', 'X', 'Y', 'Z']
params['fan off'] = ['P']
param_names = {}
param_names["E"] = "extrude (mm)"
param_names["F"] = "speed (mm/minute)"
param_names["P"] = "index"  # such as fan number (default is 0)

code_numbers = {}
for k, v in commands.items():
    code_numbers[k] = Decimal(v[1:])


# E extrudes that many mm of filament (relative of course)
stw_cmd = commands['set temperature and wait']
stw_param0 = params['set temperature and wait'][0]
start_temperature_found = False
l = 0
# for height in heights:
height = 0
desired_temperatures = []

max_temperature = None  # This is set automatically according to height:
temperature = temperature_range[0]
while True:
    if l < len(heights):
        height = heights[l]
        # print("* adding level {} ({} C) at"
              # " {}mm".format(l, temperature, height))
        temperatures.append(temperature)
        max_temperature = temperature
    desired_temperatures.append(temperature)
    temperature += temperature_step
    if temperature > temperature_range[1]:
        temperature -= temperature_step
        break
    l += 1
temperature = None
print("")
print("level:       " + "".join(["{:<9}".format(i) for i in range(len(temperatures))]))
print("temperature: " + "".join(["{:<9}".format(t) for t in temperatures]))
print("height:     " + "".join(["{:>8.3f}mm".format(t) for t in heights]))
print("")
if max_temperature < temperature_range[1]:
    print("INFO: Only {} floors will be present since the"
          " number of desired temperatures is greater than the"
          " available {} floors in the model"
          " (counting by {} C).".format(len(temperatures), len(heights),
                                        temperature_step))
elif len(temperatures) < len(heights):
    print("INFO: Only {} floors will be present since the"
          " temperature range (counting by {}) has fewer steps than the"
          " {}-floor tower model.".format(len(temperatures),
                                          temperature_step,
                                          len(heights)))

src_path = None

default_path = "tower.gcode" # ConfigurableTempTower-10-story


if (len(sys.argv) == 2) or (len(sys.argv) == 4):
    src_path = sys.argv[1]
    print("* You set the tower path to '{}'...".format(src_path))
else:
    print("")
    src_path = default_path
    print("* checking for '{}'...".format(src_path))
    print("")
    # exit(1)

try:
    if len(sys.argv) == 4:
        temperature_range[0] = int(sys.argv[2])
        temperature_range[1] = int(sys.argv[3])
    elif len(sys.argv) == 3:
        temperature_range[0] = int(sys.argv[1])
        temperature_range[1] = int(sys.argv[2])
    else:
        raise ValueError("The command is not formatted correctly.")
except ValueError:
    print("")
    print("ERROR:")
    print("- You must specify the temperature range.")
    usage()
    exit(1)


if not os.path.isfile(src_path):
    print("")
    print("'{}' does not exist.".format(src_path))
    if src_path == default_path:
        print("You must first slice {}:".format(towerName))
        print("  " + downloadPageURL)

    print("")
    exit(1)

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


tmp_path = src_path + ".tmp"
dst_path = ("{}-{}_".format(temperature_range[0], max_temperature)
            + os.path.splitext(src_path)[0] + ".gcode")
new_line_count = 0
stop_building = False
last_height = None
something_printed = False  # Tells the program whether "actual" printing ever occurred yet.
previous_values = {}
deltas = {}  # difference from previous (only for keys in current line)
current_values = {}  # values known by current OR previous lines
current_values_lines = {}  # for respective current_values entry's line#
given_values = None  # ONLY values from the current line
previous_values = {}
previous_dst_line = None
previous_src_line = None

with open(src_path) as ins:
    with open(tmp_path, 'w') as outs:
        line_number = 0
        for original_line in ins:
            next_level_height = None
            next_level_temperature = None
            if level + 1 < len(heights):
                next_level_height = heights[level + 1]
            if level + 1 < len(temperatures):
                next_level_temperature = temperatures[level + 1]
            if given_values is not None:
                for k, v in given_values.items():
                    previous_values[k] = v
            given_values = {}  # This is ONLY for the current command.
                               # current_values are known values.
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
                        print("Line {}: WARNING: extra param (this should never happen) in '{}'".format(line_number, line))
                    try:
                        current_values[cmd_meta[i][0]] = Decimal(cmd_meta[i][1])
                        current_values_lines[cmd_meta[i][0]] = line_number
                        given_values[cmd_meta[i][0]] = Decimal(cmd_meta[i][1])
                    except decimal.InvalidOperation as e:
                        if type(e) == 'decimal.ConversionSyntax':
                            print("Line {}: ERROR: Bad conversion syntax: '{}'".format(line_number, cmd_meta[i][1]))
                        else:
                            print("Line {}: ERROR: Bad Decimal (InvalidOperation): '{}'".format(line_number, cmd_meta[i][1]))
                        print("  cmd_meta: {}".format(cmd_meta))
                for k, v in given_values.items():
                    previous_v = previous_values.get(k)
                    if previous_v is not None:
                        deltas[k] = v - previous_v
                if stop_building:
                    # print(str(cmd_meta))
                    if (len(cmd_meta) == 2):
                        if (cmd_meta[1][0] == "F"):
                            # It ONLY has F param, so it is not end gcode
                            would_move_for_build = True
                        # elif given_values.get("F") is not None:
                            # print("Line {}: ERROR: Keeping unnecessary"
                                  # " F in:"
                                  # " {}".format(line_number, cmd_meta))
                    # else:
                        # print("Line {}: ERROR: Keeping necessary F"
                        # " in: {}".format(line_number, cmd_meta))
            if cmd_meta is None:
                if (not stop_building) or (not double_blank):
                    outs.write(original_line.rstrip("\n").rstrip("\r") + "\n")
                    previous_dst_line = line
                continue
            code_number = int(cmd_meta[0][1])
            if cmd_meta[0][0] == "G":
                if given_values.get('E') is not None:
                    would_extrude = True
                    #if (comment is not None) or ("retract filament slightly" in comment):
                    if end_retraction_flag in line:
                        if Decimal(given_values.get('E')) < 0:
                            # NOTE: Otherwise includes retractions in end gcode
                            # (negative # after E)
                            would_extrude = False
                    # Otherwise, discard BOTH negative and positive
                    # filament feeding after tower is finished.
                # NOTE: homing is still allowed (values without params
                # are not in given_values).
                if given_values.get('X') is not None:
                    would_move_for_build = True
                # elif given_values.get('Y') is not None:
                    # # NOTE: This can't help but eliminate moving the
                    # # (Prusa-style) bed forward for easy removal in end
                    # # gcode.
                    # would_move_for_build = True
                delta_z = deltas.get("Z")
                if (delta_z is not None):
                    if (abs(delta_z) <= max_z_build_movement):
                        # This is too small to be a necessary move
                        # (it is probably moving to the next layer)
                        would_move_for_build = True
                    elif stop_building and not would_move_for_build:
                        print("Line {}: Moving from {} (from line {}) to {} would"
                              " move a lot {} (keeping '{}').".format(
                                line_number,
                                current_values.get("Z"),
                                current_values_lines.get("Z"),
                                given_values.get("Z"),
                                abs(deltas.get("Z")),
                                line
                              ))
                elif stop_building and (current_values.get("Z") is None):
                    print("Line {}: ERROR: No recorded z delta but build is over.".format(line_number))

                would_build = would_extrude or would_move_for_build

                if code_number == 1:
                    if stop_building:
                        if would_build:
                            # NOTE: this removes any retraction
                            # (negative value after 'E' param) in stop
                            # gcode.
                            continue
                        else:
                            print("Line {}: WARNING: Allowing '{}'"
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
                        height = Decimal(0.00)
                        last_height = height
                        level = 0
                        # print("Line {}: Missing value after '{}'".format(
                            # line_number,
                            # cmd_meta[1][0])
                        # )
                        # continue
                        # if len(cmd_meta[1]) == 1:  # already checked
                        print("Line {}: INFO: Homing was detected so"
                              " level & height were changed"
                              " to 0.")
                        continue
                    else:
                        # NOTE: already determined to have "Z"
                        #   (See `continue` further up.)
                        # NOTE: len(cmd_meta[z_index]) cannot be 0 since
                        #   it is obtained using split.
                        height = Decimal(cmd_meta[z_index][1])
                        last_height = height
                        if next_level_height is None:
                            if not stop_building:
                                stop_building = True
                                if next_level_temperature is not None:
                                    print("* Line {}: The tower ends"
                                          " (there is no level beyond"
                                          " {}) at {}"
                                          " before the temperature"
                                          " range, so there will be"
                                          " no temperature beyond {}"
                                          .format(
                                            line_number,
                                            level,
                                            height,
                                            temperatures[level]
                                          )
                                    )
                                else:
                                    print("* Line {}: The tower ends"
                                          " (there is no level beyond"
                                          " {}) at {} nor another"
                                          " level in the temperature"
                                          " range, so there will be"
                                          " no temperature beyond {}"
                                          .format(
                                            line_number,
                                            level,
                                            height,
                                            temperatures[level]
                                          )
                                    )
                                print("  (Future extrusion will"
                                      " be suppressed)")

                                continue
                        elif height >= next_level_height:
                            # This code can still be reached if not
                            # would_extrude:
                            if next_level_temperature is None:
                                if not stop_building:
                                    stop_building = True
                                    print("* Line {}: The tower will be"
                                          " truncated since there is no"
                                          " new temperature available"
                                          " (no level beyond {}) at"
                                          " {}".format(
                                            line_number,
                                            level,
                                            height
                                          )
                                    )
                                    print("  (Future extrusion will"
                                          " be suppressed)")
                                continue
                            if not start_temperature_found: # level == 0
                                print("Line {}: INFO: Splicing"
                                      " temperature at {} will be"
                                      " skipped since the old set temp"
                                      " and wait ({}) wasn't found yet"
                                      " (level is {}), so this is"
                                      " z move is presumably start"
                                      " gcode.".format(
                                        line_number,
                                        height,
                                        stw_cmd,
                                        level
                                      )
                                )
                            elif ((len(heights) > level + 2)
                                  and (height > heights[level + 2])):
                                print("Line {}: WARNING: Splicing"
                                      " temperature at height"
                                      " {} will be skipped since"
                                      " the height is greater than"
                                      " the next level after the one"
                                      " starting here (since this may"
                                      " be a wait or purge"
                                      " position)".format(
                                        line_number,
                                        height,
                                      )
                                )
                            else:
                                # if level + 1 < len(temperatures):
                                # already checked (see this clause and
                                # the previous if clause).
                                level += 1
                                # print("Line {}: INFO: "
                                          # " **temperature** at height"
                                          # " {} will become {}"
                                          # " (for level {})".format(
                                            # line_number,
                                            # height,
                                            # temperatures[level],
                                            # level
                                          # )
                                # )
                                new_line = "{} {}{:.2f}".format(
                                    stw_cmd,
                                    stw_param0,
                                    temperatures[level]
                                )
                                # print(new_line)
                                outs.write(new_line + "\n")
                                previous_dst_line = new_line
                                new_line_count += 1
                                print("Line {}: Inserted: {}".format(
                                    line_number,
                                    new_line
                                ))
                                print("- after '{}'".format(line))
                                print("- new line #: {}".format(
                                    line_number+new_line_count
                                ))

                else:  # some other G code
                    if stop_building:
                        if would_build:
                            continue
                        else:
                            if code_number == 91:
                                print("Line {}: INFO: Allowing '{}'"
                                      " after stop".format(
                                        line_number, line
                                      ))
                            else:
                                print("Line {}: WARNING: Allowing '{}'"
                                      " after stop".format(
                                        line_number, line
                                      ))
                    outs.write(line + "\n")
                    previous_dst_line = line

            elif cmd_meta[0][0] == "M":
                if line[0:5] == stw_cmd + " ":  # set temperature & wait
                    # (extruder temperature)
                    # d for decimal integer format (with no decimals):
                    new_line = "{} {}{:d}".format(stw_cmd, stw_param0,
                                                  temperatures[level])
                    if start_temperature_found:
                        print("Line {}: Extra temperature command at {}: {}".format(line_number, height, line))
                        print("- changed to: {}".format(new_line))
                    else:
                        print("Line {}: Initial temperature command at {}: {}".format(line_number, height, line))
                        print("- changed to: {}".format(new_line))
                    outs.write(new_line + "\n")
                    previous_dst_line = line
                    # if level == 0:
                        # if level + 1 < len(temperatures):
                            # level += 1
                            # # print("Level {} is next.".format(level))
                    start_temperature_found = True
                elif stop_building and (code_number == code_numbers['set fan speed']):
                    # Do not keep the fan speed line.
                    continue
                else:
                    outs.write(line + "\n")
                    previous_dst_line = line
            else:
                outs.write(line + "\n")
                previous_dst_line = line
                pass
                # print("Unknown command: {}".format(cmd_meta[0][0]))
shutil.move(tmp_path, dst_path)
print("* saved {}".format(dst_path))
# @G1 Z16.40
# +M104 S240
# @G1 Z30.16
# +M104 S245
# @G1 Z43.60
# +M104 S250
# @G1 Z57.04
# +M104 S255
