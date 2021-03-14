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

python_mr=`python python_major_revision.py`
pycodestyle_cmd="pycodestyle-3"

if [ ! -f "`command -v pycodestyle-3`" ]; then
    py_msg="."
    if [ "$python_mr" = "2" ]; then
        py_msg=", but your default python is python$python_mr so other steps may be required to make the command available."
    fi
    echo "pycodestyle-3 is missing. You must first install the python3-pycodestyle package$py_msg"
    if [ -f "`command -v python3`" ]; then
        pycodestyle_cmd="python3 -m pycodestyle"
    else
        pycodestyle_cmd="python -m pycodestyle"
    fi
    echo "* attempting to use $pycodestyle_cmd..."
    cat > /dev/null <<END
    $pycodestyle_cmd >& /dev/null
    if [ $? -eq 127 ]; then
        echo "* The module was not found."
        exit 127
    fi
END
fi

echo > style-check-output.txt
for fname in gcodefollower.py TowerConfiguration.pyw TowerConfigurationCLI.py
do
    if [ ! -f "$fname" ]; then
        echo "Error: The list of files to test is hard-coded but \"$fname\" is not in \"`pwd`\"."
        exit 1
    fi
    $pycodestyle_cmd $fname >> style-check-output.txt
done
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
