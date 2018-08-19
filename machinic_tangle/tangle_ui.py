# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import argparse
import atexit
import attr
import redis
import subprocess
import json
import pathlib
import fnmatch
from ma_cli import data_models

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.properties import BooleanProperty

r_ip, r_port = data_models.service_connection()
binary_r = redis.StrictRedis(host=r_ip, port=r_port)
redis_conn = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)

# write and store mqtt.conf in /tmp
# need ip and bind

@attr.s
class Service(object):
    name = attr.ib()
    args = attr.ib(default=attr.Factory(list))
    kwargs = attr.ib(default=attr.Factory(dict))
    with_sudo = attr.ib(default=False)

class ServiceItem(BoxLayout):
    def __init__(self, name, app=None, *args, **kwargs):
        self.service = Service(name)
        self.app = app
        super(ServiceItem, self).__init__()
        process_row = BoxLayout(height=30, size_hint_y=None)
        run_process_check = CheckBox()
        run_process_check.bind(active=self.toggle_process)
        process_row.add_widget(run_process_check)
        process_row.add_widget(Label(text=str(name)))
        self.add_widget(process_row)

    def toggle_process(self, widget, value):
        if value:
            self.app.run_process(self.service.name)
        else:
            self.app.stop_process(self.service.name)

class SsidMap(BoxLayout):
    def __init__(self, ssid_source=None, app=None, *args, **kwargs):
        self.ssid_source = ssid_source
        super(SsidMap, self).__init__()
        self.ssid_container = BoxLayout(orientation="vertical")
        self.add_widget(self.ssid_container)

    def update_ssids(self, ssids):
        try:
            highlight_patterns = self.ssid_source.associate_patterns
        except:
            highlight_patterns = []
        self.ssid_container.clear_widgets()
        for ssid in ssids:
            background_color = [.5, .5, .5, 1]
            for pattern in highlight_patterns:
                if fnmatch.fnmatch(ssid, pattern):
                    background_color = [0, 1, 0, 1]
            self.ssid_container.add_widget(Button(text=str(ssid), background_color=background_color))

class WirelessDetails(BoxLayout):
    def __init__(self, app=None, *args, **kwargs):
        self.associate_patterns = ["homie-*"]
        self.associate_template = ""
        self.associate_template_file = "homie_associate.json"
        super(WirelessDetails, self).__init__()
        self.discovered_ssids = SsidMap()
        self.template_input = TextInput()
        self.add_widget(self.template_input)
        self.load_template(self.associate_template_file)
        self.ssid_map = SsidMap(ssid_source=self)
        self.add_widget(self.ssid_map)
        self.ssid_map.update_ssids([])

    def load_template(self, file):
        self.associate_template = pathlib.Path(pathlib.PurePath(pathlib.Path(__file__).parents[0], file)).read_text()
        print(self.associate_template)
        self.template_input.text = self.associate_template

class TangleApp(App):
    def __init__(self, *args, **kwargs):
        # store kwargs to passthrough
        self.kwargs = kwargs
        self.processes = {}
        self.services = ["mosquitto", "create_ap", "bridge"]
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
        service_container = BoxLayout(orientation="vertical")
        for service in self.services:
            service_container.add_widget(ServiceItem(service, app=self))
        root.add_widget(service_container)
        root.add_widget(WirelessDetails())
        return root

    def run_process(self, process_name, process_args=None):
        self.stop_process(process_name)
        self.processes[process_name] = self.process_in_subprocess(process_name, process_args)

    def process_in_subprocess(self, process, process_args=None):
        print("running", process)
        if process_args is None:
            process_args = []
        process_call = [process, *process_args]
        p = subprocess.Popen(process_call)
        return p

    def handle_db_events(self, message):
        msg = message["channel"].replace("__keyspace@0__:","")
        # if msg in ():
        #     Clock.schedule_once(lambda dt: self.update_env_values(), .1)

    def stop_process(self, name=None):
        if name is None:
            for p, p_pid in self.processes.items():
                p_pid.terminate()
                p_pid.kill()
        else:
            try:
                self.processes[name].kill()
                self.processes[name].terminate()
            except:
                pass

    def on_stop(self):
        # stop pubsub thread if window closed with '[x]'
        self.db_event_subscription.thread.stop()
        self.stop_process()

    def app_exit(self):
        self.db_event_subscription.thread.stop()
        self.stop_process()
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
