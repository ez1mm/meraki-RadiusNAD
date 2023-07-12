# meraki-RadiusNAD
Meraki RADIUS NAD Tool - Generate a list of IP addresses to use with your NAC.
Displays list of IP addresses or output to CSV.

## Overview

Generates IP address for MR / CW / MS / MX / Z3 / Z4 devices, following Alternate Management Interfaces and MX rules for determining the proper IP address when necessary.

https://documentation.meraki.com/MR/Other_Topics/Alternate_Management_Interface_on_MR_Devices
https://documentation.meraki.com/MS/Other_Topics/Alternate_Management_Interface_on_MS_Devices
https://documentation.meraki.com/MX/Other_Topics/MX_and_Z3_Source_IP_for_RADIUS_Authentication

## Installation
### Clone and setup
```
git clone https://github.com/ez1mm/meraki-RadiusNAD && cd meraki_scripts
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Usage
### Set API key
```bash
export APIKEY=<apikey>
```

### Options
`mernad.py` Meraki RADIUS NAD Tool
```
usage: mernad.py [-h] [-o O] [-n N] [--type [{MR,CW,MS,MX,Z3,Z4} ...]]
                 [--csv] [--log] [-v] [-d]

Select options.

options:
  -h, --help            show this help message and exit
  -o O                  Organization name for operation
  -n N                  Network name for operation (optional)
  --type [{MR,CW,MS,MX,Z3,Z4} ...]
                        Meraki device type
  --csv                 Write CSV file
  --log                 Log to file
  -v                    verbose
  -d                    debug
```

You must provide an Organization (-o) as an option, if you provide a Network name (-n) only that network will be parsed, if you do not specify a network, all eligible Networks in the Organization will be parsed.

## Example
```
python mernad.py -o MY_ORG --type MR MS --csv
** Gathering Networks and Devices
MR56-1     - MR - 172.19.200.139
MR42       - MR - 10.200.4.8
MS355      - MS - 10.10.50.108
MS120      - MS - 10.10.10.4
MR57-1     - MR - 10.10.10.66
MS390      - MS - 10.10.10.200
** Writing /Users/username/code/meraki-RadiusNAD/output/report_20230712-151005.csv
Script complete, total runtime 0:00:08.772073
```

## TODO
* Auto import devices in to Cisco ISE
* Output CSV following NAC standard template for common NACs
