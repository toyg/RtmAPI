#  Copyright (c) 2019 Giacomo Lacava, TarGLet Limited
#  Copyright (c) 2017 Tom Matheussen
#  Copyright (c) 2010 Michael Gruenewald
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#  THE SOFTWARE.
#

import hashlib
import httplib2
import logging
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ElementTree
import json

__author__ = "Michael Gruenewald <mail@michaelgruenewald.eu>,\n" \
             "Giacomo Lacava <giac@autoepm.com>,\n" \
             "Tom Matheussen <ommatheussen5@hotmail.com>"
__all__ = ('Rtm', 'RtmException')


def _anonimize_url(url):
    parsedurl = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsedurl.query)
    for param in ('api_key', 'auth_token', 'api_sig'):
        if param in qs:
            qs[param] = '...'
    rejoined = "&".join([key + '=' + "".join(value) for key, value in qs.items()])
    parsedurl = parsedurl._replace(query=rejoined)
    return urllib.parse.urlunparse(parsedurl)


class RtmException(Exception):
    pass


class RtmRequestFailedException(RtmException):
    def __str__(self):
        return "Request %s failed. Status: %s, reason: %s." % self.args


class Rtm(object):
    _auth_url = "http://api.rememberthemilk.com/services/auth/"
    _base_url = "http://api.rememberthemilk.com/services/rest/"

    def __init__(self, api_key, shared_secret, perms="read", token=None, api_version=None):
        """
        @param api_key: your API key
        @param shared_secret: your shared secret
        @param perms: desired access permissions, one of "read", "write"
                      and "delete"
        @param token: token for granted access (optional)
        @param api_version: version of API (optional)
        """
        self.api_key = api_key
        self.shared_secret = shared_secret
        self.perms = perms
        self.token = token
        self.api_version = api_version
        self.http = httplib2.Http()

    def authenticate_desktop(self):
        """
        Authenticate as a desktop application.

        @returns: (url, frob) tuple with url being the url the user should open
                              and frob the identifier for usage with
                              retrieve_token after the user authorized the
                              application
        """
        rsp = self._call_method("rtm.auth.getFrob", api_key=self.api_key)
        frob = rsp.frob.value
        url = self._make_request_url(self._auth_url, api_key=self.api_key,
                                     perms=self.perms, frob=frob)
        return url, frob

    def authenticate_webapp(self):
        """
        Authenticate as a web application.
        @returns: url
        """
        url = self._make_request_url(self._auth_url, api_key=self.api_key,
                                     perms=self.perms)
        return url

    def token_valid(self):
        """
        Checks whether the stored token is valid.
        @returns: bool validity
        """
        if self.token is None:
            return False
        try:
            self._call_method("rtm.auth.checkToken",
                              api_key=self.api_key,
                              auth_token=self.token)
        except RtmException:
            return False
        return True

    def retrieve_token(self, frob):
        """
        Retrieves a token for the given frob.
        @returns: bool success
        """
        try:
            rsp = self._call_method("rtm.auth.getToken",
                                    api_key=self.api_key,
                                    frob=frob)
        except RtmException:
            self.token = None
            return False
        self.token = rsp.auth.token.value
        return True

    def _call_method(self, method_name, **params):
        if self.api_version and method_name not in ["rtm.auth.getToken", "rtm.auth.checkToken"]:
            params.setdefault("v", "2")
        infos, data = self._make_request(method=method_name, **params)
        if infos.status != 200:
            raise RtmException(
                "Request %s failed (HTTP). Status: %s, reason: %s" % (
                    method_name, infos.status, infos.reason))
        
        if params.get('format', 'xml') == 'json':
            json_obj = json.loads(data.decode("utf-8"))

            return json_obj['rsp']
        else:
            tree = ElementTree.fromstring(data)
            assert tree.tag == "rsp"
            if tree.get("stat") == "fail":
                err = tree.find("err")
                raise RtmRequestFailedException(
                    method_name, err.get("code"), err.get("msg"))
            return RtmObject(tree, tree.tag)

    def _call_method_auth(self, method_name, **params):
        all_params = dict(api_key=self.api_key, auth_token=self.token)
        all_params.update(params)
        return self._call_method(method_name, **all_params)

    def _make_request(self, request_url=None, **params):
        final_url = self._make_request_url(request_url, **params)
        logging.debug(_anonimize_url(final_url))
        return self.http.request(final_url, headers={
            'Cache-Control': 'no-cache, max-age=0'})

    def _make_request_url(self, request_url=None, **params):
        all_params = list(params.items()) + [("api_sig", self._sign_request(params))]
        params_joined = urllib.parse.urlencode(
            [(k, v.encode('utf-8')) for k, v in all_params])
        return (request_url or self._base_url) + "?" + params_joined

    def _sign_request(self, params):
        param_pairs = list(params.items())
        param_pairs.sort()
        request_string = self.shared_secret + ''.join(k + v
                                                       for k, v in param_pairs
                                                       if v is not None)
        return hashlib.md5(request_string.encode('utf-8')).hexdigest()

    def __getattr__(self, name):
        return RtmName(self, name)


class RtmName(object):
    def __init__(self, rtm, name):
        self.rtm = rtm
        self.name = name

    def __call__(self, **params):
        return self.rtm._call_method_auth(self.name, **params)

    def __getattr__(self, name):
        return RtmName(self.rtm, "%s.%s" % (self.name, name))


class RtmBase(object):
    LISTS = {
        "arguments": "argument",
        "contacts": "contact",
        "errors": "error",
        "groups": "group",
        "list": "taskseries",
        "tasks": "list",
        "methods": "method",
        "notes": "note",
        "participants": "participant",
        "tags": "tag",
        "timezones": "timezone",
        "lists": "list"
    }

    @classmethod
    def new_object(cls, element):
        if element.tag in cls.LISTS:
            return RtmIterableObject(element,
                                     element.tag,
                                     cls.LISTS[element.tag])
        return RtmObject(element, element.tag)


class RtmIterable(RtmBase):
    def __init__(self, element, tag):
        self.__element = element
        self.__tag = tag

    def __get_collection(self):
        return [self.new_object(element)
                for element
                in self.__element.findall(self.__tag)]

    def __getitem(self, key):
        return self.__get_collection()[key]

    def __iter__(self):
        return iter(self.__get_collection())

    def __len__(self):
        return len(self.__get_collection)


class RtmObject(RtmBase):
    MORE_LISTS = {
        ("list", "deleted"): "deleted/taskseries",
    }

    def __init__(self, element, name):
        self.__element = element
        self.__name = name

    def __repr__(self):
        return "<%s %s>" % (type(self),
                            self.__name.encode('ascii', 'replace'))

    def __getattr__(self, name):
        if name == "value":
            return self.__element.text
        elif name in list(self.__element.keys()):
            return self.__element.get(name)
        elif (self.__name, name) in self.MORE_LISTS:
            return RtmIterable(self.__element,
                               self.MORE_LISTS[self.__name, name])
        else:
            element = self.__element.find(name)
            if element is None:
                return None
            return self.new_object(element)


class RtmIterableObject(RtmObject, RtmIterable):
    def __init__(self, element, name, tag):
        RtmObject.__init__(self, element, name)
        RtmIterable.__init__(self, element, tag)
