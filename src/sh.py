# sh.py

__version__ = '1.0.20240628'  # Major.Minor.Patch

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



class CustomIO:
    def __init__(self):
        self.input_content = ""
        self.output_content = ""
        self.sockets = []  # List of open TCP/IP sockets for both input and output
        self.outfiles = []  # List of open file objects for output
        self.infiles = []   # List of open file objects for input
        self.socket_buffers = {}  # Dictionary to store buffers for each socket
        self.history_file = "/.history.txt"  # Path to the history file

        self._nbuf = ""
        self._line = ""
        self._cursor_pos = 0
        self._lastread = time.monotonic()
        self._esc_seq = ""
        self._reading_esc = False
        self._insert_mode = True  # Default to insert mode
        self._hist_loc = -1  # Start with the most recent command (has 1 added before use; 0 means last)

        # New global variables for terminal size and type
        self._TERM_WIDTH = 80
        self._TERM_HEIGHT = 24
        self._TERM_TYPE = ""
        self._TERM_TYPE_EX = ""

        if time.time() < 1718841600 and wifi.radio.ipv4_address: self.set_time() # set the time if possible and not already set


    # Initialize buffers for sockets
    def initialize_buffers(self):
        self.socket_buffers = {sock: "" for sock in self.sockets}

    def _read_nonblocking(self):
        if supervisor.runtime.serial_bytes_available:
            self._nbuf += sys.stdin.read(supervisor.runtime.serial_bytes_available)
            i=self._nbuf.find('\n')+1
            if i<1: i=None
            ret=self._nbuf[:i]
            self._nbuf=self._nbuf[len(ret):]
            return ret
        return None


    def ins_command(self,command,mv=True):
        # Replace this with the actual command execution logic
        if self._cursor_pos>0:
            print(f'\033[{self._cursor_pos}D', end='')  # Move cursor left by current cursor_pos
        print(f'{command}\033[K', end='')  # output the new line, and clear anything after it
        if mv:
            self._cursor_pos=len(command)
        else:
            m=len(command)-self._cursor_pos
            if m>0:
                print(f'\033[{m}D', end='')  # Move cursor back to same place it was
        self._line=command

    def get_history_line(self,n):
        with open(self.history_file, "r") as f:
            for i, line in enumerate(f):
                if i == n - 1:
                    return line.split('\t', 1)[1].strip()
        return None
    

    def search_history(self, pfx, hist_loc):
        with open(self.history_file, "rb") as f:
            f.seek(0, 2)  # Seek to the end of the file
            file_size = f.tell()
            remaining = file_size
            buffer_size = 64
            partial_line = b""
            #matches = []
            match=-1
            prevm=''
            match_idx = file_size - hist_loc * buffer_size

            while remaining > 0 or partial_line:
                read_size = min(buffer_size, remaining)
                f.seek(remaining - read_size)
                buffer = f.read(read_size)
                remaining -= read_size

                lines = buffer.split(b'\n')
                if partial_line:
                    lines[-1] += partial_line
                partial_line = lines[0] if remaining > 0 else b""

                for line in reversed(lines[1:] if remaining > 0 else lines):
                    try:
                        if line.strip():
                            decoded_line = line.decode('utf-8').split('\t', 1)[1].strip()
                            #print(f"considering line: {decoded_line}")
                            if decoded_line.startswith(pfx):
                                if decoded_line != prevm: # ignore duplicates
                                    match += 1
                                prevm=decoded_line
                                #matches.append(decoded_line)
                                #print(f"yes match={match} want={hist_loc} pfx='{pfx}'")
                                if match==hist_loc:
                                    return decoded_line
                            #else:
                            #   #print(f"no match={match} want={hist_loc} pfx='{pfx}'")
                    except IndexError as e:
                        print(f"possible history_file error: {e} for line: {line}")

                #if len(matches) > hist_loc:
                #    return matches[hist_loc]

        return None


    def _process_input(self, char):
        self._lastread = time.monotonic()
        
        if self._reading_esc:
            self._esc_seq += char
            if time.monotonic() - self._lastread > 0.1:
                self._reading_esc = False
                self._esc_seq = ""
                return self._line, "esc", self._cursor_pos
            if self._esc_seq[-1] in 'ABCDEFGH~Rnc': 
                response = self._handle_esc_sequence(self._esc_seq[2:])
                self._reading_esc = False
                self._esc_seq = ""
                if response:
                    return response
        elif char == '\x1b':  # ESC sequence
            self._reading_esc = True
            self._esc_seq = char
        elif char in ['\x7f', '\b']:  # Backspace
            if self._cursor_pos > 0:
                self._line = self._line[:self._cursor_pos - 1] + self._line[self._cursor_pos:]
                self._cursor_pos -= 1
                print('\b \b' + self._line[self._cursor_pos:] + ' ' + '\b' * (len(self._line) - self._cursor_pos + 1), end='')
        elif char in ['\r', '\n']:  # Enter
            ret_line = self._line
            err='sh: !{}: event not found'
            if ret_line.startswith("!"): # put history into buffer
                if ret_line[1:].isdigit():
                    nth = int(ret_line[1:])
                    history_line = self.get_history_line(nth)
                    if history_line:
                        self.ins_command(history_line)
                    else:
                        print(err.format(nth)) # sh: !123: event not found
                        return '' # re-show the prompt
                else:
                    pfx = ret_line[1:]
                    history_line = self.search_history(pfx,0)
                    if history_line:
                        self.ins_command(history_line)
                    else:
                        print(err.format(pfx)) # sh: !{pfx}: event not found
                        return '' # re-show the prompt
            else:
                print('\r')
                self._line = ""
                self._cursor_pos = 0
                self._hist_loc = -1
                return ret_line, 'enter', self._cursor_pos

        elif char == '\001':  # repl exit
            return 'exit', 'enter', 0
        elif char == '\t':  # Tab
            #return self._line, 'tab', self._cursor_pos
            current_input = self._line[:self._cursor_pos]
            if any(char in current_input for char in [' ', '<', '>', '|']):
                # Extract the word immediately at the cursor
                last_space = current_input.rfind(' ') + 1
                #if last_space == -1:
                #    last_space = 0
                #else:
                #    last_space += 1
                word = current_input[last_space:self._cursor_pos]
        
                try:
                    for entry in os.listdir():
                        if entry.startswith(word):
                            self.ins_command(self._line[:self._cursor_pos] + entry[len(word):] + self._line[self._cursor_pos:])
                            break
                except OSError as e:
                    print(f"Error listing directory: {e}")

            else:
                from sh1 import _iter_cmds
                for cmd in _iter_cmds():
                    if cmd.startswith(current_input):
                         self.ins_command(self._line[:self._cursor_pos] + cmd[len(current_input):] + ' ' + self._line[self._cursor_pos:])
                         break
                del sys.modules["sh1"]

        else:
            if self._insert_mode:
                self._line = self._line[:self._cursor_pos] + char + self._line[self._cursor_pos:]
                print(f'\033[@{char}', end='')  # Print char and insert space at cursor position
            else:
                self._line = self._line[:self._cursor_pos] + char + self._line[self._cursor_pos + 1:]
                print(char, end='')
            self._cursor_pos += 1
        
        return None

    def _handle_esc_sequence(self, seq):

        if seq in ['A', 'B']:  # Up or Down arrow
            i = 1 if seq == 'A' else -1
            
            if seq == 'B' and self._hist_loc < 1:
                return
        
            self._hist_loc += i

            history_line = self.search_history(self._line[:self._cursor_pos], self._hist_loc)

            #print(f"arrow {seq} line {self._hist_loc} h={history_line}")
            
            if history_line:
                self.ins_command(history_line,mv=False)
            else:
                self._hist_loc -= i

            #return self._line, 'up' if seq == 'A' else 'down', self._cursor_pos
        elif seq == 'C':  # Right arrow
            if self._cursor_pos < len(self._line):
                self._cursor_pos += 1
                print('\033[C', end='')
        elif seq == 'D':  # Left arrow
            if self._cursor_pos > 0:
                self._cursor_pos -= 1
                print('\033[D', end='')
        elif seq == '3~':  # Delete
            if self._cursor_pos < len(self._line):
                self._line = self._line[:self._cursor_pos] + self._line[self._cursor_pos + 1:]
                print('\033[1P', end='')  # Delete character at cursor position
        elif seq == '2~':  # Insert
            self._insert_mode = not self._insert_mode
        elif seq in ['H', '1~']:  # Home
            if self._cursor_pos > 0:
                print(f'\033[{self._cursor_pos}D', end='')  # Move cursor left by current cursor_pos
            self._cursor_pos = 0
        elif seq in ['F', '4~']:  # End
            d=len(self._line) - self._cursor_pos
            if d>0:
                print(f'\033[{d}C', end='')  # Move cursor right by difference
            self._cursor_pos = len(self._line)
        elif seq == '1;5D':  # Ctrl-Left
            if self._cursor_pos > 0:
                prev_pos = self._cursor_pos
                while self._cursor_pos > 0 and self._line[self._cursor_pos - 1].isspace():
                    self._cursor_pos -= 1
                while self._cursor_pos > 0 and not self._line[self._cursor_pos - 1].isspace():
                    self._cursor_pos -= 1
                print(f'\033[{prev_pos - self._cursor_pos}D', end='')
        elif seq == '1;5C':  # Ctrl-Right
            if self._cursor_pos < len(self._line):
                prev_pos = self._cursor_pos
                while self._cursor_pos < len(self._line) and not self._line[self._cursor_pos].isspace():
                    self._cursor_pos += 1
                while self._cursor_pos < len(self._line) and self._line[self._cursor_pos].isspace():
                    self._cursor_pos += 1
                print(f'\033[{self._cursor_pos - prev_pos}C', end='')
        elif seq.endswith('R'):  # Cursor position report
            try:
                self._TERM_HEIGHT, self._TERM_WIDTH = map(int, seq[:-1].split(';'))
            except Exception as e:
                print(f"term-size set command {seq[:-1]} error: {e}")
            return self._line, 'sz', self._cursor_pos
        elif seq.startswith('>') and seq.endswith('c'):  # Extended device Attributes
            self._TERM_TYPE_EX = seq[1:-1]
            return seq, 'attr', self._cursor_pos
        elif seq.startswith('?') and seq.endswith('c'):  # Device Attributes
            self._TERM_TYPE = seq[1:-1]
            return seq, 'attr', self._cursor_pos
        return None



    # Read input from stdin, sockets, or files
    def read_input(self):

        # Read from stdin
        chars=1 # keep doing this 'till we get nothing more
        while chars:
            #print("r1")
            chars = self._read_nonblocking()
            #print("r2")
            if chars:

                for char in chars:
                    response = self._process_input(char)
                    if response:
                        user_input, key, cursor = response
                        if key=='enter':
                            if len(user_input):
                                self.add_hist(user_input)
                            return user_input
                        elif key != 'sz': 
                            oops=f" (mode {key} not implimented)";
                            print(oops +  '\b' * (len(oops)), end='')

                # #print("wt")
                # self.send_chars_to_all(chars) # echo it
                # #print("wd")
                # if chars.endswith('\n'):
                #     chars = self.input_content + chars.rstrip('\n') # don't append \n to the commandline
                #     self.input_content = ""
                #     self.add_hist(chars)
                #     return chars
                # self.input_content += chars 
                # self._lastread=time.monotonic()
            elif time.monotonic()-self._lastread>0.1:
                time.sleep(0.1)  # Small delay to prevent high CPU usage

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
            sys.stdout.write(chars) # + "\x1b[s\x1b[1B\x1b[1C\x1b[u")
            # sys.stdout.flush() # AttributeError: 'FileIO' object has no attribute 'flush'
            # Send to all output files
            for file in self.outfiles:
                try:
                    file.write(chars)
                    file.flush()
                except Exception as e:
                    print(self.get_desc('3').format(e)) #  File write exception: {}

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
                print(self.get_desc('4').format(e)) # Socket send exception: {}
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
            #print("Output file opened successfully.")
        except Exception as e:
            print(self.get_desc('5').format(e)) # Output file setup failed: {}

    # Method to open an input file
    def open_input_file(self, filepath):
        try:
            file = open(filepath, 'r')
            self.infiles.append(file)
            #print("Input file opened successfully.")
        except Exception as e:
            print(self.get_desc('6').format(e)) # Input file setup failed: {}

    # Method to open a socket
    def open_socket(self, address, port, timeout=10):
        try:
            pool = socketpool.SocketPool(wifi.radio)
            sock = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((address, port))
            self.sockets.append(sock)
            #print("Socket connected successfully.") #DBG
            self.initialize_buffers()
        except Exception as e:
            print(self.get_desc('7').format(e)) # Socket setup failed: {}

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
            print(self.get_desc('8').format(e)) # Failed to get NTP time: {}
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

    # error-message expander helpers
    def _ea(shell, cmdenv):
        print(shell.get_desc('9').format(cmdenv['args'][0])) # {}: missing operand(s)

    def _ee(shell, cmdenv, e):
        print(shell.get_desc('10').format(cmdenv['args'][0],e)) # {}: {}


    def file_exists(self, filepath):
        try:
            os.stat(filepath)
            return True
        except OSError:
            return False


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
                    #print(f"` start={start} value={value}")
                    end = value.find('`', start + 1)
                    #print(f"` end={end} value={value}")
                    if end == -1:
                        break
                    command = value[start + 1:end]
                    #print(f"` command={command}")
                    value = value[:start] + self.execute_command(command) + value[end + 1:]
                    #print(f"` new value={value}")
                if '$(' in value:
                    start = value.find('$(')
                    #print(f"$( start={start} value={value}")
                    end = start + 2
                    #print(f"$( end={end} value={value}")
                    open_parens = 1
                    while open_parens > 0 and end < len(value):
                        if value[end] == '(':
                            open_parens += 1
                        elif value[end] == ')':
                            open_parens -= 1
                        end += 1
                    command = value[start + 2:end - 1]
                    command = value[start + 2:end]
                    #print(f"$( command={command}")
                    value = value[:start] + self.execute_command(command) + value[end:]
                    #print(f"$( new value={value}")
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


    def human_size(self,size):
        # Convert bytes to human-readable format
        for unit in ['B', 'K', 'M', 'G', 'T']:
            if size < 1024:
                return f"{round(size):,}{unit}"
            size /= 1024
        return f"{round(size):,}P"  # Handle very large sizes as petabytes

    
    def execute_command(self,command):
        # """Execute a command and return its output. Placeholder for actual execution logic."""
        for _ in range(2): # optional alias expander
            parts = self.parse_command_line(command)
            cmdenv = parts[0]  # Assuming simple commands for mock execution
            cmd=cmdenv['args'][0]
            #print("executing: {}".format(cmdenv['line'])) #DBG

            alias = os.getenv(cmd)
            if alias is not None:
                command=alias + command[command.find(' '):] if ' ' in command else alias
            else:
                break

        # internal commands
        if cmd == 'exit':
            return 0


        #if cmd == 'echo':
        #    print( cmdenv['line'].split(' ', 1)[1] if ' ' in cmdenv['line'] else '') # " ".join(cmdenv['args'][1:])
        #elif cmd == 'sort':
        #    return "\n".join(sorted(cmdenv['args'][1:], reverse='-r' in cmdenv['sw']))
        #elif cmd == 'ls':
        #    return "file1.txt\nfile2.txt\nfile3.txt"


        for mod in ["sh0", "sh1", "sh2"]:
            gc.collect()
            module = __import__(mod)

            # sh_module = sys.modules['sh0']
            command_function = getattr(module, cmd,None)
            if command_function:
                #print(f"running {mod}.{cmd}")
                ret=command_function(self,cmdenv)  # Run the command
                del sys.modules[mod]
                gc.collect()
                return 1
                # return ret
                break
            del sys.modules[mod]
            gc.collect()

        print(self.get_desc('0').format(cmd)) # {} command not found
        return 1 # keep running
    



# Main function to demonstrate usage
def main():

    custom_io = CustomIO()
    #custom_io.open_socket('chrisdrake.com', 9887)
    #custom_io.open_output_file('/example.txt')
    #custom_io.open_input_file('/testin.txt')
    #NG: custom_io.open_listening_socket()  # Open listening socket on telnet port 23 - no code for accept() etc exists yet.


    # Use the custom context manager to redirect stdout and stdin
    with IORedirector(custom_io):

        shell = sh()

        # see sh1.py/test() for argument parsing tests

        # test $VAR expansion
        #print(shell.subst_env("$GRN$HOSTNAME$NORM:{} cpy\$ ").format(os.getcwd()))
        # print("GET /lt.asp?cpy HTTP/1.0\r\nHost: chrisdrake.com\r\n\r\n")

        #ng: print("helpme");help("modules");print("grr")

        # test input
        run=1
        print("\033[s\0337\033[999C\033[999B\033[6n\r\033[u\0338", end='')  # Request terminal size.
        while run>0:
            run=1
            user_input = input(shell.subst_env("$GRN$HOSTNAME$NORM:{} cpy\$ ").format(os.getcwd())) # the stuff in the middle is the prompt
            if user_input:
                #print("#############")
                #print(''.join(f' 0x{ord(c):02X} ' if ord(c) < 0x20 else c for c in user_input))
                #print("#############")
                #hex_values = ' '.join(f'{ord(c):02x}' for c in user_input)
                #print("input=0x " + hex_values)
                # print(f"Captured input: {user_input}")
                # print(f"input=0x{' '.join(f'{ord(c):02x}' for c in user_input)}") # print(f"input=0x {user_input.hex()}")
                # print(shell.execute_command(user_input))
                run=2 # bypass the sleep 1 time
                try:
                    run=shell.execute_command(user_input) # IORedirector takes care of sending the "print" statements from these to the right place(s)
                except KeyboardInterrupt:
                    print("^C")
            if run>1: time.sleep(0.1)  # Perform other tasks here


    custom_io.flush()

# run it right now
main()
if "sh" in sys.modules:
    del sys.modules["sh"] # so we can re-run us later


### See also ###
# import storage
# storage.erase_filesystem()
#
# import storage
# storage.disable_usb_drive()
# storage.remount("/", readonly=False)
