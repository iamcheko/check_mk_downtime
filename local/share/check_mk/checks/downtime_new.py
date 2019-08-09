#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
# -----------------------------------------------------------------------------
#
#   Programm        : downtime_new.py
#
# -----------------------------------------------------------------------------
#
#   Description     : This script is a extension of the old downtime script.
#
#   Author          : Manuel Hagg
#   Copyright (C)   : (2019) Swisscom
#   Version         : 0.0.1
#   Created         : 2019-07-23
#   Last update     : 2019-07-23    Marek Zavesicky
#                                   Extended the existing script with features,
#                                   well there is not a lot left of Manuel's
#                                   script.
#
#   Change history  : See "git log"
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#   External Modules
# -----------------------------------------------------------------------------
import json
import os
import subprocess
import time

# -----------------------------------------------------------------------------
#   Globale Variables
# -----------------------------------------------------------------------------
def inventory_downtime_new(info):
    yield "New Downtime Collector", None


def run_downtime(gid, user, password, author, operation, cat, comment, duration, data):
    """
    This method calls the downtime script and passes all needed arguments. In
    the event, that the given category isn't known, it return a string

    Attributes:
        gid             a groupedid needed to identify the downtime
        user            a user, should be an automation user
        author          the author for the downtime must be the username
        password        a secret
        cat             a category one of host, service, host- or servicegroup
        comment         a descriptive comment for the downtime
        duration        the duration of the downtime
        data            the host, service, host- or servicegroup name

    Return:
        string      a message
    """
    output = ""
    cmd = os.path.expanduser("~/local/bin/downtime_new")
    now = time.time()
    if operation in ['add', 'remove']:
        cmd_string = "{} -g {} -u {} -p {} -o {} -a {} ".format(cmd, str(gid), user, password, op, author)
        if operation == 'add':
            cmd_string += "-d {} -c {} ".format(str(duration), comment)
    else:
        return 2, "ERROR unknown operation " + operation + "\n"

    if cat == 'host':
        cmd_string += '-n ' + ",".join(data['hostname'])
    elif cat == 'service':
        cmd_string += '-n ' + ",".join(data['hostname']), '-s ' + ",".join(data['servicename'])
    elif cat == 'hostgroup':
        cmd_string += '-N ' + ",".join(data['hostgroup'])
    elif cat == 'servicegroup':
        cmd_string += '-S ' + ",".join(data['servicegroup'])
    else:
        return 2, "ERROR couldn't add a downtime, category " + cat + " is unknown" + '\n'

    return_code = subprocess.Popen(cmd_string.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if return_code != 0:
        output += "ERROR "
        for line in return_code.stderr.readlines():
            output += line
        return 2, output
    else:
        for line in return_code.stdout.readlines():
            output += line
        return 0, output

# the check function (dummy)
def check_downtime_new(item, params, info):
    status = 0

    if not info:
        return 0, "New Downtime Collector has nothing to do..."

    # Initial string
    output = 'New Downtime Collector will process the following definitions:\n'

    for line in info:
        data = json.loads(" ".join(line[1:]))
        for mandatory in ['user', 'password', 'author', 'id', 'operation']:
            if mandatory not in data.keys():
                status = 2
                output += "ERROR in collected downtime data, {0} is mandatory".format(mandatory)
        if status != 0:
            return status, output

        comment = data['comment'] if 'comment' in data.keys() else ""
        duration = data['duration'] if 'duration' in data.keys() else 7200

        for op in operation.keys():
            for cat in operation[op].keys():
                status, message = run_downtime(data['gid'], data['user'], data['password'], data['author'], op, cat, comment, duration, operation[op][cat])
                elif op == 'remove':
                    status, message = remove_downtime(gid, user, password, author, cat, operation[op][cat])
                else:
                    status, message = "ERROR: Unknown operation " + op

                if status != 0
                output += message

    return 1, output


check_info["downtime_new"] = {
    "check_function"        : check_downtime_new,
    "inventory_function"    : inventory_downtime_new,
    "service_description"   : "",
    "has_perfdata"          : False,
}
