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
#                     Exitcodes:    0   Nothing to do
#                                   1   Some hosts and services have been added
#                                       or removed from downtime
#                                   2   Something went wrong during execution
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
        int             a return code (1 = We found data, 2 = An error occured)
        string          a message
        string          all errors that happend
    """
    output = ''
    errors = ''
    cmd = os.path.expanduser("~/local/bin/downtime_new")

    if operation in ['add', 'remove']:
        cmd_string = "{0} -g {1} -u {2} -p {3} -o {4} -a {5} ".format(cmd, str(gid), user, password, operation, author)
        if operation == 'add':
            cmd_string += "-d {0} -c {1} ".format(str(duration), comment)
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
        return 2, "", "ERROR couldn't add a downtime, category " + cat + " is unknown" + '\n'

    proc = subprocess.Popen(cmd_string.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.wait()
    if proc.returncode != 0:
        errors += "ERROR "
        for line in proc.stderr.readlines():
            errors += line
        return 2, output, errors
    else:
        for line in proc.stdout.readlines():
            output += line
        return 1, output, errors

# the check function (dummy)
def check_downtime_new(item, params, info):
    status = 0
    errors = ''

    if not info:
        return status, "New Downtime Collector has nothing to do..."

    # Initial string
    output = 'New Downtime Collector will process the following definitions:\n'

    for line in info:
        if line[0] == 'data:':
            data = json.loads(" ".join(line[1:]))
            error = False
            for mandatory in ['user', 'password', 'author', 'id', 'operation']:
                if mandatory not in data.keys():
                    error = True
                    errors += "ERROR in collected downtime data, {0} is mandatory\n".format(mandatory)
            if not error:
                comment = data['comment'] if 'comment' in data.keys() else ""
                duration = data['duration'] if 'duration' in data.keys() else 7200
                operation = data['operation']

                for op in operation.keys():
                    for cat in operation[op].keys():
                        rc, msg, err = run_downtime(data['id'], data['user'], data['password'], data['author'], op, cat, comment, duration, operation[op][cat])
                        output += msg
                        errors += err

                        if rc > status:
                            status = rc
        else:
            status = 2
            errors += " ".join(line) + '\n'

    return status, errors + output


check_info["downtime_new"] = {
    "check_function"        : check_downtime_new,
    "inventory_function"    : inventory_downtime_new,
    "service_description"   : "",
    "has_perfdata"          : False,
}
