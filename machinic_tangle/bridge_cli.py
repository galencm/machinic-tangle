# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import argparse
import redis
from machinic_tangle import bridge
import time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-host",  default="127.0.0.1", help="db host ip")
    parser.add_argument("--db-port", type=int, default=6379, help="db port")
    parser.add_argument("--broker-host",  default="127.0.0.1", help="broker host ip")
    parser.add_argument("--broker-port", type=int, default=1883, help="broker port")
    parser.add_argument("--allow-shell-calls", action="store_true", help="allow ling shell calls")
    parser.add_argument("--verbose", action="store_true", help="")
    args = parser.parse_args()
    print(args.db_host, args.db_port, args.broker_host, args.broker_port)
    b = bridge.Bridge(args.db_host, args.db_port, args.broker_host, args.broker_port, allow_shell_calls=args.allow_shell_calls)
    while True:
        time.sleep(0.1)
