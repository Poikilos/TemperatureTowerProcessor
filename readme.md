# Python GUI for Variable-Height Configurable Temperature Tower
https://www.thingiverse.com/thing:4068975 by Poikilos

Sourcecode: https://github.com/poikilos/TemperatureTowerProcessor

To test different retraction lengths you can try: https://github.com/poikilos/RetractionTowerProcessor

You can calibrate further using my related projects:
- [LinearAdvanceTowerGenerator](https://github.com/poikilos/LinearAdvanceTowerGenerator)
- [RetractionTowerProcessor](https://github.com/poikilos/RetractionTowerProcessor)


## Configurable Compact Temperature Calibration Tower
based on "Smart compact temperature calibration tower"

### Differences in Poikilos' remix
- Make a tower without numbers so that gcode can be processed in one step using my TemperatureTowerProcessor GUI.
- Make the base larger and thicker as a heat shield for soft materials requiring cooling (This requires infill not solid so trapped air is in the insulator pad).


## Requirements
- When installing Python on Windows, ensure that the **add to PATH** option is checked during install. Then open set_temperatures.pyw with "C:\Program Files (x86)\Python 3\pythonw" or whatever your "pythonw.exe" is (some versions install to C:\Python3*).


## How to Use
- If you have Windows, install and configure Python 3 according to the "Requirements" above.
- You MUST slice the file as "tower.gcode" (or manually enter the path into the "Tower Configuration" Window).
- Run TowerConfiguration.pyw (on Windows, double-click the file and choose pythonw as described in "Requirements" above).
- Type a start and end temperature for the tower. There can be no more than 10 steps 5 degrees Celcius apart--for example, 180-225. However, most of the time your filament can only handle a smaller range such as 180-210 for most PLA, or 190-210 for better adhesion.
- Click the "Generate" button.
- A new gcode file should appear, automatically named containing the temperature range you specified. 3D print that file.
  - You will usually get an "INFO" message saying that only a certain number of levels will be present. That is expected. The top of the tower will have a hole, but that is normal. The program doesn't manipulate the gcode, other than changing and inserting temperatures and removing commands past the level you need.


## Custom Tower
- If you use the blend file, then after exporting you must import again, go to edit mode, click Mesh, Cleanup "merge by distance" then export again.
- Whenever you change the tower or change to a different tower, you must change settings.json to match it. To get the default settings.json file, run TowerConfiguration.pyw once (you do not have to push generate), or run TowerConfigurationCLI.py with no parameters.


## Post-Processing
- After printing, I recommend writing the temperatures and filament type and brand on your tower using permanent marker. You may want to write each temperature on the flat side of each level, and the bottom has plenty of room to write other information.


## Authors & License
- Code:
  - GPLv3
  - Author: Poikilos
- Smart compact temperature calibration tower:
  - [Creative Commons Attribution-ShareAlike 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/) (CC BY-SA 3.0)
  - by gaaZolee and Poikilos
  - based on [Smart compact temperature calibration tower](https://www.thingiverse.com/thing:2729076) by [gaaZolee](https://www.thingiverse.com/gaaZolee) December 24, 2017
- ConfigurableTempTower (unused):
  - [Creative Commons Attribution 3.0 Unported](http://creativecommons.org/licenses/by/3.0/) (CC BY 3.0)
  - Authors: [Poikilos](https://www.thingiverse.com/poikilos), [3dMakernoob](https://www.thingiverse.com/3dMakernoob), [bjorntm](https://www.thingiverse.com/bjorntm)
  - based on [Temperature Tower Generic](http://www.thingiverse.com/thing:2092820) by [3dMakernoob](https://www.thingiverse.com/3dMakernoob)
- Everything else:
  - [Creative Commons Attribution-ShareAlike 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/) (CC BY-SA 3.0)
  - Authors: [Poikilos](https://www.thingiverse.com/poikilos)


## History

### (unused)
ConfigurableTempTower
- Based on 3dMakernoob's "Temperature Tower Generic":
  > http://www.thingiverse.com/thing:2092820
  > Temperature Tower Generic by 3dMakernoob is licensed under the Creative Commons - Attribution license.
  > http://creativecommons.org/licenses/by/3.0/
  >
  > # Summary
  >
  > Update: Added a Version 2 in order to strengthen the fine detail extended tower as it might fail depending on the filament type
  >
  > This is a Remix of the Ultimaker tower which i modified slightly to also include bridging, stringing and also fine detail. No gcode supplied. . . .
  - based on [Ultimaker 2 temperature torture calibration test](http://www.thingiverse.com/thing:696093)
#### Differences from 3dMakernoob's Version
- The mesh is now cleaner, and has separated parts including separate end cap for use with Blender's array modifier.
  - Position and count of vertices at top and bottom now match.
- I created a Python GUI to configure the tower.
  - I also included an old version without a GUI (TowerConfigurationCLI.py) in case you need to automate the process or run it remotely. The CLI version now uses the same backend module, so it will continue to have the same results as the GUI version going forward.


## Developer Notes
### Reference Material
- See <https://jgmakerwiki.com/start-and-end-gcode>
- See <http://www.cnctrainingcentre.com/tips-tricks/g28-verses-g53/>
- See <https://reprap.org/wiki/G-code#G0_.26_G1:_Move>
