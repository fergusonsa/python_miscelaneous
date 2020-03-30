import argparse
import datetime
import pathlib
import re

from bs4 import BeautifulSoup
import requests

import environment

verbose = False

def get_logs_from_local(env_name, app_name, timestamp):
    '''
        Logs are stored in a local directory with names in th eformat of <app_name>_[<server_name>_]<start-timestamp>_<end-timestamp>.log
        Example: ID-FILING_wasdev5_20200229-19331583004828_20200311-05451583905506.log
    '''
    filename_pattern = re.compile("(?P<app_nane>[a-zA-Z-]*)_(?P<server_name>[a-zA-Z0-9]*_)?(?P<start_year>\d{4})(?P<start_month>\d{2})(?P<start_day>\d{2})-(?P<start_hours>\d{2})(?P<start_minutes>\d{2})(?P<start_seconds>\d{2})\d*_(?P<end_year>\d{4})(?P<end_month>\d{2})(?P<end_day>\d{2})-(?P<end_hours>\d{2})(?P<end_minutes>\d{2})(?P<end_seconds>\d{2})\d*.log")
    log_dir = pathlib.Path(environment.LOCAL_LOG_DIRECTORY, env_name, app_name)
    found_files = []
    if log_dir.exists():
        for log_path in log_dir.glob("*.log"):
            # Parse out the start and end timestamps from the file names to see if the desired timestamp is present
            parts = filename_pattern.match(log_path.name)
            if parts:
                start = datetime.datetime(int(parts.groupdict()['start_year']), int(parts.groupdict()['start_month']), int(parts.groupdict()['start_day']),
                                              int(parts.groupdict()['start_hours']), int(parts.groupdict()['start_minutes']), int(parts.groupdict()['start_seconds']))
                end = datetime.datetime(int(parts.groupdict()['end_year']), int(parts.groupdict()['end_month']), int(parts.groupdict()['end_day']),
                                              int(parts.groupdict()['end_hours']), int(parts.groupdict()['end_minutes']), int(parts.groupdict()['end_seconds']))
                if start <= timestamp and timestamp <= end:
                    found_files.append(log_path)
                    if verbose:
                        print("VERBOSE: Log file {0} does contain timestamp {1}".format(log_path, timestamp))
                elif verbose:
                    print("VERBOSE: Log file name {0} does NOT contain timestamp {1}".format(log_path, timestamp))
            elif verbose:
                print("VERBOSE: Log file name {0} does NOT contain timestamps".format(log_path, timestamp))
    elif verbose:
        print("VERBOSE: There are not local copies of logs for the {0} app in the {1} environment.".format(app_name, env_name))
    if verbose:
        print("VERBOSE: Found {0} local copies of log files for the {1} app in the {2} environment that contain timestamp {3}".format(len(found_files), app_name, env_name, timestamp))
        
    return found_files

NOTE_FILE_LINE_PATTERN = re.compile("^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}) (?P<hours>\d{2}):(?P<minutes>\d{2})(:(?P<seconds>\d{2}))?(,(?P<milliseconds>[0-9]{3}))?\s*(?P<rest>.*)$")
'''2020-03-26 14:07:10,296 DEBUG [ca.gc.ic.cipo.ec.job.scheduling.SchedulingManager] - Maximum retry count is 0'''

def parse_line(line):
    parts = NOTE_FILE_LINE_PATTERN.match(line)
    if parts:
        # print(parts.groupdict())
        hours = int(parts.groupdict()['hours'])
        if parts.groupdict()['seconds']:
            seconds = int(parts.groupdict()['seconds'])
        else:
            seconds = 0
        timestamp = datetime.datetime(int(parts.groupdict()['year']), int(parts.groupdict()['month']), int(parts.groupdict()['day']),
                                      hours, int(parts.groupdict()['minutes']), seconds)
        rest = parts.groupdict()['rest']
    else:
        timestamp = None
        rest = line
    return timestamp, rest


def save_log_from_url_to_file(url, env_name, app_name, server_name, log_dir):
    log_file_path = None
    # Headers to mimic a browser visit
    headers = {'User-Agent': 'Mozilla/5.0'}

    # Returns a requests.models.Response object
    try:
        myfile = requests.get(url, headers=headers)
    except Exception as ex:
        if verbose:
            print("VERBOSE: Could not get url {0}. Exception {1}".format(url, ex.getMessage()))
        return None, None, None
    tmp_file = pathlib.Path(log_dir, "temp_file.log")
    count = 0
    while tmp_file.exists():
        tmp_file = pathlib.Path(log_dir, "temp_file-{0}.log".format(count))
        count += 1
    
    open(tmp_file, 'wb').write(myfile.content)
    first_timestamp = last_timestamp = timestamp = None
    proper_log_file_name = tmp_file
    with open(tmp_file, "r") as log_h:
        for line in log_h.readlines():
            timestamp, rest_of_line = parse_line(line)
            
            if timestamp:
                if (not first_timestamp or timestamp < first_timestamp):
                    first_timestamp = timestamp
                elif (not last_timestamp or timestamp > last_timestamp):
                    last_timestamp = timestamp
    if first_timestamp and last_timestamp:
        # <app_name>_[<server_name>_]<start-timestamp>_<end-timestamp>.log
        proper_log_file_name = pathlib.Path(log_dir, "{0}_{1}_{2:%Y%m%d-%H%M%s}_{3:%Y%m%d-%H%M%s}.log".format(app_name, server_name, first_timestamp, last_timestamp))
        if verbose:
            print("VERBOSE: Renaming temp download file {0} to proper filename {1}".format(tmp_file, proper_log_file_name))
        tmp_file.rename(proper_log_file_name)
    elif verbose:
        print("VERBOSE: Did not get first_timestamp {0} and last_timestamp {1} from file at url {2} so could not rename the file from {3}".format(first_timestamp, last_timestamp, url, tmp_file))
    return proper_log_file_name, first_timestamp, last_timestamp


def copy_logs_from_remote_to_local(env_name, app_name, timestamp):
    log_dir = pathlib.Path(environment.LOCAL_LOG_DIRECTORY, env_name, app_name)
    if not log_dir.exists():
        if verbose:
            print("VERBOSE: Creating log directory {0}".format(log_dir))
        log_dir.mkdir(parents=True, exist_ok=True)
    # WORKING HERE!!!!!!!!!
    found_files = []
    if env_name == "localhost": 
        raise Exception("Need to handle looking for logs for localhost!")
    else:
        for server_name in environment.LOG_LOCATIONS[env_name]["servers"]:
            url = "{0}{1}{2}".format(environment.LOG_LOCATIONS[env_name]["root"], server_name, environment.LOG_APP_PATHS[app_name].format(prefix=environment.LOG_LOCATIONS[env_name]["prefix"]))
            if verbose:
                print("VERBOSE: Going to check url: {0}".format(url))
            log_file_path, first_timestamp, last_timestamp = save_log_from_url_to_file(url, env_name, app_name, server_name, log_dir)
            file_count = 0
            while first_timestamp and last_timestamp and not (first_timestamp <= timestamp and timestamp <= last_timestamp) :
                file_count += 1
                url = "{0}{1}{2}.{3:03d}".format(environment.LOG_LOCATIONS[env_name]["root"], server_name, environment.LOG_APP_PATHS[app_name].format(prefix=environment.LOG_LOCATIONS[env_name]["prefix"]), file_count)
                if verbose:
                    print("VERBOSE: Going to check url: {0}".format(url))
                log_file_path, first_timestamp, last_timestamp = save_log_from_url_to_file(url, env_name, app_name, server_name, log_dir)

            else:
                if verbose:
                    print("VERBOSE: Found log file containint timestamp {0} for application {1}, in environment {2}, in file {3}.".format(timestamp, app_name, env_name, log_file_path))
                found_files.append(log_file_path)
                    
    return found_files
    
    
def get_logs(env_name, app_name, timestamp=None):
    if env_name not in environment.LOG_LOCATIONS.keys():
        raise Exception()
    if app_name not in environment.LOG_APP_PATHS.keys():
        raise Exception()
    if not timestamp:
        timestamp = datetime.Datetime.now()
    log_paths = get_logs_from_local(env_name, app_name, timestamp)
    if not log_paths:
        log_paths = copy_logs_from_remote_to_local(env_name, app_name, timestamp)
    return log_paths


def valid_datetime_type(arg_datetime_str):
    """custom argparse type for user datetime values given from the command line - from https://gist.github.com/monkut/e60eea811ef085a6540f"""
    try:
        return datetime.datetime.strptime(arg_datetime_str, "%Y-%m-%d %H:%M")
    except ValueError:
        msg = "Given Datetime ({0}) not valid! Expected format, 'YYYY-MM-DD HH:mm'!".format(arg_datetime_str)
        raise argparse.ArgumentTypeError(msg)        
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Flag to print verbose log messages.")
    parser.add_argument("-g", "--get_logs", dest="get_logs", action="store_true", help="Get logs for the specified application in the specified environment")
    parser.add_argument("-e", "--environment", dest="env_name", choices=environment.LOG_LOCATIONS.keys(), help="Environment name to get logs from")
    parser.add_argument("-a", "--application", dest="app_name", choices=environment.LOG_APP_PATHS.keys(), help="Application name to get logs for")
    parser.add_argument('-t', '--timestamp', dest='timestamp',
                        type=valid_datetime_type,
                        default=datetime.datetime.now(),
                        help='Timestamp to get logs for in format "YYYY-MM-DD HH:mm". Defaults to now.')    
    args = parser.parse_args()
    verbose = args.verbose
    
    if args.get_logs:
        if not args.env_name:
            print("To get logs, you must supply an environment name.")
            sys.exit(0)
        if not args.app_name:
            print("To get logs, you must supply an application name.")
            sys.exit(0)
        log_paths = get_logs(args.env_name, args.app_name, args.timestamp) 
        if log_paths:
            print("\nThe logs for the {0} app in the {1} environment can be found here:".format(args.app_name, args.env_name))
            for pth in log_paths:
                print("\t{0}".format(pth))
        else:
            print("\nCould not find logs for the {0} app in the {1} environment.".format(args.app_name, args.env_name))
        
   
