#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
# ------------------------------------------------------------------------------
#
#   Programm        : downtime.py
#
# ------------------------------------------------------------------------------
#
#   Description     : This program is a command line tool for Check_MK that
#                     sets and remove downtimes on hosts, services, host- and
#                     servicegroups.
#                     It relates on the Check_MK webapi mainly to figure out
#                     the status of a specific site and livestatus to maintain
#                     the needed downtime manipulations.
#
#   Author          : Marek Zavesicky
#   Copyright (C)   : (2019) Marek Zavesicky
#   License         : AGPL3
#   URL             : https://github.com/iamcheko/check_mk_downtime
#   Version         : 0.0.1
#   Created         : 2019/05/24
#   Last update     : 2019/06/07
#
#   Change history  : See "git log"
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
#   External Modules
# ------------------------------------------------------------------------------
import os
import logging
import argparse
from datetime import datetime
import livestatus
import requests
import sys


# ------------------------------------------------------------------------------
#   Globale Variables
# ------------------------------------------------------------------------------
# make loging facility globaly available
global logger

# build the working environment
path_bin = os.path.dirname(os.path.realpath(__file__))
path_etc = os.path.dirname(path_bin) + "/etc"
path_lib = os.path.dirname(path_bin) + "/lib"
path_var_log = os.path.dirname(path_bin) + "/var/log"
if not os.path.exists(path_var_log):
    os.mkdir(path_var_log)


# ------------------------------------------------------------------------------
#   Part            : Class definition
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
#   Class           : Sites
# ------------------------------------------------------------------------------
#   Description     : The Sites class stores all active check_mk sites in its
#                     object.
#
#   Inherits from   : object
# ------------------------------------------------------------------------------
class Sites(object):
    logger = None

    # --------------------------------------------------------------------------
    #   Method          : __init__
    # --------------------------------------------------------------------------
    #   Description     : The Sites constructor method.
    #
    #   Arguments       : self          A reference to the object itself
    #                     user          The user name
    #                     secret        The secret of the user
    #                     path          The base path (OMD_ROOT)
    #                     url           The url
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def __init__(self, user, secret, path, url):
        if Sites.logger == None:
            Sites.logger = setup_logging(self.__class__.__name__)
        self.user = user
        self.secret = secret
        self.path = path
        self.url = url
        self.sites = {}
        self.sites_with_data = []
        self.payload = {
            "action"        : 'get_site',
            "_username"     : self.user,
            "_secret"       : self.secret,
            "output_format" : 'python',
            "site_id"       : '',
        }

        self.logger.debug('Constructor call passed arguments user: %s, path: %s, url: %s', self.user, self.path, self.url)
        for sitename in os.listdir(self.path):
            self.payload["site_id"] = sitename
            self.logger.debug('Collecting informations for site %s', sitename)
            response = requests.get(self.url + "webapi.py", params = self.payload)
            site_struct = eval(response.content)

            # Make sure that the collected sites are available
            if site_struct['result_code'] == 0 and site_struct['result']['site_config']['disabled'] == False:
                self.logger.debug('Site %s is enabled', sitename)
                socket_path = self.path + "/" + sitename + "/tmp/run/live"
                if os.path.exists(socket_path):
                    self.logger.debug('Livestatus socket found: %s', socket_path)
                    self.sites[sitename] = Site(sitename, site_struct['result']['site_config']['alias'], "unix:" + socket_path)
                else:
                    self.logger.error('Livestatus socket not found: %s', socket_path)
            else:
                self.logger.debug('Site %s is disabled', sitename)

    # --------------------------------------------------------------------------
    #   Method          : append_obj_to_site
    # --------------------------------------------------------------------------
    #   Description     : This method takes a obj of class host or service. It
    #                     will find the site to which the obj is related and
    #                     stores it to the evaluated site or sites.
    #
    #   Arguments       : self          A reference to the object itself
    #                     obj           The object of a class host or service
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def append_obj_to_site(self, obj):
        for site in self.sites.keys():
            self.sites[site].validate_data(obj)
        self.collect_sites_with_data()

    # --------------------------------------------------------------------------
    #   Method          : collect_sites_with_data
    # --------------------------------------------------------------------------
    #   Description     : This method will find all sites that have valid data
    #                     and store the site name in a list.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def collect_sites_with_data(self):
        for site in self.sites.keys():
            if self.sites[site].has_data:
                self.sites_with_data.append(site)

    # --------------------------------------------------------------------------
    #   Method          : get_sites
    # --------------------------------------------------------------------------
    #   Description     : This method returns all sites which are active.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : list          A list of all active sites
    # --------------------------------------------------------------------------
    def get_sites(self):
        return self.sites.keys()

    # --------------------------------------------------------------------------
    #   Method          : get_sites_with_data
    # --------------------------------------------------------------------------
    #   Description     : This method returns all sites which have data.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : list          A list of all sites with data
    # --------------------------------------------------------------------------
    def get_sites_with_data(self):
        return self.sites_with_data


# ------------------------------------------------------------------------------
#   Class           : Site
# ------------------------------------------------------------------------------
#   Description     : The Site class represents all sites of a check_mk multi-
#                     site environment.
#
#   Inherits from   : object
# ------------------------------------------------------------------------------
class Site(object):
    logger = None

    # --------------------------------------------------------------------------
    #   Method          : __init__
    # --------------------------------------------------------------------------
    #   Description     : The Site constructor method.
    #
    #   Arguments       : self          A reference to the object itself
    #                     sitename      A string with the site name
    #                     alias         A string with the alias of the site
    #                     socket        The filename with the absoluth path of
    #                                   the livestatus socket
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def __init__(self, sitename, alias, socket):
        if Site.logger == None:
            Site.logger = setup_logging(self.__class__.__name__)
        self.sitename = sitename
        self.alias = alias
        self.socket = socket
        self.connection = livestatus.SingleSiteConnection(self.socket)
        self.monitoring_objects = []
        self.logger.debug('Constructor call passed arguments sitename: %s, alias: %s, socket: %s', self.sitename, self.alias, self.socket)

    # --------------------------------------------------------------------------
    #   Method          : get_sitename
    # --------------------------------------------------------------------------
    #   Description     : Getter method that returns the site name.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        The site name
    # --------------------------------------------------------------------------
    def get_sitename(self):
        return self.sitename

    # --------------------------------------------------------------------------
    #   Method          : get_connection
    # --------------------------------------------------------------------------
    #   Description     : Returns the connection to the livestatus socket.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : filehandle    The filehandel to the livestatus socket
    # --------------------------------------------------------------------------
    def get_connection(self):
        return self.connection

    # --------------------------------------------------------------------------
    #   Method          : validate_data
    # --------------------------------------------------------------------------
    #   Description     : This methode validates the data of the passed object.
    #
    #   Arguments       : self          A reference to the object itself
    #                     obj           The object that needs to be validated
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def validate_data(self, obj):
        self.logger.debug('Validate data for site %s', self.get_sitename())
        obj.get_data(self.get_connection(), self.push, obj.get_query)

    # --------------------------------------------------------------------------
    #   Method          : push
    # --------------------------------------------------------------------------
    #   Description     : Pushes a object to the monitoring_objects list.
    #
    #   Arguments       : self          A reference to the object itself
    #                     obj           The object which is appended
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def push(self, obj):
        self.monitoring_objects.append(obj)

    # --------------------------------------------------------------------------
    #   Method          : has_data
    # --------------------------------------------------------------------------
    #   Description     : Returns True if there is data in the object list or
    #                     False if there is not.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : boolean       True if data is available else False
    # --------------------------------------------------------------------------
    def has_data(self):
        return True if len(self.monitoring_objects) > 0 else False

    # --------------------------------------------------------------------------
    #   Method          : get_monitoring_objects
    # --------------------------------------------------------------------------
    #   Description     : This is a generator methode which returns the list of
    #                     monitoring_objects.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : obj           A object reference of Host or Service
    # --------------------------------------------------------------------------
    def get_monitoring_objects(self):
        for obj in self.monitoring_objects:
            yield obj


# ------------------------------------------------------------------------------
#   Class           : Host
# ------------------------------------------------------------------------------
#   Description     : The Host class represents a check_mk host.
#
#   Inherits from   : object
# ------------------------------------------------------------------------------
class Host(object):
    logger = None
    _table = 'hosts'
    _columns = ['name']

    # --------------------------------------------------------------------------
    #   Method          : __init__
    # --------------------------------------------------------------------------
    #   Description     : The Host constructor method.
    #
    #   Arguments       : self          A reference to the object itself
    #                     host_name     A string with the host name
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def __init__(self, host_name):
        if Host.logger == None:
            Host.logger = setup_logging(self.__class__.__name__)
        self.host_name = host_name
        self.logger.debug('Constructor call passed arguments host_name: %s', self.host_name)

    # --------------------------------------------------------------------------
    #   Method          : get_query
    # --------------------------------------------------------------------------
    #   Description     : This method returns the query for the listing of hosts
    #                     in downtime.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        the query
    # --------------------------------------------------------------------------
    def get_query(self):
        query = Query
        return query.get_query(self._table, self._columns, { self._columns[0]: self.get_host_name()})

    # --------------------------------------------------------------------------
    #   Method          : get_host_name
    # --------------------------------------------------------------------------
    #   Description     : This method returns the host name of the Host object.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        The host name
    # --------------------------------------------------------------------------
    def get_host_name(self):
        return self.host_name

    # --------------------------------------------------------------------------
    #   Method          : get_data
    # --------------------------------------------------------------------------
    #   Description     : This method retrieves the data for a object and stores
    #                     it.
    #
    #   Arguments       : self          A reference to the object itself
    #                     connection    The connection to the livestatus socket
    #                     store_func    A reference to a method
    #                     query_func    A reference to a method
    #                     obj           Optional a object reference
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def get_data(self, connection, store_func, query_func, obj = None):
        if obj == None:
            data = connection.query_table(query_func())
        else:
            data = connection.query_table(query_func(obj))
        if data:
            store_func(data, obj, connection)

    # --------------------------------------------------------------------------
    #   Method          : get_filter_for_downtime
    # --------------------------------------------------------------------------
    #   Description     : This method returns the dictionary that is needed to
    #                     generate the filter part of a query.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : dictionary    A dictionary for a filter
    # --------------------------------------------------------------------------
    def get_filter_for_downtime(self):
        return {'host_name': self.get_host_name()}

    # --------------------------------------------------------------------------
    #   Method          : get_as_a_string
    # --------------------------------------------------------------------------
    #   Description     : This method returns the hostname.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        The host name of the Host object
    # --------------------------------------------------------------------------
    def get_as_a_string(self):
        return self.get_host_name()

    # --------------------------------------------------------------------------
    #   Method          : get_downtime_operation
    # --------------------------------------------------------------------------
    #   Description     : This method returns the operator for the downtime
    #                     command.
    #
    #   Arguments       : self          A reference to the object itself
    #                     operator      schedule or something else
    #   Return          : string        Nether SCHEDULE_HOST_DOWNTIME or
    #                                   DEL_HOST_DOWNTIME
    # --------------------------------------------------------------------------
    def get_downtime_operation(self, operator):
        return "SCHEDULE_HOST_DOWNTIME" if operator == 'schedule' else "DEL_HOST_DOWNTIME"


# ------------------------------------------------------------------------------
#   Class           : Service
# ------------------------------------------------------------------------------
#   Description     : The Service class represents a check_mk service.
#
#   Inherits from   : object
# ------------------------------------------------------------------------------
class Service(object):
    logger = None
    _table = 'services'
    _columns = ['host_name', 'description']

    # --------------------------------------------------------------------------
    #   Method          : __init__
    # --------------------------------------------------------------------------
    #   Description     : The Service constructor method.
    #
    #   Arguments       : self          A reference to the object itself
    #                     host_name     A string with the host name
    #                     service_name  A string with the service name
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def __init__(self, host_name = None, service_name = None):
        if Service.logger == None:
            Service.logger = setup_logging(self.__class__.__name__)
        self.host_name = host_name
        self.service_name = service_name
        self.logger.debug('Constructor call passed arguments host_name: %s, service_name: %s', self.host_name, self.service_name)

    # --------------------------------------------------------------------------
    #   Method          : get_query
    # --------------------------------------------------------------------------
    #   Description     : This method returns the query for the listing of
    #                     services in downtime.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        the query
    # --------------------------------------------------------------------------
    def get_query(self):
        query = Query
        return query.get_query(self._table, self._columns, {self._columns[0]: self.get_host_name(), self._columns[1]: self.get_service_name()})

    # --------------------------------------------------------------------------
    #   Method          : get_host_name
    # --------------------------------------------------------------------------
    #   Description     : This method returns the host name of the Service
    #                     object.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        The host name
    # --------------------------------------------------------------------------
    def get_host_name(self):
        return self.host_name

    # --------------------------------------------------------------------------
    #   Method          : get_service_name
    # --------------------------------------------------------------------------
    #   Description     : This method returns the service name of the Service
    #                     object.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        The host name
    # --------------------------------------------------------------------------
    def get_service_name(self):
        return self.service_name

    # --------------------------------------------------------------------------
    #   Method          : get_data
    # --------------------------------------------------------------------------
    #   Description     : This method retrieves the data for a object and stores
    #                     it.
    #
    #   Arguments       : self          A reference to the object itself
    #                     connection    The connection to the livestatus socket
    #                     store_func    A reference to a method
    #                     query_func    A reference to a method
    #                     obj           Optional a object reference
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def get_data(self, connection, store_func, query_func, obj = None):
        if obj == None:
            data = connection.query_table(query_func())
        else:
            data = connection.query_table(query_func(obj))
        if data:
            store_func(data, obj, connection)

    # --------------------------------------------------------------------------
    #   Method          : get_filter_for_downtime
    # --------------------------------------------------------------------------
    #   Description     : This method returns the dictionary that is needed to
    #                     generate the filter part of a query.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : dictionary    A dictionary for a filter
    # --------------------------------------------------------------------------
    def get_filter_for_downtime(self):
        return {'host_name': self.get_host_name(), 'service_description': self.get_service_name()}

    # --------------------------------------------------------------------------
    #   Method          : get_as_a_string
    # --------------------------------------------------------------------------
    #   Description     : This method returns the hostname and service.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        The host and service name of the Service
    #                                   object
    # --------------------------------------------------------------------------
    def get_as_a_string(self):
        return "{};{}".format(self.get_host_name(), self.get_service_name())

    # --------------------------------------------------------------------------
    #   Method          : get_downtime_operation
    # --------------------------------------------------------------------------
    #   Description     : This method returns the operator for the downtime
    #                     command.
    #
    #   Arguments       : self          A reference to the object itself
    #                     operator      schedule or something else
    #   Return          : string        Nether SCHEDULE_SVC_DOWNTIME or
    #                                   DEL_SVC_DOWNTIME
    # --------------------------------------------------------------------------
    def get_downtime_operation(self, operator):
        return "SCHEDULE_SVC_DOWNTIME" if operator == 'schedule' else "DEL_SVC_DOWNTIME"


# ------------------------------------------------------------------------------
#   Class           : Hostgroup
# ------------------------------------------------------------------------------
#   Description     : The Hostgroup class receives a servicegroup name and
#                     creates for each host of this group a object of a
#                     Host class.
#
#   Inherits from   : object
# ------------------------------------------------------------------------------
class Hostgroup(object):
    logger = None
    _table = 'hostgroups'
    _columns = ['members']

    # --------------------------------------------------------------------------
    #   Method          : __init__
    # --------------------------------------------------------------------------
    #   Description     : The Hostgroup constructor method.
    #
    #   Arguments       : self          A reference to the object itself
    #                     hostgroup     A string with the name of the hosgroup
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def __init__(self, hostgroup):
        if Hostgroup.logger == None:
            Hostgroup.logger = setup_logging(self.__class__.__name__)
        self.hostgroup = hostgroup
        self.logger.debug('Constructor call passed arguments hostgroup: %s', self.hostgroup)

    # --------------------------------------------------------------------------
    #   Method          : get_query
    # --------------------------------------------------------------------------
    #   Description     : A getter method to retrieve the query.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        The query string
    # --------------------------------------------------------------------------
    def get_query(self):
        query = Query()
        return query.get_query(self._table, self._columns, {'name': self.get_hostgroup()})

    # --------------------------------------------------------------------------
    #   Method          : get_hostgroup
    # --------------------------------------------------------------------------
    #   Description     : A getter method to retrieve the name of the hostgroup.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        A string with the hostgroup name
    # --------------------------------------------------------------------------
    def get_hostgroup(self):
        return self.hostgroup

    # --------------------------------------------------------------------------
    #   Method          : get_data
    # --------------------------------------------------------------------------
    #   Description     : This method retrieves the data for a object and stores
    #                     it.
    #
    #   Arguments       : self          A reference to the object itself
    #                     connection    The connection to the livestatus socket
    #                     store_func    A reference to a method
    #                     query_func    Not used but needed
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def get_data(self, connection, store_func, query_func = None):
        data = connection.query_table(self.get_query())
        if data:
            for data_set in data[0][0]:
                obj = Host(data_set)
                store_func(obj)


# ------------------------------------------------------------------------------
#   Class           : Servicegroup
# ------------------------------------------------------------------------------
#   Description     : The Servicegroup class receives a servicegroup name and
#                     creates for each service of this group a object of a
#                     Service class.
#
#   Inherits from   : object
# ------------------------------------------------------------------------------
class Servicegroup(object):
    logger = None
    _table = 'servicegroups'
    _columns = ['members']

    # --------------------------------------------------------------------------
    #   Method          : __init__
    # --------------------------------------------------------------------------
    #   Description     : The Servicegroup constructor method.
    #
    #   Arguments       : self          A reference to the object itself
    #                     servicegroup  A string with the name of the servicegroup
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def __init__(self, servicegroup):
        if Servicegroup.logger == None:
            Servicegroup.logger = setup_logging(self.__class__.__name__)
        self.servicegroup = servicegroup
        self.logger.debug('Constructor call passed arguments servicegroup: %s', self.servicegroup)

    # --------------------------------------------------------------------------
    #   Method          : get_query
    # --------------------------------------------------------------------------
    #   Description     : A getter method to retrieve the query.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        The query string
    # --------------------------------------------------------------------------
    def get_query(self):
        query = Query()
        return query.get_query(self._table, self._columns, {'name': self.get_servicegroup()})

    # --------------------------------------------------------------------------
    #   Method          : get_servicegroup
    # --------------------------------------------------------------------------
    #   Description     : A getter method to retrieve the name of the service-
    #                     group.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        A string with the servicegroup name
    # --------------------------------------------------------------------------
    def get_servicegroup(self):
        return self.servicegroup

    # --------------------------------------------------------------------------
    #   Method          : get_data
    # --------------------------------------------------------------------------
    #   Description     : This method retrieves the data for a object and stores
    #                     it.
    #
    #   Arguments       : self          A reference to the object itself
    #                     connection    The connection to the livestatus socket
    #                     store_func    A reference to a method
    #                     query_func    Not used but needed
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def get_data(self, connection, store_func, query_func = None):
        data = connection.query_table(self.get_query())
        if data:
            for data_set in data[0][0]:
                obj = Service(data_set[0], data_set[1])
                store_func(obj)


# ------------------------------------------------------------------------------
#   Class           : Downtime
# ------------------------------------------------------------------------------
#   Description     : The Downtime class lists or removes existing or adds new
#                     downtimes. Important is, the comment ist the key to select
#                     the downtimes to remove.
#
#   Inherits from   : object
# ------------------------------------------------------------------------------
class Downtime(object):
    logger = None
    _table = 'downtimes'
    _columns = ['id', 'author', 'host_name', 'service_description', 'start_time', 'end_time', 'duration', 'fixed', 'comment']
    _lables = ['ID', 'Author', 'Hostname', 'Servicename', 'Start', 'End', 'Duration', 'Fixed', 'Comment']

    # --------------------------------------------------------------------------
    #   Method          : __init__
    # --------------------------------------------------------------------------
    #   Description     : The Downtime constructor method.
    #
    #   Arguments       : self          A reference to the object itself
    #                     sites         A Sites object reference
    #                     author        A string with the user name
    #                     comment       A string with the comment for the down-
    #                                   time
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def __init__(self, sites, author, comment = None):
        if Downtime.logger == None:
            Downtime.logger = setup_logging(self.__class__.__name__)
        self.sites = sites
        self.author = author
        self.comment = comment
        self.data = []
        self.dates = {
            'now'           : int(datetime.now().strftime('%s')),
            'start_time'    : None,
            'end_time'      : None,
            'duration'      : None,
        }
        self.logger.debug('Constructor call passed arguments sites (keys): %s, author: %s, comment: %s', self.sites.sites.keys(), self.author, self.comment)

    # --------------------------------------------------------------------------
    #   Method          : _request_object
    # --------------------------------------------------------------------------
    #   Description     : This is a generator method. It loops through all sites
    #                     that contain data and returns the site and the object.
    #                     group.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : site          A string with the site name
    #                     obj           A object reference of Host or Service
    # --------------------------------------------------------------------------
    def _request_objects(self):
        for site in self.sites.get_sites_with_data():
            for obj in self.sites.sites[site].get_monitoring_objects():
                self.logger.debug('Found object on site %s: discovered data is %s', site, obj.get_as_a_string())
                yield site, obj

    # --------------------------------------------------------------------------
    #   Method          : get_data
    # --------------------------------------------------------------------------
    #   Description     : This method retrieves the data for a object and stores
    #                     it.
    #
    #   Arguments       : self          A reference to the object itself
    #                     connection    The connection to the livestatus socket
    #                     store_func    A reference to a method
    #                     query_func    Not used but needed
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def get_data(self, connection, store_func, query_func):
        self.logger.debug('Querying livestatus query: %s', query_func())
        data = connection.query_table(query_func())
        if data:
            self.logger.debug('Retrieved data: %s', data)
            store_func(data)

    # --------------------------------------------------------------------------
    #   Method          : get_query
    # --------------------------------------------------------------------------
    #   Description     : A getter method to retrieve the query. If object is
    #                     specified a livestatus filter gets also returned.
    #
    #   Arguments       : self          A reference to the object itself
    #                     obj           A object reference of Host or Service
    #   Return          : string        The query string
    # --------------------------------------------------------------------------
    def get_query(self, obj = None):
        query = Query()
        if obj == None:
            return query.get_query(self._table, self._columns)
        else:
            return query.get_query(self._table, self._columns, obj.get_filter_for_downtime())

    # --------------------------------------------------------------------------
    #   Method          : list_downtimes
    # --------------------------------------------------------------------------
    #   Description     : This method queries livestatus and passes the result
    #                     to a print method. If the optional filter is not given
    #                     all downtimes get retrieved.
    #                     optional.
    #
    #   Arguments       : self          A reference to the object itself
    #                     filter        A boolean, ether True or False
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def list_downtimes(self, filter=True):
        print "{0:8s} {1:10s} {2:20s} {3:40s} {4:10s} {5:10s} {6:10s} {7:6s} {8:80s}".format(
            self._lables[0],
            self._lables[1],
            self._lables[2],
            self._lables[3],
            self._lables[4],
            self._lables[5],
            self._lables[6],
            self._lables[7],
            self._lables[8]
        )
        if filter:
            for site, obj in self._request_objects():
                obj.get_data(self.sites.sites[site].get_connection(), self.print_downtime, self.get_query, obj)
        else:
            for site in self.sites.get_sites():
                self.get_data(self.sites.sites[site].get_connection(), self.print_downtime, self.get_query)

    # --------------------------------------------------------------------------
    #   Method          : add_downtimes
    # --------------------------------------------------------------------------
    #   Description     : This method sends commands to livestatus to add the
    #                     requested downtimes.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def add_downtimes(self):
        for site, obj in self._request_objects():
            cmd = Command()
            self.sites.sites[site].get_connection().command(cmd.add_downtime(obj, self))

    # --------------------------------------------------------------------------
    #   Method          : remove_downtimes
    # --------------------------------------------------------------------------
    #   Description     : This method sends commands to livestatus to evaluate
    #                     the downtime id and creates and executes the command
    #                     to remove the specified downtime.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def remove_downtimes(self):
        for site, obj in self._request_objects():
            obj.get_data(self.sites.sites[site].get_connection(), self.exec_comand, self.get_query, obj)

    # --------------------------------------------------------------------------
    #   Method          : print_downtime
    # --------------------------------------------------------------------------
    #   Description     : This method prints all retrieved data if comment is
    #                     None or the comment of the downtime matches the
    #                     comment passed to the programm.
    #
    #   Arguments       : self          A reference to the object itself
    #                     data          A list of lists
    #                     obj           Optional and not used
    #                     connection    Optional and not used
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def print_downtime(self, data, obj = None, connection = None):
        for line in data:
            if self.get_comment() == None or self.get_comment() == line[8].encode('utf-8'):
                print "{0:8d} {1:10s} {2:20s} {3:40s} {4:10d} {5:10d} {6:10d} {7:6d} {8:80s}".format(
                    line[0],
                    line[1][:10].encode('utf-8'),
                    line[2][:20].encode('utf-8'),
                    line[3][:40].encode('utf-8'),
                    line[4],
                    line[5],
                    line[6],
                    line[7],
                    line[8][:80].encode('utf-8')
                )

    # --------------------------------------------------------------------------
    #   Method          : exec_command
    # --------------------------------------------------------------------------
    #   Description     : This method executes a command if the comment passed
    #                     by data matches the comment stored in this object.
    #
    #   Arguments       : self          A reference to the object itself
    #                     data          A list of lists
    #                     obj           the object of which the downtime might
    #                                   be removed
    #                     connection    The connecten to livestatus
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def exec_comand(self, data, obj, connection):
        # Compare the comment
        if data[0][8] == self.get_comment():
            cmd = Command()
            connection.command(cmd.remove_downtime(obj, data, self))

    # --------------------------------------------------------------------------
    #   Method          : get_author
    # --------------------------------------------------------------------------
    #   Description     : Getter method, returns the author.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        The user name
    # --------------------------------------------------------------------------
    def get_author(self):
        return self.author

    # --------------------------------------------------------------------------
    #   Method          : get_comment
    # --------------------------------------------------------------------------
    #   Description     : Getter method, returns the downtime comment.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : string        The comment
    # --------------------------------------------------------------------------
    def get_comment(self):
        return self.comment

    # --------------------------------------------------------------------------
    #   Method          : get_now
    # --------------------------------------------------------------------------
    #   Description     : Getter method, returns the actual date if available
    #                     for the downtime object.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : int           Date as unix epoch time else None
    # --------------------------------------------------------------------------
    def get_now(self):
        return self.dates['now'] if self.dates['now'] else None

    # --------------------------------------------------------------------------
    #   Method          : get_start_time
    # --------------------------------------------------------------------------
    #   Description     : Getter method, returns the start time for the downtime
    #                     object.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : int           Date as unix epoch time else None
    # --------------------------------------------------------------------------
    def get_start_time(self):
        return self.dates['start_time'] if self.dates['start_time'] else None

    # --------------------------------------------------------------------------
    #   Method          : set_start_time
    # --------------------------------------------------------------------------
    #   Description     : Setter method, retrieves the start time.
    #
    #   Arguments       : self          A reference to the object itself
    #                     start_time    Date in unix epoch time
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def set_start_time(self, start_time):
        self.dates['start_time'] = int(start_time)
        self.logger.debug('Setting downtime start time to: %d', self.dates['start_time'])

    # --------------------------------------------------------------------------
    #   Method          : get_end_time
    # --------------------------------------------------------------------------
    #   Description     : Getter method, returns the end time for the downtime
    #                     object.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : int           Date as unix epoch time else None
    # --------------------------------------------------------------------------
    def get_end_time(self):
        return self.dates['end_time'] if self.dates['end_time'] else None

    # --------------------------------------------------------------------------
    #   Method          : set_end_time
    # --------------------------------------------------------------------------
    #   Description     : Setter method, retrieves the end time.
    #
    #   Arguments       : self          A reference to the object itself
    #                     end_time      Date in unix epoch time
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def set_end_time(self, end_time):
        self.dates['end_time'] = int(end_time)
        self.logger.debug('Setting downtime end time to: %d', self.dates['end_time'])

    # --------------------------------------------------------------------------
    #   Method          : get_duration
    # --------------------------------------------------------------------------
    #   Description     : Getter method, returns the duration in second for the
    #                     downtime object.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : int           Date as unix epoch time else None
    # --------------------------------------------------------------------------
    def get_duration(self):
        return self.dates['duration'] if self.dates['duration'] else None

    # --------------------------------------------------------------------------
    #   Method          : set_duration
    # --------------------------------------------------------------------------
    #   Description     : Setter method, retrieves the duration of the downtime.
    #
    #   Arguments       : self          A reference to the object itself
    #                     duration      Duration in seconds
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def set_duration(self, duration):
        self.dates['duration'] = int(duration)
        self.logger.debug('Setting downtime duration to: %d', self.dates['duration'])

    # --------------------------------------------------------------------------
    #   Method          : calculate_end_time
    # --------------------------------------------------------------------------
    #   Description     : If start time and duration is given, this method
    #                     calculates the end time.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def calculate_end_time(self):
        self.set_end_time(self.get_start_time() + self.get_duration())
        self.logger.debug('Calculating downtime end time')

    # --------------------------------------------------------------------------
    #   Method          : calculate_duration
    # --------------------------------------------------------------------------
    #   Description     : If start time and end time is given, this method
    #                     calculates the duration.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def calculate_duration(self):
        self.set_duration(self.get_start_time() - self.get_end_time())
        self.logger.debug('Calculating downtime duration')

    # --------------------------------------------------------------------------
    #   Method          : validate_dates
    # --------------------------------------------------------------------------
    #   Description     : This method validates the given dates on
    #                     plausibility.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : boolean       True if plausible else False
    # --------------------------------------------------------------------------
    def validate_dates(self):
        self.logger.debug('Validate downtime: %d < %d and %d > %d', self.get_start_time(), self.get_end_time(), self.get_end_time(), self.get_now())
        return True if self.get_start_time() < self.get_end_time() and self.get_end_time() > self.get_now() else False


# ------------------------------------------------------------------------------
#   Class           : Query
# ------------------------------------------------------------------------------
#   Description     : The Query class receives a bunch of arguments and creates
#                     a livestatus query out of it.
#
#   Inherits from   : object
# ------------------------------------------------------------------------------
class Query(object):
    logger = None

    # --------------------------------------------------------------------------
    #   Method          : __init__
    # --------------------------------------------------------------------------
    #   Description     : The Query constructor method.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def __init__(self):
        if Query.logger == None:
            Query.logger = setup_logging(self.__class__.__name__)

    # --------------------------------------------------------------------------
    #   Method          : get_query
    # --------------------------------------------------------------------------
    #   Description     : The method creates a query string with all the
    #                     received arguments. Then it returns the created query.
    #
    #   Arguments       : self          A reference to the object itself
    #                     table         The name of the livestatus table.
    #                     columns       The requested columns.
    #                     filter        Optional a dictionary of key value pairs
    #                                   to form the Filter. The key has to be a
    #                                   valid column name of the queried table
    #   Return          : string        The query string
    # --------------------------------------------------------------------------
    def get_query(self, table, columns, filter = None):
        query = "GET {0}{1}{2}".format(
            table,
            self._columns(columns),
            self._filter(filter))
        self.logger.debug('Livestatus query: %s', ' - '.join(query.split('\n')))
        return query

    # --------------------------------------------------------------------------
    #   Method          : _columns
    # --------------------------------------------------------------------------
    #   Description     : If the passed columns list is not empty, this method
    #                     will join all columns with a space and return it.
    #
    #   Arguments       : self          A reference to the object itself
    #                     columns       The requested columns.
    #   Return          : string        The query string
    # --------------------------------------------------------------------------
    def _columns(self, columns):
        if columns == None:
            return ""
        else:
            return "\nColumns: " + " ".join(columns)

    # --------------------------------------------------------------------------
    #   Method          : _filter
    # --------------------------------------------------------------------------
    #   Description     : This methode creates a query filter. The key has to
    #                     be one of the column names of the queried table.
    #
    #   Arguments       : self          A reference to the object itself
    #                     filter        A dictionary of column: requested value
    #                                   pairs
    #   Return          : string        The query string
    # --------------------------------------------------------------------------
    def _filter(self, filter):
        string = ""

        if filter == None:
            return string

        for key, value in filter.items():
            if type(value) == list:
                for v in value:
                    string += "\nFilter: " + key + " = " + v
                if len(value) > 1:
                    string += "\nOr: " + str(len(value))
            else:
                string += "\nFilter: " + key + " = " + value
        return string


# ------------------------------------------------------------------------------
#   Class           : Command
# ------------------------------------------------------------------------------
#   Description     : This class mainly creates a livestatus command which can
#                     be passed to the command method of the livestatus module.
#
#   Inherits from   : object
# ------------------------------------------------------------------------------
class Command(object):
    logger = None

    # --------------------------------------------------------------------------
    #   Method          : __init__
    # --------------------------------------------------------------------------
    #   Description     : The Command constructor method.
    #
    #   Arguments       : self          A reference to the object itself
    #   Return          : -             N/A
    # --------------------------------------------------------------------------
    def __init__(self):
        if Command.logger == None:
            Command.logger = setup_logging(self.__class__.__name__)

    # --------------------------------------------------------------------------
    #   Method          : add_downtime
    # --------------------------------------------------------------------------
    #   Description     : The method creates a command string with the settings
    #                     of the passed object references to add a downtime for
    #                     a Host or Service object.
    #
    #   Arguments       : self          A reference to the object itself
    #                     obj           A reference to a object of class Host or
    #                                   Service
    #                     downtime      A reference to a object of class
    #                                   Downtime
    #   Return          : command       The created command string
    # --------------------------------------------------------------------------
    def add_downtime(self, obj, downtime):
        command  = "[" + str(downtime.get_now()) + "] "
        command += obj.get_downtime_operation('schedule') + ";"
        command += obj.get_as_a_string() + ";"
        command += str(downtime.get_start_time()) + ";"
        command += str(downtime.get_end_time()) + ";0;0;"
        command += str(downtime.get_duration()) + ";"
        command += downtime.get_author() + ";"
        command += downtime.get_comment() + "\n"
        self.logger.debug('Livestatus command: COMMAND %s', command)

        return command

    # --------------------------------------------------------------------------
    #   Method          : remove_downtime
    # --------------------------------------------------------------------------
    #   Description     : The method creates a command string with the settings
    #                     of the passed object references to remove a downtime
    #                     for a Host or Service object.
    #
    #   Arguments       : self          A reference to the object itself
    #                     obj           A reference to a object of class Host or
    #                                   Service
    #                     data          A list reference with information to a
    #                                   specific obj, where data[0][0] holds
    #                                   the needed downtime id
    #   Return          : command       The created command string
    # --------------------------------------------------------------------------
    def remove_downtime(self, obj, data, downtime):
        command = "[{0}] {1};{2}\n".format(
            str(downtime.get_now()),
            obj.get_downtime_operation('remove'),
            str(data[0][0]))
        self.logger.debug('Livestatus command: COMMAND %s', command)

        return command


# ------------------------------------------------------------------------------
#   Part            : Main Body
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
#   Function        : setup_logging
# ------------------------------------------------------------------------------
#   Description     : This function allows to setup the logging facility for
#                     main and all inline classes the same but also take the
#                     class name as the logger.
#
#   Arguments       : name          The name of the logger
#   Return          : object        The reference to the logging object
# ------------------------------------------------------------------------------
def setup_logging(name):
    # setup of the log facility
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # define formatter
    form_console = logging.Formatter(
        '[%(module)s:%(name)s:%(funcName)s:%(lineno)d] %(levelname)s:%(message)s'
    )
    form_file = logging.Formatter(
        '%(asctime)s [%(module)s:%(name)s:%(funcName)s:%(lineno)d] %(levelname)s:%(message)s'
    )

    # define handler
    log_console = logging.StreamHandler(sys.stdout)
    log_file = logging.FileHandler(path_var_log + "/downtime.log")

    # define log level for each handler
    log_console.setLevel(logging.DEBUG)
    log_file.setLevel(logging.DEBUG)

    # assign formatter to each handler
    log_console.setFormatter(form_console)
    log_file.setFormatter(form_file)

    # assign each handler to the logger
    logger.addHandler(log_console)
    logger.addHandler(log_file)

    return logger

# ------------------------------------------------------------------------------
#   Function        : validate_downtime
# ------------------------------------------------------------------------------
#   Description     : Validate the start- end enddate of the downtime. The
#                     results get stored in a Downtime object.
#
#   Arguments       : args          All given command line arguments
#                     sites         A reference to the MultiSite Class
#   Return          : boolean       True if all went fine else False
# ------------------------------------------------------------------------------
def validate_downtime(args, downtime):
    # Check argument combination for the dates
    # -b and -B (mandatory)
    downtime.set_start_time(datetime.strptime(args.begindate + " " + args.begin, "%d-%m-%Y %H:%M").strftime('%s'))
    # -e and -E (optional)
    if args.enddate or args.end:
        if args.enddate:
            if args.end:
                downtime.set_end_time(datetime.strptime(args.enddate + " " + args.end, "%d-%m-%Y %H:%M").strftime('%s'))
            else:
                logger.critical('Please specify the end time (-e) of the downtime')
                return False
        else:
            downtime.set_end_time(datetime.strptime(datetime.now().strftime('%d-%m-%Y') + " " + args.end, "%d-%m-%Y %H:%M").strftime('%s'))
        downtime.calculate_duration()
    # -d (optional)
    else:
        # use duration instead
        downtime.set_duration(args.duration)
        downtime.calculate_end_time()

    # Check for plausability
    return downtime.validate_dates()

# ------------------------------------------------------------------------------
#   Function        : validate_date
# ------------------------------------------------------------------------------
#   Description     : Validate a date string past as command line argument.
#                     This function is only used in the argparse part.
#
#   Arguments       : date          Date string
#   Return          : date          The validated string
# ------------------------------------------------------------------------------
def validate_date(date):
    try:
        logger.debug('Valid date: %s', datetime.strptime(date, "%d-%m-%Y").strftime("%d-%m-%Y"))
        return datetime.strptime(date, "%d-%m-%Y").strftime("%d-%m-%Y")
    except ValueError:
        msg = "Date argument is not in a valid format: '{0}'.".format(date)
        logger.critical(msg)
        raise argparse.ArgumentTypeError(msg)

# ------------------------------------------------------------------------------
#   Function        : validate_time
# ------------------------------------------------------------------------------
#   Description     : Validate a time string passed as command line argument.
#                     This function is only used in the argparse part.
#
#   Arguments       : time          Time string
#   Return          : time          The validated string
# ------------------------------------------------------------------------------
def validate_time(time):
    try:
        logger.debug('Valid time: %s', datetime.strptime(time, "%H:%M").strftime("%H:%M"))
        return datetime.strptime(time, "%H:%M").strftime("%H:%M")
    except ValueError:
        msg = "Time argument is not in a valid format: '{0}'.".format(time)
        logger.critical(msg)
        raise argparse.ArgumentTypeError(msg)

# ------------------------------------------------------------------------------
#   Function        : validate_args
# ------------------------------------------------------------------------------
#   Description     : Validate all arguments and store the data into the related
#                     class object.
#
#   Arguments       : args          Arguments passed by commandline
#                     sites         Reference to the Sites object
#   Return          : boolean       True if okay else False
# ------------------------------------------------------------------------------
def validate_args(args, sites):

    # only a host and service is given
    if args.service and args.host:
        # Generator to create all posible combinations of host and service
        mp = ((h, s) for h in args.host.split(',') for s in args.service.split(','))
        # Loop through the list mp and create an object of class service
        for h, s in mp:
            obj = Service(h, s)
            sites.append_obj_to_site(obj)
    # only a host is given
    elif args.host:
        for h in args.host.split(','):
            obj = Host(h)
            sites.append_obj_to_site(obj)
    # only a hostgroup is given
    elif args.hostgroup:
        obj = Hostgroup(args.hostgroup)
        sites.append_obj_to_site(obj)
    # only a servicegroup is given
    elif args.servicegroup:
        obj = Servicegroup(args.servicegroup)
        sites.append_obj_to_site(obj)
    # in all other cases generate an error message
    else:
        if args.ignore or (args.comment != None and args.operation == 'list'):
            logger.debug('Ignore flag is set or just a listing of all downtimes is requested')
            return True
        else:
            logger.critical('Allowed is either a hostgroup or a servicegroup or a host or host and service')
            return False

    return True


# ------------------------------------------------------------------------------
#   Function        : main
# ------------------------------------------------------------------------------
#   Description     : Parse the given command line arguments and create a nice
#                     formatted help output if requested.
#
#   Arguments       : argv          The argument list
#   Return          : int           0 if everything went fine else 1
# ------------------------------------------------------------------------------
def main(argv):
    parser = argparse.ArgumentParser()

    # group host
    ghost = parser.add_mutually_exclusive_group()
    ghost.add_argument('-n', '--host', type=str,
        help='The name of the host'
    )
    ghost.add_argument('-N', '--hostgroup', type=str,
        help='The name of the hostgroup'
    )

    # group service
    gservice = parser.add_mutually_exclusive_group()
    gservice.add_argument('-s', '--service', type=str,
        help='The name of the service'
    )
    gservice.add_argument('-S', '--servicegroup', type=str,
        help='The name of the servicegroup'
    )

    # general
    parser.add_argument('-o', '--operation', type=str, default='list',
        choices=['add', 'list', 'remove'],
        help='Specify a operation, one of add, remove or list (default is list)'
    )
    gcomment = parser.add_mutually_exclusive_group()
    gcomment.add_argument('-c', '--comment', type=str, default=None,
        help='Descriptive comment for the downtime downtime'
    )
    gcomment.add_argument('-i', '--ignore', action='store_true', default=False,
        help='Bypass the comment argument, only available for the list argument'
    )
    parser.add_argument('-U', '--url', type=str,
        default='http://localhost/cmk_master/check_mk/',
        help='Base-URL of Multisite (default: guess local OMD site)'
    )
    parser.add_argument('-P', '--path', type=str,
        default='/omd/sites',
        help='The OMD base path (default: /omd/sites)'
    )
    parser.add_argument('-v', '--verbose', action='store_true',
        help='Verbose output'
    )

    # Begin Time and Date
    parser.add_argument('-b', '--begin', type=validate_time,
        default=datetime.now().strftime('%H:%M'),
        help='Start time of the downtime (format: HH:MM, default: now)',
    )
    parser.add_argument('-B', '--begindate', type=validate_date,
        default=datetime.today().strftime('%d-%m-%Y'),
        help='Start date of the downtime (format: dd-mm-yyyy, default: today)'
    )

    # End Time and Date
    parser.add_argument('-e', '--end', type=validate_time,
        help='End time of the downtime (format: HH:MM)'
    )
    parser.add_argument('-E', '--enddate', type=validate_date,
        help='End date of the downtime, -E is ignored if -e is not set (format: dd-mm-yyyy)'
    )

    # Duration
    parser.add_argument('-d', '--duration', type=int, default=7200,
        help='Duration of the downtime in seconds, if -e is set, duration is ignored (default: 7200)'
    )

    # Identification
    parser.add_argument('-u', '--user', type=str, required=True,
        help='Name of the automation user'
    )
    parser.add_argument('-p', '--secret', type=str, required=True,
        help='Secret of the automation user'
    )
    args = parser.parse_args(argv)
    logger.debug('Passed CLI arguments: %r', args)

    # Collecting and validating all data
    logger.debug('Collect and validate all passed data')
    sites = Sites(args.user, args.secret, args.path, args.url)
    logger.debug('Create downtime object')
    downtime = Downtime(sites, args.user, args.comment)
    if args.operation == 'add' and not validate_downtime(args, downtime):
        logger.critical('Error in date and time arguments')
        return 1
    if not validate_args(args, sites):
        return 1

    # List, set or remove downtimes
    # List downtimes
    if args.operation == 'list':
        if (args.ignore and len(sites.get_sites_with_data()) == 0) or (args.comment != None and len(sites.get_sites_with_data()) == 0):
            downtime.list_downtimes(filter = False)
        else:
            downtime.list_downtimes()

    # Add downtimes
    elif args.operation == 'add':
        downtime.add_downtimes()

    # Remove downtimes
    elif args.operation == 'remove':
        downtime.remove_downtimes()

    return 0

# ------------------------------------------------------------------------------
#   Main
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    logger = setup_logging('main')
    sys.exit(main(sys.argv[1:]))
