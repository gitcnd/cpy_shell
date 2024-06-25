# sh2.py

__version__ = '1.0.20240626'  # Major.Minor.Patch

# Created by Chris Drake.
# Linux-like shell interface for CircuitPython.  https://github.com/gitcnd/cpy_shell
# 
# This is a separate module for holding some commands.
# it is separate to save RAM

import gc
import time
import wifi
import ipaddress
import socketpool


def free(shell, cmdenv):
    try:
        gc.collect()
        total_memory = gc.mem_alloc() + gc.mem_free()
        free_memory = gc.mem_free()
        used_memory = gc.mem_alloc()
        print(f"Total Memory: {total_memory} bytes")
        print(f"Used Memory: {used_memory} bytes")
        print(f"Free Memory: {free_memory} bytes")
    except Exception as e:
        _ee(shell, cmdenv, e)  # print(f"free: {e}")


def ping(shell, cmdenv):
    if len(cmdenv['args']) < 2:
        print("usage: ping <address>")
        return

    dom = cmdenv['args'][1]

    pool = socketpool.SocketPool(wifi.radio)

    try:
        addr_info = pool.getaddrinfo(dom, 80)  # Using port 80 for HTTP
        ip = addr_info[0][4][0]
        ip1 = ipaddress.ip_address(ip)
    except Exception as e:
        print(f'Error getting IP address: {e}')
        return

    print(f"PING {dom} ({ip}) 56(84) bytes of data.")
    
    packet_count = 4
    transmitted = 0
    received = 0
    total_time = 0
    times = []

    for seq in range(1, packet_count + 1):
        transmitted += 1
        start_time = time.monotonic()
        
        result = wifi.radio.ping(ip1)
        rtt = (time.monotonic() - start_time) * 1000  # Convert to milliseconds
        total_time += rtt
        
        if result is not None:
            received += 1
            times.append(rtt)
            print(f"64 bytes from {ip}: icmp_seq={seq} time={rtt:.1f} ms")
        else:
            print(f"Request timeout for icmp_seq {seq}")
        
        if rtt<1000:
            time.sleep((1000-rtt)/1000)

    print(f"--- {ip} ping statistics ---")
    print(f"{transmitted} packets transmitted, {received} received, {((transmitted - received) / transmitted) * 100:.0f}% packet loss, time {total_time:.0f}ms")

    if times:
        min_time = min(times)
        avg_time = sum(times) / len(times)
        max_time = max(times)
        mdev_time = (sum((x - avg_time) ** 2 for x in times) / len(times)) ** 0.5
        print(f"rtt min/avg/max/mdev = {min_time:.3f}/{avg_time:.3f}/{max_time:.3f}/{mdev_time:.3f} ms")

