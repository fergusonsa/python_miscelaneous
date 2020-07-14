import argparse
import datetime
import logging
import pathlib
import re

import requests

import common_utils
import environment

FILENAME_PATTERN = re.compile("(?P<app_nane>[a-zA-Z-]*)_(?P<server_name>[a-zA-Z0-9]*_)?(?P<start_year>\d{4})(?P<start_month>\d{2})(?P<start_day>\d{2})-(?P<start_hours>\d{2})(?P<start_minutes>\d{2})(?P<start_seconds>\d{2})\d*_(?P<end_year>\d{4})(?P<end_month>\d{2})(?P<end_day>\d{2})-(?P<end_hours>\d{2})(?P<end_minutes>\d{2})(?P<end_seconds>\d{2})\d*.log")

def get_logs_from_local(env_name, app_name, timestamp, end_timestamp=None):
    '''
        Logs are stored in a local test_data with names in th eformat of <app_name>_[<server_name>_]<start-timestamp>_<end-timestamp>.log
        Example: ID-FILING_wasdev5_20200229-19331583004828_20200311-05451583905506.log
    '''
    log_dir = pathlib.Path(environment.LOCAL_LOG_DIRECTORY, env_name, app_name)

    found_files = []
    if log_dir.exists():
        for log_path in log_dir.glob("*.log"):
            # Parse out the start and end timestamps from the file names to see if the desired timestamp is present
            parts = FILENAME_PATTERN.match(log_path.name)
            if parts:
                start = datetime.datetime(int(parts.groupdict()['start_year']), int(parts.groupdict()['start_month']), int(parts.groupdict()['start_day']),
                                              int(parts.groupdict()['start_hours']), int(parts.groupdict()['start_minutes']), int(parts.groupdict()['start_seconds']))
                end = datetime.datetime(int(parts.groupdict()['end_year']), int(parts.groupdict()['end_month']), int(parts.groupdict()['end_day']),
                                              int(parts.groupdict()['end_hours']), int(parts.groupdict()['end_minutes']), int(parts.groupdict()['end_seconds']))
                if start <= timestamp and timestamp <= end:
                    found_files.append(log_path)
                    logging.debug("Log file {0} does contain timestamp {1}".format(log_path, timestamp))
                elif end_timestamp and start <= end_timestamp and end_timestamp <= end:
                    found_files.append(log_path)
                    logging.debug("Log file {0} does contain end timestamp {1}".format(log_path, end_timestamp))
                else:
                    logging.debug("Log file name {0} does NOT contain timestamp {1}".format(log_path, timestamp))
            else:
                logging.debug("Log file name {0} does NOT contain timestamps".format(log_path, timestamp))
    else:
        logging.debug("There are not local copies of logs for the {0} app in the {1} environment.".format(app_name, env_name))
    logging.debug("Found {0} local copies of log files for the {1} app in the {2} environment that contain timestamp {3}".format(len(found_files), app_name, env_name, timestamp))

    return found_files

NOTE_FILE_LINE_PATTERN = re.compile("^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}) (?P<hours>\d{2}):(?P<minutes>\d{2})(:(?P<seconds>\d{2}))?(,(?P<milliseconds>[0-9]{3}))?\s*(?P<rest>.*)$")
'''2020-03-26 14:07:10,296 DEBUG [ca.gc.ic.cipo.ec.job.scheduling.SchedulingManager] - Maximum retry count is 0'''

def parse_line(line):
    parts = NOTE_FILE_LINE_PATTERN.match(line)
    if parts:
        # logging.info(parts.groupdict())
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

def get_unique_file_path(dir, prefix, extension):
    tmp_file = pathlib.Path(dir, "{}.{}".format(prefix, extension))
    count = 0
    while tmp_file.exists():
        tmp_file = pathlib.Path(dir, "{}-{}.{}".format(prefix, count, extension))
        count += 1
    return tmp_file

    
def save_log_from_url_to_file(url, env_name, app_name, server_name, log_dir):
    log_file_path = None
    # Headers to mimic a browser visit
    headers = {'User-Agent': 'Mozilla/5.0'}

    # Returns a requests.models.Response object
    try:
        myfile = requests.get(url, headers=headers)
    except Exception as ex:
        logging.debug("Could not get url {0}. Exception {1}".format(url, ex.getMessage()))
        return None, None, None

    if myfile.status_code != 200:
        logging.debug("Attempting to get url {0} returned with a status code of {1}".format(url, myfile.status_code))
        return None, None, None
        
    tmp_file = get_unique_file_path(log_dir, "temp_file", "log")    
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
            elif not first_timestamp:
                if line == '<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">':
                    proper_log_file_name = None
                    break
                    
    if first_timestamp and last_timestamp:
        # <app_name>_[<server_name>_]<start-timestamp>_<end-timestamp>.log
        proper_log_file_name = pathlib.Path(log_dir, "{0}_{1}_{2:%Y%m%d-%H%M%s}_{3:%Y%m%d-%H%M%s}.log".format(app_name, server_name, first_timestamp, last_timestamp))
        if proper_log_file_name.exists():
            logging.debug("Deleting temp file {0} from url {1} as there is already a file with the name {2}.".format(tmp_file, url, proper_log_file_name))
            tmp_file.unlink()
        else:
            logging.debug("Renaming temp download file {0} to proper filename {1}".format(tmp_file, proper_log_file_name))
            tmp_file.rename(proper_log_file_name)
    elif not proper_log_file_name:
        logging.debug("Deleting temp file {0} as it does not appear to be a log file. Could not find url {1} ".format(tmp_file, url))
        tmp_file.unlink()
    logging.debug("Did not get first_timestamp {0} and last_timestamp {1} from file at url {2} so could not rename the file from {3}".format(first_timestamp, last_timestamp, url, tmp_file))
    return proper_log_file_name, first_timestamp, last_timestamp


def copy_logs_from_remote_to_local(env_name, app_name, timestamp, end_timestamp=None):
    log_dir = pathlib.Path(environment.LOCAL_LOG_DIRECTORY, env_name, app_name)
    if not log_dir.exists():
        logging.debug("Creating log test_data {0}".format(log_dir))
        log_dir.mkdir(parents=True, exist_ok=True)
    found_files = []
    if env_name == "localhost": 
        raise Exception("Need to handle looking for logs for localhost!")
    else:
        for server_name in environment.LOG_LOCATIONS[env_name]["servers"]:
            url = "{0}{1}{2}".format(environment.LOG_LOCATIONS[env_name]["root"], server_name, environment.LOG_APP_PATHS[app_name].format(prefix=environment.LOG_LOCATIONS[env_name]["prefix"]))
            logging.debug("Going to check url: {0}".format(url))
            log_file_path, first_timestamp, last_timestamp = save_log_from_url_to_file(url, env_name, app_name, server_name, log_dir)
            file_count = 0
            while first_timestamp and last_timestamp and not (first_timestamp <= timestamp and timestamp <= last_timestamp) :
                file_count += 1
                url = "{0}{1}{2}.{3:03d}".format(environment.LOG_LOCATIONS[env_name]["root"], server_name, environment.LOG_APP_PATHS[app_name].format(prefix=environment.LOG_LOCATIONS[env_name]["prefix"]), file_count)
                logging.debug("Going to check url: {0}".format(url))
                log_file_path, first_timestamp, last_timestamp = save_log_from_url_to_file(url, env_name, app_name, server_name, log_dir)

            else:
                if log_file_path:
                    logging.debug("Found log file containing timestamp {0} for application {1}, in environment {2}, in file {3}.".format(timestamp, app_name, env_name, log_file_path))
                    found_files.append(log_file_path)
                logging.debug("Could not find valid log file at the url {}.".format(url))
                    
    return found_files

    
def get_log_msg(log_h, current_line=None):
    timestamp = None
    log_msg_lines = []
    if not current_line:
        current_line = log_h.readline()
    timestamp, rest_of_line = parse_line(current_line)
    next_timestamp = None
    log_msg_lines.append(current_line)
    while not next_timestamp and current_line: 
        current_line = log_h.readline()
        next_timestamp, rest_of_line = parse_line(current_line)
        if not next_timestamp:
            log_msg_lines.append(current_line)
    
    return timestamp, log_msg_lines, current_line


def extract_to_new_files(found_files, env_name, app_name, start_timestamp, end_timestamp):
    extracted_log_dir = pathlib.Path(environment.LOCAL_LOG_DIRECTORY, env_name, app_name, "extracted")
    if not extracted_log_dir.exists():
        extracted_log_dir.mkdir()
    extracted_files = {}
    for file_path in found_files:    
        parts = FILENAME_PATTERN.match(file_path.name)
        if parts:
            server = parts.groupdict()['server_name']
        else:
            server = ""
            logging.debug("Cannot parse server name from filename {}. Using no server name for generated extract file name".format())
        if server not in extracted_files:
            extracted_file_path = pathlib.Path(extracted_log_dir, "{}-{}-{}-{}.log".format(app_name, server, start_timestamp.strftime('%Y-%m-%d_%H-%M-%S'), end_timestamp.strftime('%Y-%m-%d_%H-%M-%S')))
            if extracted_file_path.exists():
                extracted_file_path.unlink()
            extracted_files[server] = {"handle": open(extracted_file_path, "w"), "path": extracted_file_path}
        with open(file_path, "r") as file_h:
            current_line = None
            log_timestamp, rest_of_line, current_line = get_log_msg(file_h, current_line)
            while rest_of_line and current_line and log_timestamp and log_timestamp <= end_timestamp:
                if start_timestamp <= log_timestamp and log_timestamp <= end_timestamp:
                    for line in rest_of_line:
                        extracted_files[server]["handle"].write(line)

                log_timestamp, rest_of_line, current_line = get_log_msg(file_h, current_line)
                # logging.info("\rpath: {} read {:2.0f}% timestamp: {}  rest_of_line empty: {}".format(path, (log_h.tell()/file_size*100), start_timestamp, not rest_of_line))
        
    for extracted_file in extracted_files.values():
        if extracted_file["handle"] and not extracted_file["handle"].closed:
            extracted_file["handle"].close()

    return [extracted_file["path"] for extracted_file in extracted_files.values()]


def get_logs(env_name, app_name, timestamp=None, end_timestamp=None, force_get=None, extract_to_new_file=None):
    if env_name not in environment.LOG_LOCATIONS.keys():
        raise Exception()
    if app_name not in environment.LOG_APP_PATHS.keys():
        raise Exception()
    if not timestamp:
        timestamp = datetime.Datetime.now() - 1
    if not force_get:
        log_paths = get_logs_from_local(env_name, app_name, timestamp, end_timestamp)
    else:
        logging.info("Forced to get latest files from remote!")
        log_paths = []
    if not log_paths:
        log_paths = copy_logs_from_remote_to_local(env_name, app_name, timestamp, end_timestamp)
    if extract_to_new_file:
        return extract_to_new_files(log_paths, env_name, app_name, timestamp, end_timestamp)
    else:
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
    parser.add_argument("-x", "--extract", dest="extract", action="store_true", help="Extract logs for the specified application in the specified environment for the time period in the start to end parameters")
    parser.add_argument("-f", "--force", dest="force_get", action="store_true", help="Force getting logs from the remote location instead of relying on existing local files.")
    parser.add_argument("-e", "--environment", dest="env_name", required=True, choices=environment.LOG_LOCATIONS.keys(), help="Environment name to get logs from")
    parser.add_argument("-a", "--application", dest="app_name", required=True, choices=environment.LOG_APP_PATHS.keys(), help="Application name to get logs for")
    parser.add_argument('-t', '--timestamp', dest='timestamp', type=valid_datetime_type, default=(datetime.datetime.now()-datetime.timedelta(days=1)), help='Starting Timestamp to get logs for in format "YYYY-MM-DD HH:mm". Use qutes around the timestamp if including hours and minutes. Defaults to one day before now.')    
    parser.add_argument('-n', '--end', dest='end_timestamp', type=valid_datetime_type, default=(datetime.datetime.now()), help='End Timestamp to get logs for in format "YYYY-MM-DD HH:mm". Use quotes around the timestamp if including hours and minutes. Defaults to now.')    
    parser.add_argument("-o", "--open", dest="open_output", action="store_true", help="Flag to indicate to open the log file(s) in an editor once the script has completed.")
    args = parser.parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    
    log_file_path = common_utils.get_log_file_path("/home/fergusos/reports", "logs")
    common_utils.setup_logger_to_console_file(log_file_path, log_level)
    
    log_paths = []
    end_timestamp = args.end_timestamp 
    if args.extract:
        logging.info("\nExtracting logs for the {0} app in the {1} environment for the time period between {2:%Y%m%d-%H%M%s} and {3:%Y%m%d-%H%M%s}.\n".format(args.app_name, args.env_name, args.timestamp, end_timestamp))
        log_paths = get_logs(args.env_name, args.app_name, args.timestamp, end_timestamp, args.force_get, args.extract)
        if log_paths:
            logging.info("\nThe logs for the {0} app in the {1} environment can be found here:".format(args.app_name, args.env_name))
            for pth in log_paths:
                logging.info("\t{0}".format(pth))
        else:
            logging.info("\nCould not find logs for the {0} app in the {1} environment for the time period of {2} to {3}.".format(args.app_name, args.env_name, args.timestamp, args.end_timestamp))
    else:
        logging.info("\nSearching for logs for the {0} app in the {1} environment for the time period between {2:%Y%m%d-%H%M%s} and {3:%Y%m%d-%H%M%s}.\n".format(args.app_name, args.env_name, args.timestamp, end_timestamp))
        log_paths = get_logs(args.env_name, args.app_name, args.timestamp, end_timestamp, args.force_get, args.extract)
        if log_paths:
            logging.info("\nThe logs for the {0} app in the {1} environment can be found here:".format(args.app_name, args.env_name))
            for pth in log_paths:
                logging.info("\t{0}".format(pth))
        else:
            logging.info("\nCould not find logs for the {0} app in the {1} environment.".format(args.app_name, args.env_name))
    
    if args.open_output and log_paths:
        for pth in log_paths:
            common_utils.open_file_in_editor(pth)
