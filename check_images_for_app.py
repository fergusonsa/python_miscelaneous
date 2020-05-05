import argparse
import logging
import subprocess

import common_utils
import environment


def check_images_for_application(env_name, app_number, extension):
    command = "ls {}/{}/{}/{}/{}/".format(environment.FILE_STORAGE_IMAGE_ROOT_PATH, app_number[0:2], app_number[2:4], app_number[4:6], extension)
    try:
        result = subprocess.run(['ssh', '{}@{}'.format(environment.FILE_STORAGE_USER, environment.FILE_STORAGE_SERVERS[env_name]), command], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    except subprocess.CalledProcessError as e:
        logging.error("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output), e)
        return None, None
    
    if result and result.returncode == 0:
        files_l = result.stdout.decode().splitlines()
        thumbs = [f for f in files_l if f.startswith("t")]
        fulls = [f for f in files_l if not f.startswith("t")]
        num_thumbnails = len(thumbs)
        num_full_images = len(fulls)
        logging.debug("Found {} thumbnails and {} full images for application {} {}".format(num_thumbnails, num_full_images, app_number, extension))
        if len(files_l) > 0:
            logging.debug("{} Files for application {} {}: {}".format(len(files_l), app_number, extension, files_l))
            missing_thumbs = [f for f in fulls if "t{}.png".format(f[0:-4]) not in thumbs] 
            missing_fulls = [f for f in thumbs if "{}.jpg".format(f[1:-4]) not in fulls and "{}.tif".format(f[1:-4]) not in fulls ]
            if missing_fulls:
                logging.warn("Missing full images for these {} thumbnails: {}".format(len(missing_fulls), missing_fulls))
            if missing_thumbs:
                logging.warn("Missing thumbnails for these {} full images: {}".format(len(missing_thumbs), missing_thumbs))
    elif result and result.returncode != 0:
        num_thumbnails = num_full_images = None
        if result.returncode == 2 and result.stderr.decode().endswith(" does not exist.\n"):
            logging.debug("SSH command '{}' did not find any files for application {} {}".format(command, app_number, extension))
        else:
            logging.warn("SSH command '{}' failed with returncode {} and stderr {} for application {} {}".format(command, result.returncode, result.stderr.decode(), app_number, extension))
    else:
        logging.error("SSH command '{}' failed with and did not return a result for application {} {}".format(command, app_number, extension))
        num_thumbnails = num_full_images = None
    return num_thumbnails, num_full_images
        

def valid_app_number_pattern(string):
    if len(string) != 6:
        msg = "Application numbers must be 6 digits long. '{}' is not a valid application number.".format(string)
        raise argparse.ArgumentTypeError(msg)
    if not all(map(str.isdigit, string)):
        msg = "Application numbers must only contain numbers. '{}' is not a valid application number.".format(string)
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
    parser.add_argument("app_number", type=valid_app_number_pattern, help="Application number to check for images")
    parser.add_argument("extension", nargs="?", default="0", type=valid_extension_number_pattern, help="Extension number for the application. Defaults to '%(default)s'")
    parser.add_argument("-e", "--environment", dest="env_name", default="DEV", choices=environment.FILE_STORAGE_SERVERS.keys(), help="Environment name to check in")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Flag to print verbose log messages.")
    parser.add_argument("-o", "--open", dest="open_output", action="store_true", help="Flag to indicate to open the log file in an editor once the script has completed.")

    args = parser.parse_args()
    verbose = args.verbose
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_file_path = common_utils.get_log_file_path("~/reports", "check_images_for_app_{}_{}".format(args.app_number, args.extension))
    common_utils.setup_logger_to_console_file(log_file_path, log_level)

    logging.info(' ')
    num_thumbnails, num_full_images = check_images_for_application(args.env_name, args.app_number, args.extension)
    if num_full_images == 0 and num_full_images == num_thumbnails:
        logging.warn("In the {} environment, for the application {} {}, found NO images (neither thumbnails and full images)\n\n".format(args.env_name, args.app_number, args.extension))
    elif num_full_images != 0 and num_full_images == num_thumbnails:
        logging.info("In the {} environment, for the application {} {}, found {} images (both thumbnails and full images)\n\n".format(args.env_name, args.app_number, args.extension, num_full_images))
    else: 
        logging.warn("In the {} environment, for the application {} {}, found {} thumbnails and {} full images)\n\n".format(args.env_name, args.app_number, args.extension, num_thumbnails, num_full_images))
    logging.info('Log file: {}'.format(log_file_path))
    if args.open_output:
        common_utils.open_file_in_editor(log_file_path)
