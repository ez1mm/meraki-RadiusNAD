#!/usr/bin/env python
import csv
import os
import asyncio
import logging
import sys

import meraki.aio

from argparse import ArgumentParser
from datetime import datetime

BOLD = '\033[1m'
ENDC = '\033[0m'
BLUE = '\033[94m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
PURPLE = '\033[35m'
LGRAY = '\033[97m'
DGRAY = '\033[90m'

def csv_writer(devices):
    csvdir = os.path.join(os.getcwd(), "output")
    if not os.path.exists(csvdir):
        os.makedirs(csvdir)

    csvfile = f"{csvdir}/report_{datetime.now():%Y%m%d-%H%M%S}.csv"

    print(f"** Writing {csvfile}")

    with open(csvfile, 'w', newline='') as cf:
        fieldnames = ['name', 'type', 'radiusAddress']

        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        for dev in devices:
            writer.writerow({
                'name': dev.name,
                'type': dev.type,
                'radiusAddress': dev.radius_address
            })


async def getOrgs(aiodash, org_name=None, org_id=None, tag=None):
    if org_id:
        result = await aiodash.organizations.getOrganization(org_id)
        logger.debug(f"organizations: {BLUE}{result}{ENDC}")
        yield result
    elif org_name:
        organizations = await aiodash.organizations.getOrganizations()
        for result in organizations:
            if result['name'] == org_name and result['api']['enabled'] == True:
                logger.debug(f"organizations: {BLUE}{result}{ENDC}")
                yield result
    else:
        organizations = await aiodash.organizations.getOrganizations()
        for result in organizations:
            if result['api']['enabled'] == True:
                logger.debug(f"organizations: {BLUE}{result}{ENDC}")
                await asyncio.sleep(0)
                yield result


async def getNetworks(aiodash, org_id, net_name=None, tag=None):
    product_filter = "systemsManager"
    networks = aiodash.organizations.getOrganizationNetworks(org_id, 
                                                             perPage=1000, 
                                                             total_pages='all')
    logger.debug(f"networks: {BLUE}{networks}{ENDC}")

    if net_name:
        async for result in networks:
            if result['name'] == net_name:
                yield result
    else:
        async for result in networks:
            if product_filter not in result['productTypes']:
                await asyncio.sleep(0)
                yield result


async def getOrgDevices(aiodash, org_id, net_id=None):
    if net_id:
        devices = aiodash.organizations.getOrganizationDevices(org_id, 
                                                                perPage=1000,
                                                                networkIds=net_id,
                                                                total_pages='all')
        logger.debug(f"devices: {BLUE}{devices}{ENDC}")
        async for result in devices:
            if result['networkId'] == net_id:
                yield result
    else:
        devices = aiodash.organizations.getOrganizationDevices(org_id, 
                                                                perPage=1000,
                                                                total_pages='all')
        logger.debug(f"devices: {BLUE}{devices}{ENDC}")
        async for result in devices:
            yield result


async def getNetDevices(aiodash, net_id):
    result = await aiodash.networks.getNetworkDevices(net_id)
    logger.debug(f"netdevs: {result}")
    return result


class Network(object):
    @classmethod
    async def create(cls, aiodash, net):
        self = Network()
        self.net = net
        logger.debug(f"self.net: {CYAN}{self.net}, {self.net['id']}{ENDC}")
        self.net_id = net['id']
        if "switch" in self.net['productTypes']:
            self.ms_ami = await self.getMsAmi(aiodash, self.net['id'])
        if "wireless" in self.net['productTypes']:
            self.mr_ami = await self.getMrAmi(aiodash, self.net['id'])
        if "appliance" in self.net['productTypes']:
            self.vpn_vlans = await self.getVpnVlans(aiodash, self.net['id'])
            self.net_vlans = await self.getNetworkVlans(aiodash, self.net['id'])
        return self


    def __repr__(self):
        return f"Network({self.net['name']}, {self.net['id']})"


    async def getMsAmi(self, aiodash, net_id):
        try:
            result = await aiodash.switch.getNetworkSwitchAlternateManagementInterface((net_id))
            return result
        except:
            logger.info(f"{BLUE}Not able to get MS AMI, continuing{ENDC}")
        
    async def getMrAmi(self, aiodash, net_id):
        try:
            result = await aiodash.wireless.getNetworkWirelessAlternateManagementInterface((net_id))
            return result
        except:
            logger.info(f"{BLUE}Not able to get MR AMI, continuing{ENDC}")


    async def getVpnVlans(self, aiodash, net_id):
        try:
            result = await aiodash.appliance.getNetworkApplianceVpnSiteToSiteVpn(net_id)
            return result
        except meraki.exceptions.AsyncAPIError as e:
            logger.debug(f"{e}")


    async def getNetworkVlans(self, aiodash, net_id):
        try:
            result = await aiodash.appliance.getNetworkApplianceVlans(net_id)
            return result
        except meraki.exceptions.AsyncAPIError as e:
            logger.debug(f"{e}")


class Device(object):
    def __init__(self, device, net_obj):

        self.name = device['name']
        self.type = device['model'][:2]
        self._radius_address = None
        logger.debug(f"Device: {CYAN}{device}{ENDC}")

    def __repr__(self):
        return f"Device({self.name}, {self.type})"

    def __getitem__(self, key):
        return getattr(self, key)

    @property
    def radius_address(self):
        return self._radius_address

    @staticmethod
    def createDevice(device, net_obj):
        try:
            dev = device['model'][:2]
            if dev == "MR" or dev == "CW":
                return MRDevice(device, net_obj)
            elif dev == "MS":
                return MSDevice(device, net_obj)
            elif dev == "MX" or dev == "Z3" or dev == "Z4":
                return MXDevice(device, net_obj)
        except Exception as e:
            logger.debug(f"Error: {e}", exc_info=True)

    def check_ami(self, dev, net_obj):
        origdev = dev
        logger.debug(f"{PURPLE}check_ami() dev: {dev['name']}{ENDC}")
        if dev['model'][:2] == "MR":
            for wami in net_obj.mr_ami['accessPoints']:
                if dev['serial'] == wami['serial']:
                    logging.debug(f"{BLUE}{dev['name']} has AMI wami: {wami}{ENDC}")
                    dev['radius_address'] = wami['alternateManagementIp']
        elif dev['model'][:2] == "MS":
            for sami in net_obj.ms_ami['switches']:
                if dev['serial'] == sami['serial']:
                    logging.debug(f"{BLUE}{dev['name']} has AMI sami: {sami}{ENDC}")
                    dev['radius_address'] = sami['alternateManagementIp']
        if dev is not None:
            return dev
        else:
            return origdev


class MRDevice(Device):
    def __init__(self, device, net_obj):
        super().__init__(device, net_obj)
        
        if (net_obj.mr_ami and net_obj.mr_ami['enabled'] is True 
                and "radius" in net_obj.mr_ami['protocols']):
            device = self.check_ami(device, net_obj)

        if "radius_address" in device.keys():
                self._radius_address = device['radius_address']
        else:
            self._radius_address = device['lanIp']
        logger.info(f"{GREEN}Created {self.type} - {device['name']}{ENDC}")
        logger.info(f"{GREEN}RADIUS Address: {self._radius_address}{ENDC}")


class MSDevice(Device):
    def __init__(self, device, net_obj):
        super().__init__(device, net_obj)

        if (net_obj.ms_ami and net_obj.ms_ami['enabled'] is True 
                and "radius" in net_obj.ms_ami['protocols']):
            device = self.check_ami(device, net_obj)
        
        if 'radius_address' in device.keys():
            self._radius_address = device['radius_address']
        else:
            self._radius_address = device['lanIp']
            
        logger.info(f"{GREEN}Created {self.type} - {device['name']}{ENDC}")
        logger.info(f"{GREEN}RADIUS Address: {self._radius_address}{ENDC}")


class MXDevice(Device):
    def __init__(self, device, net_obj):
        super().__init__(device, net_obj)
        
        logger.info(f"{GREEN}Created {self.type} - {device['name']}{ENDC}")      

        vpn_vlans = net_obj.vpn_vlans

        if vpn_vlans['mode'] == "none":
            self._radius_address = device['wan1Ip']
            logger.debug(f"{BOLD}{GREEN}{self.type} VPN disabled{ENDC}")
        elif vpn_vlans['mode'] == "spoke":
            logger.debug(f"{BOLD}{GREEN}{self.type} VPN spoke mode{ENDC}")
            
            vpn_vlan = [
                subnet['localSubnet']
                for subnet in vpn_vlans['subnets']
                if subnet['useVpn'] == True
            ]

            net_vlans = net_obj.net_vlans

            radius_address = { 'id': 0 }

            if net_vlans is None:
                self._radius_address = device['wan1Ip']
            else:
                for nv in net_vlans:
                    for k, v in nv.items():
                        if v in vpn_vlan:
                            if nv['id'] > radius_address['id']:
                                radius_address['id'] = nv['id']
                                radius_address['ip'] = nv['applianceIp']
            
                self._radius_address = radius_address['ip']
        elif vpn_vlans['mode'] == "hub":
            logger.debug(f"{BOLD}{GREEN}{self.type} VPN hub mode{ENDC}")
            self._radius_address = device['wan1Ip']
        
        logger.info(f"{GREEN}RADIUS Address: {self._radius_address}{ENDC}")
        

async def main():
    async with meraki.aio.AsyncDashboardAPI(
        api_key=os.getenv("APIKEY"),
        base_url="https://api.meraki.com/api/v1",
        print_console=True,
        use_iterator_for_get_pages=True,
        suppress_logging=suppress_logging,
        inherit_logging_config=False,
        output_log=output_log,
        log_file_prefix=os.path.basename(__file__)[:-3],
        log_path=log_path,
        single_request_timeout=12,
        maximum_concurrent_requests=50,
        maximum_retries=100,
        wait_on_rate_limit=True,
    ) as aiodash:

        print("** Gathering Networks and Devices")

        async for org in getOrgs(aiodash, org_name=org_name, org_id=org_id):
            radius_devices = []
            devices = []

            async for dev in getOrgDevices(aiodash, org['id'], net_id=net_id):
                devices.append(dev)

            if devices:
                m_devices = {}
                for dev in devices:
                    if dev['model'][:2] in dev_types:
                        logger.debug(f"{GREEN}{dev}{ENDC}")
                        if dev['networkId'] not in m_devices.keys():
                            m_devices[dev['networkId']] = []
                        m_devices[dev['networkId']].append(dev)
                logger.debug(f"m_devices: {BLUE}{m_devices}{ENDC}")

            if m_devices:
                net_task = []
                async for net in getNetworks(aiodash, org['id'], net_name=net_name):
                    if net['id'] in m_devices:
                        await asyncio.sleep(0)
                        logger.debug(f"{BOLD}{BLUE}net: {net}{ENDC}")
                        net_task.append(Network.create(aiodash, net))

                for net_obj in asyncio.as_completed(net_task):
                    logger.debug(f"{BOLD}{CYAN}net_obj: {net_obj}{ENDC}")
                    await asyncio.sleep(0)
                    result = await net_obj
                    logger.debug(f"{PURPLE}{result}{ENDC}")
                    for dev in m_devices[result.net_id]:
                        radius_devices.append(Device.createDevice(dev, result))

            if radius_devices:
                logger.debug(f"{BOLD}{GREEN}{radius_devices}{ENDC}")
                
                for raddev in radius_devices:
                    logger.debug(f"{BOLD}{YELLOW}{raddev}{ENDC}")
                    print(f"{raddev.name:10} - {raddev.type:2} - {raddev.radius_address:}")

                if WRITE_CSV:
                    csv_writer(radius_devices)
            else:
                print(f"{RED}Unable to identify RADIUS eligible devices{ENDC}")


if __name__ == "__main__":
    start_time = datetime.now()
    parser = ArgumentParser(description="Select options.")
    parser.add_argument("-o", type = str,
                        default=None,
                        help = "Organization name for operation")
    parser.add_argument("-i", type = str,
                        default=None,
                        help = "Organization ID for operation")
    parser.add_argument("-n", type = str,
                        default=None,
                        help = "Network name for operation")
    # parser.add_argument("--tag",
    #                      type=str,
    #                      default=None,
    #                      help="Org or Network tag to use")
    parser.add_argument("--type", 
                        nargs="*",
                        type=str,
                        default=['MR', 'CW'],  
                        # types needs better parsing for Z devices and MR/CW
                        # maybe switch to wireless, appliance, switch?
                        choices=['MR', 'CW', 'MS', 'MX', 'Z3', 'Z4'],
                        help="Meraki device type")
    parser.add_argument("--csv", action = "store_true",
                        help = 'Write CSV file')
    parser.add_argument("--log", action = "store_true",
                        help = 'Log to file')
    parser.add_argument("-v", action = "store_true",
                        help = 'verbose')
    parser.add_argument("-d", action="store_true",
                        help="debug")
    args = parser.parse_args()

    logging.getLogger(__name__)
    logger = logging.getLogger(__name__)

    # # tag = args.tag # to be implemented
    dev_types = args.type

    if args.o and args.i:
        print(f"{RED}Specify either -o or -i, not both{ENDC}")
        sys.exit()
    elif args.o:
        org_name = args.o
        org_id = None
    elif args.i:
        org_id = args.i
        org_name = None
    else:
        print(f"{RED}Must define an Org with -o or -i option{ENDC}")
        sys.exit()

    if args.v or args.d:
        logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            fmt="%(asctime)s %(name)12s: %(levelname)8s > %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        handler_console = logging.StreamHandler()
        handler_console.setFormatter(formatter)

        if args.v:
            handler_console.setLevel(logging.INFO)
        else:
            handler_console.setLevel(logging.DEBUG)

        logger.addHandler(handler_console)
        logger.propagate = False

    if args.csv:
        WRITE_CSV = True
    else:
        WRITE_CSV = False

    log_path = os.path.join(os.getcwd(), "log")
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    if args.log:
        suppress_logging = False
        output_log = True
    elif args.v or args.d:
        suppress_logging = False
        output_log = False
    else:
        suppress_logging = True
        output_log = False

    # if args.tag:
    #     target_tag = args.tag

    if args.n:
        net_name = args.n
        net_id = None
    else:
        net_name = None
        net_id = None

    asyncio.run(main())
    end_time = datetime.now()
    print(f"Script complete, total runtime {end_time - start_time}")
