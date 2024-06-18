# sh2.py

__version__ = '1.0.0'  # Major.Minor.Patch

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



"""

import os
import supervisor

import sys
import socketpool
import wifi
import time

# Custom output class for redirection and handling sockets/files
class ShellOutput:
    def __init__(self):
        self.sockets = []  # List of open TCP/IP sockets
        self.files = []    # List of open file objects
        self.socket_buffers = {}  # Dictionary to store buffers for each socket

    # Initialize buffers for sockets
    def initialize_buffers(self):
        self.socket_buffers = {sock: "" for sock in self.sockets}

    # Send characters to all sockets and files
    def send_chars_to_all(self, chars):
        if chars:
            sys.stdout.write(chars)
            # Send to all files
            for file in self.files:
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

    # Method to open a file
    def open_file(self, filepath):
        try:
            file = open(filepath, 'w')
            self.files.append(file)
            print("File opened successfully.")
        except Exception as e:
            print("File setup failed:", e)

    # Method to open a socket
    def open_socket(self, address, port, timeout=10):
        try:
            pool = socketpool.SocketPool(wifi.radio)
            sock = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
            # sock.setblocking(False)

            try:
                sock.connect((address, port))
            except OSError as e:
                if e.errno != 119:  # EINPROGRESS
                    raise

            start_time = time.monotonic()
            while True:
                try:
                    sock.send(b'') # cannot fail - nonblocking?
                    break
                except OSError as e:
                    if e.errno != 11:  # EAGAIN, try again
                        raise
                    if time.monotonic() - start_time > timeout:
                        raise TimeoutError("Timeout while waiting for socket connection")
                    time.sleep(0.1)
            
            self.sockets.append(sock)
            print("Socket connected successfully.")
            self.initialize_buffers()
        except Exception as e:
            print("Socket setup failed:", e)

    # Method to flush buffers
    def flush(self):
        while self.send_chars_to_all(""):
            time.sleep(0.1)  # Prevent a tight loop

# Output redirector context manager
class OutputRedirector:
    def __init__(self, new_output):
        self.new_output = new_output
        self.old_print = None

    def __enter__(self):
        import builtins
        self.old_print = builtins.print
        builtins.print = self.custom_print

    def __exit__(self, exc_type, exc_val, exc_tb):
        import builtins
        builtins.print = self.old_print

    def custom_print(self, *args, **kwargs):
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        output = sep.join(map(str, args)) + end
        self.new_output.send_chars_to_all(output)



class sh:
    def __init__(self):
        self.history_file = "/history.txt"

    def handle_environment_variables(self, value):
        """Replace environment variables in the argument."""
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
                            value = self.handle_environment_variables(substitute_backticks(value))
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
                        part = self.handle_environment_variables(substitute_backticks(part))
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
        return "<executed {}>".format(command)






# Main function to demonstrate usage
def main():
    shell_output = ShellOutput()
    # shell_output.open_socket('chrisdrake.com', 9887)	# works (might be blocking?)
    # shell_output.open_file('/example.txt')		# works

    # Use the custom context manager to redirect stdout
    with OutputRedirector(shell_output):
        #print("GET /lt.asp?cpy HTTP/1.0\r\nHost: chrisdrake.com\r\n\r\n")


        # Example usage:
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


        print(shell.handle_environment_variables("$GRN$HOSTNAME$NORM:{} cpy\$ ").format(os.getcwd()))


    shell_output.flush()


# run it right now
main()



