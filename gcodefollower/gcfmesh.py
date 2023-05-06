#!/usr/bin/env python
'''
If run as a script, this *permanently* resizes *all* stl files in the
*current working directory*!

This requires the flatpak version of PrusaSlicer for now.
'''
import sys
import os
import shlex
import subprocess
import shutil

SLICER = "/usr/bin/flatpak run --branch=stable --arch=x86_64 --command=entrypoint --file-forwarding com.prusa3d.PrusaSlicer"


def echo0(*args):
    print(*args, file=sys.stderr)


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


def main():
    ROOT=".."
    return resize_all((25.4+.1)/20.2, ROOT)


if __name__ == "__main__":
    sys.exit(main())
