# sh0.py

__version__ = '1.0.20240624'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

import os
import time


def ls(shell,cmdenv):	# impliments -F -l -a -t -r -S -h
    args=cmdenv['args']
    tsort=[]

    def list_items(items):
        for f in sorted(items, reverse=bool(cmdenv['sw'].get('r'))):
            if f.startswith('.') and not cmdenv['sw'].get('a'): continue
            pt = os.stat(f)
	    fsize = shell.human_size(pt[6]) if cmdenv['sw'].get('h') else pt[6]
            mtime = time.localtime(pt[7])
            mtime_str = f"{mtime.tm_year}-{mtime.tm_mon:02}-{mtime.tm_mday:02} {mtime.tm_hour:02}:{mtime.tm_min:02}.{mtime.tm_sec:02}"
            tag = "/" if cmdenv['sw'].get('F') and pt[0] & 0x4000 else ""
            ret=f"{fsize:,}\t{mtime_str}\t{f}{tag}" if cmdenv['sw'].get('l') else f"{f}{tag}"
            if cmdenv['sw'].get('t'):
                tsort.append((pt[7], ret))
            elif cmdenv['sw'].get('S'):
                tsort.append((pt[6], ret))
            else:
                print(ret)

    for path in cmdenv['args'][1:] if len(cmdenv['args']) > 1 else [os.getcwd()]:
 
        try:
            fstat = os.stat(path)
            if fstat[0] & 0x4000:  # Check for directory bit
                if path.endswith("/"):
                    path = path[:-1]
                path_pre = f"{path}/" if path else ""
    
                list_items([f"{path_pre}{filename}" for filename in os.listdir(path)])
            else:
                list_items([path])
        except OSError:
            print(f"{path} Not found")  # Handle non-existent paths


    if cmdenv['sw'].get('t') or cmdenv['sw'].get('S'):
        for _, ret in sorted(tsort, reverse=not bool(cmdenv['sw'].get('r'))):
            print(ret)

    return '' # cmdenv specified where output goes to
