# Sample of environment configuration settings
#

NEXUS_INFO = {"root_url" : "0",
              "snapshots_root_url": "https://nexus.priv/maven-proxy/content/groups/all-snapshots/",
              "released_root_url": "https://nexus.priv/maven-proxy/content/groups/all-released",
              }

WORKSPACE_ROOT_ID = "/cygdrive/c/dev/new_workspace"

LOCAL_LOG_DIRECTORY = "/cygdrive/c/dev/logs"

LOG_LOCATIONS = {
                    "localhost": {"prefix":"local", "root": "//cygdrive/C/logs","servers": []},
                    "DEV": {"prefix":"dev1", "root": "http://dev.logs.priv/", "servers": ["serv5", "serv6"]},
                    "INT": {"prefix":"int1", "root": "http://int.logs.priv/", "servers": ["serv5", "serv6"]},
                    "QA": {"prefix":"qa1", "root": "http://qa.logs.priv/", "servers": ["serv5", "serv6"]},
                    "UAT": {"prefix":"uat1", "root": "http://uat.logs.priv/", "servers": ["serv5", "serv6"]},
                    "DEV2": {"prefix":"dev2", "root": "http://dev_maint.logs.priv/", "servers": ["serv1", "serv2"]},
                    "INT2": {"prefix":"int2", "root": "http://int_maint.logs.priv/", "servers": ["serv5", "serv6"]},
                    "QA2": {"prefix":"qa2", "root": "http://qa_maint.logs.priv/", "servers": ["serv5", "serv6"]},
                    "UAT2": {"prefix":"uat2", "root": "http://uat-maint.logs.priv/", "servers": ["serv5", "serv6"]},
                    "PROD": {"prefix":"prod", "root": "http://prod.logs.priv/logs/", "servers": ["serv1", "serv2", "public1", "public2"]}
                }
                
LOG_APP_PATHS = {
                    "APP1": "/apps/logs/{prefix}-app1.log",
                    "APP2": "/apps/logs/{prefix}-app2.log",
                    "APP3": "/apps/logs/{prefix}-app3.log",
                    "APP4": "/apps/logs/{prefix}-app4.log",
                    "SERVICE1": ["/apps/service1/logs/service1.log"],
                    "SERVICE2": ["/apps/servvice2/logs/service2.log"],
                }

APP_LOG_PATTERNS = {
                        "APP1": ["ERROR"],
                        "APP2": ["ERROR"],
                        "APP3": ["ERROR"],
                        "APP4": ["ERROR"],
                        "SERVICE1": ["ERROR"],
                        "SERVICE2": ["ERROR"],
                   }

                   
APPLICATIONS_URL_PATHS = {  "APP1": "app/app1/login.html",
                            "APP2": "app/app2/login.html",
                            "APP3": "app/app3/login.html",
                            "APP4": "app/app4/login.html",
                         }

SERVICES_URL_PATHS = {"SERVICE1": "",
                      "SERVICE2": "",
                     }    

ENVIRONMENTS_HOST = {
                     "DEV":         "www-dev.app-srv.priv.org",
                     "DEV2":        "www-dev2.app-srv.priv.org",
                     "INT":         "www-int.app-srv.priv.org",
                     "INT2":        "www-int2.app-srv.priv.org",
                     "PROD":        "www.app-srv.priv.org",
                     "QA":          "www-qa.app-srv.priv.org",
                     "QA2":         "www-qa2.app-srv.priv.org",
                     "UAT":         "www-uat.app-srv.priv.org",
                     "UAT2":        "www-uat2.app-srv.priv.org",
                     "localhost":   "localhost:9443",
                    }
 
 
FILE_STORAGE_USER = "remoteuser"

FILE_STORAGE_SERVERS = {
                     "DEV":        "dev.files.priv.org",
                     "DEV_MAINT":  "dev_maint.files.priv.org",
                     "INT":        "int.files.priv.org",
                     "QA":         "qa.files.priv.org",
                     "QA_MAINT":   "qa_maint.files.priv.org",
                     "UAT":        "uat.files.priv.org",
                     "UAT-MAINT":  "uat_maint.files.priv.org",
                    }
                    
FILE_STORAGE_IMAGE_ROOT_PATH = "/data/files"


GROUP_ID_BASE = "ca.company.project1"
''' All group ids that start with this are controlled by this organization '''


PYTHON_WORKSPACE_PATH = "/cygdrive/c/dev/project1/python_workspace"


GIT_REMOTES = [
    "ssh://git@github.com/project/project1.git",
]
