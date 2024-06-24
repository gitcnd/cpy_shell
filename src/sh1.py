# sh1.py

__version__ = '1.0.20240624'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

def sort(cmdenv):
    return "\n".join(sorted(cmdenv['args'][1:], reverse='-r' in cmdenv['sw']))
