#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
# ------------------------------------------------------------------------------
#
#   Program         : downtime.py
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
import sys
import logging
import argparse
from datetime import datetime
import livestatus
import requests


# ------------------------------------------------------------------------------
#   Global Variables
# ------------------------------------------------------------------------------
# make logging facility globally available
global logger

# build the working environment
path_bin = os.path.dirname(os.path.realpath(__file__))
path_base = os.path.dirname(path_bin)
path_etc = os.path.join(path_base, 'etc')
path_var_log = os.path.join(path_base, 'var/log')
if not os.path.exists(path_var_log):
    os.mkdir(path_var_log)


# ------------------------------------------------------------------------------
#   Part            : Class definition
# ------------------------------------------------------------------------------
# TODO: Rethink the architecture of the classes
# TODO: Add unit testing


class Sites(object):
    """
    The Sites class stores all active check_mk sites in its object.
    """
    # TODO: Create method __iter__ and __next__ (Python 2 next()) to make the object iterable
    logger = None

    def __init__(self, user, secret, path, url):
        """
        The constructor method for class Sites.

        Attributes:
            user        the name of the user
            secret      the secret of the given user
            path        the base path (OMD_ROOT)
            url         the url
        """
        if Sites.logger is None:
            Sites.logger = setup_logging(self.__class__.__name__)
        self.user = user
        self.secret = secret
        self.path = path
        self.url = url
        self.sites = {}
        self.sites_with_data = []
        self.itter_idx = 0
        self.payload = {
            "action": 'get_site',
            "_username": self.user,
            "_secret": self.secret,
            "output_format": 'python',
            "site_id": '',
        }

        self.logger.debug('Constructor call passed arguments user: %s, path: %s, url: %s',
                          self.user, self.path, self.url)
        for sitename in os.listdir(self.path):
            self.payload["site_id"] = sitename
            self.logger.debug('Collecting informations for site %s', sitename)
            response = requests.get(self.url + "webapi.py", params=self.payload)
            site_struct = eval(response.content)

            # Make sure that the collected sites are available
            if site_struct['result_code'] == 0 and site_struct['result']['site_config']['disabled'] is False:
                self.logger.debug('Site %s is enabled', sitename)
                socket_path = self.path + "/" + sitename + "/tmp/run/live"
                if os.path.exists(socket_path):
                    self.logger.debug('Livestatus socket found: %s', socket_path)
                    self.sites[sitename] = Site(sitename, site_struct['result']['site_config']['alias'],
                                                "unix:" + socket_path)
                else:
                    self.logger.error('Livestatus socket not found: %s', socket_path)
            else:
                self.logger.debug('Site %s is disabled', sitename)

    def __iter__(self):
        """
        The object iterator.

        Return:
            obj         reference to its self
        """
        return self

    def next(self):
        """
        The next method for the iterator.

        Raises:
            StopIteration

        Return:
            obj             reference to its self
        """
        if self.itter_idx <= len(self.sites_with_data):
            self.itter_idx += 1
            return self.sites_with_data[self.itter_idx - 1]
        else:
            raise StopIteration

    def append_obj_to_site(self, obj):
        """
        This method takes a obj of class host or service. It will find the site
        to which the obj is related and stores it to the evaluated site or sites.

        Attributes:
            obj         a object of a class host or service
        """
        for site in self.sites.keys():
            self.sites[site].validate_data(obj)
        self.collect_sites_with_data()

    def collect_sites_with_data(self):
        """
        This method will find all sites that have valid data and stores the site
        name in a list.
        """
        for site in self.sites.keys():
            if self.sites[site].has_data:
                self.sites_with_data.append(site)

    def get_sites(self):
        """
        This method returns all sites which are active.

        Return:
            list        a list of all active sites
        """
        return self.sites.keys()

    def get_sites_with_data(self):
        """
        This method returns all sites which have data.

        Return:
             list       a list of all sites with data
        """
        return self.sites_with_data


class Site(object):
    """
    The Site class represents all sites of a check_mk multisite environment.
    """
    # TODO: Create method __iter__ and __next__ (Python 2 next()) to make the object iterable
    logger = None

    def __init__(self, sitename, alias, socket):
        """
        The constructor method for class Sites.

        Attributes:
            sitename    a string with the site name
            alias       a string with the alias of the site
            socket      the filename with the absolute path of the livestatus
                        socket
        """
        if Site.logger is None:
            Site.logger = setup_logging(self.__class__.__name__)
        self.sitename = sitename
        self.alias = alias
        self.socket = socket
        self.connection = livestatus.SingleSiteConnection(self.socket)
        self.monitoring_objects = []
        self.logger.debug('Constructor call passed arguments sitename: %s, alias: %s, socket: %s',
                          self.sitename, self.alias, self.socket)

    def get_sitename(self):
        """
        Getter method that returns the site name.

        Return:
            string      returns the site name
        """
        return self.sitename

    def get_connection(self):
        """
        Returns the connection to the livestatus socket.

        Return:
            filehandle  the filehandle to the lifestatus socket
        """
        return self.connection

    def validate_data(self, obj):
        """
        This method validates the data of the passed object.

        Arguments:
            obj         the object that needs to be validated
        """
        self.logger.debug('Validate data for site %s', self.get_sitename())
        obj.get_data(self.get_connection(), self.push, obj.get_query)

    def push(self, obj):
        """
        This method appends an obj to the monitored object list.
        """
        self.monitoring_objects.append(obj)

    def has_data(self):
        """
        Returns True if there is data in the object list or False if there is
        not.

        Return:
            boolean     True if data is available els False
        """
        return True if len(self.monitoring_objects) > 0 else False

    def get_monitoring_objects(self):
        """
        This is a generator method which returns the list of monitoring_objects.

        Return:
            obj         an object reference of Host or Service
        """
        for obj in self.monitoring_objects:
            yield obj


class Host(object):
    """
    The Host class represents a host in check_mk.
    """
    logger = None
    _table = 'hosts'
    _columns = ['name']

    def __init__(self, host_name):
        """
        The constructor method for class Host.

        Attributes:
            host_name   a string with the name of the host
        """
        if Host.logger is None:
            Host.logger = setup_logging(self.__class__.__name__)
        self.host_name = host_name
        self.logger.debug('Constructor call passed arguments host_name: %s', self.host_name)

    def get_query(self):
        """
        This method returns the query for the listing of hosts in downtime.

        Return:
            string      returns a livestatus query string
        """
        query = Query()
        return query.get_query(self._table, self._columns, {self._columns[0]: self.get_host_name()})

    def get_host_name(self):
        """
        This method returns the host name of the Host object.

        Return:
            string      returns a string with the host name
        """
        return self.host_name

    def get_data(self, connection, store_func, query_func, obj=None):
        """
        This method retrieves the data for a object and stores it. If the object
        isn't set all object will be received.

        Attributes:
            connection  the connection filehandle to the livestatus socket
            store_func  a reference to a method
            query_func  a reference to a method
            obj         a object reference which is optional
        """
        if obj is None:
            data = connection.query_table(query_func())
            if data:
                store_func(self)
        else:
            data = connection.query_table(query_func(obj))
            if data:
                store_func(data, obj, connection)

    def get_filter_for_downtime(self):
        """
        This method returns the dictionary that is needed to generate the filter
        part of a query.

        Return:
            dictionary  returns a dictionary for a filter
        """
        return {'host_name': self.get_host_name()}

    def get_as_a_string(self):
        """
        This method returns the hostname.

        Return:
            string      the host name of the host or service object
        """
        return self.get_host_name()

    @staticmethod
    def get_downtime_operation(operator):
        """
        This method returns the operator for the downtime command.

        Attributes:
            operator    a string schedule to add a downtime every other string
                        will return a delete operation

        Return:
            string      nether SCHEDULE_HOST_DOWNTIME or DEL_HOST_DOWNTIME
        """
        return "SCHEDULE_HOST_DOWNTIME" if operator == 'schedule' else "DEL_HOST_DOWNTIME"


class Service(Host):
    """
    The Service class represents a check_mk service.
    """
    logger = None
    _table = 'services'
    _columns = ['host_name', 'description']

    def __init__(self, host_name=None, service_name=None):
        """
        The constructor method for class Service.

        Attributes:
            host_name       a string with the name of the host
            service_name    a string with the service name
        """
        if Service.logger is None:
            Service.logger = setup_logging(self.__class__.__name__)
        self.host_name = host_name
        self.service_name = service_name
        self.logger.debug('Constructor call passed arguments host_name: %s, service_name: %s',
                          self.host_name, self.service_name)

    def get_query(self):
        """
        This method returns the query for the listing of services in downtime.

        Return:
            string          a string with the livesstatus query
        """
        query = Query()
        return query.get_query(self._table, self._columns, {self._columns[0]: self.get_host_name(),
                                                            self._columns[1]: self.get_service_name()})

    def get_service_name(self):
        """
        This method returns the service name of the Service object.

        Return:
            string          a string with the service name
        """
        return self.service_name

    def get_filter_for_downtime(self):
        """
        This method returns the dictionary that is needed to generate the filter
        part of a query.

        Return:
            dictionary      a dictionary needed to build the filter for a
                            livestatus query
        """
        return {'host_name': self.get_host_name(), 'service_description': self.get_service_name()}

    def get_as_a_string(self):
        """
        This method returns the hostname and service.

        Return:
            string          the host and service name of the Service object
        """
        return "{0};{1}".format(self.get_host_name(), self.get_service_name())

    @staticmethod
    def get_downtime_operation(operator):
        """
        This method returns the operator for the downtime command.

        Attributes:
            operator        expects schedule to add a downtime or it will delete
                            an existing scheduled downtime

        Return:
            string          Nether SCHEDULE_SVC_DOWNTIME or DEL_SVC_DOWNTIME
        """
        return "SCHEDULE_SVC_DOWNTIME" if operator == 'schedule' else "DEL_SVC_DOWNTIME"


class Hostgroup(object):
    """
    The Hostgroup class receives a hostgroup name and creates for each host of
    this group a object of a Host class.
    """
    logger = None
    _table = 'hostgroups'
    _columns = ['members']

    def __init__(self, name):
        """
        The constructor method for class Hostgroup.

        Attributes:
            hostgroup       a string with the name of the hostgroup
        """
        if Hostgroup.logger is None:
            Hostgroup.logger = setup_logging(self.__class__.__name__)
        self.name = name
        self.logger.debug('Constructor call passed arguments %s: %s', Hostgroup._table, self.name)

    def get_query(self):
        """
        A getter method to retrieve the query.

        Return:
            string          the query sring for livestatus
        """
        query = Query()
        return query.get_query(self._table, self._columns, {'name': self.get_name()})

    def get_name(self):
        """
        A getter method to retrieve the name of the hostgroup.

        Return:
            string          a string with the hostgroup name
        """
        return self.name

    def get_data(self, connection, store_func, query_func=None):
        """
        This method retrieves the data for a object and stores it.

        Attributes:
            connection      the connection to the livestatus socket
            store_func      a reference to a method
            query_func      not used but needed
        """
        data = connection.query_table(self.get_query())
        if data:
            for data_set in data[0][0]:
                obj = Host(data_set)
                store_func(obj)


class Servicegroup(Hostgroup):
    """
    The Servicegroup class receives a servicegroup name and creates for each
    service of this group a object of a Service class.
    """
    logger = None
    _table = 'servicegroups'
    _columns = ['members']

    def __init__(self, name):
        """
        The constructor method for class Servicegroup.

        Attributes:
            servicegroup    a string with the name of the servicegroup
        """
        if Servicegroup.logger is None:
            Servicegroup.logger = setup_logging(self.__class__.__name__)
        self.name = name
        self.logger.debug('Constructor call passed arguments %s: %s', Servicegroup._table, self.name)

    def get_data(self, connection, store_func, query_func=None):
        """
        This method retrieves the data for a object and stores it.

        connection          the connection to the livestatus socket
        store_func          a reference to a method
        query_func          not used but needed
        """
        data = connection.query_table(self.get_query())
        if data:
            for data_set in data[0][0]:
                obj = Service(data_set[0], data_set[1])
                store_func(obj)


class Downtime(object):
    """
    The Downtime class lists or removes existing or adds new downtimes.
    Important is, the comment ist the key to select the downtimes to remove.
    """
    logger = None
    _table = 'downtimes'
    _columns = ['id', 'author', 'host_name', 'service_description', 'start_time',
                'end_time', 'duration', 'fixed', 'comment']
    _lables = ['ID', 'Author', 'Hostname', 'Servicename', 'Start', 'End', 'Duration', 'Fixed', 'Comment']

    def __init__(self, sites, author, comment=None, epoch=False):
        """
        The constructor method for class Downtime.

        Attributes:
            sites           a object reference of class Sites
            author          a string with the name of the author
            comment         a comment string for the downtime
            epoch           show time representations in epoch instead of human
                            readable
        """
        if Downtime.logger is None:
            Downtime.logger = setup_logging(self.__class__.__name__)
        self.sites = sites
        self.author = author
        self.comment = comment
        self.epoch = epoch
        self.data = []
        self.dates = {
            'now': int(datetime.now().strftime('%s')),
            'start_time': None,
            'end_time': None,
            'duration': None,
        }
        self.logger.debug('Constructor call passed arguments sites (keys): %s, author: %s, comment: %s',
                          self.sites.sites.keys(), self.author, self.comment)

    def _request_objects(self):
        """
        This is a generator method. It loops through all sites that contain data
        and returns the site name and the object reference of class Host or Service

        Return:
            site            a string with the site name
            obj             a object reference of class Host or Service
        """
        for site in self.sites.get_sites_with_data():
            for obj in self.sites.sites[site].get_monitoring_objects():
                self.logger.debug('Found object on site %s: discovered data is %s', site, obj.get_as_a_string())
                yield site, obj

    def get_data(self, connection, store_func, query_func):
        """
        This method retrieves the data for a object and stores it.

        Attributes:
            connection      the connection to the livestatus socket
            store_func      a reference to a method
            query_func      not used but needed
        """
        self.logger.debug('Querying livestatus query: %s', query_func())
        data = connection.query_table(query_func())
        if data:
            self.logger.debug('Retrieved data: %s', data)
            store_func(data)

    def get_query(self, obj=None):
        """
        A getter method to retrieve the query. If object is specified a
        livestatus filter gets also returned.

        Attributes:
            obj             a object reference of Host or Service

        Return:
            string          a string with the query for livestatus
        """
        query = Query()
        if obj is None:
            return query.get_query(self._table, self._columns)
        else:
            return query.get_query(self._table, self._columns, obj.get_filter_for_downtime())

    def list_downtimes(self, is_filter=True):
        """
        This method queries livestatus and passes the result to a print method.
        If the optional filter is not given all downtimes get retrieved.

        Attributes:
            is_filter       a boolean True if a filter has been provided
        """
        print "{0:8s} {1:10s} {2:20s} {3:40s} {4:19s} {5:19s} {6:10s} {7:6s} {8:80s}".format(
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
        if is_filter:
            for site, obj in self._request_objects():
                obj.get_data(self.sites.sites[site].get_connection(), self.print_downtime, self.get_query, obj)
        else:
            for site in self.sites.get_sites():
                self.get_data(self.sites.sites[site].get_connection(), self.print_downtime, self.get_query)

    def add_downtimes(self):
        """
        This method sends commands to livestatus to add the requested downtimes.
        """
        for site, obj in self._request_objects():
            cmd = Command()
            self.sites.sites[site].get_connection().command(cmd.add_downtime(obj, self))

    def remove_downtimes(self):
        """
        This method sends commands to livestatus to evaluate the downtime id and
        creates and executes the command to remove the specified downtime.
        """
        for site, obj in self._request_objects():
            obj.get_data(self.sites.sites[site].get_connection(), self.exec_comand, self.get_query, obj)

    def print_downtime(self, data, obj=None, connection=None):
        """
        This method prints all retrieved data if comment is None or the comment
        of the downtime matches the comment passed to the programm.

        Attributes:
            data            a list of lists returnd from livestatus
            obj             optional
            connection      optional
        """
        for line in data:
            if self.get_comment() is None or self.get_comment() == line[8].encode('utf-8'):
                start_date = line[4] if self.epoch else str(datetime.fromtimestamp(line[4]))
                end_date = line[5] if self.epoch else str(datetime.fromtimestamp(line[5]))
                print "{0:8d} {1:10s} {2:20s} {3:40s} {4:19s} {5:19s} {6:10d} {7:6d} {8:80s}".format(
                    line[0],
                    line[1][:10].encode('utf-8'),
                    line[2][:20].encode('utf-8'),
                    line[3][:40].encode('utf-8'),
                    start_date,
                    end_date,
                    line[6],
                    line[7],
                    line[8][:80].encode('utf-8')
                )

    def exec_comand(self, data, obj, connection):
        """
        This method executes a command if the comment passed by data matches the
        comment stored in this object.

        Attributes:
            data            a list of lists from livestatus
            obj             the object reference of type Host or Service from
                            which the downtime shall be removed
            connection      the connection to livestatus
        """
        # Compare the comment
        if data[0][8] == self.get_comment():
            cmd = Command()
            connection.command(cmd.remove_downtime(obj, data, self))

    def get_author(self):
        """
        Getter method, returns the author.

        Return:
            string          a string with the user name
        """
        return self.author

    def get_comment(self):
        """
        Getter method, returns the downtime comment.

        Return:
            string          the comment string
        """
        return self.comment

    def get_now(self):
        """
        Getter method, returns the actual date if available for the downtime
        object.

        Return:
            int             the date as Unix epoch time
        """
        return self.dates['now'] if self.dates['now'] else None

    def get_start_time(self):
        """
        Getter method, returns the start time for the downtime object.

        Return:
            int             the date as Unix epoch time or None
        """
        return self.dates['start_time'] if self.dates['start_time'] else None

    def set_start_time(self, start_time):
        """
        Setter method, retrieves the start time.

        Attributes:
            start_time      the start time as Unix epoch time
        """
        self.dates['start_time'] = int(start_time)
        self.logger.debug('Setting downtime start time to: %d', self.dates['start_time'])

    def get_end_time(self):
        """
        Getter method, returns the end time for the downtime object.

        Return:
            int             the date as Unix epoch time or None
        """
        return self.dates['end_time'] if self.dates['end_time'] else None

    def set_end_time(self, end_time):
        """
        Setter method, retrieves the end time.

        Attributes:
            end_time        the end time as Unix epoch time
        """
        self.dates['end_time'] = int(end_time)
        self.logger.debug('Setting downtime end time to: %d', self.dates['end_time'])

    def get_duration(self):
        """
        Getter method, returns the duration in second for the downtime object.

        Return:
            int             the time in seconds between the start and end date
        """
        return self.dates['duration'] if self.dates['duration'] else None

    def set_duration(self, duration):
        """
        Setter method, retrieves the duration of the downtime.

        Attributes:
            duration        the duration of the downtime in seconds
        """
        self.dates['duration'] = int(duration)
        self.logger.debug('Setting downtime duration to: %d', self.dates['duration'])

    def calculate_end_time(self):
        """
        If start time and duration is given, this method calculates the end time.
        """
        self.set_end_time(self.get_start_time() + self.get_duration())
        self.logger.debug('Calculating downtime end time')

    def calculate_duration(self):
        """
        If start time and end time is given, this method calculates the duration.
        :return:
        """
        self.set_duration(self.get_start_time() - self.get_end_time())
        self.logger.debug('Calculating downtime duration')

    def validate_dates(self):
        """
        This method validates the given dates on plausibility.

        Return:
            boolean         True if date is valid else False
        """
        self.logger.debug('Validate downtime: %d < %d and %d > %d', self.get_start_time(),
                          self.get_end_time(), self.get_end_time(), self.get_now())
        return True if self.get_start_time() < self.get_end_time() and self.get_end_time() > self.get_now() else False


class Query(object):
    """
    The Query class receives a bunch of arguments and creates a livestatus query
    out of it.
    """
    # TODO: Add authentication to allow only permited user to set, remove or list downtimes
    # TODO: Combine queries instead of per object querying
    logger = None

    def __init__(self):
        """
        The constructor method for class Query.
        """
        if Query.logger is None:
            Query.logger = setup_logging(self.__class__.__name__)

    def get_query(self, table, columns, is_filter=None):
        """
        The method creates a query string with all the received arguments. Then
        it returns the created query.

        Attributes:
            table           the name of the livestatus table
            columns         the requested columns
            is_filter       optional a dictionary of key value pairs to form the
                            Filter. The key has to be a valid column name of the
                            queried table

        Return:
            string          the query string for livestatus
        """
        query = "GET {0}{1}{2}".format(
            table,
            self._columns(columns),
            self._filter(is_filter))
        self.logger.debug('Livestatus query: %s', ' - '.join(query.split('\n')))
        return query

    @staticmethod
    def _columns(columns):
        """
        If the passed columns list is not empty, this method will join all
        columns with a space and return it.

        Attributes:
            columns         the requested columns

        Return:
            string          a query string for livestatus
        """
        if columns is None:
            return ""
        else:
            return "\nColumns: " + " ".join(columns)

    @staticmethod
    def _filter(a_filter):
        """
        This methode creates a query filter. The key has to be one of the column
        names of the queried table.
        Attributes:
            a_filter        a dictionary of column: requested value pairs
        """
        string = ""

        if a_filter is None:
            return string

        for key, value in a_filter.items():
            if type(value) == list:
                for v in value:
                    string += "\nFilter: " + key + " = " + v
                if len(value) > 1:
                    string += "\nOr: " + str(len(value))
            else:
                string += "\nFilter: " + key + " = " + value
        return string


class Command(object):
    """
    This class creates mainly a livestatus command which can be passed to the
    command method of the livestatus module.
    """
    logger = None

    def __init__(self):
        """
        The constructor method for class Command.
        """
        if Command.logger is None:
            Command.logger = setup_logging(self.__class__.__name__)

    def add_downtime(self, obj, downtime):
        """
        The method creates a command string with the settings of the passed
        object references to add a downtime for a Host or Service object.

        Attributes:
            obj         a reference to a object of class Host or Service
            downtime    a reference to the downtime object

        Return:
            string      the created livestatus command string
        """
        command = "[" + str(downtime.get_now()) + "] "
        command += obj.get_downtime_operation('schedule') + ";"
        command += obj.get_as_a_string() + ";"
        command += str(downtime.get_start_time()) + ";"
        command += str(downtime.get_end_time()) + ";0;0;"
        command += str(downtime.get_duration()) + ";"
        command += downtime.get_author() + ";"
        command += downtime.get_comment() + "\n"
        self.logger.debug('Livestatus command: COMMAND %s', command)

        return command

    def remove_downtime(self, obj, data, downtime):
        """
        The method creates a command string with the settings of the passed
        object references to remove a downtime for a Host or Service object.

        Attribute:
            obj         a reference to a object of class Host or Service
            data        a list reference with informations to a specific object
                        where data[0][0] has the needed downtime id
            downtime    a reference to the downtime object

        Return:
            string      the created livestatus command string
        """
        command = "[{0}] {1};{2}\n".format(
            str(downtime.get_now()),
            obj.get_downtime_operation('remove'),
            str(data[0][0]))
        self.logger.debug('Livestatus command: COMMAND %s', command)

        return command


# ------------------------------------------------------------------------------
#   Part            : Main Body
# ------------------------------------------------------------------------------

def setup_logging(name):
    """
    This function allows to setup the logging facility for main and all inline
    classes the same but also take the class name as the logger.

    Attribute:
        name        the name of the logger

    Return:
        object      a reference to a logging object
    """
    # TODO: Create a class to be able to implement logging by association (has a)
    # setup of the log facility
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)

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
    log_console.setLevel(logging.INFO)
    log_file.setLevel(logging.DEBUG)

    # assign formatter to each handler
    log_console.setFormatter(form_console)
    log_file.setFormatter(form_file)

    # assign each handler to the logger
    log.addHandler(log_console)
    log.addHandler(log_file)

    return log


def validate_downtime(args, downtime):
    """
    This function validates the start- and enddate and time of the downtime. The
    result gets stored in the passed downtime object.

    Attributes:
        args        all passed command line arguments
        downtime    a reference to a downtime object

    Return:
        boolean     True if all went fine else False
    """
    # Check argument combination for the dates
    # -b and -B (mandatory)
    downtime.set_start_time(datetime.strptime(args.begindate + " " + args.begin,
                                              "%d-%m-%Y %H:%M").strftime('%s'))
    # -e and -E (optional)
    if args.enddate or args.end:
        if args.enddate:
            if args.end:
                downtime.set_end_time(datetime.strptime(args.enddate + " " + args.end,
                                                        "%d-%m-%Y %H:%M").strftime('%s'))
            else:
                logger.critical('Please specify the end time (-e) of the downtime')
                return False
        else:
            downtime.set_end_time(datetime.strptime(datetime.now().strftime('%d-%m-%Y') + " " + args.end,
                                                    "%d-%m-%Y %H:%M").strftime('%s'))
        downtime.calculate_duration()
    # -d (optional)
    else:
        # use duration instead
        downtime.set_duration(args.duration)
        downtime.calculate_end_time()

    # Check for plausability
    return downtime.validate_dates()


def validate_date(date):
    """
    This function validates the passed date argument.

    Raises:
        ArgumentTypeError

    Attribute:
        time        the date string

    Return:
        string      a valid date string
    """
    try:
        logger.debug('Valid date: %s', datetime.strptime(date, "%d-%m-%Y").strftime("%d-%m-%Y"))
        return datetime.strptime(date, "%d-%m-%Y").strftime("%d-%m-%Y")
    except ValueError:
        msg = "Date argument is not in a valid format: '{0}'.".format(date)
        logger.critical(msg)
        raise argparse.ArgumentTypeError(msg)


def validate_time(time):
    """
    This function validates the passed time argument.

    Raises:
        ArgumentTypeError

    Attribute:
        time        the time string

    Return:
        string      a valid time string
    """
    try:
        logger.debug('Valid time: %s', datetime.strptime(time, "%H:%M").strftime("%H:%M"))
        return datetime.strptime(time, "%H:%M").strftime("%H:%M")
    except ValueError:
        msg = "Time argument is not in a valid format: '{0}'.".format(time)
        logger.critical(msg)
        raise argparse.ArgumentTypeError(msg)


def validate_args(args, sites):
    """
    This function will prepare relevant arguments like the passed host, service,
    hostgroup and servicegroup. It creates the related objects and store the
    validated data into it.

    Attributes:
        args        the relevant arguments passed by command line
        sites       a reference to a class Sites object

    Return:
        boolean     True if all went well else False
    """

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
        if args.ignore or (args.comment is not None and args.operation == 'list'):
            logger.debug('Ignore flag is set or just a listing of all downtimes is requested')
            return True
        else:
            logger.critical('Allowed is either a hostgroup or a servicegroup or a host or host and service')
            return False

    return True


def main(argv):
    """
    Parse the given command line arguments and create a nice formatted help
    output if requested.

    Attributes:
        argv        the argument list passed on the command line
    Return:
        int         0 if everything went fine else 1
    """
    parser = argparse.ArgumentParser()
    # TODO: Add grouped_id argument to set an ID for this collection of downtime
    # TODO: Add grouped_id random generator in case the id is not set
    # TODO: Add exclude list as argument for host- and servicegroup

    # group host
    ghost = parser.add_mutually_exclusive_group()
    ghost.add_argument('-n', '--host',
                       help='The name of the host'
                       )
    ghost.add_argument('-N', '--hostgroup',
                       help='The name of the hostgroup'
                       )

    # group service
    gservice = parser.add_mutually_exclusive_group()
    gservice.add_argument('-s', '--service',
                          help='The name of the service'
                          )
    gservice.add_argument('-S', '--servicegroup',
                          help='The name of the servicegroup'
                          )

    # general
    parser.add_argument('-o', '--operation', default='list',
                        choices=['add', 'list', 'remove'],
                        help='Specify a operation, one of add, remove or list (default is list)'
                        )
    gcomment = parser.add_mutually_exclusive_group()
    gcomment.add_argument('-c', '--comment', default=None,
                          help='Descriptive comment for the downtime downtime'
                          )
    gcomment.add_argument('-i', '--ignore', action='store_true', default=False,
                          help='Bypass the comment argument, only available for the list argument'
                          )
    parser.add_argument('-C', '--epoch', action='store_true',
                        default=False,
                        help='Shows the listed downtimes in epoch instead of date and time (default: False)'
                        )
    parser.add_argument('-U', '--url',
                        default='http://localhost/cmk_master/check_mk/',
                        help='Base-URL of Multisite (default: guess local OMD site)'
                        )
    parser.add_argument('-P', '--path',
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
    parser.add_argument('-u', '--user', required=True,
                        help='Name of the automation user'
                        )
    parser.add_argument('-p', '--secret', required=True,
                        help='Secret of the automation user'
                        )
    args = parser.parse_args(argv)
    logger.debug('Passed CLI arguments: %r', args)

    # Collecting and validating all data
    logger.debug('Collect and validate all passed data')
    sites = Sites(args.user, args.secret, args.path, args.url)
    logger.debug('Create downtime object')
    downtime = Downtime(sites, args.user, args.comment, args.epoch)
    if args.operation == 'add' and not validate_downtime(args, downtime):
        logger.critical('Error in date and time arguments')
        return 1
    if not validate_args(args, sites):
        return 1

    # List, set or remove downtimes
    # List downtimes
    if args.operation == 'list':
        if (args.ignore and len(sites.get_sites_with_data()) == 0) or\
                (args.comment is not None and len(sites.get_sites_with_data()) == 0):
            downtime.list_downtimes(is_filter=False)
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

