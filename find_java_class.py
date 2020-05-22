import argparse
import io
import logging
import pathlib
import zipfile

import common_utils


def search_file(jar_path, archive, library_name, check_all):
    list1 = [x for x in archive.namelist() if
             library_name in x or x.endswith(".jar") or x.endswith(".ear") or x.endswith(".war")]
    found_lib = False
    for ele in list1:
        if library_name in ele:
            logging.info("\nFound library '{0}' inside {1} in file {2}\n".format(library_name, jar_path, ele))
            if not check_all:
                return True
            found_lib = True
        else:
            logging.debug("checking {0} inside {1}".format(ele, jar_path))
            zfiledata = io.BytesIO(archive.read(ele))
            with zipfile.ZipFile(zfiledata) as zfile2:
                if search_file(jar_path + "::" + ele, zfile2, library_name, check_all):
                    if not check_all:
                        return True
                    found_lib = found_lib or True
    return found_lib


def main(class_name, search_location, check_all):
    if search_location.is_dir():
        logging.warning("Not implemented yet! {0} is a directory to search.\n".format(search_location))
    elif search_location.is_file() and search_location.suffix in [".jar", ".war", ".ear", ".zip"]:
        with zipfile.ZipFile(search_location, 'r') as archive:
            if not search_file(search_location, archive, class_name, check_all):
                logging.info("Could not find the library {0} inside {1}.\n".format(class_name, search_location))
    elif search_location.is_file():
        logging.warning("The search location {0} is not a valid format to search.\n".format(search_location))
    else:
        logging.warning("Could not find the search location {0} to search.\n".format(search_location))


def valid_path(pth_str):
    if not pth_str:
        msg = "search location cannot be null or an empty string."
        raise argparse.ArgumentTypeError(msg)
    return pathlib.Path(pth_str)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("class_name", help="Java class name to search for")
    parser.add_argument("search_location", type=valid_path,
                        help="Java archive file or directory path to search for the desired class")
    parser.add_argument("-a", dest="check_all", action="store_true",
                        help="Flag to indicate to search for all instances of library with desired name. Defaults to stop after finding only the first one")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        help="Flag to print verbose log messages.")
    parser.add_argument("-o", "--open", dest="open_output", action="store_true",
                        help="Flag to indicate to open the log file in an editor once the script has completed.")

    args = parser.parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO

    log_file_path = common_utils.get_log_file_path("~/reports", "find_java_class")
    common_utils.setup_logger_to_console_file(log_file_path, log_level)

    main(args.class_name, args.search_location, args.check_all)

    logging.info('\n\nLog file: {}\n'.format(log_file_path))
    if args.open_output:
        common_utils.open_file_in_editor(log_file_path)
