import argparse
import datetime
import sys
import urllib.parse

from lxml import etree
import requests


applications_info = {"app1": "app1/path/login.htm",
                     "app2": "app2/path/login.htm",
                     "app3": "app3/path/login.htm",
                     "app4": "app4/path/login.htm",
                    }


environments_info = {"localhost": "localhost:9443",
                     "DEV": "dev.host.com",
                     "INT": "int.host.com",
                     "QA": "qa.host.com",
                     "UAT": "uat.host.com",
                     "TRAINING": "",
                     "PROD": "www.host.com",
                    }

def build_app_url(env, app_name):
    return "https://{0}/{1}".format(environments_info[env], applications_info[app_name])

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
        r = requests.get(url)
        if r.status_code == requests.codes.ok:
            return get_app_version_from_page_source(url, r.text)
        else:
            return "page unavailable: {}".format(r.status_code), "N/A"
    except:
        e = sys.exc_info()
        print('\nEXCEPTION trying to get url {}! {} \n{} \n{}\n'.format(url, e[0], e[1], e[2]))
        return "url unavailable", "N/A"
    
def main(env_param=None, applications=None, verbose=None):
    if applications is None:
        applications = applications_info
    if verbose is None:
        verbose = False

    if env_param is None:
        envs = environments_info.keys()
    elif env_param in environments_info.keys():
        envs = [env_param]
    else:
        print("Cannot find env '{0}'.".format(env))
        return
        
    for env in envs:
        print("\n{} Environment at {}".format(env, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        for app in applications:
            version, timestamp = get_deployed_app_version(env, app, verbose)
            print("{0:<20}  {1:<18}  {2}".format(app, version, timestamp))

if __name__ == "__main__": 
    parser = argparse.ArgumentParser()
    parser.add_argument("env")
    parser.add_argument("apps", nargs="*")
    parser.add_argument("-v", dest="verbose", action="store_true")
    
    args = parser.parse_args()

    main(args.env, applications_info if len(args.apps) == 0 else args.apps, args.verbose)
