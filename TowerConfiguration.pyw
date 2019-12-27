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

import decimal
from decimal import Decimal
import threading
from gcodefollower import GCodeFollower
import tkinter as tk
from tkinter import ttk

gcode = None


class ConfigurationFrame(ttk.Frame):
    def __init__(self, parent):
        global gcode
        gcode = GCodeFollower(echo_callback=self.echo,
                              enable_ui_callback=self.enableUI)
        self.generateTimer = None
        self.templateGCodePath = tk.StringVar()
        self.temperatureVs = [tk.StringVar(), tk.StringVar()]
        self.statusV = tk.StringVar()
        ttk.Frame.__init__(self, parent)
        self.pack(fill=tk.BOTH, expand=True)
        row = 0
        ttk.Label(self, text="Template G-Code Path:").grid(column=0, row=row, sticky=tk.E)
        ttk.Entry(self, width=35, textvariable=self.templateGCodePath).grid(column=1, columnspan=2, row=row, sticky=tk.E)
        row += 1
        ttk.Label(self, text="Start Temperature (C):").grid(column=0, row=row, sticky=tk.E)
        ttk.Entry(self, width=35, textvariable=self.temperatureVs[0]).grid(column=1, columnspan=2, row=row, sticky=tk.E)
        row += 1
        ttk.Label(self, text="Stop Temperature (C)").grid(column=0, row=row, sticky=tk.E)
        ttk.Entry(self, width=35, textvariable=self.temperatureVs[1]).grid(column=1, columnspan=2, row=row, sticky=tk.E)
        row += 1
        ttk.Label(self, text="").grid(column=0, row=row, sticky=tk.E)
        # See Mitch McMabers' answer
        # at https://stackoverflow.com/questions/4011354/create-resizable-multiline-tkinter-ttk-labels-with-word-wrap
        # ttk.Label(self, width=25, wraplength=72, anchor=tk.W, justify=tk.LEFT, textvariable=self.statusV, state="readonly").grid(column=0, columnspan=3, row=row, sticky=tk.E)
        ttk.Label(self, width=72, wraplength=600, anchor=tk.W, textvariable=self.statusV, state="readonly").grid(column=0, columnspan=3, row=row, sticky=tk.W)
        row += 1
        self.generateButton = ttk.Button(self, text="Generate", command=self.generateTower)
        self.generateButton.grid(column=1, row=row, sticky=tk.E)
        ttk.Button(self, text="Exit", command=root.destroy).grid(column=2, row=row, sticky=tk.E)
        for child in self.winfo_children():
            child.grid_configure(padx=6, pady=3)
        # (Urban & Murach, 2016, p. 515)

        try:
            gcode.checkSettings()
            self.pullSettings()
            # Even if it returns True, don't save settings yet since
            # gcode.generateTowerThread will do that.
        except ValueError:
            self.echo("The temperatures must be integers.")
        except FileNotFoundError:
            # self.echo("")
            # checkSettings already called echo_callback in this case.
            pass

    def pushSettings(self):
        gcode.setVar("min_temperature", self.temperatureVs[0].get())
        gcode.setVar("max_temperature", self.temperatureVs[1].get())
        gcode.setVar("template_gcode_path", self.templateGCodePath.get())

    def pullSettings(self):
        self.temperatureVs[0].set(gcode.getVar("min_temperature"))
        self.temperatureVs[1].set(gcode.getVar("max_temperature"))
        self.templateGCodePath.set(gcode.getVar("template_gcode_path"))

    def echo(self, msg):
        print(msg)
        self.statusV.set(msg)

    def enableUI(self, enable):
        if enable:
            self.generateButton.config(state=tk.NORMAL)
        else:
            self.generateButton.config(state=tk.DISABLED)

    def generateTower(self):
        self.pushSettings()
        gcode.enableUI(False)  # generateTowerThread will call
                               # enable_ui_callback(true).
        # Start a thread, so that events related to enableUI(False) can
        # occur before processing.
        self.generateTimer = threading.Timer(0.01, gcode.generateTowerThread)
        self.generateTimer.start()


def main():
    global root
    root = tk.Tk()
    root.title("Tower Configuration by Poikilos")
    ConfigurationFrame(root)
    root.mainloop()
    # (Urban & Murach, 2016, p. 515)

if __name__ == "__main__":
    main()

# References
# Urban, M., & Murach, J. (2016). Murach’s Python Programming
#     [VitalSource Bookshelf]. Retrieved from
#     https://bookshelf.vitalsource.com/#/books/9781943872152
