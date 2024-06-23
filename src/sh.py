# sh2.py

__version__ = '1.0.20240623'  # Major.Minor.Patch

"""
Created by Chris Drake.
Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell

Notes:
 scripts:
        This runtest script __name__ is: __main__
        Error with __file__: name '__file__' is not defined
 modules:
        This test script __name__ is: test
        This test script __file__ is located at: /lib/test.py

https://github.com/todbot/circuitpython-tricks
Alternatives: if supervisor.runtime.serial_bytes_available:

terminalio.Terminal().read(1) # for connected LCD things ?
sys.stdin.read(1)        # for serial?
https://chatgpt.com/share/41987e5d-4c73-432e-95cf-1e434479c1c1




"""

import os
import supervisor


import sys
import socketpool
import wifi
import time
import supervisor



def read_nonblocking():
    if supervisor.runtime.serial_bytes_available:
        return sys.stdin.read(1)
    return None


class CustomIO:
    def __init__(self):
        self.input_content = ""
        self.output_content = ""
        self.sockets = []  # List of open TCP/IP sockets for both input and output
        self.outfiles = []  # List of open file objects for output
        self.infiles = []   # List of open file objects for input
        self.socket_buffers = {}  # Dictionary to store buffers for each socket

    # Initialize buffers for sockets
    def initialize_buffers(self):
        self.socket_buffers = {sock: "" for sock in self.sockets}

    # Read input from stdin, sockets, or files
    def read_input(self):

        # Read from stdin
        char = read_nonblocking()
        if char:
            self.input_content += char
            self.send_chars_to_all(char) # echo it
            if char == '\n':
                line = self.input_content
                self.input_content = ""
                return line

        # Read from input files
        for file in self.infiles:
            line = file.readline()
            if line:
                return line

        # Read from sockets
        for sock in self.sockets:
            try:
                data = sock.recv(1024).decode('utf-8')
                if data:
                    return data
            except Exception as e:
                continue

        return None

    def readline(self):
        if self.input_content:
            line = self.input_content
            self.input_content = ""
            return line
        raise EOFError("No more input")

    # Send characters to all sockets and files
    def send_chars_to_all(self, chars):
        if chars:
            chars = chars.replace('\\n', '\r\n')  # Convert LF to CRLF
            sys.stdout.write(chars)
            # Send to all output files
            for file in self.outfiles:
                try:
                    file.write(chars)
                    file.flush()
                except Exception as e:
                    print(f"File write exception: {e}")

        # Flag to check if any buffer has remaining data
        any_buffer_non_empty = False

        # Send to all sockets
        for sock in self.sockets:
            try:
                if self.socket_buffers[sock]:
                    chars_to_send = self.socket_buffers[sock] + chars
                    sock.send(chars_to_send.encode('utf-8'))
                    self.socket_buffers[sock] = ""
                else:
                    sock.send(chars.encode('utf-8'))
            except Exception as e:
                print(f"Socket send exception: {e}")
                self.socket_buffers[sock] += chars
                if len(self.socket_buffers[sock]) > 80:
                    self.socket_buffers[sock] = self.socket_buffers[sock][-80:]  # Keep only the last 80 chars

            # Update the flag if there is still data in the buffer
            if self.socket_buffers[sock]:
                any_buffer_non_empty = True

        return any_buffer_non_empty

    # Method to open an output file
    def open_output_file(self, filepath):
        try:
            file = open(filepath, 'w')
            self.outfiles.append(file)
            print("Output file opened successfully.")
        except Exception as e:
            print("Output file setup failed:", e)

    # Method to open an input file
    def open_input_file(self, filepath):
        try:
            file = open(filepath, 'r')
            self.infiles.append(file)
            print("Input file opened successfully.")
        except Exception as e:
            print("Input file setup failed:", e)

    # Method to open a socket
    def open_socket(self, address, port, timeout=10):
        try:
            pool = socketpool.SocketPool(wifi.radio)
            sock = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((address, port))
            self.sockets.append(sock)
            print("Socket connected successfully.")
            self.initialize_buffers()
        except Exception as e:
            print("Socket setup failed:", e)

    # Method to flush buffers
    def flush(self):
        while self.send_chars_to_all(""):
            pass # time.sleep(0.1)  # Prevent a tight loop

class IORedirector:
    def __init__(self, custom_io):
        self.custom_io = custom_io
        self.old_input = None
        self.old_print = None

    def __enter__(self):
        import builtins
        self.old_input = builtins.input
        self.old_print = builtins.print
        builtins.input = self.custom_input
        builtins.print = self.custom_print

    def __exit__(self, exc_type, exc_val, exc_tb):
        import builtins
        builtins.input = self.old_input
        builtins.print = self.old_print

    def custom_input(self, prompt=''):
        self.custom_print(prompt, end='')
        while True:
            line = self.custom_io.read_input()
            if line is not None:
                return line.rstrip('\n')
            time.sleep(0.1)  # Small delay to prevent high CPU usage

    def custom_print(self, *args, **kwargs):
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        output = sep.join(map(str, args)) + end
        self.custom_io.send_chars_to_all(output)



class sh:
    def __init__(self):
        self.history_file = "/history.txt"


    # """For reading help and error messages etc out of a text file"""
    def get_desc(self,keyword):
        with open(__file__.rsplit('.', 1)[0] + '.txt', 'r') as file:   # /lib/sh.txt
            for line in file:
                try:
                    key, description = line.split('\t', 1)
                    if key == keyword:
                        return self.subst_env(description.strip())
                except: 
                    return 'corrupt help file'

        return None


    # """Replace environment variables in the argument."""
    def subst_envo(self, value):
        result = ''
        i = 0
        while i < len(value):
            if value[i] == '\\' and i + 1 < len(value) and value[i + 1] == '$':
                result += '$'
                i += 2
            elif value[i] == '$' and i + 1 < len(value) and value[i + 1].isalpha():
                var_start = i + 1
                var_end = var_start
                while var_end < len(value) and (value[var_end].isalpha() or value[var_end].isdigit() or value[var_end] == '_'):
                    var_end += 1
                var_name = value[var_start:var_end]
                env_value = os.getenv(var_name)
                if env_value is not None:
                    result += env_value
                else:
                    result += f'${var_name}'
                i = var_end
            else:
                result += value[i]
                i += 1
        return result


    def exp_env(self,start,value):
        if value[start] == '{':
            end = value.find('}', start)
            var_name = value[start + 1:end]
            if var_name.startswith('!'):
                var_name = os.getenv(var_name[1:], f'${{{var_name}}}')
                var_value = os.getenv(var_name, f'${{{var_name}}}')
            else:
                var_value = os.getenv(var_name, f'${{{var_name}}}')
            return end + 1, var_value
        else:
            end = start
            while end < len(value) and (value[end].isalpha() or value[end].isdigit() or value[end] == '_'):
                end += 1
            var_name = value[start:end]
            var_value = os.getenv(var_name, f'${var_name}')
            return end, var_value

    def subst_env(self, value):
        result = ''
        i = 0
        while i < len(value):
            if value[i] == '\\' and i + 1 < len(value) and value[i + 1] == '$':
                result += '$'
                i += 2
            elif value[i] == '$':
                i += 1
                i, expanded = self.exp_env(i,value)
                result += expanded
            else:
                result += value[i]
                i += 1
        return result


    def parse_command_line(self, command_line):
        def split_command(command_line):
            """Split command line into parts respecting quotes and escape sequences."""
            parts = []
            part = ''
            in_single_quote = False
            in_double_quote = False
            escape = False

            for char in command_line:
                if escape:
                    part += char
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"' and not in_single_quote:
                    in_double_quote = not in_double_quote
                    part += char
                elif char == "'" and not in_double_quote:
                    in_single_quote = not in_single_quote
                    part += char
                elif char.isspace() and not in_single_quote and not in_double_quote:
                    if part:
                        parts.append(part)
                        part = ''
                elif char in '|<>':
                    if part:
                        parts.append(part)
                        part = ''
                    parts.append(char)
                else:
                    part += char

            if part:
                parts.append(part)
            return parts

        def substitute_backticks(value):
            """Substitute commands within backticks and $(...) with their output."""
            def substitute(match):
                command = match.group(1)
                return self.execute_command(command)  # Placeholder for actual command execution

            while '`' in value or '$(' in value:
                if '`' in value:
                    start = value.find('`')
                    end = value.find('`', start + 1)
                    if end == -1:
                        break
                    command = value[start + 1:end]
                    value = value[:start] + self.execute_command(command) + value[end + 1:]
                if '$(' in value:
                    start = value.find('$(')
                    end = start + 2
                    open_parens = 1
                    while open_parens > 0 and end < len(value):
                        if value[end] == '(':
                            open_parens += 1
                        elif value[end] == ')':
                            open_parens -= 1
                        end += 1
                    command = value[start + 2:end - 1]
                    value = value[:start] + self.execute_command(command) + value[end:]
            return value

        def process_parts(parts):
            """Process parts into switches and arguments."""
            sw = {}
            arg = []
            redirections = {'stdin': None, 'stdout': None, 'stderr': None}
            current_cmd = {'switches': sw, 'arguments': arg, 'redirections': redirections, 'pipe_from': None}

            cmds = [current_cmd]
            i = 0
            while i < len(parts):
                part = parts[i]
                if part == '|':
                    current_cmd = {'switches': {}, 'arguments': [], 'redirections': {'stdin': None, 'stdout': None, 'stderr': None}, 'pipe_from': cmds[-1]}
                    cmds.append(current_cmd)
                elif part == '>':
                    redirections['stdout'] = parts[i + 1]
                    i += 1
                elif part == '>>':
                    redirections['stdout'] = {'append': parts[i + 1]}
                    i += 1
                elif part == '<':
                    redirections['stdin'] = parts[i + 1]
                    i += 1
                elif part.startswith('--'):
                    if '=' in part:
                        key, value = part[2:].split('=', 1)
                        if not (value.startswith("'") and value.endswith("'")):
                            value = self.subst_env(substitute_backticks(value))
                        current_cmd['switches'][key] = value
                    else:
                        current_cmd['switches'][part[2:]] = True
                elif part.startswith('-') and len(part) > 1:
                    j = 1
                    while j < len(part):
                        if part[j].isalpha():
                            current_cmd['switches'][part[j]] = True
                            j += 1
                        else:
                            current_cmd['switches'][part[j]] = part[j + 1:] if j + 1 < len(part) else True
                            break
                else:
                    if not (part.startswith("'") and part.endswith("'")):
                        part = self.subst_env(substitute_backticks(part))
                    current_cmd['arguments'].append(part)
                i += 1

            return cmds

        parts = split_command(command_line)
        cmds = process_parts(parts)

        return cmds

    def execute_command(self, command):
        """Execute a command and return its output. Placeholder for actual execution logic."""
        parts = self.parse_command_line(command)
        cmd = parts[0]  # Assuming simple commands for mock execution
        if cmd['arguments'][0] == 'ls':
            return "file1.txt\nfile2.txt\nfile3.txt"
        elif cmd['arguments'][0] == 'echo':
            return " ".join(cmd['arguments'][1:])
        elif cmd['arguments'][0] == 'sort':
            return "\n".join(sorted(cmd['arguments'][1:], reverse='-r' in cmd['switches']))
        elif cmd['arguments'][0] == 'grep':
            pattern = cmd['arguments'][1]
            return "\n".join(line for line in ["file1.txt", "file2.txt", "file3.txt"] if pattern in line)
        elif cmd['arguments'][0] == 'man':
            if len(cmd['arguments']) > 1:
                keyword = cmd['arguments'][1]
                description = self.get_desc(keyword)
                if description:
                    description = self.subst_env(f"\n${{WHT}}{keyword}${{NORM}} - ") + description
                    return description
                return self.get_desc('1').format(keyword)       # f"No manual entry for {keyword}"
            return self.get_desc('2')                           # "Usage: man [keyword]"
        return "<executed {}>".format(command)






# Main function to demonstrate usage
def main():

    custom_io = CustomIO()
    #custom_io.open_socket('chrisdrake.com', 9887)
    #custom_io.open_output_file('/example.txt')
    #custom_io.open_input_file('/testin.txt')

    # Use the custom context manager to redirect stdout and stdin
    with IORedirector(custom_io):

        # test arg parsing
        shell = sh()
        test_cases = [
            r'ls --test=5 -abc "file name with spaces" $HOSTNAME $HOME | grep "pattern" > output.txt',
            r'sort -n -k2,3 < input.txt',
            r'echo `ls` | sort -r',
            r'echo $(sort $(echo "-r" `echo - -n`) -n)'
        ]

        for command_line in test_cases:
            cmds = shell.parse_command_line(command_line)
            print(f"Test case: {command_line}")
            for i, cmd in enumerate(cmds):
                print(f"Command {i + 1}:")
                print("  Switches:", cmd['switches'])
                print("  Arguments:", cmd['arguments'])
                print("  Redirections:", cmd['redirections'])
                print("  Pipe from:", cmd['pipe_from'])
            print()

        # test $VAR expansion
        #print(shell.subst_env("$GRN$HOSTNAME$NORM:{} cpy\$ ").format(os.getcwd()))
        # print("GET /lt.asp?cpy HTTP/1.0\r\nHost: chrisdrake.com\r\n\r\n")

        #ng: print("helpme");help("modules");print("grr")

        # test input
        while True:
            user_input = input(shell.subst_env("$GRN$HOSTNAME$NORM:{} cpy\$ ").format(os.getcwd())) # the stuff in the middle is the prompt
            if user_input:
                print(f"Captured input: {user_input}")
                print(shell.execute_command(user_input))
            time.sleep(0.1)  # Perform other tasks here


    custom_io.flush()

# run it right now
main()



