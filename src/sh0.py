# sh0.py

__version__ = '1.0.20240624'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

import os
import time


#print(self.get_desc('4').format(e)) # Socket send exception: {}
def _ea(shell, cmdenv):
    print(shell.get_desc('9').format(cmdenv['args'][0])) # {}: missing operand(s)

def _ee(shell, cmdenv, e):
    print(shell.get_desc('10').format(cmdenv['args'][0],e)) # {}: {}


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


def cd(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        _ea(shell, cmdenv) # print(self.get_desc('9').format(cmdenv['args'][0])) # {}: missing operand(s)
    else:
        try:
            os.chdir(cmdenv['args'][1])
        except OSError as e:
            _ee(shell, cmdenv, e) # print(f"cd: {e}")

def mv(shell, cmdenv):
    if len(cmdenv['args']) < 3:
         _ea(shell, cmdenv) # print("mv: missing file operand")
    else:
        try:
            os.rename(cmdenv['args'][1], cmdenv['args'][2])
        except OSError as e:
            _ee(shell, cmdenv,e) # print(f"mv: {e}")


def rm(shell, cmdenv):
    if len(cmdenv['args']) < 2:
         _ea(shell, cmdenv) # print("rm: missing file operand")
    else:
        path = cmdenv['args'][1]
        try:
            if os.stat(path)[0] & 0x4000:  # Check if it's a directory
                os.rmdir(path)
            else:
                os.remove(path)
        except OSError as e:
            _ee(shell, cmdenv,e) # print(f"rm: {e}")


def cp(shell, cmdenv):
    if len(cmdenv['args']) < 3:
         _ea(shell, cmdenv) # print("cp: missing file operand")
    else:
        try:
            with open(cmdenv['args'][1], 'rb') as src_file:
                with open(cmdenv['args'][2], 'wb') as dest_file:
                    dest_file.write(src_file.read())
        except OSError as e:
            _ee(shell, cmdenv,e) # print(f"{}: {e}")


def pwd(shell, cmdenv):
    print(os.getcwd())


def mkdir(shell, cmdenv):
    if len(cmdenv['args']) < 2:
         _ea(shell, cmdenv) # print("mkdir: missing file operand")
    else:
        try:
            os.mkdir(cmdenv['args'][1])
        except OSError as e:
            _ee(shell, cmdenv,e) # print(f"{}: {e}")


def rmdir(shell, cmdenv):
    if len(cmdenv['args']) < 2:
         _ea(shell, cmdenv) # print("rmdir: missing file operand")
    else:
        try:
            os.rmdir(cmdenv['args'][1])
        except OSError as e:
            print(f"rmdir: {e}")


def touch(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        _ea(shell, cmdenv) # print("touch: missing file operand")
    else:
        path = cmdenv['args'][1]
        try:
            try:
                # Try to open the file in read-write binary mode
                with open(path, 'r+b') as file:
                    first_char = file.read(1)
                    if first_char:
                        file.seek(0)
                        file.write(first_char)
                    else:
                        raise OSError(2, '') # 'No such file or directory')  # Simulate file not found to recreate it
            except OSError as e:
                if e.args[0] == 2:  # Error code 2 corresponds to "No such file or directory"
                    with open(path, 'wb') as file:
                        pass  # Do nothing after creating the file
                else:
                    raise e  # Re-raise the exception if it is not a "file not found" error
        except Exception as e:
            _ee(shell, cmdenv, e)  # print(f"{}: {e}")


def cat(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        _ea(shell, cmdenv)  # print("cat: missing file operand")
    else:
        try:
            with open(cmdenv['args'][1], 'rb') as file:
                while True:
                    chunk = file.read(64)
                    if not chunk:
                        break
                    print(chunk.decode('utf-8'), end='')
        except Exception as e:
            _ee(shell, cmdenv, e)  # print(f"cat: {e}")


def df(shell, cmdenv):
    try:
        fs_stat = os.statvfs('/')
        block_size = fs_stat[0]
        total_blocks = fs_stat[2]
        free_blocks = fs_stat[3]
        total_size = total_blocks * block_size
        free_size = free_blocks * block_size
        used_size = total_size - free_size
        print(f"Filesystem Size Used Available")
        print(f"/ {shell.human_size(total_size)} {shell.human_size(used_size)} {shell.human_size(free_size)}")
    except OSError as e:
        _ee(shell, cmdenv,e) # print(f"{}: {e}")
