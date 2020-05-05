import argparse
import io
import logging
import zipfile

import common_utils


def searchFile(jar_path, archive, library_name, check_all):
    list1 = [x for x in archive.namelist() if library in x or x.endswith(".jar") or x.endswith(".ear") or x.endswith(".war")]
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
                if searchFile(jar_path + "::" + ele, zfile2, library_name, check_all):
                    if not check_all:
                        return True
                    found_lib = found_lib or True
    return found_lib


def main(jar_path, library_name, check_all):
    with zipfile.ZipFile(jar_path,'r') as archive:
        if not searchFile(jar_path, archive, library_name, check_all):
            logging.info("\nCould not find the library {0} inside {1}.\n".format(library_name, jar_path))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("jar", help="jar, ear, or war file to check inside of")
    parser.add_argument("library", help="part or all of library name to search for")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Flag to print verbose log messages.")
    parser.add_argument("-a", dest="check_all", action="store_true", help="Flag to indicate to search for all instances of library with desired name. Defaults to stop after finding only the first one")
    
    args = parser.parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    
    log_file_path = common_utils.get_log_file_path("~/reports", "check_java_archive_for_library")
    common_utils.setup_logger_to_console_file(log_file_path, log_level)
    if args.jar:
        jar_path = args.jar
        library = args.library
        check_all = args.check_all
    else:    
        jar_path = "/cygdrive/c/Users/fergusos/Downloads/CIPO-ec-id-filing-app-4.2.9.ear"
        library = "itext"
        check_all = False
    main(jar_path, library, check_all)
    
    logging.info('\n\nLog file: {}'.format(log_file_path))

