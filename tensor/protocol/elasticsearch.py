import time
import uuid
import json
import base64

from tensor import utils

class ElasticSearch(object):
    """Twisted ElasticSearch API
    """

    def __init__(self, host='127.0.0.1', port=9200, index='logstash-%Y.%m.%d'):
        self.host = host
        self.port = port
        self.index = index

    def _get_index(self):
        return time.strftime(self.index)
        
    def _request(self, path, data=None, method='GET'):
        if data:
            data = json.dumps(data)


        url = 'http://%s:%s/' % (
            self.host, self.port)

        return utils.HTTPRequest().getJson(
            url + path, method, data=data)
        
    def _gen_id(self):
        return base64.b64encode(uuid.uuid4().bytes).rstrip('=')
        
    
    def insertIndex(self, type, data):
        return self._request('%s/%s/%s' % (
                self._get_index(), type, self._gen_id()
            ), data, 'PUT')
        
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

        print 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
        print serdata

        return self._request('_bulk/', serdata.rstrip('\n'), 'PUT')
