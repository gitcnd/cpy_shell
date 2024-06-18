# cpy_shell
Linux-like shell interface for CircuitPython

Inspired by [mipyshell](https://github.com/vsolina/mipyshell) and busybox, here is a command-line shell for your CircuitPython board carefully implementing a range of useful commands.

Everything is written to save RAM and Flash; command bytecode is not loaded if you don't run the command, history is stored in a file, not in RAM, pipes use flash instead of RAM, etc.

## Installation and running:

* place the .mpy files into /lib/ on your CircuitPython device
* run the following from the >>> repl
` import sh `

## Supported Commands

### File Management
- `dir` - List directory contents (similar to `ls`)
- `cd` - Change directory
- `mv` - Move or rename files or directories
- `ls` - List directory contents
- `rm` - Remove files or directories
- `cp` - Copy files or directories
- `pwd` - Print working directory
- `find` - Search for files in a directory hierarchy
- `sort` - Sort lines of text files
- `mkdir` - Make directories
- `df` - Report file system disk space usage
- `du` - Estimate file space usage
- `rmdir` - Remove empty directories
- `touch` - Change file timestamps or create an empty file

### Text Processing
- `vi` - vim-like Text editor
- `nano` - Text editor
- `edit` - Text editor
- `grep` - Search text using patterns
- `cat` - Concatenate and display files
- `tail` - Output the last part of files
- `head` - Output the first part of files
- `echo` - Display a line of text
- `more` - View file contents page-by-page
- `wc` - Word, line, character, and byte count
- `zcat` - Concatenate compressed files and output
- `less` - View file contents page-by-page with backward movement (similar to `more`)
- `hexedit` - View and edit files in hexadecimal format

### System Information
- `history` - Command history
- `uname` - Print system information
- `uptime` - Tell how long the system has been running
- `hostname` - Show or set the system's hostname
- `date` - Display or set the system date and time
- `whois` - Query domain name information
- `env` - Display or set environment variables
- `setenv` - Set environment variables (equivalent of `export` in some contexts)
- `export` - Set environment variables
- `printenv` - Print all or part of the environment
- `diff` - Compare files line by line

### Networking Utilities
- `curl` - Transfer data from or to a server
- `wget` - Non-interactive network downloader (alias for `curl`)
- `ping` - Send ICMP ECHO_REQUEST to network hosts
- `dig` - DNS lookup
- `ssh` - OpenSSH remote login client
- `scp` - Secure copy (remote file copy program)
- `telnet` - User interface to the TELNET protocol
- `ifconfig` - Configure network interfaces
- `ftp` - File Transfer Protocol client

### Package Management
- `pip` - Package manager - aliases to help with installing 
- `yum` - Package manager - alias for `pip`
- `apt` - Advanced Package Tool - alias for `pip`

### File Compression
- `tar` - Archive files
- `gzip` - Compress files
- `gunzip` - Decompress files
- `bzip2` - Compress files
- `bunzip2` - Decompress files

### Development Tools
- `python` - inbuilt - alias for `run`
- `sh` - inbuilt - aliasthis tool itself (you can run commands from a .sh file through this shell)
- `git` - Distributed version control system
- `diff` - Compare files line by line

### Miscellaneous Utilities
- `locate` - Find files by name
- `sz` - Send files (ZModem)
- `rz` - Receive files (ZModem)
- `now` - Display the current date and time (alias for `date`)
- `who` - Show who is logged on
- `which` - Locate a command
- `clear` - Clear the terminal screen
- `reboot` - Reboot the system
- `poweroff` - Halt, power-off, or reboot the machine
- `passwd` - Change user password
- `sleep` - Delay for a specified amount of time
- `unalias` - Remove alias definitions
- `alias` - Create an alias for a command
- `exit` - Exit the shell
- `help` - Display help information about built-in commands
- `md5sum` - Calculate MD5 checksums
- `sha1sum` - Calculate SHA-1 checksums
- `sha256sum` - Calculate SHA-256 checksums
- `hexedit` - View and edit files in hexadecimal format

### Hardware Extensions
- `blink` - flash the device LED
- `set` - set the state of a GPIO pin
- `pins` - display the input coming in to a GPIO pin
- `adc` - display the analogue input from a GPIO
- `button` - display the state of the default button
- `photo` - take a photo from the device camera
- `neo_blink` - set one or more neopixel LED colours
- `blink_all_pins` - output pin numbers using TTL 1's and 0's to identify pins (e.g. 7 x 1-0 pulses for GPIO7)
- `beep` - send an analogue tone to the default speaker
- `freq` - set a specific analogue output to a GPIO pin (e.g. move a servo)
####
- `display` - control the screen
- `print` - write some text onto the screen
- `showbmp` - put a graphic onto the screen
- `clear` - erase the screen
####
- `mountsd` - attach an SD card
- `umount` - un-attach it
####
- `run` - execute a python program from the shell - does progressive-compilation to save space.
####
- `espnowreceiver` - show incoming espnow messages
- `espnowsender` - send espnow messages
####
- `hardreset` - reboot the chip
####
- `memtest` - test memory
####
- `bluescan` - show visible bluetooth devices and data
- `scani2c` - show attached I2C devices found
####
- `temperature` - print current temperature
- `mag` - show the X, Y, and Z field strength from a magnetometer
- `gps` - display your latitude and longitude
- `radar` - output data from your attached radar device
####
- `telnetd` - listen for terminal input over TCP/IP
####
- `wifi` - control your wifi settings


## Features

### Command History
Implement a command history that allows users to scroll through previously entered commands using the up and down arrow keys (without wasting RAM, and persists across reboots)

### Tab Completion
Add tab completion for command and file and directory names to improve user experience.

#### Piping and Redirection
Basic support for some piping (`|`) and redirection (`>`, `>>`, `<`) to chain commands and redirect input/output.

### Environment Variables
Allow users to set, view, and use environment variables.

### Scripting
Support for easily running Python, using progressive compilation, enabling running larger programs that would not otherwise fit into RAM

### Aliases
Allow users to create command aliases for frequently used commands.

### Help System
Implements a `help` command that provides information about available commands and their usage.

### User Customization
Supports settings.toml for configuration and environment where users can customize their shell experience.
