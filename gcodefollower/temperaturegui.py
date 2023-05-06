#!/usr/bin/env python3
'''
This program changes and inserts temperatures into gcode that builds a
temperature tower.
Copyright (C) 2019  Jake "Poikilos" Gustafson
'''

from __future__ import print_function
from __future__ import division
import os
import sys
import decimal
from decimal import Decimal
import threading
try:
    import Tkinter as tk
    import ttk
except ImportError as ex2:
    # python 3
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as ex3:
        print()
        print("ERROR: Tk is not present."
              " Try installing python-tk or python3-tk")
        print()
        print()
        sys.exit(1)

from gcodefollower import (
    GCodeFollower,
    GCodeFollowerArgParser,
    echo0,
    encVal,
    usage,
)

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

gcode = None
runParams = None


def echo1(msg):
    global runParams
    if not runParams.verbose:
        return
    echo0(msg)


class ConfigurationFrame(ttk.Frame):
    def __init__(self, parent):
        echo1("* initializing ConfigurationFrame...")
        global gcode
        gcode = GCodeFollower(echo_callback=self.echo,
                              enable_ui_callback=self.enableUI,
                              verbose=runParams.verbose)
        gcode.loadSettings()
        gcode.saveDocumentationOnce()
        self.generateTimer = None
        self.templateGCodePath = tk.StringVar()
        self.temperatureVs = [tk.StringVar(), tk.StringVar()]
        self.statusV = tk.StringVar()
        ttk.Frame.__init__(self, parent)
        self.pack(fill=tk.BOTH, expand=True)
        row = 0
        self.tgcLabel = ttk.Label(self, text="Template G-Code Path:")
        self.tgcLabel.grid(column=0, row=row, sticky=tk.E)
        self.tgcEntry = ttk.Entry(self, width=35,
                                  textvariable=self.templateGCodePath)
        self.tgcEntry.grid(column=1, columnspan=2, row=row, sticky=tk.E)
        row += 1
        self.minLabel = ttk.Label(self, text="Minimum Temperature (C):")
        self.minLabel.grid(column=0, row=row, sticky=tk.E)
        self.minEntry = ttk.Entry(self, width=35,
                                  textvariable=self.temperatureVs[0])
        self.minEntry.grid(column=1, columnspan=2, row=row, sticky=tk.E)
        row += 1
        self.maxLabel = ttk.Label(self, text="Maximum Temperature (C)")
        self.maxLabel.grid(column=0, row=row, sticky=tk.E)
        self.maxEntry = ttk.Entry(self, width=35,
                                  textvariable=self.temperatureVs[1])
        self.maxEntry.grid(column=1, columnspan=2, row=row, sticky=tk.E)
        row += 1
        ttk.Label(self, text="").grid(column=0, row=row, sticky=tk.E)
        # See Mitch McMabers' answer
        # at <https://stackoverflow.com/questions/4011354/\
        # create-resizable-multiline-tkinter-ttk-labels-with-word-wrap>
        # self.statusLabel = ttk.Label(self, width=25, wraplength=72,
        #                              anchor=tk.W, justify=tk.LEFT,
        #                              textvariable=self.statusV,
        #                              state="readonly")
        # self.statusLabel.grid(column=0, columnspan=3, row=row,
        #                       sticky=tk.E)
        self.statusLabel = ttk.Label(self, width=72, wraplength=600,
                                     anchor=tk.W,
                                     textvariable=self.statusV,
                                     state="readonly")
        self.statusLabel.grid(column=0, columnspan=3, row=row,
                              sticky=tk.W)
        row += 1
        self.generateButton = ttk.Button(self, text="Generate",
                                         command=self.generateTower)
        self.generateButton.grid(column=1, row=row, sticky=tk.E)
        self.exitButton = ttk.Button(self, text="Exit",
                                     command=root.destroy)
        self.exitButton.grid(column=2, row=row, sticky=tk.E)
        for child in self.winfo_children():
            child.grid_configure(padx=6, pady=3)
        # (Urban & Murach, 2016, p. 515)
        ok, err = self.checkSettingsAndShow()
        if err is not None:
            echo0("Error: {}".format(err))
        if not ok:
            echo0("^ Ignore settings errors above unless trying to"
                  " run non-interactively, because the error"
                  " occurred on startup.")

        self.pullSettings()  # Get the path even if temperature is bad.
        if not os.path.isfile(gcode._settingsPath):
            gcode.saveSettings()
        self.statusV.set("")

    def checkSettingsAndShow(self):
        '''

        Returns:
        a tuple (is_good, error_message). See also GCodeFollower's
        checkSettings documentation.
        '''
        msg = None
        try:
            echo1(
                "* template_gcode_path: {} in {}"
                "".format(
                    encVal(gcode.getVar('template_gcode_path')),
                    'checkSettingsAndShow'
                )
            )
            return gcode.checkSettings()
            # Even if it returns True, don't save settings yet since
            # gcode.generateTower will do that.
        except ValueError as ex:
            self.enableUI(True)
            msg = ("The temperatures must be integers or Generate"
                   " cannot proceed:")
            self.echo()
            self.echo("- {}".format(ex))
        except FileNotFoundError:
            self.enableUI(True)
            msg = ("* FileNotFoundError: checkSettings should have already"
                   "  called echo_callback above in this case.")
            # self.echo(msg)
            msg = None
            # ^ Ignore msg since echo_callback should already have run
        return False, msg

    def pushSettings(self):
        echo1("* setting ranged vars:")
        for i in range(2):
            gcode.setRangeVar("temperature", i,
                              self.temperatureVs[i].get())
        gcode.setVar("template_gcode_path",
                     self.templateGCodePath.get())

    def pullSettings(self):
        '''
        Keyword arguments:
        prevent_exceptions -- This is True by default so a bad config
            file doesn't prevent the GUI from appearing.
        '''
        for i in range(2):
            v = gcode.getRangeVar("temperature", i)
            if v is not None:
                self.temperatureVs[i].set(v)
        # print("got template_gcode_path: "
        #       + gcode.getVar("template_gcode_path"))
        self.templateGCodePath.set(gcode.getVar("template_gcode_path"))

    def echo(self, msg):
        if len(msg) > 0:
            print("STATUS: " + msg)
            self.statusV.set(msg)
        else:
            print(msg)

    def enableUI(self, enable):
        state = tk.DISABLED
        if enable:
            state = tk.NORMAL
        # self.generateButton['state'] = state
        self.generateButton.config(state=state)

    def generateTower(self):
        global gcode
        self.pushSettings()
        gcode.enableUI(False)
        # ^ generateTower MUST call enable_ui_callback(true) even if
        #   there is an error.

        # Start a thread, so that events related to enableUI(False) can
        # occur before processing.
        ok, err = self.checkSettingsAndShow()
        if ok:
            self.generateTimer = threading.Timer(0.01, self._generateTower)
            self.generateTimer.start()
        else:
            self.enableUI(True)
        if err is not None:
            self.echo(err)
        if gcode.error is not None:
            self.echo(gcode.error)
            gcode.error = None

    def _generateTower(self):
        try:
            echo0("Calling gcode.generateTower...")
            gcode.generateTower()
        except Exception as ex:
            self.echo(str(ex))
            raise ex
        echo0("Done")


def main():
    global root
    global runParams
    root = tk.Tk()
    root.title("Tower Configuration by Poikilos")

    runParams = GCodeFollowerArgParser()
    if runParams.help:
        gcode = GCodeFollower()  # Initialize the help system.
        usage()
        return 0
    frame = ConfigurationFrame(root)

    if runParams.template_gcode_path is not None:
        echo1("* template_gcode_path is set to {}"
              "".format(runParams.template_gcode_path))
        frame.templateGCodePath.set(runParams.template_gcode_path)

    if runParams.temperatures is not None:
        echo1("* temperatures is set to {}"
              "".format(runParams.temperatures))
        frame.temperatureVs[0].set(runParams.temperatures[0])
        frame.temperatureVs[1].set(runParams.temperatures[1])

    root.mainloop()
    # (Urban & Murach, 2016, p. 515)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# References
# Urban, M., & Murach, J. (2016). Murach's Python Programming
#     [VitalSource Bookshelf]. Retrieved from
#     https://bookshelf.vitalsource.com/#/books/9781943872152
