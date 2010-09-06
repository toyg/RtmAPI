import hashlib
import httplib2
import urllib
import xml.etree.ElementTree as ElementTree

__author__ = "Michael Gruenewald"
__all__ = ('Rtm',)

class Rtm(object):
    _auth_url = "http://api.rememberthemilk.com/services/auth/"
    _base_url = "http://api.rememberthemilk.com/services/rest/"
    
    def __init__(self, api_key, shared_secret, perms = "read", token = None):
        self.api_key = api_key
        self.shared_secret = shared_secret
        self.perms = perms
        self.token = token
    
    def _call_method_auth(self, name, **params):
        all_params = dict(api_key = self.api_key, auth_token = self.token)
        all_params.update(params)
        return self._call_method(name, **all_params)
    
    def _call_method(self, name, **params):
        infos, data = self._make_request(method = name, **params)
        assert infos['status'] == "200"
        return RtmObject(ElementTree.fromstring(data), name)
    
    def authenticate_desktop(self):
        frob = self._call_method("rtm.auth.getFrob", api_key = self.api_key).frob.value
        return self._make_request_url(self.auth_url, api_key = self.api_key, perms = self.perms, frob = frob), frob
    
    def authenticate_webapp(self):
        raise NotImplementedError
    
    def token_valid(self):
        if self.token is None:
            return False
        rsp = self._call_method("rtm.auth.checkToken", api_key = self.api_key, auth_token = self.token)
        return rsp.stat == "ok"
    
    def retrieve_token(self, frob):
        self.token = self._call_method("rtm.auth.getToken", api_key = self.api_key, frob = frob).auth.token.value
        return self.token
    
    def _make_request(self, url = None, **params):
        final_url = self._make_request_url(url, **params)
        return httplib2.Http().request(final_url)
    
    def _make_request_url(self, url = None, **params):
        all_params = params.items() + [("api_sig", self._sign_request(params))]
        params_joined = "&".join("%s=%s" % (urllib.quote_plus(k.encode('utf-8')),
                                            urllib.quote_plus(v.encode('utf-8'))) for k, v in all_params)
        return (url or self.base_url) + "?" + params_joined
    
    def _sign_request(self, params):
        param_pairs = params.items()
        param_pairs.sort()
        request_string = self.shared_secret + u''.join(k + v for k, v in param_pairs)
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


class RtmObject(object):
    _lists = (
        "contacts/contact",
        "groups/group",
        "groups/group/contacts/contact",
        "method/arguments/argument",
        "method/errors/error",
        "methods/method",
        "list/taskseries/task",
        "list/taskseries/task/tags/tag",
        "lists/list",
        "locations/location",
        "tasks/list",
        "tasks/list/taskseries",
        "tasks/list/taskseries/task",
        "timezones/timezone",
    )
    
    def __init__(self, element, name):
        self._element = element
        self._name = name
    
    def __getattr__(self, name):
        newname = "%s/%s" % (self._name, name)
        if name == "value":
            return self._element.text
        elif name in self._element.keys():
            return self._element.get(name)
        elif newname.partition("/")[2] in self._lists:
            return [RtmObject(element, newname) for element in self._element.findall(name)]
        else:
            return RtmObject(self._element.find(name), newname)
    
    def __repr__(self):
        return ("<RtmObject %s>" % self._name).encode('ascii', 'replace')
