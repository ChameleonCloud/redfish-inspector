#!python3

import json
import sushy
from sushy import auth


class NodeConnection:

    session = None

    def __init__(self, username, password, uri):
        sushy_auth = auth.SessionOrBasicAuth(username=username, password=password)
        self.session = sushy.Sushy(uri, sushy_auth)
