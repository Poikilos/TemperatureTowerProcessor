#!/usr/bin/env python
'''
If run as a script, this *permanently* resizes *all* stl files in the
*current working directory*!

This is only tested with PrusaSlicer in known GNU/Linux system paths.

Command-Line Interface (CLI) usage:
resize-all <scale>

Example:
cd directory_of_stl_files_to_change_PERMANENTLY
# To convert a 20.2 width to 25.5, use the result of (25.4+.1)/20.2
# as follows:
python resize-all.py 1.26237623752376

'''
import sys
import os
import shlex
import subprocess
import shutil


def echo0(*args):
    print(*args, file=sys.stderr)


SLICER = "/usr/bin/flatpak run --branch=stable --arch=x86_64 --command=entrypoint --file-forwarding com.prusa3d.PrusaSlicer"
paths = os.environ['PATH'].split(os.pathsep)
prusaslicer_paths = [os.path.join(path, "prusa-slicer") for path in paths]
slic3r_paths = [os.path.join(path, "slic3r") for path in paths]
try_paths = prusaslicer_paths + slic3r_paths

for try_path in try_paths:
    if os.path.isfile(try_path):
        if "prusa" not in try_path:
            echo0("[gcfmesh] Warning: scale_mesh"
                  " is only tested with PrusaSlicer"
                  " but it was not found at any of the following locations:"
                  " {}"
                  "".format(prusaslicer_paths))
        SLICER = try_path
        break


def scale_mesh(old_path, new_path, scale):
    '''
    Scale (multiply the size of) the mesh file with the file path
    old_path and create *or replace* new_path at the new size.

    Note that PrusaSlicer modifies the file in the same directory as the
    original, so copy the file first!
    '''
    shutil.copy(old_path, new_path)
    del old_path  # Make sure the old file isn't modified in place.
    # subprocess.check_output([SCRIPT, "-d", date], shell=True).
    parts = shlex.split(SLICER)
    if not os.path.isfile(parts[0]):
        raise FileNotFoundError(
            'Error: There is no executable "{}". Provide a full & correct path.'
            ''.format(parts[0])
        )
    # From <https://manual.slic3r.org/advanced/command-line>:
    parts += ["--scale", str(scale), "--export-stl", new_path]
    echo0("Running: {}".format(shlex.join(parts)))
    code = subprocess.call(parts)
    if code != 0:
        raise RuntimeError(
            'The process failed: {}'.format(shlex.join(parts))
        )


def resize_all(scale, parent, destination=os.getcwd()):
    '''
    Scale each STL file in parent and place each result in the
    destination directory.
    '''
    for sub in os.listdir(parent):
        if not sub.lower().endswith(".stl"):
            continue
        sub_path = os.path.join(parent, sub)
        if not os.path.isfile(sub_path):
            continue
        new_path = os.path.join(destination, sub)
        scale_mesh(sub_path, new_path, scale)
        if not os.path.isfile(new_path):
            echo0("Error: The command didn't fail but didn't create '{}'"
                  "".format(new_path))
            break  # debug only
        print("'{}'".format(new_path))
    echo0("Done")
    return 0


def usage():
    echo0(__doc__)


def main():
    ROOT=".."
    if len(sys.argv) < 2:
        usage()
        echo0("Error: You must specify a scale.")
        return 1
    return resize_all(float(sys.argv[1]), ROOT)


if __name__ == "__main__":
    sys.exit(main())
