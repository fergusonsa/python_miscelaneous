import argparse
import logging
import subprocess

import common_utils
import environment


def get_files_list_for_application(env_name, app_number, extension):
    command = "ls {}/{}/{}/{}/{}/".format(environment.FILE_STORAGE_IMAGE_ROOT_PATH, app_number[0:2], app_number[2:4],
                                          app_number[4:6], extension)
    try:
        result = subprocess.run(
            ['ssh', '{}@{}'.format(environment.FILE_STORAGE_USER, environment.FILE_STORAGE_SERVERS[env_name]), command],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    except subprocess.CalledProcessError as e:
        logging.error("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output), e)
        return []

    if result and result.returncode == 0:
        return result.stdout.decode().splitlines()
    elif result and result.returncode != 0:
        if result.returncode == 2 and result.stderr.decode().endswith(" does not exist.\n"):
            logging.debug(
                "SSH command '{}' did not find any files for application {} {}".format(command, app_number, extension))
        else:
            logging.warning(
                "SSH command '{}' failed with returncode {} and stderr {} for application {} {}".format(command,
                                                                                                        result.returncode,
                                                                                                        result.stderr.decode(),
                                                                                                        app_number,
                                                                                                        extension))
    else:
        logging.error(
            "SSH command '{}' failed with and did not return a result for application {} {}".format(command, app_number,
                                                                                                    extension))
    return []


def check_images_for_application(env_name, app_number, extension):
    num_thumbnails = 0
    num_full_images = 0
    files_l = get_files_list_for_application(env_name, app_number, extension)
    if files_l and len(files_l) > 0:
        thumbs_d = {
            f: {"base": f[1:-4], "base#": int(f[1:f.find("_")]), "version": int(f[f.find("_") + 1:-4]), "name": f} for f
            in files_l if f.startswith("t")}
        max_thumbs = {v["base#"]: v for (k, v) in thumbs_d.items() if v["version"] == max(
            list([vv["version"] for vv in thumbs_d.values() if vv["base#"] == v["base#"]]))}
        fulls_d = {
            f: {"base": f[0:-4], "base#": int(f[0:f.find("_")]), "version": int(f[f.find("_") + 1:-4]), "name": f} for f
            in files_l if not f.startswith("t")}
        max_fulls = {v["base#"]: v for (k, v) in fulls_d.items() if
                     v["version"] == max(list([vv["version"] for vv in fulls_d.values() if vv["base#"] == v["base#"]]))}
        logging.debug("{} Files for application {} {}: {}".format(len(files_l), app_number, extension, files_l))

        missing_thumbs_d = {k: v for (k, v) in max_fulls.items() if k not in max_thumbs}
        missing_fulls_d = {k: v for (k, v) in max_thumbs.items() if k not in max_fulls}
        num_thumbnails = len(max_thumbs)
        num_full_images = len(max_fulls)

        logging.debug("Found {} thumbnails and {} full images for appl # {} {}".format(num_thumbnails, num_full_images,
                                                                                       app_number, extension))
        if missing_fulls_d:
            logging.warning(
                "Missing full images for these {} thumbnails: {}".format(len(missing_fulls_d),
                                                                         [v["name"] for v in missing_fulls_d.values()]))
        if missing_thumbs_d:
            logging.warning(
                "Missing thumbnails for these {} full images: {}".format(len(missing_thumbs_d), [v["name"] for v in
                                                                                                 missing_thumbs_d.values()]))

        # thumbs = [f for f in files_l if f.startswith("t")]
        # fulls = [f for f in files_l if not f.startswith("t")]
        # num_thumbnails = len(thumbs)
        # num_full_images = len(fulls)
        # missing_thumbs = [f for f in fulls if "t{}.png".format(f[0:-4]) not in thumbs]
        # missing_fulls = [f for f in thumbs if
        # "{}.jpg".format(f[1:-4]) not in fulls and "{}.tif".format(f[1:-4]) not in fulls]
        # if missing_fulls:
        # logging.warning(
        # "Missing full images for these {} thumbnails: {}".format(len(missing_fulls), missing_fulls))
        # if missing_thumbs:
        # logging.warning(
        # "Missing thumbnails for these {} full images: {}".format(len(missing_thumbs), missing_thumbs))
    else:
        logging.info(
            "No files found for application {} {}. Could have been an error checking, see previous messages.".format(
                app_number, extension))
    return num_thumbnails, num_full_images


def valid_app_number_pattern(string):
    str_len = len(string)
    if str_len != 6 and str_len != 1:
        msg = "Application numbers must be 6 digits long and Extenion numbers must be 1 character long. '{}' is not a valid application number or extension number.".format(
            string)
        raise argparse.ArgumentTypeError(msg)
    if str_len == 6 and not all(map(str.isdigit, string)):
        msg = "Application numbers must only contain numbers. '{}' is not a valid application number.".format(string)
        raise argparse.ArgumentTypeError(msg)
    elif str_len == 1 and string != "0" and string < "A" and string > "Z":
        msg = "Extension numbers must either '0' or 'A' to 'Z'. '{}' is not a valid extension number.".format(string)
        raise argparse.ArgumentTypeError(msg)
    return string


def valid_extension_number_pattern(string):
    if len(string) != 1:
        msg = "Extension must be only 1 character long. '{}' is not a valid extension.".format(string)
        raise argparse.ArgumentTypeError(msg)
    if string != "0" and not string.isupper():
        msg = "Extension must be an upper character or '0'. '{}' is not a valid extension.".format(string)
        raise argparse.ArgumentTypeError(msg)
    return string


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("app_numbers", type=valid_app_number_pattern, nargs="+",
                        help="Application numbers to check for images. Can include single character extension numbers as well.")
    parser.add_argument("-e", "--environment", dest="env_name", default="DEV",
                        choices=environment.FILE_STORAGE_SERVERS.keys(), help="Environment name to check in")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        help="Flag to print verbose log messages.")
    parser.add_argument("-o", "--open", dest="open_output", action="store_true",
                        help="Flag to indicate to open the log file in an editor once the script has completed.")

    args = parser.parse_args()
    verbose = args.verbose
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_file_path = common_utils.get_log_file_path("~/reports", "check_images_for_app")
    common_utils.setup_logger_to_console_file(log_file_path, log_level)

    # Parse out the application numbers and extension numbers
    app_ext_numbers = []
    prev_number = None
    for num in args.app_numbers:
        if len(num) == 6 and prev_number:
            app_ext_numbers.append((prev_number, "0"))
            logging.debug("Found app # '{}' ext # '0'".format(prev_number))
            prev_number = num
        elif len(num) == 6 and not prev_number:
            prev_number = num
        elif len(num) == 1 and prev_number:
            app_ext_numbers.append((prev_number, num))
            logging.debug("Found app # '{}' ext # '{}'".format(prev_number, num))
            prev_number = None
        elif len(num) == 1 and not prev_number:
            logging.warning("Got an extension number '{}' without an application number. Ignoring....".format(num))
        else:
            logging.warning(
                "Got an application or extension number '{}' that is not a valid length. Ignoring....".format(num))
    if prev_number:
        app_ext_numbers.append((prev_number, "0"))
        logging.debug("Found app # '{}' ext # '0'".format(prev_number))
    logging.debug(
        "Got {} application and extension numbers from args: {}".format(len(app_ext_numbers), args.app_numbers))
    logging.info(' ')
    for (app_num, ext_num) in app_ext_numbers:
        num_thumbnails, num_full_images = check_images_for_application(args.env_name, app_num, ext_num)
        if num_full_images == 0 and num_full_images == num_thumbnails:
            logging.warning(
                "In the {} environment, for the application {} {}, found NO images (neither thumbnails and full images)\n".format(
                    args.env_name, app_num, ext_num))
        elif num_full_images != 0 and num_full_images == num_thumbnails:
            logging.info(
                "In the {} environment, for the application {} {}, found {} images (both thumbnails and full images)\n".format(
                    args.env_name, app_num, ext_num, num_full_images))
        else:
            logging.warning(
                "In the {} environment, for the application {} {}, found {} thumbnails and {} full images)\n".format(
                    args.env_name, app_num, ext_num, num_thumbnails, num_full_images))
    logging.info('Log file: {}'.format(log_file_path))
    if args.open_output:
        common_utils.open_file_in_editor(log_file_path)
