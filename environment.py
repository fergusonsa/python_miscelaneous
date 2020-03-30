# Sample of environment configuration settings
#

NEXUS_INFO = {"root_url" : "0",
              "snapshots_rool_url": "https://nexus.priv/maven-proxy/content/groups/all-snapshots/",
              "released_rool_url": "https://nexus.priv/maven-proxy/content/groups/all-released",
              }

WORKSPACE_ROOT_ID = "/cygdrive/c/dev/new_workspace"

LOCAL_LOG_DIRECTORY = "/cygdrive/c/dev/logs"

LOG_LOCATIONS = {
                    "localhost": {"prefix":"local", "root": "//cygdrive/C/logs","servers": []},
                    "DEV": {"prefix":"cipodev", "root": "http://dev.logs.priv/", "servers": ["serv5", "serv6"]},
                    "INT": {"prefix":"cipoint", "root": "http://int.logs.priv/", "servers": ["serv5", "serv6"]},
                    "QA": {"prefix":"cipoqa", "root": "http://qa.logs.priv/", "servers": ["serv5", "serv6"]},
                    "UAT": {"prefix":"cipouat", "root": "http://uat.logs.priv/", "servers": ["serv5", "serv6"]},
                    "DEV_MAINT": {"prefix":"dev", "root": "http://dev_maint.logs.priv/", "servers": ["serv1", "serv2"]},
                    "INT_MAINT": {"prefix":"cipoint", "root": "http://int_maint.logs.priv/", "servers": ["serv5", "serv6"]},
                    "QA_MAINT": {"prefix":"cipoqa", "root": "http://qa_maint.logs.priv/", "servers": ["serv5", "serv6"]},
                    "UAT-MAINT": {"prefix":"cipouat", "root": "http://uat-maint.logs.priv/", "servers": ["serv5", "serv6"]},
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
