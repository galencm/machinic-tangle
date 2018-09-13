#!/usr/bin/python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import os
import sys
import subprocess
import pathlib
import redis
import paho.mqtt.client as mosquitto
from textx.metamodel import metamodel_from_file


class Bridge(object):
    def __init__(
        self,
        db_host,
        db_port,
        broker_host,
        broker_port,
        env_vars=None,
        allow_shell_calls=False,
    ):
        self.routing_ling = "pathling"
        self.routes_key = "machinic:routes:{}:{}".format(db_host, db_port)
        self.env_vars = env_vars
        self.allow_shell_calls = allow_shell_calls
        self.pathling_model_file = pathlib.Path(
            pathlib.PurePath(pathlib.Path(__file__).parents[0], "pathling.tx")
        )
        self.pathling_metamodel = metamodel_from_file(self.pathling_model_file)
        db_settings = {"host": db_host, "port": db_port}
        self.binary_r = redis.StrictRedis(**db_settings)
        self.redis_conn = redis.StrictRedis(**db_settings, decode_responses=True)

        self.broker_client = mosquitto.Client()
        self.broker_client.on_message = self.on_message
        sub_topics = "#"
        self.broker_client.connect(broker_host, broker_port, 60)
        self.broker_client.subscribe(sub_topics, 0)
        self.broker_client.loop_start()

    def on_message(self, mosq, obj, msg):
        self.routing(msg.topic, msg.payload)

    def routing(self, channel, message):
        routes = self.redis_conn.hgetall(self.routes_key)
        substitutions = {}
        try:
            substitutions.update(self.env_vars())
        except:
            pass
        message = message.decode()
        substitutions["$message"] = message
        substitutions["$channel"] = channel
        for route_hash, route in routes.items():
            try:
                path = self.pathling_metamodel.model_from_str(route)
                print(path.munge)
                try:
                    # try to do substitutions
                    message = path.munge.template
                    for k, v in substitutions.items():
                        message = message.replace(str(k), str(v))
                        print(message)
                except Exception as ex:
                    print(ex)
                if path.source == channel:
                    if path.send_as == "->":
                        # publish
                        self.redis_conn.publish(path.destination, message)
                    elif path.send_as == ">>":
                        # set key
                        if isinstance(path.destination, str):
                            self.redis_conn.set(path.destination, message)
                        else:
                            self.redis_conn.hmset(
                                path.destination.name, {path.destination.field: message}
                            )
                    elif path.send_as == "--":
                        if self.allow_shell_calls:
                            # strip trailing spaces that may cause subprocess call problems
                            path.destination.call = path.destination.call.strip(" ")
                            path.destination.args = [
                                arg.strip(" ") for arg in path.destination.args
                            ]
                            print("sub dict: ", substitutions)
                            print(
                                "shell call (pre-sub):",
                                path.destination.call,
                                path.destination.args,
                            )
                            # substitutions for shell call and args
                            for k, v in substitutions.items():
                                path.destination.call = path.destination.call.replace(
                                    str(k), str(v)
                                )
                                for i, shell_param in enumerate(path.destination.args):
                                    path.destination.args[i] = shell_param.replace(
                                        str(k), str(v)
                                    )
                            print(
                                "shell call (post-sub):",
                                path.destination.call,
                                path.destination.args,
                            )

                            if "NonblockingCall" in str(path.destination):
                                subprocess.Popen(
                                    [path.destination.call, *path.destination.args]
                                )
                            elif "BlockingCall" in str(path.destination):
                                subprocess.Call(
                                    [path.destination.call, *path.destination.args]
                                )
                        else:
                            print("routing does not allow shell calls")
                            print(path.destination.call, path.destination.args)
            except Exception as ex:
                print(ex)
                pass
