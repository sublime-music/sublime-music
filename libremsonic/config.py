import os

from typing import Any, Dict, List, Optional
import json

from libremsonic.from_json import from_json


class ServerConfiguration:
    name: str
    server_address: str
    local_network_address: str
    local_network_ssid: str
    username: str
    password: str
    browse_by_tags: bool
    sync_enabled: bool

    def __init__(self,
                 name='Default',
                 server_address='http://yourhost',
                 local_network_address='',
                 local_network_ssid='',
                 username='',
                 password='',
                 browse_by_tags=False,
                 sync_enabled=True):

        self.name = name
        self.server_address = server_address
        self.local_network_address = local_network_address
        self.local_network_ssid = local_network_ssid
        self.username = username
        self.password = password
        self.browse_by_tags = browse_by_tags
        self.sync_enabled = sync_enabled


class AppConfiguration:
    servers: List[ServerConfiguration]
    current_server: Optional[int]

    def to_json(self):
        return {
            'servers': [s.__dict__ for s in self.servers],
            'current_server': self.current_server,
        }


def get_config(filename: str) -> AppConfiguration:
    with open(filename, 'r') as f:
        try:
            response_json = json.load(f)
        except json.decoder.JSONDecodeError:
            response_json = None

        if not response_json:
            default_configuration = AppConfiguration()
            default_configuration.servers = []
            default_configuration.current_server = None
            return default_configuration

        return from_json(AppConfiguration, response_json)


def save_config(config: AppConfiguration, filename: str):
    with open(filename, 'w+') as f:
        f.write(json.dumps(config.to_json(), indent=2, sort_keys=True))
