import argparse
import datetime
import hashlib
import logging
import pathlib
import re

import common_utils


def get_md5(file_path):
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as file_h:
        for byte_block in iter(lambda: file_h.read(4096), b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()
    
    
def get_file_info(file_path_str):
    file_path = pathlib.Path(file_path_str)
    if not file_path or not file_path.is_file():
        logging.error("{} is not a valid file!".format(file_path))
        return None
    return {"path": file_path,
            "name": file_path.name,
            "md5": get_md5(file_path),
            "last_modified": datetime.datetime.utcfromtimestamp(file_path.stat().st_mtime),
            "size": file_path.stat().st_size}


COMPARE_LINE_PATTERN = re.compile("^(?P<filename>[\w.]+)\s+(?P<size>\d*)\s+(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}) (?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2})(?P<milliseconds>[0-9]*)\s+(?P<md5>.*)$")
'''
check_deployed_versions.py                      2921  2020-04-20 20:55:1587416113   c52ab7f2d025264da3b24ace42afaf16
'''


def parse_compare_line(line):
    """ returns a dict containing the same keys as get_file_info() """
    parts = COMPARE_LINE_PATTERN.match(line)
    if parts:
        gp = parts.groupdict()
        # logging.info(parts.groupdict())
        hours = int(gp['hours'])
        if gp['seconds']:
            seconds = int(gp['seconds'])
        else:
            seconds = 0
        last_modified = datetime.datetime(int(parts.groupdict()['year']),
                                          int(parts.groupdict()['month']),
                                          int(parts.groupdict()['day']),
                                      hours, int(parts.groupdict()['minutes']), seconds)

        file_name = gp["filename"]
        md5 = gp["md5"]
        size = int(gp["size"])
        return {"path": None,
                "name": file_name,
                "md5": md5,
                "last_modified": last_modified,
                "size": size}
    else:
        logging.debug("Could not parse comparison line '{}'".format(line))
        return None


def save_dir_files_info(dir_path, output_path):
    dirs_info = get_file_infos(dir_path)
    if dirs_info:
        with open(output_path, "w") as output_h:
            for (file_name, file_info) in dirs_info.items():
                output_h.write("{name}  {size}  {last_modified:%Y-%m-%d %H:%M:%S}   {md5}\n".format(**file_info))
        logging.info("Wrote info for {} files to file {}".format(len(dirs_info), output_path))
    else:
        logging.info("No file info found in the test_data {}, so could not write anything to file {}"
                     .format(dir_path, output_path))


def load_compare_info(compare_path):
    """ returns a dict with file basenames as keys and dicts as values. Same value dict as returned from
    get_file_info() """
    files_info_dict = {}
    with open(compare_path, "r") as compare_h:
        for line in compare_h.readlines():
            info = parse_compare_line(line)
            if info:
                files_info_dict[info["name"]] = info
    logging.debug("Loaded info for {} files from compare file {}".format(len(files_info_dict), compare_path))
    return files_info_dict
    

def get_file_infos(dir_path):
    """ returns a dict with file basenames as keys and dicts as values.
    Same value dict as returned from get_file_info() """
    files_info_dict = {}
    for file_path in [f for f in dir_path.iterdir() if f.is_file()]:
        file_info = get_file_info(file_path)
        if file_info:
            files_info_dict[file_path.name] = file_info
    logging.debug("Loaded info for {} files from test_data {}".format(len(files_info_dict), dir_path))
    return files_info_dict


def compare_file_against_directory_file(compare_path, dir_path):
    compare_info = load_compare_info(compare_path)
    files_info = get_file_infos(dir_path)
    
    dir_files = set(files_info.keys())
    compare_files = set(compare_info.keys())

    extra_files = dir_files - compare_files
    missing_files = compare_files - dir_files
    common_files = dir_files.intersection(compare_files)
    changed_files = set([f for f in common_files if files_info[f]["name"] == compare_info[f]["name"] and 
                        (files_info[f]["size"] != compare_info[f]["size"] or
                         files_info[f]["md5"] != compare_info[f]["md5"])])
    same_files = common_files - changed_files
    
    logging.info("Number of common files with same sizes: {}\n".format(len(same_files)))
    for file in sorted(same_files):
        logging.info("{name:40}  {size:10}  {last_modified:%Y-%m-%d %H:%M:%S}   {md5}".format(**files_info[file]))
    logging.info(" ")
    logging.info("Number of common files with different sizes: {}\n".format(len(changed_files)))
    for file in sorted(changed_files):
        logging.info("{0[name]:40}  {0[size]:10}  {0[last_modified]:%Y-%m-%d %H:%M:%S}   {0[md5]}  {1[size]:10}  {1[last_modified]:%Y-%m-%d %H:%M:%S}   {1[md5]}".format(files_info[file], compare_info[file]))
    logging.info(" ")
    
    logging.info("Number of files in test_data and not in comparison file: {}\n".format(len(extra_files)))
    for file in sorted(extra_files):
        logging.info("{name:40}  {size:10}  {last_modified:%Y-%m-%d %H:%M:%S}   {md5}".format(**files_info[file]))
    logging.info(" ")
    logging.info("Number of files in comparison file and not in test_data: {}\n".format(len(missing_files)))
    for file in sorted(missing_files):
        logging.info("{name:40}  {size:10}  {last_modified:%Y-%m-%d %H:%M:%S}   {md5}".format(**compare_info[file]))
    logging.info(" ")
    
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        help="Flag to print verbose log messages.")
    parser.add_argument("-f", "--file", dest="file_path", help="File path to display information for.")
    parser.add_argument("-w", "--write", dest="write_path",
                        help="File path to write the file info to. Used with the -d/--test_data argument.")
    parser.add_argument("-d", "--test_data", dest="dir_path",
                        help="Directory path containing files to display information for.")
    parser.add_argument("-c", "--compare", dest="compare_path",
                        help="File path containing the file information to compare against. Used with the -d/--test_data argument.")
    # parser.add_argument("-i", "--include", dest="include",
    #                     help="Filter pattern for files to display information for. Used with the -d/--test_data argument.")
    parser.add_argument("-o", "--open", dest="open_output", action="store_true",
                        help="Flag to indicate to open the log file(s) in an editor once the script has completed.")
    args = parser.parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    
    log_file_path = common_utils.get_log_file_path("~/reports", "file_changes")
    common_utils.setup_logger_to_console_file(log_file_path, log_level)

    if args.file_path:
        file_info = get_file_info(args.file_path)
        if file_info:
            logging.info("{name:40}  {size:10}  {last_modified:%Y-%m-%d %H:%M:%S}   {md5}".format(**file_info))
        else:
            logging.debug("Could not get file infor for {}".format(args.file_path))
    elif args.dir_path:
        dir_path = pathlib.Path(args.dir_path)
        if dir_path.is_dir():
            if args.compare_path:
                compare_path = pathlib.Path(args.compare_path)
                if compare_path.is_file():
                    compare_file_against_directory_file(compare_path, dir_path)
                else:
                    logging.error("'{}' is not a valid file containing comparable information.".format(args.compare_path))
            elif args.write_path:
                write_path = pathlib.Path(args.write_path)
                if write_path and write_path.exists() and write_path.is_dir():
                    write_path = common_utils.get_timestamped_file_name(write_path, "file-info")
                if write_path and write_path.exists() and write_path.is_file():
                    logging.error("There already is a file with the path {}".format(write_path))
                elif write_path and not write_path.exists():
                    save_dir_files_info(dir_path, write_path)
                else:
                    logging.error("Could not find a valid location to put output file in {}.".format(write_path))
            else:
                for file_path in [f for f in dir_path.iterdir() if f.is_file()]:
                    file_info = get_file_info(file_path)
                    if file_info:
                        logging.info("{name:40}  {size:10}  {last_modified:%Y-%m-%d %H:%M:%S}   {md5}".format(**file_info))
                        # logging.info("{name:40}  {size:10}  {last_modified}   {md5}".format(**file_info))
                    else:
                        logging.debug("Could not get file infor for {}".format(file_path))
        else:
            logging.error("'{}' is not a valid test_data!".format(args.dir_path))
    if args.open_output:
        common_utils.open_file_in_editor(log_file_path)
