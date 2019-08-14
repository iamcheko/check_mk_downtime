# check_mk_downtime
This is a command line script for check_mk to list, add or remove downtimes. It can be used to trigger downtimes from command line.

The script comes with a help function.
```
usage: downtime.py  [-h] [-n HOST | -N HOSTGROUP] [-x]
                    [-s SERVICE | -S SERVICEGROUP] [-o {add,list,remove}]
                    [-c COMMENT] (-g GROUPEDID | -i) [-C] [-U URL] [-P PATH]
                    [-v] [-b BEGIN] [-B BEGINDATE] [-e END] [-E ENDDATE]
                    [-d DURATION] [-a AUTHOR] -u USER -p SECRET [-A] [-q]
                    [-l LIMIT]

optional arguments:
  -h, --help            show this help message and exit
  -n HOST, --host HOST  The name of the host
  -N HOSTGROUP, --hostgroup HOSTGROUP
                        The name of the hostgroup
  -x, --exclusive       Just define downtime for the host without services
  -s SERVICE, --service SERVICE
                        The name of the service
  -S SERVICEGROUP, --servicegroup SERVICEGROUP
                        The name of the servicegroup
  -o {add,list,remove}, --operation {add,list,remove}
                        Specify a operation, one of add, remove or list
                        (default is list)
  -c COMMENT, --comment COMMENT
                        Descriptive comment for the downtime downtime
  -g GROUPEDID, --groupedid GROUPEDID
                        Provide an ID to identify the group of hosts and
                        services
  -i, --ignore          Bypass the groupedid argument, only available for the
                        list argument
  -C, --epoch           Shows the listed downtimes in epoch instead of date
                        and time (default: False)
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
  -a AUTHOR, --author AUTHOR
                        Check_MK user name
  -u USER, --user USER  Name of the automation user
  -p SECRET, --secret SECRET
                        Secret of the automation user
  -A, --authorization   This enables the AuthUser function of livestatus
  -q, --quiet           Be quiet, there will be no output for add or removed
                        downtimes
  -l LIMIT, --limit LIMIT
                        Limit the output for adding or removing downtimes
                        (default: 100)
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
./downtime.py -u <automation> -p <secret> -c "Downtime for maintenance" -g 123 -o list
```
Will show all scheduled downtimes with the matching 'ID' tag, which gets appended to the comment string if provided. The ID
makes sure, to make all set downtimes made by the script, identifiable. The comment is not required, but is common use. 
```
./downtime.py -u <automation> -p <secret> -c "Downtime for maintenance" -g 123 -o remove
```
Will remove all the scheduled downtimes with the given ID.
```
./downtime.py -u <automation> -p <secret> -c "Happy patching" -g 123 -S <servicegroup> -B 2019-06-23 -b 12:00 -E 2019-06-25 -e 12:00 -o add
```
Will add a downtime with the ID 123 for a servicegroup for two days beginning at June 23 2019 12:00 PM and ending at June 25 2019 12:00 PM.
```
./downtime.py -u <automation> -p <secret> -c "Happy patching" -g 123 -S <servicegroup> -B 2019-06-23 -b 12:00 -E 2019-06-25 -e 12:00 -o add -a cmkuser -A -q
```
Will add a downtime like before, but it will activete AuthUser and only set services in downtime where the check_mk user given by -a is permitted to do so. There will be no output (-q).
```
./downtime.py -u <automation> -p <secret> -g 123 -S <servicegroup> -o remove
```
Will remove the downtime set before.
```
./downtime.py -u <automation> -p <secret> -c "Happy patching" -g 123 -S <servicegroup> -B 2019-06-23 -b 12:00 -E 2019-06-25 -e 12:00 -o add -a cmkuser -A -q
./downtime.py -u <automation> -p <secret> -c "Happy patching" -g 124 -S <servicegroup> -B 2019-06-23 -b 12:00 -E 2019-06-25 -e 12:00 -o add -a cmkuser -A -q
./downtime.py -u <automation> -p <secret> -g 123 -S <servicegroup> -o remove
```
Will create a downtime with ID 123 and one with downtime 124. It will then remove the downtime with the ID 123. The downtime with ID 124 will still exist.

Since I'm not really familiar with python, I still learning, I highly appreciate any input that helps me to improve my skills.  
