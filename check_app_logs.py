import argparse
import datetime
import logging

import common_utils
import environment
import logs

verbose_level = 0


def contains_pattern(app_name, msg_lines, pattern):
    patterns = [pattern] if pattern else environment.APP_LOG_PATTERNS.get(app_name)

    for pattern in patterns:
        for line in msg_lines:
            if pattern in line:
                logging.debug("found pattern {0} in line {1}".format(pattern, line))
                return True
    logging.debug("did NOT find pattern {0} in line {1}".format(pattern, msg_lines))
    return False


def check_app_logs(app_name, log_paths, start_timestamp, end_timestamp, pattern):
    for path in log_paths:
        if not path.exists():
            logging.info("The expected log file {0} does not exist.".format(path))
            continue
        logging.info("\nChecking file {0}".format(path))
        file_size = path.stat().st_size
        found_lines = []
        with open(path, "r") as log_h:
            current_line = None
            timestamp, rest_of_line, current_line = logs.get_log_msg(log_h, current_line)
            while current_line and timestamp and rest_of_line and timestamp <= end_timestamp:
                if start_timestamp <= timestamp and timestamp <= end_timestamp and
                    contains_pattern(app_name, rest_of_line, pattern):
                    found_lines.append((timestamp, rest_of_line))

            timestamp, rest_of_line, current_line = logs.get_log_msg(log_h, current_line)
            # logging.info("\rpath: {} read {:2.0f}% timestamp: {}  rest_of_line empty: {}".format(path, (log_h.tell()/file_size*100), timestamp, not rest_of_line))

    if found_lines:
        logging.info("\nFound {0} log messages in file {1}\n".format(len(found_lines), path))
        for (timestamp, rest_of_line) in found_lines:
            logging.info("{0:%Y-%m-%d %H:%M:%s}  {1}".format(timestamp, rest_of_line[0]))
            for idx in range(1, len(rest_of_line) - 1):
                logging.info("{0}  {1}".format(" " * 24, rest_of_line[idx]))
    else:
        logging.info("\nFound NO log messages in file {0}\n".format(path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        help="Flag to print verbose log messages.")
    parser.add_argument("-e", "--environment", dest="env_name", required=True, choices=environment.LOG_LOCATIONS.keys(),
                        help="Environment name to get logs from")
    parser.add_argument("-f", "--force", dest="force_get", action="store_true",
                        help="Force getting logs from the remote location instead of relying on existing local files.")
    parser.add_argument("-a", "--application", dest="app_name", default="ID-FILING",
                        choices=environment.LOG_APP_PATHS.keys(), help="Application name to get logs for")
    parser.add_argument("-p", "--pattern", dest="pattern",
                        help="Pattern to search for. If none provided, then it uses the pattern(s) for the specified application listed in env.py")
    parser.add_argument('-t', '--timestamp', dest='start_timestamp', type=logs.valid_datetime_type,
                        default=(datetime.datetime.now() - datetime.timedelta(days=1)),
                        help='Starting Timestamp to get logs for in format "YYYY-MM-DD HH:mm". Use qutes around the timestamp if including hours and minutes. Defaults to one day before now.')
    parser.add_argument('-n', '--end', dest='end_timestamp', type=logs.valid_datetime_type, default=None,
                        help='End Timestamp to get logs for in format "YYYY-MM-DD HH:mm". Use quotes around the timestamp if including hours and minutes. Defaults to 1 day after the starting timestamp or now, whichever comes first.')
    args = parser.parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO

    log_file_path = common_utils.get_log_file_path("~/reports", "check_app_logs")
    common_utils.setup_logger_to_console_file(log_file_path, log_level)

    log_paths = []
    if args.end_timestamp and args.end_timestamp <= datetime.datetime.now():
        end_timestamp = args.end_timestamp
    elif not args.end_timestamp and args.start_timestamp >= (datetime.datetime.now() - datetime.timedelta(days=1)):
        end_timestamp = args.start_timestamp - datetime.timedelta(days=1)
    else:
        end_timestamp = datetime.datetime.now()

    log_paths = logs.get_logs(args.env_name, args.app_name, args.start_timestamp, end_timestamp, args.force_get)
    if log_paths:
        logging.info(
            "\nFound {0} files for the {1} app in the {2} environment for the timeframe of {3:%Y-%m-%d %H:%M:%S.%f} to {4:%Y-%m-%d %H:%M:%S.%f} to check.\n".format(
                len(log_paths), args.app_name, args.env_name, args.start_timestamp, end_timestamp))
        check_app_logs(args.app_name, log_paths, args.start_timestamp, end_timestamp, args.pattern)
    else:
        logging.info(
            "Cannot find logs for {0} app in the {1} environment for the timeframe {2} to {3}.".format(args.app_name,
                                                                                                       args.env_name,
                                                                                                       args.start_timestamp,
                                                                                                       end_timestamp))
