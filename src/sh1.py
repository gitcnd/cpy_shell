# sh1.py

__version__ = '1.0.20240624'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

def sort(shell,cmdenv):
    return "\n".join(sorted(cmdenv['args'][1:], reverse='-r' in cmdenv['sw']))


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
        print(f"\n[32;1mTest case: {command_line}[0m")
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
