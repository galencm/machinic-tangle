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
import time
import pathlib
import fnmatch
import hashlib
import threading
import jinja2
import shutil
import operator
import paho.mqtt.client as mosquitto
import paho.mqtt.publish
from textx.metamodel import metamodel_from_file
import netifaces
from ma_cli import data_models
from machinic_tangle import associative
from machinic_tangle import bridge

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.properties import BooleanProperty
from kivy.uix.dropdown import DropDown

r_ip, r_port = data_models.service_connection()
binary_r = redis.StrictRedis(host=r_ip, port=r_port)
redis_conn = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)

# write and store mqtt.conf in /tmp
# need ip and bind


class DropDownInput(TextInput):
    def __init__(self, preload=None, preload_attr=None, preload_clean=True, **kwargs):
        self.multiline = False
        self.drop_down = DropDown()
        self.drop_down.bind(on_select=self.on_select)
        self.bind(on_text_validate=self.add_text)
        self.preload = preload
        self.preload_attr = preload_attr
        self.preload_clean = preload_clean
        self.not_preloaded = set()
        super(DropDownInput, self).__init__(**kwargs)
        self.add_widget(self.drop_down)

    def add_text(self, *args):
        if args[0].text not in [
            btn.text
            for btn in self.drop_down.children[0].children
            if hasattr(btn, "text")
        ]:
            btn = Button(text=args[0].text, size_hint_y=None, height=44)
            self.drop_down.add_widget(btn)
            btn.bind(on_release=lambda btn: self.drop_down.select(btn.text))
            if "preload" not in args:
                self.not_preloaded.add(btn)

    def on_select(self, *args):
        self.text = args[1]
        if args[1] not in [
            btn.text
            for btn in self.drop_down.children[0].children
            if hasattr(btn, "text")
        ]:
            self.drop_down.append(Button(text=args[1]))
            # self.not_preloaded.add(btn)
        # call on_text_validate after selection
        # to avoid having to select textinput and press enter
        self.dispatch("on_text_validate")

    def on_touch_down(self, touch):
        preloaded = set()
        if self.preload:
            for thing in self.preload:
                if self.preload_attr:
                    # use operator to allow dot access of attributes
                    thing_string = str(operator.attrgetter(self.preload_attr)(thing))
                else:
                    thing_string = str(thing)
                self.add_text(Button(text=thing_string), "preload")
                preloaded.add(thing_string)

        # preload_clean removes entries that
        # are not in the preload source anymore
        if self.preload_clean is True:
            added_through_widget = [
                btn.text for btn in self.not_preloaded if hasattr(btn, "text")
            ]
            for btn in self.drop_down.children[0].children:
                try:
                    if (
                        btn.text not in preloaded
                        and btn.text not in added_through_widget
                    ):
                        self.drop_down.remove_widget(btn)
                except Exception as ex:
                    pass

        return super(DropDownInput, self).on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.grab_current == self:
            self.drop_down.open(self)
        return super(DropDownInput, self).on_touch_up(touch)


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
        self.app = app
        super(SsidMap, self).__init__()
        self.ssid_container = BoxLayout(orientation="vertical")
        self.ssid_list = TextInput()
        self.ssid_container.add_widget(self.ssid_list)
        self.add_widget(self.ssid_container)

    def update_ssids(self, ssids):
        try:
            highlight_patterns = self.ssid_source.associate_patterns
        except Exception as ex:
            highlight_patterns = []
        self.ssid_list.text = ""
        for ssid in ssids:
            for pattern in highlight_patterns:
                if fnmatch.fnmatch(ssid.lower(), pattern.lower()):
                    # on match
                    # render template, connect, send
                    template_vars = {}
                    template_vars["device_name"] = "foo"
                    template_vars["device_id"] = "foo"
                    template_vars["ssid"] = self.ssid_source.config_vars["ap_ssid"]
                    template_vars["ssid_pass"] = self.ssid_source.config_vars["ap_pass"]
                    template_vars[
                        "mqtt_host"
                    ] = (
                        self.ssid_source.ap_ip
                    )  # "192.168.12.1" # ap0 iface inet address
                    template_vars["mqtt_port"] = 1883
                    template = (
                        jinja2.Environment()
                        .from_string(self.ssid_source.template_input.text)
                        .render(template_vars)
                    )
                    try:
                        associative.associate(
                            self.ssid_source.scan_iface, ssid, template, retries=5
                        )
                    except Exception as ex:
                        pass
            self.ssid_list.text += "{}\n".format(ssid)


class BrokerService(BoxLayout):
    def __init__(self, app=None, allow_shell_calls=False, *args, **kwargs):
        self.config_vars = {}
        self.config_vars["mqtt_port"] = 1883
        self.config_vars["mqtt_host"] = "127.0.0.1"
        self.config_location = "/tmp"
        self.config_file = "mosquitto.conf"
        self.config_template = "mosquitto.conf"
        self.process_name = "mosquitto"
        self.app = app
        self.update_config()
        # start mosquitto with config file
        # config file is needed to specify listener port
        self.create_broker()
        # add slight delay before connecting client
        time.sleep(0.5)
        # connect a client
        self.create_client()
        super(BrokerService, self).__init__()
        # start a bridge
        b = bridge.Bridge(
            self.app.db_host,
            self.app.db_port,
            self.config_vars["mqtt_host"],
            self.config_vars["mqtt_port"],
            env_vars=self.env_vars,
            allow_shell_calls=allow_shell_calls,
        )
        print(b)

    def env_vars(self):
        env = {}
        env["$DB_PORT"] = self.app.db_port
        env["$DB_HOST"] = self.app.db_host
        return env

    def create_broker(self):
        # stop any existing if updating
        try:
            self.app.stop_process(self.process_name)
        except Exception as ex:
            pass
        self.app.run_process(
            self.process_name,
            ["-c", str(pathlib.Path(self.config_location, self.config_file))],
        )

    def create_client(self):
        # clear existing in case connection
        # parameters have changed
        try:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            del self.mqtt_client
        except Exception as ex:
            pass
        # create client
        self.mqtt_client = mosquitto.Client()
        # handle in app to update text display
        self.mqtt_client.on_message = self.app.on_mqtt_message
        self.mqtt_client.connect(
            self.config_vars["mqtt_host"], int(self.config_vars["mqtt_port"]), 60
        )
        # subscribe to everything after connect
        self.mqtt_client.subscribe("#", 0)
        self.mqtt_client.loop_start()

    def update_config(self, overwrite=False):
        config = pathlib.Path(self.config_location, self.config_file)
        template = pathlib.Path(
            pathlib.PurePath(pathlib.Path(__file__).parents[0], self.config_template)
        ).read_text()
        template = jinja2.Environment().from_string(template).render(self.config_vars)
        if not config.is_file() or overwrite is True:
            with config.open("w+") as f:
                f.write(template)


class AccessPointConfig(BoxLayout):
    def __init__(self, app=None, *args, **kwargs):
        self.orientation = "vertical"
        self.interfaces = []
        self.app = app
        super(AccessPointConfig, self).__init__()
        self.ssid_input = TextInput(height=30, size_hint_y=None, multiline=False)
        self.pass_input = TextInput(height=30, size_hint_y=None, multiline=False)

        # netifaces will detect even if interface is deactivated
        wireless_interfaces = [
            iface for iface in netifaces.interfaces() if iface.startswith("w")
        ]
        self.scan_ifaces = DropDownInput(
            preload=wireless_interfaces, height=30, size_hint_y=None
        )
        self.scan_ifaces.bind(
            on_text_validate=lambda widget: self.app.wireless_details.update_scan(
                widget.text
            )
        )
        self.ap_ifaces = DropDownInput(
            preload=wireless_interfaces, height=30, size_hint_y=None
        )
        self.ap_ifaces.bind(
            on_text_validate=lambda widget: self.app.wireless_details.update_ap(
                widget.text, self.ssid_input.text, self.pass_input.text
            )
        )

        # set default text
        self.scan_ifaces.text = "wls1"
        self.ap_ifaces.text = "wlp0s26f7u1"
        self.ssid_input.text = "foo"
        self.pass_input.text = "bar_bar_"

        for label, widget in (
            ("ssid", self.ssid_input),
            ("password", self.pass_input),
            ("scan interface", self.scan_ifaces),
            ("ap interface", self.ap_ifaces),
        ):
            row = BoxLayout(height=30, size_hint_y=None)
            row.add_widget(Label(text=label))
            row.add_widget(widget)
            self.add_widget(row)


class PathlingWidget(BoxLayout):
    def __init__(self, app=None, *args, **kwargs):
        self.orientation = "vertical"
        self.app = app
        self.routes_key = "machinic:routes:{}:{}".format(app.db_host, app.db_port)
        super(PathlingWidget, self).__init__()
        self.add_widget(Label(text="routes:", height=30, size_hint_y=None))
        self.route_input = TextInput()
        self.route_add = Button(text="update routes", height=30, size_hint_y=None)
        self.route_add.bind(on_press=lambda widget: self.update_routes())
        self.add_widget(self.route_input)
        self.add_widget(self.route_add)

        test_row = BoxLayout(height=30, size_hint_y=None, orientation="horizontal")
        self.add_widget(
            Label(text="broker test [channel | message]", height=30, size_hint_y=None)
        )
        for widget in ("test_channel", "test_message"):
            input_widget = TextInput(multiline=False)
            setattr(self, widget, input_widget)
            test_row.add_widget(input_widget)
        self.test_channel.bind(
            on_text_validate=lambda widget: self.channel_test(
                self.test_channel.text, self.test_message.text
            )
        )
        self.test_message.bind(
            on_text_validate=lambda widget: self.channel_test(
                self.test_channel.text, self.test_message.text
            )
        )
        self.add_widget(test_row)
        self.pathling_model_file = pathlib.Path(
            pathlib.PurePath(pathlib.Path(__file__).parents[0], "pathling.tx")
        )
        self.pathling_metamodel = metamodel_from_file(self.pathling_model_file)
        self.fetch_routes()

    def channel_test(self, channel, message):
        paho.mqtt.publish.single(channel, message, hostname="127.0.0.1", port=1883)

    def update_routes(self):
        updated = []
        for route in self.route_input.text.split("\n"):
            # print(route)
            if route.startswith("-"):
                # flagged to delete
                self.remove_route(route)
            elif not route.startswith("#"):
                try:
                    # validate path
                    self.pathling_metamodel.model_from_str(route)
                    self.add_route(route)
                except Exception as ex:
                    print(ex)
                    # comment out invalid routes
                    # and add error as comment beneath
                    route = "#" + route
                    route += "\n#{}".format(ex)
                updated.append(route)
        self.route_input.text = "\n".join(updated)
        self.fetch_routes

    def remove_route(self, route):
        if route.startswith("-"):
            route = route.split("-", 1)[-1].strip()
        route_hash = hashlib.sha224(route.encode()).hexdigest()
        redis_conn.hdel(self.routes_key, route_hash)

    def add_route(self, route):
        route_hash = hashlib.sha224(route.encode()).hexdigest()
        redis_conn.hmset(self.routes_key, {route_hash: route})

    def fetch_routes(self):
        db_routes = redis_conn.hgetall(self.routes_key)
        for _, route in db_routes.items():
            if route not in self.route_input.text.split("\n"):
                self.route_input.text += route + "\n"


class WirelessDetails(BoxLayout):
    def __init__(self, app=None, *args, **kwargs):
        self.orientation = "vertical"
        self.app = app
        self.associate_patterns = ["homie-*"]
        self.associate_template = ""
        self.associate_template_file = "homie_associate.json"
        super(WirelessDetails, self).__init__()
        self.template_input = TextInput()
        self.ssid_map = SsidMap(ssid_source=self, app=self.app)
        self.add_widget(Label(text="scanned ssids:", height=30, size_hint_y=None))
        self.add_widget(self.ssid_map)
        self.connected_clients = TextInput()
        self.connected_to_ap = TextInput()
        self.add_widget(Label(text="ap", height=30, size_hint_y=None))
        self.add_widget(self.connected_clients)
        self.add_widget(Label(text="ap connections", height=30, size_hint_y=None))
        self.add_widget(self.connected_to_ap)
        self.add_widget(Label(text="template:", height=30, size_hint_y=None))
        self.add_widget(self.template_input)
        self.load_template(self.associate_template_file)
        self.scan_iface = "wls1"
        self.config = BoxLayout(orientation="vertical")
        # scan for aps in a thread so it does not block ui
        self.scheduled_scan = Clock.schedule_interval(
            lambda foo: threading.Thread(target=self.scan_aps).start(), int(10)
        )
        # create_ap process
        # sudo means than a password prompt appears in terminal
        self.config_vars = {}
        self.config_vars["ap_wifi_iface"] = "wlp0s26f7u1"
        self.config_vars["ap_ssid"] = "foo"
        self.config_vars["ap_pass"] = "bar_bar_"
        self.config_vars["ap_virtual_iface"] = "ap0"
        self.create_ap()
        self.scheduled_check = Clock.schedule_interval(
            lambda foo: self.check_connected(), int(5)
        )

    def update_scan(self, iface):
        self.scan_iface = iface

    def update_ap(self, iface, ssid, ssid_pass):
        self.config_vars["ap_wifi_iface"] = iface
        self.config_vars["ap_ssid"] = ssid
        self.config_vars["ap_pass"] = ssid_pass
        self.create_ap()

    @property
    def ap_ip(self):
        iface = self.config_vars["ap_virtual_iface"]
        iface_ip = netifaces.ifaddresses(iface)[2][0]["addr"]
        return iface_ip

    def create_ap(self):
        # stop any existing create_ap instances
        # since if previous process was not terminaled
        # create_ap will increment virtual interfaces
        # on the same wifi card ie ap0 ap1
        try:
            running_aps = subprocess.check_output(
                ["create_ap", "--list-running"]
            ).decode()
        except Exception as ex:
            running_aps = ""

        if running_aps:
            pids = []
            for line in running_aps.split("\n"):
                for word in line.split(" "):
                    try:
                        pids.append(int(word))
                    except Exception as ex:
                        pass

            # sudo causes password prompt in terminal
            for pid in pids:
                print(
                    subprocess.check_output(
                        ["sudo", "create_ap", "--stop", str(pid)]
                    ).decode()
                )

        self.app.run_process(
            "sudo",
            "create_ap -n {ap_wifi_iface} {ap_ssid} {ap_pass}".format_map(
                self.config_vars
            ).split(),
        )

    def scan_aps(self):
        found = associative.scan(self.scan_iface)
        self.ssid_map.update_ssids(found)

    def load_template(self, file):
        self.associate_template = pathlib.Path(
            pathlib.PurePath(pathlib.Path(__file__).parents[0], file)
        ).read_text()
        print(self.associate_template)
        self.template_input.text = self.associate_template

    def check_connected(self):
        running_aps = subprocess.check_output(["create_ap", "--list-running"]).decode()
        pids = []
        for line in running_aps.split("\n"):
            for word in line.split(" "):
                try:
                    pids.append(int(word))
                except Exception as ex:
                    pass

        self.connected_clients.text = ""
        for pid in pids:
            try:
                connected_clients = subprocess.check_output(
                    ["create_ap", "--list-clients", str(pid)]
                ).decode()
                print(connected_clients)
                self.connected_clients.text += connected_clients
            except Exception as ex:
                # not a pid
                pass

        threading.Thread(target=self.enumerate_connected).start()

    def enumerate_connected(self):
        try:
            self.connected_to_ap.text = subprocess.check_output(
                "nmap -sP {ap_ip}/24".format(ap_ip=self.ap_ip).split()
            ).decode()
        except Exception as ex:
            print(ex)


class TangleApp(App):
    def __init__(self, *args, **kwargs):
        # store kwargs to passthrough
        self.kwargs = kwargs
        self.processes = {}
        self.allow_shell_calls = False
        if kwargs["allow_shell_calls"]:
            self.allow_shell_calls = True
        if kwargs["db_host"] and kwargs["db_port"]:
            global binary_r
            global redis_conn
            db_settings = {"host": kwargs["db_host"], "port": kwargs["db_port"]}
            binary_r = redis.StrictRedis(**db_settings)
            redis_conn = redis.StrictRedis(**db_settings, decode_responses=True)

        self.db_port = redis_conn.connection_pool.connection_kwargs["port"]
        self.db_host = redis_conn.connection_pool.connection_kwargs["host"]

        super(TangleApp, self).__init__()

    def build(self):
        root = BoxLayout()
        self.db_event_subscription = redis_conn.pubsub()
        # subscribe to everything
        self.db_event_subscription.psubscribe(**{"*": self.handle_db_events})
        # add thread to pubsub object to stop() on exit
        self.db_event_subscription.thread = self.db_event_subscription.run_in_thread(
            sleep_time=0.001
        )
        input_container = BoxLayout(orientation="vertical")
        input_container.add_widget(PathlingWidget(app=self))
        input_container.add_widget(AccessPointConfig(app=self))
        root.add_widget(input_container)
        self.wireless_details = WirelessDetails(app=self)
        root.add_widget(self.wireless_details)
        view_container = BoxLayout(orientation="vertical")
        root.add_widget(view_container)
        self.views = {}
        self.views["redis"] = TextInput()
        self.views["mqtt"] = TextInput()
        for view_name, view in self.views.items():
            view_container.add_widget(
                Label(text=view_name, height=30, size_hint_y=None)
            )
            view_container.add_widget(view)
        self.broker_service = BrokerService(app=self, allow_shell_calls=self.allow_shell_calls)

        return root

    def on_mqtt_message(self, client, userdata, message):
        # print("{} {}".format(message.topic, message.payload.decode()))
        try:
            Clock.schedule_once(
                lambda dt: self.update_view(
                    "mqtt",
                    "topic: {} contents: {}".format(
                        message.topic, message.payload.decode()
                    ),
                ),
                .01,
            )
        except Exception as ex:
            print(ex)

    def run_process(self, process_name, process_args=None):
        self.stop_process(process_name)
        self.processes[process_name] = self.process_in_subprocess(
            process_name, process_args
        )

    def process_in_subprocess(self, process, process_args=None):
        print("running", process, process_args)
        if process_args is None:
            process_args = []
        process_call = [process, *process_args]
        p = subprocess.Popen(process_call)
        return p

    def handle_db_events(self, message):
        try:
            msg = {}
            msg["channel"] = message["channel"]
            msg["data"] = message["data"]
            Clock.schedule_once(lambda dt: self.update_view("redis", msg), .01)
        except Exception as ex:
            print(ex)

    def update_view(self, view, message):
        self.views[view].text += str(message) + "\n"

    def stop_process(self, name=None):
        if name is None:
            for p, p_pid in self.processes.items():
                p_pid.terminate()
                p_pid.kill()
        else:
            try:
                self.processes[name].kill()
                self.processes[name].terminate()
            except Exception as ex:
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
    parser.add_argument("--db-key", help="db hash key")
    parser.add_argument("--db-key-field", help="db hash field")
    parser.add_argument("--db-host", help="db host ip, requires use of --db-port")
    parser.add_argument(
        "--db-port", type=int, help="db port, requires use of --db-host"
    )
    parser.add_argument(
        "--allow-shell-calls", action="store_true", help="allow shell calls in routing"
    )
    args = parser.parse_args()

    if bool(args.db_host) != bool(args.db_port):
        parser.error("--db-host and --db-port values are both required")

    app = TangleApp(**vars(args))
    # atexit.register(app.save_session)
    app.run()
