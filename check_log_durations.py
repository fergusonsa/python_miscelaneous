import csv
import datetime
import logging
import pprint
import re
import string

import common_utils


class DeltaTemplate(string.Template):
    delimiter = "%"

def timedelta_format(tdelta, fmt):
    """ adapted from https://stackoverflow.com/questions/8906926/formatting-python-timedelta-objects

    """
    data = {'D': tdelta.days}
    data['H'], rem = divmod(tdelta.seconds, 3600)
    data['M'], data['S'] = divmod(rem, 60)

    if '%D'not in fmt:
        data['H'] += 24 * data['D']
    if '%H'not in fmt:
        data['M'] += 60 * data['H']
    if '%M'not in fmt:
        data['S'] += 60 * data['M']

    t = DeltaTemplate(fmt)
    return t.substitute(**data)

def display_durations(log_entries):
    csv_file_path = "/home/fergusos/reports/check_log_durations_{:%Y%m%d_%H%M%S}.csv".format(datetime.datetime.now())
    logging.info()
    with open(csv_file_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["pattern_key", "start", "finish", "duration"], extrasaction="ignore")
        writer.writeheader()
        for dur_key in log_entries.keys():
            logging.info("\nDurations for {0}\n".format(dur_key))
            logging.info("{:<26}   {}".format("Start time", "Duration"))
            for entry in log_entries[dur_key]:
                writer.writerow(entry)
                if entry.get("finish"):
                    logging.info("{:%Y-%m-%d %H:%M:%S.%f}   {}".format(entry["start"], entry["duration"]))
                else:
                    logging.info("{:%Y-%m-%d %H:%M:%S.%f}   No apparent finish time!".format(entry["start"]))
    logging.info("\nWrote to csv file {}".format(csv_file_path))
    

def is_pattern_in_line(patterns, line):
    for (key, pat) in patterns.items():
        if pat["start"] in line or pat["finish"] in line:
            return key
    return None

def convert_to_datetime(date_str):
    '''
    Expecting a string containing a date in the format of 2019-12-04 11:08:57,131    
    '''
    return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S,%f")
    
def get_log_entries(patterns, file_path):
    # log_entries = [] # array of dicts {"pattern_key": "<string>", "start": <Datetime>, "finish": <Datetime>}
    log_entries = {} # dict of array of dicts {"pattern_key": ["<string>", "start": <Datetime>, "finish": <Datetime>]}
    PARSE_PATTERN = re.compile("^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (DEBUG|INFO|WARN|ERROR)\s(\[\w* : \d*)\]\s(\[[\w.]*\]) - (.*)$")
    with open(file_path) as file:
        last_starts = {}
        for line in file:
            pat_key = is_pattern_in_line(patterns, line)
            if pat_key:
                match = PARSE_PATTERN.match(line)
                if match:
                    if patterns[pat_key]["start"] in match.group():
                        if last_starts.get(pat_key):                            
                            if pat_key not in log_entries:
                                log_entries[pat_key] = []
                            log_entries[pat_key].append({"pattern_key": pat_key, "start": last_starts[pat_key], "finish": None, "duration": None})
                            del last_starts[pat_key]
                        last_starts[pat_key] = convert_to_datetime(match.group(1))
                    else:
                        if pat_key not in log_entries:
                            log_entries[pat_key] = []
                        finish_timestamp = convert_to_datetime(match.group(1))
                        log_entries[pat_key].append({"pattern_key": pat_key, "start": last_starts[pat_key], "finish": finish_timestamp, "duration": datetime.timedelta.total_seconds(finish_timestamp - last_starts[pat_key])})
                        del last_starts[pat_key]
    for (key, val) in last_starts.items():
        if val:
            if key not in log_entries:
                log_entries[key] = []
            log_entries[key].append({"pattern_key": key, "start": val, "finish": None, "duration": None})
    return log_entries


def main(log_file_path):
    patterns = {
        "getAuthorizedApplicationByAppNumber": {"start": "PL/SQL -- execute getAuthorizedApplicationByAppNumber before succeeds!", "finish": "PL/SQL -- execute getAuthorizedApplicationByAppNumber succeeds!"},
        # "": {"start": "", "finish": ""},
        }
    log_entries = get_log_entries(patterns, log_file_path)
    display_durations(log_entries)

    
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Flag to print verbose log messages.")
    parser.add_argument(dest='log_file_path', help='Log file to check durations from.')
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    
    output_file_path = common_utils.get_log_file_path("/home/fergusos/reports", "check_log_durations")
    common_utils.setup_logger_to_console_file(output_file_path, log_level)

    main(args.log_file_path)

    logging.info('\n\nLog file: {}'.format(output_file_path))
