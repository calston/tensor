import time
import uuid
import json
from base64 import b64encode

from tensor import utils

class ElasticSearch(object):
    """Twisted ElasticSearch API
    """
    def __init__(self, url='http://localhost:9200', user=None, password=None,
                 index='logstash-%Y.%m.%d'):
        self.url = url.rstrip('/')
        self.index = index
        self.user = user
        self.password = password

    def _get_index(self):
        return time.strftime(self.index)

    def _request(self, path, data=None, method='GET'):
        headers = {}
        if self.user:
            authorization = b64encode('%s:%s' % (self.user, self.password))
            headers['Authorization'] = ['Basic ' + authorization]

        return utils.HTTPRequest().getJson(
            self.url + path, method, headers=headers, data=data)

    def _gen_id(self):
        return b64encode(uuid.uuid4().bytes).rstrip('=')

    def stats(self):
        return self._request('/_cluster/stats')

    def node_stats(self):
        return self._request('/_nodes/stats')

    def insertIndex(self, type, data):
        return self._request('/%s/%s/%s' % (
                self._get_index(), type, self._gen_id()
            ), json.dumps(data), 'PUT')

    def bulkIndex(self, data):
        serdata = ""

        for row in data:
            if '_id' in row:
                id = row['id']
                del row['id']
            else:
                id = self._gen_id()

            d = {
                "index": {
                    "_index": self._get_index(),
                    "_type": row.get('type', 'log'),
                    "_id": id,
                }
            }
            serdata += json.dumps(d) + '\n'
            serdata += json.dumps(row) + '\n'

        return self._request('/_bulk', serdata.rstrip('\n'), 'PUT')
