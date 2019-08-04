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


def add_downtime(gid, user, password, cat, comment, duration, data):
    """
    This method calls the downtime script and passes all needed arguments. In
    the event, that the given category isn't known, it return a string
    :param gid:
    :param user:
    :param password:
    :param cat:
    :param comment:
    :param duration:
    :param data:
    :return:
    """
    cmd = os.path.expanduser("~/local/bin/downtime_new")
    now = time.time()

    if cat == 'host':
        subprocess.call([cmd, '-g ' + str(gid), '-u ' + user, '-p ' + password, '-o', 'add', '-d ' + str(duration), '-c ' + comment, '-n ' + ",".join(data['hostname'])])
        return 0, 'Adding downtime for server ' + ",".join(data['hostname']) + ' from now until ' + time.ctime(now + duration) + '\n'
    elif cat == 'service':
        subprocess.call([cmd, '-g ' + str(gid), '-u ' + user, '-p ' + password, '-o', 'add', '-d ' + str(duration), '-c ' + comment, '-n ' + ",".join(data['hostname']), '-s ' + ",".join(data['servicename'])])
        return 0, 'Adding downtime for server ' + ",".join(data['hostname']) + ' and service ' ",".join(data['servicename']) + ' from now until ' + time.ctime(now + duration) + '\n'
    elif cat == 'hostgroup':
        subprocess.call([cmd, '-g ' + str(gid), '-u ' + user, '-p ' + password, '-o', 'add', '-d ' + str(duration), '-c ' + comment, '-N ' + ",".join(data['hostgroup'])])
        return 0, 'Adding downtime for hostgroup ' + ",".join(data['hostgroup']) + ' from now until ' + time.ctime(now + duration) + '\n'
    elif cat == 'servicegroup':
        subprocess.call([cmd, '-g ' + str(gid), '-u ' + user, '-p ' + password, '-o', 'add', '-d ' + str(duration), '-c ' + comment, '-S ' + ",".join(data['servicegroup'])])
        return 0, 'Adding downtime for servicegroup ' + ",".join(data['servicegroup']) + ' from now until ' + time.ctime(now + duration) + '\n'
    else:
        return "Couldn't add a downtime, category " + cat + " is unknown" + '\n'


# remove downtime
def remove_downtime(gid, user, password, cat, data):
    cmd = os.path.expanduser("~/local/bin/downtime_new")

    if cat == 'host':
        subprocess.call([cmd, '-g ' + str(gid), '-u ' + user, '-p ' + password, '-o', 'remove', '-n ' + ",".join(data['hostname'])])
        return 0, 'Removing downtime for server ' + ",".join(data['hostname']) + '\n'
    elif cat == 'service':
        subprocess.call([cmd, '-g ' + str(gid), '-u ' + user, '-p ' + password, '-o', 'remove', '-n ' + ",".join(data['hostname']), '-s ' + ",".join(data['servicename'])])
        return 0, 'Removing downtime for server ' + ",".join(data['hostname']) + ' and service ' ",".join(data['servicename']) + '\n'
    elif cat == 'hostgroup':
        subprocess.call([cmd, '-g ' + str(gid), '-u ' + user, '-p ' + password, '-o', 'remove', '-N ' + ",".join(data['hostgroup'])])
        return 0, 'Removing downtime for hostgroup ' + ",".join(data['hostgroup']) + '\n'
    elif cat == 'servicegroup':
        subprocess.call([cmd, '-g ' + str(gid), '-u ' + user, '-p ' + password, '-o', 'remove', '-S ' + ",".join(data['servicegroup'])])
        return 0, 'Removing downtime for servicegroup ' + ",".join(data['servicegroup']) + '\n'
    else:
        return 2, "Couldn't add a downtime, category " + cat + " is unknown" + '\n'


# the check function (dummy)
def check_downtime_new(item, params, info):
    if not info:
        return 0, "New Downtime Collector has nothing to do..."

    # Initial string
    output = 'New Downtime Collector will process the following definitions:\n'

    for line in info:
        data = json.loads(" ".join(line[1:]))
        user = data['user'] if 'user' in data.keys() else None
        password = data['password'] if 'password' in data.keys() else None
        gid = data['id'] if 'id' in data.keys() else None
        comment = data['comment'] if 'comment' in data.keys() else ""
        duration = data['duration'] if 'duration' in data.keys() else 7200
        operation = data['operation'] if 'operation' in data.keys() else None
        for op in operation.keys():
            for cat in operation[op].keys():
                if op == 'add':
                    status, message = add_downtime(gid, user, password, cat, comment, duration, operation[op][cat])
                elif op == 'remove':
                    status, message = remove_downtime(gid, user, password, cat, operation[op][cat])
                else:
                    status, message = "ERROR: Unknown operation " + op

                if status >
                output += message

    return 1, output


check_info["downtime_new"] = {
    "check_function"        : check_downtime_new,
    "inventory_function"    : inventory_downtime_new,
    "service_description"   : "",
    "has_perfdata"          : False,
}
