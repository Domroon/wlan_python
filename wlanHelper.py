from time import sleep
import argparse
import configparser

import pywifi
from cryptography.fernet import Fernet


INTERFACE_STATUS = [
    "disconnected",
    "scanning",
    "inactive",
    "connecting",
    "connected"
]
SECRET_KEY = b'Qu099307GwgscI9IGGdHOa1r97aXCABiDceb6P3kY_Y='


def create_profile(ssid, key=None):
    profile = pywifi.Profile()
    profile.ssid = ssid
    profile.auth = pywifi.const.AUTH_ALG_OPEN
    if key is not None:
        profile.akm.append(pywifi.const.AKM_TYPE_WPA2PSK)
        profile.cipher = pywifi.const.CIPHER_TYPE_CCMP
        profile.key = key
    else:
        profile.akm.append(pywifi.const.AKM_TYPE_NONE)
        
    return profile


def connect(profile, interface):
    profile = interface.add_network_profile(profile)
    interface.connect(profile)
    for _ in range(10):
        status = INTERFACE_STATUS[interface.status()]
        if status == 'connected':
            print(f'connected with "{profile.ssid}"')
            break
        elif status == 'connecting':
            print(f'connecting to "{profile.ssid}"')
        else:
            print(status)
        sleep(1)
        
        
def get_network_names(interface):
    interface.scan()
    print('scanning for networks\n')
    sleep(2)
    scanned_profiles = interface.scan_results()
    ssids = []
    for profile in scanned_profiles:
        ssids.append(profile.ssid)
    return set(ssids)


def get_prog_args():
    parser = argparse.ArgumentParser(description='This program connects the current device to the saved wireless networks. The ranking corresponds to the order in which the networks are stored.')

    subparsers = parser.add_subparsers(help='sub-commands', dest='sub')
    connect_parser = subparsers.add_parser('connect', help='connect the computer')

    connect_loop_parser = subparsers.add_parser('connect-loop', help='connect and reconnect the computer if it is disconnected.')

    show_parser = subparsers.add_parser('show', help='show available wifi networks near you')

    show_stored_parser = subparsers.add_parser('show-stored', help='show wifi networks that you have already stored')

    add_parser = subparsers.add_parser('add', help='save a network')
    add_parser.add_argument('ssid', type=str, help='networkname that you want to add to your connection list')
    add_parser.add_argument('key', nargs='?', type=str, help='wpa2-key for the network')

    delete_parser = subparsers.add_parser('delete', help='delete a saved network')
    delete_parser.add_argument('ssid', type=str, help='networkname that you want to delete from your connection list')

    return parser.parse_args()


def store_network(ssid, config, key=None):
    config_list = config.read('networks.ini')
    if not config_list:
        print('no config file')
        print('create config file')
        config['Network 1'] = {'ssid': ssid}
        if key:
            config['Network 1']['key'] = key
        with open('networks.ini', 'w') as configfile:
            config.write(configfile)
    else:
        network_qty = len(config.sections())
        network_identifier = f'Network {network_qty + 1}'
        config[network_identifier] = {'ssid': ssid}
        if key:
            config[network_identifier]['key'] = key
        with open('networks.ini', 'w') as configfile:
            config.write(configfile)


def get_stored_networks(config):
    config.read('networks.ini')
    stored_networks = []
    for network in config.sections():
        stored_network = {}
        stored_network['network'] = config[network].name
        stored_network['ssid'] = config[network]['ssid']
        try:
            stored_network['key'] = config[network]['key']
        except KeyError:
            stored_network['key'] = None
        stored_networks.append(stored_network)
    return stored_networks


def connect_wisely(interface, config, fernet):
    stored_networks = get_stored_networks(config)
    available_networks = get_network_names(interface)
    
    for stored_network in stored_networks:
        if stored_network['ssid'] in available_networks:
            print(f'Found "{stored_network["network"]}" with SSID "{stored_network["ssid"]}"')
            stored_key = stored_network['key']
            if stored_key:
                encoded_key = stored_key.encode()
                key = fernet.decrypt(encoded_key).decode()
                profile = create_profile(stored_network['ssid'], key=key)
            else:
                profile = create_profile(stored_network['ssid'])
            connect(profile, interface)
            return True
            

def delete_stored_network(ssid, config):
    config_list = config.read('networks.ini')
    stored_networks = get_stored_networks(config)
    is_stored = False
    for network in stored_networks:
        if network['ssid'] == ssid:
            config.remove_section(f'{network["network"]}')
            with open('networks.ini', 'w') as configfile:
                config.write(configfile)
            is_stored = True
            print(f'deleted network with SSID "{ssid}"')
            break
    if not is_stored:
        print(f'Could not find a stored network with the SSID "{ssid}"')


def main():
    args = get_prog_args()
    wifi = pywifi.PyWiFi()
    interface = wifi.interfaces()[0]
    config = configparser.ConfigParser()
    fernet = Fernet(SECRET_KEY)
    
    if args.sub == 'connect':
        print(INTERFACE_STATUS[interface.status()])
        connected = connect_wisely(interface, config, fernet)
        if not connected:
            print('Could not find a available network that you have stored.')
    elif args.sub == 'connect-loop':
        print(INTERFACE_STATUS[interface.status()])
        while True:
            connect_wisely(interface, config, fernet)
            while True:
                if INTERFACE_STATUS[interface.status()] == 'disconnected':
                    print('disconnected')
                    break
                sleep(5)
    elif args.sub == 'show':
        for name in get_network_names(interface):
            print(name)
    elif args.sub == 'show-stored':
        for stored_network in get_stored_networks(config):
            print(stored_network['ssid'])
    elif args.sub == 'add':
        if args.key:
            encrypted_key = fernet.encrypt(args.key.encode())
            store_network(args.ssid, config, key=encrypted_key.decode())
            print(f'add network "{args.ssid}" with key "{args.key}"')
        else:
            store_network(args.ssid, config)
            print(f'add opened network "{args.ssid}" without key')
    elif args.sub == 'delete':
        delete_stored_network(args.ssid, config)


if __name__ == '__main__':
    main()