#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from skywalking import Layer, Component, config, nx_config
from skywalking.trace.context import get_context, NoopContext
from skywalking.trace.span import NoopSpan
from skywalking.trace.tags import TagHttpMethod, TagHttpURL, TagHttpStatusCode

link_vector = ['https://requests.readthedocs.io/en/master/']
support_matrix = {
    'requests': {
        '>=3.6': ['2.26', '2.25']
    }
}
note = """"""


def install():
    from requests import Session

    _request = Session.request

    Session.request = _sw_request_func(_request)


def _sw_request_func(_request):

    peer_label_func = _peer_label_func()
    op_label_func = _op_label_func()

    from requests import Session
    def _sw_request(this: Session, method, url,
                    params=None, data=None, headers=None, cookies=None, files=None,
                    auth=None, timeout=None, allow_redirects=True, proxies=None,
                    hooks=None, stream=None, verify=None, cert=None, json=None):

        from skywalking.utils.filter import sw_urlparse
        url_param = sw_urlparse(url)

        # ignore trace skywalking self request
        if config.protocol == 'http' and config.collector_address.rstrip('/').endswith(url_param.netloc):
            return _request(this, method, url, params, data, headers, cookies, files, auth, timeout,
                            allow_redirects,
                            proxies,
                            hooks, stream, verify, cert, json)

        peer = peer_label_func(url_param)
        op = op_label_func(url_param)
        
        span = NoopSpan(NoopContext()) if config.ignore_http_method_check(method) \
            else get_context().new_exit_span(op=op, peer=peer,
                                             component=Component.Requests)

        with span:
            carrier = span.inject()
            span.layer = Layer.Http

            if headers is None:
                headers = {}
            for item in carrier:
                headers[item.key] = item.val

            span.tag(TagHttpMethod(method.upper()))
            span.tag(TagHttpURL(url_param.geturl()))

            res = _request(this, method, url, params, data, headers, cookies, files, auth, timeout,
                           allow_redirects,
                           proxies,
                           hooks, stream, verify, cert, json)

            span.tag(TagHttpStatusCode(res.status_code))
            if res.status_code >= 400:
                span.error_occurred = True

            return res

    return _sw_request



def _peer_label_func():

    peer_func = None

    if(nx_config.nexa_requests_peer_unique):

        def _peer_label_unique_func(url_param):
            return nx_config.nexa_requests_peer_unique_label

        peer_func = _peer_label_unique_func

    else:

        def _peer_label_netloc_func(url_param):
            return url_param.netloc

        peer_func = _peer_label_netloc_func

    return peer_func

def _op_label_func():

    op_func = None

    if(nx_config.nexa_requests_op_type == 'netloc'):

        def _op_label_netloc_(url_param):
            return url_param.netloc

        op_func = _op_label_netloc_

    else:

        def _op_label_path_func(url_param):
            return url_param.path or '/'

        op_func = _op_label_path_func

    return op_func