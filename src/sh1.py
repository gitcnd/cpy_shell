# sh1.py

__version__ = '1.0.20240626'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

import gc
import sys
import os


def sort(shell,cmdenv):
    return "\n".join(sorted(cmdenv['args'][1:], reverse='-r' in cmdenv['sw']))


def man(shell,cmdenv):
    if len(cmdenv['args']) > 1:
        keyword = cmdenv['args'][1]
        description = shell.get_desc(keyword)
        if description:
            print(shell.subst_env(f"\n${{WHT}}{keyword}${{NORM}} - " + description)) # we deliberately want the description $VARS to be expanded
        else:
            print(shell.get_desc('1').format(keyword))       # f"No manual entry for {keyword}"
    else:
        print(shell.get_desc('2'))                       # "Usage: man [keyword]"


def _iter_cmds():
    for mod in ["sh0", "sh1", "sh2"]:
        gc.collect()
        module = __import__(mod)
        for name in dir(module):
            if not name.startswith("_"):
                obj = getattr(module, name)
                if callable(obj):
                    yield name
        if mod != "sh1":
            del sys.modules[mod]
        gc.collect()


def help(shell, cmdenv):
    try:
        commands = []
        for mod in ["sh0", "sh1", "sh2"]:
            gc.collect()
            module = __import__(mod)
            for name in dir(module):
                if not name.startswith("_"):
                    obj = getattr(module, name)
                    if callable(obj):
                        commands.append(name)
            if mod != "sh1":
                del sys.modules[mod]
            gc.collect()

        if cmdenv.get('args', [])[1:] == ["all"]:
            for cmd in sorted(commands):
                #print(f"Manual for {cmd}:")
                man(shell, {'args': ['man', cmd]})
                print()
        else:
            print("Available commands:")
            for cmd in sorted(commands):
                print(f"  {cmd}")
    except Exception as e:
        _ee(shell, cmdenv, e)  # print(f"help: {e}")


def which(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        _ea(shell, cmdenv)
        return

    command = cmdenv['args'][1]

    # Check for inbuilt commands
    try:
        for cmd in _iter_cmds():
            if command == cmd:
                print(f"{command}: (inbuilt)")
                return
    except Exception as e:
        print(f"Error checking inbuilt commands: {e}")

    # Check if the argument contains a "/" or "./" prefix and if it exists as a file
    if "/" in command or command.startswith("./"):
        try:
            os.stat(command)
            print(command)
            return
        except OSError:
            pass

    # Check /bin/ and /lib/ directories for .py or .mpy files
    for directory in ["/bin", "/lib"]:
        for ext in ["mpy", "py"]: # cpy runs the .mpy in preference
            path = f"{directory}/{command}.{ext}"
            try:
                os.stat(path)
                print(path)
                return
            except OSError:
                pass

    # If no match found
    print(f"{command}: command not found")


def test(shell,cmdenv):

    # test arg parsing
    test_cases = [
        r'ls --test=5 -abc "file name with spaces" $HOSTNAME $HOME | grep "pattern" > output.txt',
        r'sort -n -k2,3 < input.txt',
        r'echo `ls -a` | sort -r',
        r'echo `ls` | sort -r',
        r'ls $(echo out)',
        r'echo $(sort $(echo "-r" `echo - -n`) -n)'
    ]

    for command_line in test_cases:
        print(f"\n\033[32;1mTest case: {command_line}\033[0m")
        cmds = shell.parse_command_line(command_line)
        for i, cmdenv in enumerate(cmds):
            print(f"Command {i + 1}:")
            print("  Line:", cmdenv['line'])
            print("  Switches:", cmdenv['sw'])
            print("  Arguments:", cmdenv['args'])
            print("  Redirections:", cmdenv['redirections'])
            print("  Pipe from:", cmdenv['pipe_from'])
        print()
        gc.collect()

    return "ok\n"

