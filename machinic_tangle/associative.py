#!/usr/bin/python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import time
import subprocess
import sys
import argparse
import fnmatch
import netifaces
import jinja2
import json

# modified from associative.py in machinic-core


def scan_loop(iface, template=None, template_vars=None, patterns=None, rate=5):
    if patterns is None:
        patterns = "*"

    while True:
        essids = scan(iface)
        for pattern in patterns:
            for match_ssid in fnmatch.filter(essids, pattern):
                payload = (
                    jinja2.Environment().from_string(template).render(template_vars)
                )
                print("{} {}".format(match_ssid, pattern))
                print("preparing to associate...")
                associate(iface, match_ssid, payload)
        time.sleep(rate)


def scan(scan_iface):
    interfaces = netifaces.interfaces()
    wifi_ifaces = [iface for iface in interfaces if scan_iface == iface]
    found_essids = []

    for iface in wifi_ifaces:
        found = []
        print("{} scanning...".format(iface))
        found = subprocess.check_output(["sudo", "iwlist", iface, "scan"])
        found = [
            ssid.split('"')[1] for ssid in str(found).split("\\n") if "ESSID" in ssid
        ]

        print("{} found ssids: {}".format(iface, found))
        found_essids.extend(found)
    return found_essids


def associate(iface, essid, payload, delay=5, retries=None):
    # Send on association

    # currently nmcli works much better than iwconfig/dhclient
    # however it is not as portable as iwconfig/dhclient, so
    # worth improving more general / portable approaches
    #
    # see commented code block at below

    try:
        print(
            subprocess.check_output(
                "nmcli dev wifi connect {}".format(essid).split(" ")
            )
        )
        send(iface, payload)
    except Exception as ex:
        print(ex)
        # early code would continuously retry without a retries kwarg
        # if an ssid is not found it led to endless loop of calling associate
        if retries is not None and retries > 0:
            print("retry: {}".format(retries))
            retries -= 1
            time.sleep(delay)
            associate(iface, essid, payload, retries=retries)

    # # print("diassociating {} before associating".format(iface))
    # # subprocess.check_output(['sudo','iwconfig',iface,'ap','00:00:00:00:00:00'])
    # print("connecting to {}".format(essid))
    # try:
    #     print(subprocess.check_output(['sudo', 'iwconfig', iface, 'essid', '{}'.format(essid)]))
    #     print("sleeping for {} seconds".format(delay))
    #     time.sleep(delay)
    #     # -r prevents 'dhclient() is already running - exiting.'
    #     # but releases all other leases too..
    #     try:
    #         print(subprocess.check_output(['sudo', 'dhclient', '-1', iface, '-v', '-r']))
    #     except:
    #         print("no dhcp lease retrying...")
    #         associate(iface, essid, payload)
    #     try:
    #         iface_ip = netifaces.ifaddresses(iface)[2][0]['addr']
    #     except KeyError:
    #         print("no ip received retrying...")
    #         print(netifaces.ifaddresses(iface))
    #         associate(iface, essid, payload)
    # except:
    #     # send payload
    #     send(iface, payload)


def send(iface, payload, post_send_delay=5):
    iface_ip = netifaces.ifaddresses(iface)[2][0]["addr"]
    # assume ap ip ends with .1
    ap_ip = iface_ip.rsplit(".", 1)[0] + ".1"
    # logger.info("connected to {} with ip {}".format(essid,iface_ip))
    print("ap ip assumed to be {}".format(ap_ip))
    # url is homie specific and should be templated
    print("payload: ", payload)
    response = subprocess.check_output(
        [
            "curl",
            "-X",
            "PUT",
            "http://{}/config".format(ap_ip),
            "--header",
            "Content-Type:",
            "application/json",
            "-d",
            "{}".format(json.dumps(json.loads(payload))),
        ]
    )
    print("response: ", response.decode())
    # b'{"success":false,"error":"Invalid or too big JSON"}'
    # {"success":true}
    print("diassociating {}".format(iface))
    subprocess.check_output(["sudo", "iwconfig", iface, "ap", "00:00:00:00:00:00"])
    # give device change to reconfigure
    time.sleep(post_send_delay)


def main():
    parser = argparse.ArgumentParser(
        description=main.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("interface", help="wireless iface")
    parser.add_argument("--template", help="template json")
    parser.add_argument(
        "--template-vars",
        nargs="+",
        default=[],
        help="template vars (key value key value)",
    )

    args = parser.parse_args()
    template_vars = dict(zip(args.template_vars[:-1:2], args.template_vars[1::2]))
    print(template_vars)
    scan_loop(args.interface, args.template, template_vars)
