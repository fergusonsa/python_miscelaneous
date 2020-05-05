import argparse
import datetime
import logging
import sys
import urllib.parse

from lxml import etree
import requests

import common_utils
import environment


def build_app_url(env, app_name):
    return "https://{0}/{1}".format(environment.ENVIRONMENTS_HOST[env], environment.APPLICATIONS_URL_PATHS[app_name])

    
def get_app_version_from_page_source(url, page_src):
    tree = etree.HTML(page_src)
    x = tree.xpath('//*[@id="wb-dtmd"]/dd')
    version = x[0].text.strip() if len(x) > 0 else "unknown"
    x = tree.xpath('//*[@id="wb-body-sec"]/div/div/div/div/span')
    if len(x) == 0:
        x = tree.xpath('//*[@id="wb-dtmd"]/span')        
    timestamp = x[0].text.strip() if len(x) > 0 else "unknown"
    return version, timestamp
    
def get_deployed_app_version(env, app_name, verbose=None):
    url = build_app_url(env, app_name)
    try:
        verify_ssl = env != "localhost" 
        r = requests.get(url, verify=verify_ssl)
        if r.status_code == requests.codes.ok:
            return get_app_version_from_page_source(url, r.text)
        else:
            return "page unavailable: {}".format(r.status_code), "N/A"
    except:
        e = sys.exc_info()
        logging.warn('\nEXCEPTION trying to get url {}! {} \n{} \n{}\n'.format(url, e[0], e[1], e[2]))
        return "url unavailable", "N/A"
    
def main(env_param=None, applications=None, verbose=None):
    if applications is None:
        applications = environment.APPLICATIONS_URL_PATHS.keys()
    if verbose is None:
        verbose = False

    if env_param is None:
        envs = environment.ENVIRONMENTS_HOST.keys()
    elif env_param in environment.ENVIRONMENTS_HOST.keys():
        envs = [env_param]
    else:
        logging.warn("Cannot find env '{0}'.".format(env))
        return
        
    for env in envs:
        logging.info("\n{} Environment at {}".format(env, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        for app in applications:
            version, timestamp = get_deployed_app_version(env, app, verbose)
            logging.info("{0:<20}  {1:<18}  {2}".format(app, version, timestamp))

if __name__ == "__main__": 
    parser = argparse.ArgumentParser()
    parser.add_argument("env", choices=environment.ENVIRONMENTS_HOST.keys())
    parser.add_argument("apps", nargs="*", help="Should be None or one or more of {0}".format(environment.APPLICATIONS_URL_PATHS.keys()))
    parser.add_argument("-v", dest="verbose", action="store_true")
    
    args = parser.parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO

    log_file_path = common_utils.get_log_file_path("~/reports", "check_deployed_versions")
    common_utils.setup_logger_to_console_file(log_file_path, log_level)

    main(args.env, environment.APPLICATIONS_URL_PATHS.keys() if len(args.apps) == 0 else args.apps, args.verbose)
