#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

MAC_Table = {}
VLAN_Table = {}
root_bridge = -1

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bdpu_every_sec():
    while True:
        # TODO Send BDPU every second if necessary
        time.sleep(1)

def read_from_configuration_file(switch_id):
    file_name = f"configs/switch{switch_id}.cfg"
    
    with open(file_name, 'r') as file:
        lines = (line.strip() for line in file.readlines()[1:])
        
        for index, line in enumerate(lines):
            VLAN_Table[index] = int(line[-1]) if line and line[-1] != 'T' else -1

def update_packet_vlan(data, vlan_id, length, add_tag):
    if add_tag:
        return data[0:12] + create_vlan_tag(vlan_id) + data[12:], length + 4
    else:
        return data[0:12] + data[16:], length - 4


def broadcast_forwarding(interface, data, length, dest_mac, src_mac, interfaces, vlan_id):
    # Broadcast the frame to all interfaces
    for o in interfaces:
        if o != interface:
            if VLAN_Table[o] == vlan_id:
                send_to_link(o, length, data)
            else: 
                new_data, new_length = update_packet_vlan(data, vlan_id, length, True)
                send_to_link(o, new_length, new_data)

    

def forwarding_with_learning(interface, data, length, dest_mac, src_mac, interfaces, vlan_id):
    if vlan_id == -1:
        vlan_id = VLAN_Table[interface]
    else:
        data, length = update_packet_vlan(data, vlan_id, length, False)

    MAC_Table[src_mac] = interface

    if dest_mac != get_switch_mac():
        if dest_mac in MAC_Table:
            if VLAN_Table[MAC_Table[dest_mac]] == vlan_id:
                send_to_link(MAC_Table[dest_mac], length, data)
            else:
                new_data, new_length = update_packet_vlan(data, vlan_id, length, True)
                send_to_link(MAC_Table[dest_mac], new_length, new_data)
        else:
            broadcast_forwarding(interface, data, length, dest_mac, src_mac, interfaces, vlan_id)
    else:
        broadcast_forwarding(interface, data, length, dest_mac, src_mac, interfaces, vlan_id)


def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    switch_id = sys.argv[1]

    read_from_configuration_file(switch_id)

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)


    print("# Starting switch with id {}".format(switch_id), flush=True)
    print("[INFO] Switch MAC", ':'.join(f'{b:02x}' for b in get_switch_mac()))

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec)
    t.start()

    # Printing interface names
    for i in interfaces:
        print(get_interface_name(i))

    while True:
        # Note that data is of type bytes([...]).
        # b1 = bytes([72, 101, 108, 108, 111])  # "Hello"
        # b2 = bytes([32, 87, 111, 114, 108, 100])  # " World"
        # b3 = b1[0:2] + b[3:4].
        interface, data, length = recv_from_any_link()

        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        # Print the MAC src and MAC dst in human readable format
        dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac = ':'.join(f'{b:02x}' for b in src_mac)

        # Note. Adding a VLAN tag can be as easy as
        # tagged_frame = data[0:12] + create_vlan_tag(10) + data[12:]

        print(f'Destination MAC: {dest_mac}')
        print(f'Source MAC: {src_mac}')
        print(f'EtherType: {ethertype}')

        print("Received frame of size {} on interface {}".format(length, interface), flush=True)

        # TODO: Implement forwarding with learning
        # TODO: Implement VLAN support
        # from acces
        #functie de update, nu mai scot aici headerul de vlan, il scot doar cand trebuie, si in rest fac update la headerul asta, scoatandu-l si punandu-l inapoi
        forwarding_with_learning(interface, data, length, dest_mac, src_mac, interfaces, vlan_id)
        # data is of type bytes.
        # send_to_link(i, length, data)

if __name__ == "__main__":
    main()
