# check_mk_downtime
This is a command line script for check_mk to list, add or remove downtimes.

The script comes with a help function.
```
usage: dt.py [-h] [-n HOST | -N HOSTGROUP] [-s SERVICE | -S SERVICEGROUP]
             [-o {add,list,remove}] [-c COMMENT | -i] [-U URL] [-P PATH] [-v]
             [-b BEGIN] [-B BEGINDATE] [-e END] [-E ENDDATE] [-d DURATION] -u
             USER -p SECRET

optional arguments:
  -h, --help            show this help message and exit
  -n HOST, --host HOST  The name of the host
  -N HOSTGROUP, --hostgroup HOSTGROUP
                        The name of the hostgroup
  -s SERVICE, --service SERVICE
                        The name of the service
  -S SERVICEGROUP, --servicegroup SERVICEGROUP
                        The name of the servicegroup
  -o {add,list,remove}, --operation {add,list,remove}
                        Specify a operation, one of add, remove or list
                        (default is list)
  -c COMMENT, --comment COMMENT
                        Descriptive comment for the downtime downtime
  -i, --ignore          Bypass the comment argument, only available for the
                        list argument
  -U URL, --url URL     Base-URL of Multisite (default: guess local OMD site)
  -P PATH, --path PATH  The OMD base path (default: /omd/sites)
  -v, --verbose         Verbose output
  -b BEGIN, --begin BEGIN
                        Start time of the downtime (format: HH:MM, default:
                        now)
  -B BEGINDATE, --begindate BEGINDATE
                        Start date of the downtime (format: dd-mm-yyyy,
                        default: today)
  -e END, --end END     End time of the downtime (format: HH:MM)
  -E ENDDATE, --enddate ENDDATE
                        End date of the downtime, -E is ignored if -e is not
                        set (format: dd-mm-yyyy)
  -d DURATION, --duration DURATION
                        Duration of the downtime in seconds, if -e is set,
                        duration is ignored (default: 7200)
  -u USER, --user USER  Name of the automation user
  -p SECRET, --secret SECRET
                        Secret of the automation user
```

Lets see what we can do.
```
./downtime.py -h
```
Will output the above help text. By the way the only command that does not need authentication.
```
./downtime.py -u <automation> -p <secret> -i -o list
```
Will list all scheduled downtimes.
```
./downtime.py -u <automation> -p <secret> -c "Downtime for maintenance" -o list
```
Will show all scheduled downtimes with the passed comment.
```
./downtime.py -u <automation> -p <secret> -c "Downtime for maintenance" -o remove
```
Will remove all the scheduled downtimes with the given comment. That said, the comment can be used as a kind of key.
```
./downtime.py -u <automation> -p <secret> -c "Maintenance ID:002324 -S <servicegroup> -B 2019-06-23 -b 12:00 -E 2019-06-25 -e 12:00 -o add
```
Will add a downtime for a servicegroup for two days beginning at June 23 2019 12:00 PM and ending at June 25 2019 12:00 PM.
```
./downtime.py -u <automation> -p <secret> -c "Maintenance ID:002324 -S <servicegroup> -o remove
```
Will remove the downtime set before.

TODO:
  - There should be a CLI argument to list the downtimes in human readable fashion
  - The classes are just 'containers' that store data. It would make more sense to make them iterable.
  - The setup of the logging facility has been realised by calling a function. This is kind of ugly. Nice would be a reference to the logging facility (Has a)
  - It should be possible to only allow downtimes for hosts and services where the user is permitted. (How to pass the user credentials without exposing them to all others)
  - Rethink the architecture of the model (I'm not happy)
  - Make the comments python like
  - Implement unit tests
  - Combine livestatus queries instead of querying every single host or service
  
Since I'm not really familiar with python, I still learning, I highly appreciate any input that hepls me to improve my skills.  
