class ServerConfiguration:
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
