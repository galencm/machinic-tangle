# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import argparse
import atexit

import redis
from ma_cli import data_models

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button

r_ip, r_port = data_models.service_connection()
binary_r = redis.StrictRedis(host=r_ip, port=r_port)
redis_conn = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)

class TangleApp(App):
    def __init__(self, *args, **kwargs):
        # store kwargs to passthrough
        self.kwargs = kwargs
        if kwargs["db_host"] and kwargs["db_port"]:
            global binary_r
            global redis_conn
            db_settings = {"host" :  kwargs["db_host"], "port" : kwargs["db_port"]}
            binary_r = redis.StrictRedis(**db_settings)
            redis_conn = redis.StrictRedis(**db_settings, decode_responses=True)

        self.db_port = redis_conn.connection_pool.connection_kwargs["port"]
        self.db_host = redis_conn.connection_pool.connection_kwargs["host"]

        super(TangleApp, self).__init__()

    def build(self):
        root = BoxLayout()
        self.db_event_subscription = redis_conn.pubsub()
        self.db_event_subscription.psubscribe(**{'__keyspace@0__:*': self.handle_db_events})
        # add thread to pubsub object to stop() on exit
        self.db_event_subscription.thread = self.db_event_subscription.run_in_thread(sleep_time=0.001)
        return root

    def handle_db_events(self, message):
        msg = message["channel"].replace("__keyspace@0__:","")
        # if msg in ():
        #     Clock.schedule_once(lambda dt: self.update_env_values(), .1)

    def on_stop(self):
        # stop pubsub thread if window closed with '[x]'
        self.db_event_subscription.thread.stop()

    def app_exit(self):
        self.db_event_subscription.thread.stop()
        App.get_running_app().stop()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-key",  help="db hash key")
    parser.add_argument("--db-key-field",  help="db hash field")

    parser.add_argument("--db-host",  help="db host ip, requires use of --db-port")
    parser.add_argument("--db-port", type=int, help="db port, requires use of --db-host")
    args = parser.parse_args()

    if bool(args.db_host) != bool(args.db_port):
        parser.error("--db-host and --db-port values are both required")

    app = TangleApp(**vars(args))
    #atexit.register(app.save_session)
    app.run()
