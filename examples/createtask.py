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
    
    # all updates require timeline (which =~ savepoint to which
    # one can rollback)
    result = api.rtm.timelines.create()
    timeline = result.timeline.value

    # Create new list
    result = api.rtm.lists.add(timeline = timeline,
                               name = u"an example list")
    list_id = result.list.id
    print("Created list with id", list_id)

    # And task
    result = api.rtm.tasks.add(timeline = timeline,
                               list_id = list_id,
                               name = u"some task")
    task_id = result.list.taskseries.task.id
    print(task_id)
    print("Created task", task_id)


