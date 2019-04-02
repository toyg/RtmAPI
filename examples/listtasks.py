from __future__ import print_function
from builtins import input
import sys
import webbrowser
from rtmapi import Rtm

if __name__ == '__main__':
    # call the program as `listtasks.py api_key shared_secret [optional: token]`
    # get those parameters from http://www.rememberthemilk.com/services/api/keys.rtm
    api_key, shared_secret = sys.argv[1:3]
    token = sys.argv[3] if len(sys.argv) >= 4 else None
    api = Rtm(api_key, shared_secret, "delete", token)
    
    # authenication block, see http://www.rememberthemilk.com/services/api/authentication.rtm
    # check for valid token
    if not api.token_valid():
        # use desktop-type authentication
        url, frob = api.authenticate_desktop()
        # open webbrowser, wait until user authorized application
        webbrowser.open(url)
        input("Continue?")
        # get the token for the frob
        api.retrieve_token(frob)
        # print out new token, should be used to initialize the Rtm object next time
        # (a real application should store the token somewhere)
        print("New token: %s" % api.token)
    
    # get all open tasks, see http://www.rememberthemilk.com/services/api/methods/rtm.tasks.getList.rtm
    result = api.rtm.tasks.getList(filter="status:incomplete")
    for tasklist in result.tasks:
        for taskseries in tasklist:
            print(taskseries.task.due, taskseries.name)
