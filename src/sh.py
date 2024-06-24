# sh.py

__version__ = '1.0.20240623'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# Notes:
#  scripts:
#         This runtest script __name__ is: __main__
#         Error with __file__: name '__file__' is not defined
#  modules:
#         This test script __name__ is: test
#         This test script __file__ is located at: /lib/test.py
# 
# https://github.com/todbot/circuitpython-tricks
# Alternatives: if supervisor.runtime.serial_bytes_available:
# 
# terminalio.Terminal().read(1) # for connected LCD things ?
# sys.stdin.read(1)        # for serial?
# https://chatgpt.com/share/41987e5d-4c73-432e-95cf-1e434479c1c1
# 
# 1718841600 # 2024/06/20 

import os, gc
import supervisor

import sys
import socketpool
import wifi
import time

    

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
        self.history_file = "/history.txt"  # Path to the history file
        if time.time() < 1718841600 and wifi.radio.ipv4_address: self.set_time() # set the time if possible and not already set


    # Initialize buffers for sockets
    def initialize_buffers(self):
        self.socket_buffers = {sock: "" for sock in self.sockets}

    # Read input from stdin, sockets, or files
    def read_input(self):

        # Read from stdin
        char = read_nonblocking()
        if char:
            self.send_chars_to_all(char) # echo it
            if char == '\n':
                line = self.input_content
                self.input_content = ""
                self.add_hist(line)
                return line
            self.input_content += char # don't append \n to the commandline

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


    def add_hist(self, line, retry=True):
        try:
            with open(self.history_file, 'a') as hist_file:
                hist_file.write(f"{int(time.time())}\t{line}\n")
        except OSError:
            # If an OSError is raised, the file system is read-only
            if retry:
                import storage
                try:
                    storage.remount("/", False)
                    add_hist(self, line, False)
                except: 
                    pass

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

    """ # Method to open a listening socket on port 23 for Telnet
    def open_listening_socket(self, port=23):
        try:
            pool = socketpool.SocketPool(wifi.radio)
            server_sock = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
            server_sock.bind(("", port))
            server_sock.listen(1)
            print("Listening on {}:{} for incoming Telnet connections.".format(wifi.radio.ipv4_address,port))
            self.sockets.append(server_sock) # wrong approach - this is a listen, not a read or write socket...
            self.initialize_buffers()
        except Exception as e:
            print("Listening socket setup failed:", e)
    """

    # Method to flush buffers
    def flush(self):
        while self.send_chars_to_all(""):
            pass # time.sleep(0.1)  # Prevent a tight loop

    def set_time(self):
        import rtc, struct
        buf = bytearray(48)
        buf[0] = 0b00100011
    
        try:
            # Create socket
            pool = socketpool.SocketPool(wifi.radio)
            sock = pool.socket(pool.AF_INET, pool.SOCK_DGRAM)
            sock.settimeout(1)
    
            # Send NTP request
            sock.sendto(buf, ("pool.ntp.org", 123))
    
            # Receive NTP response
            sock.recv_into(buf)
    
            rtc.RTC().datetime = time.localtime(struct.unpack("!I", buf[40:44])[0] - 2208988800) # NTP timestamp starts from 1900, Unix from 1970
    
        except Exception as e:
            print("Failed to get NTP time:", e)
        finally:
            sock.close()
        self.add_hist("#boot")


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
        pass # self.history_file = "/history.txt"


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
        def split_command_o(command_line):
            # """Split command line into parts respecting quotes and escape sequences."""
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

        
        
        def split_command(command_line):
            # """Split command line into parts respecting quotes and escape sequences."""
            parts = []
            part = ''
            in_single_quote = False
            in_double_quote = False
            in_backticks = False
            in_subshell = 0
            escape = False
        
            i = 0
            while i < len(command_line):
                char = command_line[i]
                if escape:
                    part += char
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"' and not in_single_quote and not in_backticks and in_subshell == 0:
                    in_double_quote = not in_double_quote
                    part += char
                elif char == "'" and not in_double_quote and not in_backticks and in_subshell == 0:
                    in_single_quote = not in_single_quote
                    part += char
                elif char == '`' and not in_single_quote and not in_double_quote and in_subshell == 0:
                    if in_backticks:
                        in_backticks = False
                        part += char
                        parts.append(part)
                        part = ''
                    else:
                        if part:
                            parts.append(part)
                            part = ''
                        in_backticks = True
                        part += char
                elif char == '$' and i + 1 < len(command_line) and command_line[i + 1] == '(' and not in_single_quote and not in_double_quote and not in_backticks:
                    if in_subshell == 0 and part:
                        parts.append(part)
                        part = ''
                    in_subshell += 1
                    part += char
                elif char == ')' and not in_single_quote and not in_double_quote and not in_backticks and in_subshell > 0:
                    in_subshell -= 1
                    part += char
                    if in_subshell == 0:
                        parts.append(part)
                        part = ''
                elif char.isspace() and not in_single_quote and not in_double_quote and not in_backticks and in_subshell == 0:
                    if part:
                        parts.append(part)
                        part = ''
                elif char in '|<>' and not in_single_quote and not in_double_quote and not in_backticks and in_subshell == 0:
                    if part:
                        parts.append(part)
                        part = ''
                    parts.append(char)
                else:
                    part += char
                i += 1
        
            if part:
                parts.append(part)
            return parts
        



        def substitute_backticks(value):
            # """Substitute commands within backticks and $(...) with their output."""
            def substitute(match):
                command = match.group(1)
                return self.execute_command(command)  # Placeholder for actual command execution

            while '`' in value or '$(' in value:
                if '`' in value:
                    start = value.find('`')
                    print(f"` start={start} value={value}")
                    end = value.find('`', start + 1)
                    print(f"` end={end} value={value}")
                    if end == -1:
                        break
                    command = value[start + 1:end]
                    print(f"` command={command}")
                    value = value[:start] + self.execute_command(command) + value[end + 1:]
                    print(f"` new value={value}")
                if '$(' in value:
                    start = value.find('$(')
                    print(f"$( start={start} value={value}")
                    end = start + 2
                    print(f"$( end={end} value={value}")
                    open_parens = 1
                    while open_parens > 0 and end < len(value):
                        if value[end] == '(':
                            open_parens += 1
                        elif value[end] == ')':
                            open_parens -= 1
                        end += 1
                    command = value[start + 2:end - 1]
                    command = value[start + 2:end]
                    print(f"$( command={command}")
                    value = value[:start] + self.execute_command(command) + value[end:]
                    print(f"$( new value={value}")
            return value

        
        def process_parts(parts):
            # """Process parts into switches and arguments."""
            #sw = {}
            #arg = []
            redirections = {'stdin': None, 'stdout': None, 'stderr': None}
            current_cmd = {'line': '', 'sw': {}, 'args': [], 'redirections': redirections, 'pipe_from': None}

            cmds = [current_cmd]
            i = 0
            while i < len(parts):
                part = parts[i]
                if part == '|':
                    current_cmd = {'line': '', 'sw': {}, 'args': [], 'redirections': {'stdin': None, 'stdout': None, 'stderr': None}, 'pipe_from': cmds[-1]}
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
                        current_cmd['sw'][key] = value
                        current_cmd['line'] += f" --{key}={value}"
                    else:
                        current_cmd['sw'][part[2:]] = True
                        current_cmd['line'] += ' ' + part
                elif part.startswith('-') and len(part) > 1:
                    j = 1
                    while j < len(part):
                        if part[j].isalpha():
                            current_cmd['sw'][part[j]] = True
                            j += 1
                        else:
                            current_cmd['sw'][part[j]] = part[j + 1:] if j + 1 < len(part) else True
                            break
                    current_cmd['line'] += ' ' + part
                else:
                    if not (part.startswith("'") and part.endswith("'")):
                        part = self.subst_env(substitute_backticks(part))
                    current_cmd['args'].append(part)
                    current_cmd['line'] += (' ' if current_cmd['line'] else '') + part

                i += 1

            return cmds

        parts = split_command(command_line)
        cmds = process_parts(parts)

        return cmds

    def execute_commandN(self, command):
        # """Execute a command and return its output. Placeholder for actual execution logic."""
        parts = self.parse_command_line(command)
        cmd = parts[0]  # Assuming simple commands for mock execution
        if cmd['args'][0] == 'ls':
            #print(cmd)
            return "file1.txt\nfile2.txt\nfile3.txt"
        elif cmd['args'][0] == 'echo':
            return cmd['line'].split(' ', 1)[1] if ' ' in cmd['line'] else '' # " ".join(cmd['args'][1:])
        elif cmd['args'][0] == 'sort':
            return "\n".join(sorted(cmd['args'][1:], reverse='-r' in cmd['sw']))
        elif cmd['args'][0] == 'grep':
            pattern = cmd['args'][1]
            return "\n".join(line for line in ["file1.txt", "file2.txt", "file3.txt"] if pattern in line)
        elif cmd['args'][0] == 'man':
            if len(cmd['args']) > 1:
                keyword = cmd['args'][1]
                description = self.get_desc(keyword)
                if description:
                    description = self.subst_env(f"\n${{WHT}}{keyword}${{NORM}} - ") + description
                    return description
                return self.get_desc('1').format(keyword)       # f"No manual entry for {keyword}"
            return self.get_desc('2')                           # "Usage: man [keyword]"
        return "<executed {}>".format(command)


    
    def execute_command(self,command):
        # """Execute a command and return its output. Placeholder for actual execution logic."""
        parts = self.parse_command_line(command)
        cmdenv = parts[0]  # Assuming simple commands for mock execution
        cmd=cmdenv['args'][0]
        print("executing {}".format(cmdenv['line']))

        # internal commands
        if cmd == 'echo':
            return cmdenv['line'].split(' ', 1)[1] if ' ' in cmdenv['line'] else '' # " ".join(cmdenv['args'][1:])
        #elif cmd == 'sort':
        #    return "\n".join(sorted(cmdenv['args'][1:], reverse='-r' in cmdenv['sw']))
        elif cmd == 'ls':
            return "file1.txt\nfile2.txt\nfile3.txt"
        elif cmd == 'man':
            if len(cmdenv['args']) > 1:
                keyword = cmdenv['args'][1]
                description = self.get_desc(keyword)
                if description:
                    description = self.subst_env(f"\n${{WHT}}{keyword}${{NORM}} - ") + description
                    return description
                return self.get_desc('1').format(keyword)       # f"No manual entry for {keyword}"
            return self.get_desc('2')                           # "Usage: man [keyword]"

        #return "<executed {}>".format(cmdenv['line'])

        """
        # Define command lists within the function to avoid global memory usage
        sh0_commands = [
            "dir", "ls", "cd", "mv", "rm", "cp", "pwd", "mkdir", "rmdir", "touch", "cat", 
            "tail", "head", "wc", "less", "uname", "hostname", "alias", "run"
        ]
    
        sh1_commands = [
            "find", "sort", "df", "du", "vi", "nano", "edit", "grep", "more", "zcat", "hexedit",
            "history", "uptime", "date", "whois", "env", "setenv", "export", "printenv", "diff",
            "curl", "wget", "ping", "dig", "ssh", "scp", "telnet", "nc", "ifconfig", "ftp", "pip",
            "yum", "apt", "tar", "gzip", "gunzip", "bzip2", "bunzip2", "python", "sh", "git",
            "locate", "sz", "rz", "now", "who", "which", "clear", "reboot", "poweroff", "passwd",
            "sleep", "unalias", "exit", "help", "md5sum", "sha1sum", "sha256sum", "hexedit",
            "blink", "set", "pins", "adc", "button", "photo", "neo_blink", "blink_all_pins", "beep",
            "freq", "display", "print", "showbmp", "clear", "mountsd", "umount", "espnowreceiver",
            "espnowsender", "hardreset", "memtest", "bluescan", "scani2c", "temperature", "mag",
            "gps", "radar", "telnetd", "wifi"
        ]
    
        if cmd in sh0_commands:
            lib_name = 'sh0'
        elif cmd in sh1_commands:
            lib_name = 'sh1'
        else:
            return self.get_desc('0').format(cmd) # {} command not found
    
        # Ensure the module is imported
        if lib_name in sys.modules:
            sh_module = sys.modules[lib_name]
        else:
            print(f"Module {lib_name} is not imported.")
            return
    
        # Check if the command exists within the module
        if hasattr(sh_module, cmd):
            command_function = getattr(sh_module, cmd)
            command_function(cmdenv)  # Run the command
        else:
            print(f"The command {cmd} is not available in the {lib_name} module.")
        """


	for mod in ["sh0", "sh1"]:
            gc.collect()
            module = __import__(mod)

            # sh_module = sys.modules['sh0']
            command_function = getattr(module, cmd,None)
            if command_function:
                ret=command_function(cmdenv)  # Run the command
                del sys.modules[mod]
                gc.collect()
                return ret
                break
            del sys.modules[mod]
            gc.collect()

        return self.get_desc('0').format(cmd) # {} command not found
    



# Main function to demonstrate usage
def main():

    custom_io = CustomIO()
    #custom_io.open_socket('chrisdrake.com', 9887)
    #custom_io.open_output_file('/example.txt')
    #custom_io.open_input_file('/testin.txt')
    #NG: custom_io.open_listening_socket()  # Open listening socket on telnet port 23 - no code for accept() etc exists yet.


    # Use the custom context manager to redirect stdout and stdin
    with IORedirector(custom_io):

        # test arg parsing
        shell = sh()
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

        # test $VAR expansion
        #print(shell.subst_env("$GRN$HOSTNAME$NORM:{} cpy\$ ").format(os.getcwd()))
        # print("GET /lt.asp?cpy HTTP/1.0\r\nHost: chrisdrake.com\r\n\r\n")

        #ng: print("helpme");help("modules");print("grr")

        # test input
        while True:
            user_input = input(shell.subst_env("$GRN$HOSTNAME$NORM:{} cpy\$ ").format(os.getcwd())) # the stuff in the middle is the prompt
            if user_input:
                #print(f"Captured input: {user_input}")
                print(shell.execute_command(user_input))
            time.sleep(0.1)  # Perform other tasks here


    custom_io.flush()

# run it right now
main()



