#!/bin/bash
customDie() {
    echo
    echo
    echo "ERROR:"
    echo "$1"
    echo
    echo
    exit 1
}

# pep8-3 says:
# pep8 has been renamed to pycodestyle (GitHub issue #466)
# Use of the pep8 tool will be removed in a future release.
# Please install and use `pycodestyle` instead.

if [ ! -f "`command -v pycodestyle-3`" ]; then
    customDie "pycodestyle-3 is missing. You must first install the python3-pycodestyle package."
fi

pycodestyle-3 gcodefollower.py > style-check-output.txt
pycodestyle-3 TowerConfiguration.pyw >> style-check-output.txt
pycodestyle-3 TowerConfigurationCLI.py >> style-check-output.txt
if [ -f "`command -v outputinspector`" ]; then
    outputinspector style-check-output.txt
else
    cat style-check-output.txt
    cat <<END

Instead of cat, this script can use outputinspector if you install it
  (If you double-click on any error, outputinspector will tell Geany or
  Kate to navigate to the line and column in your program):

  <https://github.com/poikilos/outputinspector>

END
fi
