# sh0.py

__version__ = '1.0.20240624'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

import os
import time

def __main__(args):
    ls(args[2:])  # mipyshell first 2 arguments are "python" and "ls.py"

def ls(cmdenv):
    args=cmdenv['args']
    path = args[0] if args else os.getcwd()

    try:
        fstat = os.stat(path)
        if fstat[0] & 0x4000:  # Check for directory bit
            print("d .")
            if path != "/":
                print("d ..")
            if path.endswith("/"):
                path = path[:-1]
            path_pre = f"{path}/" if path else ""

            list_items([f"{path_pre}{filename}" for filename in os.listdir(path)])
        else:
            list_items([path])
    except OSError:
        print(f"{path} Not found")  # Handle non-existent paths

def list_items(items):
    for f in sorted(items):
        pt = os.stat(f)
        fsize = pt[6]
        mtime = time.localtime(pt[7])
        mtime_str = f"{mtime.tm_year}-{mtime.tm_mon:02}-{mtime.tm_mday:02} {mtime.tm_hour:02}:{mtime.tm_min:02}:{mtime.tm_sec:02}"
        tag = "/" if pt[0] & 0x4000 else ""
        print(f"{fsize}\t{mtime_str}\t{f}{tag}")

# When used outside of mipyshell...
if 'ARGV' in locals():
    ls(ARGV)  # invoked via REPL >>> ARGV=["bin/"];exec(open("bin/ls.py").read())
else:
    pass # ls([]) # invoked via: ampy --port $PORT run bin/ls.py
