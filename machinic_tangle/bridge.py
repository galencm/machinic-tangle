#!/usr/bin/python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import os
import sys
import redis
import paho.mqtt.client as mosquitto 
import sys

class Bridge(object):
    def __init__(self, db_host, db_port, broker_host, broker_port):
        db_settings = {"host" :  db_host, "port" : db_port}
        self.binary_r = redis.StrictRedis(**db_settings)
        self.redis_conn = redis.StrictRedis(**db_settings, decode_responses=True)

        self.broker_client = mosquitto.Client()
        self.broker_client.on_message = self.on_message
        sub_topics = "#"
        self.broker_client.connect(broker_port, broker_host, 60)
        self.broker_client.subscribe(sub_topics, 0)
        self.broker_client.loop_start()

    def on_message(self, mosq, obj, msg):
        # self.decide_routing(msg.topic, msg.payload)
        self.redis_conn.publish(msg.topic, msg.payload)
