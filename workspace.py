import argparse
import datetime
import itertools
import logging
import os.path
import pathlib
import re
import sys

import git
import requests
from bs4 import BeautifulSoup

import common_utils
import environment


def get_git_info(path):
    try:
        repo = git.Repo(path, search_parent_directories=True)
        return {"repo_url": repo.remotes.origin.url,
                "branch": repo.active_branch.name}
    except:        
        logging.warn("**** path {0} was found to not be a git repo. ********".format(path))
        return {"repo_url": "Not git repo",
                "branch": "Not git repo"}


def parse_artifact_list_page(page_source, group_id, artifact_id):                
    artifact_list_dict = {}
    soup = BeautifulSoup(page_source)
    rows = soup.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) == 4:
            anch = cols[0].find("a")
            if anch and cols[2].text.strip() == "":
                version = anch.text
                url = anch.attrs["href"]
                timestamp_str = cols[1].text
                # Convert timestamp string to DateTime - example: 'Mon Apr 06 10:30:10 EDT 2020'
                timestamp = datetime.datetime.strptime(timestamp_str, "%a %b %d %H:%M:%S %Z %Y")
                key = get_pom_key(group_id=group_id, artifact_id=artifact_id, version=version)
                artifact_list_dict[key] = {"url": url,
                                        "version": version,
                                        "groupId": group_id,
                                        "artifactId": artifact_id,
                                        "timestamp": timestamp}    
    return artifact_list_dict


def parse_artifact_version_page(page_source, group_id, artifact_id):                
    artifact_list_dict = {}
    soup = BeautifulSoup(page_source)
    rows = soup.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) == 4:
            anch = cols[0].find("a")
            if anch:
                file_name = anch.text
                extension = file_name[-4:].lowercase()
                if extension == ".ear" or extension == ".jar":
                    url = anch.attrs["href"]
                    timestamp_str = cols[1].text
                    # Convert timestamp string to DateTime - example: 'Mon Apr 06 10:30:10 EDT 2020'
                    timestamp = datetime.datetime.strptime(timestamp_str, "%a %b %d %H:%M:%S %Z %Y")
                    key = get_pom_key(group_id=group_id, artifact_id=artifact_id, version=version)
                    artifact_list_dict[key] = {"url": url,
                                            "version": version,
                                            "groupId": group_id,
                                            "artifactId": artifact_id,
                                            "filename": file_name,
                                            "timestamp": timestamp}    
    return artifact_list_dict


def find_available_versions_of_artifact(group_id, artifact_id):
    available_versions = {}
    # Headers to mimic a browser visit
    headers = {'User-Agent': 'Mozilla/5.0'}
    for (url_desc, base_url) in environment.NEXUS_INFO.items():
        if not available_versions.get(url_desc):
            available_versions[url_desc] = {}
        # Convert the group_id to a url path
        group_id_path = group_id.replace(".", "/")
        artifact_url = "{}/{}/{}/".format(base_url, group_id_path, artifact_id)
        try:
            artifact_list_page = requests.get(artifact_url, headers=headers)
        except Exception as ex:
            logging.warn("Could not get artifact_url {0} for group_id {} and artifact_id {}. Exception {1}".format(artifact_url, group_id, artifact_id, ex.getMessage()))
            continue
        if artifact_list_page.status_code != requests.codes.ok:
            logging.warn("Could not get artifact_url {0} for group_id {} and artifact_id {}. status_code {1}".format(artifact_url, group_id, artifact_id, artifact_list_page.status_code))
            continue   
        artifact_list_dict = parse_artifact_list_page(artifact_list_page.text, group_id, artifact_id)
        for artifact_item in sorted(artifact_list_dict.values(), key=lambda k: k["timestamp"], reverse=True):
            try:
                artifact_version_page = requests.get(artifact_item["url"], headers=headers)
            except Exception as ex:
                logging.warn("Could not get artifact_version url {0} for group_id {} and artifact_id {}. Exception {1}".format(artifact_item["url"], group_id, artifact_id, ex.getMessage()))
                continue
            if artifact_version_page.status_code != requests.codes.ok:
                logging.warn("Could not get artifact_version url {0} for group_id {} and artifact_id {}. status_code {1}".format(artifact_item["url"], group_id, artifact_id, artifact_version_page.status_code))
                continue   
            artifact_versions_dict = parse_artifact_version_page(artifact_version_page.text, group_id, artifact_id)
                
            available_versions.update(artifact_versions_dict)
    return artifact_versions_dict


def load_pom_file(pom_path):
    logging.debug("Attempting to load {}\n".format(pom_path))
    pom_info = {"path": pom_path}
    pom_tree = ET.parse(pom_path)
    root = pom_tree.getroot()
    nsmap = {"m": "http://maven.apache.org/POM/4.0.0"}

    _el = root.find("m:groupId", nsmap)   
    pom_info["groupId"] = "unspecified" if _el is None else _el.text
    _el = root.find("m:artifactId", nsmap)   
    pom_info["artifactId"] = "unspecified" if _el is None else _el.text
    if '${' in pom_info["artifactId"]:
        pattern = re.compile(r'\$\{([^}]*)\}')
        grps = pattern.match( pom_info["artifactId"] );
        if grps:
            if grps.group(1) == 'project.artifactId': 
                pass
    _el = root.find("m:version", nsmap)   
    pom_info["version"] = "unspecified" if _el is None else _el.text
    _el = root.find("m:name", nsmap)   
    pom_info["name"] = pom_info["artifactId"] if _el is None else _el.text
    _el = root.find("m:packaging", nsmap)   
    pom_info["packaging"] = "unspecified" if _el is None else _el.text
    _el = root.find("m:parent/m:groupId", nsmap)   
    group_id = "unknown" if _el is None else _el.text
    _el = root.find("m:parent/m:artifactId", nsmap)   
    artId = "unknown" if _el is None else _el.text
    _el = root.find("m:parent/m:version", nsmap)   
    version = "unknown" if _el is None else _el.text
    pom_info["parent"] = {"groupId": group_id, "artifactId": artId, "version": version}

    # Property variables
    properties_els = root.findall("m:properties/*", nsmap)
    pom_info["properties"] = {}
    for prop_el in properties_els:
        pom_info["properties"][prop_el.tag[len(nsmap["m"])+2:]] = prop_el.text
    
    # Dependencies
    pom_info["dependencies"] = {}
    dependencies_el_list = []
    dependencies_el_list.extend(root.findall("*/m:dependencies/m:dependency", nsmap))
    dependencies_el_list.extend(root.findall("m:dependencies/m:dependency", nsmap))
    variable_pattern = re.compile(r'\$\{([^}]*)\}')
    for dep_el in dependencies_el_list:
        _el = dep_el.find("m:version", nsmap)   
        version = "unspecified" if _el is None else _el.text
        grps = variable_pattern.match( version )
        if grps:
            prop_name = grps.group(1)
            _el = root.find("m:properties/m:{}".format(prop_name), nsmap)   
            version = version if _el is None else _el.text
        group_id = dep_el.find("m:groupId", nsmap).text
        artId = dep_el.find("m:artifactId", nsmap).text
        pom_info["dependencies"]["{}/{}".format(group_id, artId)] = { "groupId": group_id, 
                                                                    "version": version, 
                                                                    "artifactId": artId}
    # Modules (sub-projects)
    pom_info["modules"] = {}
    modules_el = root.findall("*/m:modules/m:module", nsmap)
    if not modules_el:
        modules_el = root.findall("m:modules/m:module", nsmap)
    for mod_el in modules_el:
        pom_info["modules"][mod_el.text] = None

    logging.debug("Finished loading {} which contains groupId {}, artifactId {}, and version {}, with {} modules, and {} dependencies, and {} variables\n".format(pom_path, pom_info["groupId"], pom_info["artifactId"], pom_info["version"], len(pom_info["modules"]), len(pom_info["dependencies"]), len(pom_info["properties"])))
    return pom_info


def validate_pom_dependencies(pom_info):
    is_snapshot = "SNAPSHOT" in pom_info["version"].upper()
    version_desc = "snapshot" if is_snapshot else pom_info["version"] if pom_info["version"] in ["unknown", "unspecified"] else "release"
    logging.info("POM {}, {}, is a {} version: {}".format(pom_info["name"], pom_info["path"], version_desc, pom_info["version"]))
    snapshot_deps = [v for v in pom_info["dependencies"].values() if "SNAPSHOT" in v["version"].upper()]
    if len(snapshot_deps) > 0:
        if not is_snapshot:
            logging.warn("WARNING: a released version, {}, contains {} SNAPSHOT dependencies!".format(pom_info["version"], len(snapshot_deps)))
        logging.info("The following {} dependencies are SNAPSHOT versions:".format(len(snapshot_deps)))
        for dep_info in snapshot_deps:
            logging.info("    {}/{} version: {}".format(dep_info["groupId"], dep_info["artifactId"],  dep_info["version"]))

        
def get_pom_key(pom_info=None, group_id=None, artifact_id=None, version=None):
    if not pom_info:
        pom_info = {"groupId": group_id, "artifactId": artifact_id, "version":version}
        
    return "groupId:{groupId};artifactId:{artifactId};version:{version};".format(**pom_info)

    
def generate_pom_partial_key(group_id=None, artifact_id=None, version=None):
    desired_key = "groupId:{0};".format(group_id) if group_id and group_id != "unspecified" else ""
    desired_key = "{0}artifactId:{1};".format(desired_key, artifact_id) if artifact_id else desired_key
    desired_key = "{0}version:{1};".format(desired_key, version) if version and version != "unspecified" else desired_key
    return desired_key


def find_pom_info(poms_info, group_id=None, artifact_id=None, version=None):
    desired_key = generate_pom_partial_key(group_id, artifact_id, version)
    
    return [pom_info for (k, pom_info) in poms_info.items() if desired_key in k]


def resolve_pom_variables(poms_info):
    logging.debug("Starting resolve_pom_variables(poms_info)\n")
    # Need to go through all poms to see if there are any pom variable substituions that need to be performed
    variable_pattern = re.compile(r'\$\{([^}]*)\}')
    for (pom_key, pom_info) in poms_info.items():
        parent_info = pom_info.get("parent")
        if parent_info:
            parent_pom_infos = find_pom_info(poms_info, group_id=parent_info["groupId"], artifact_id=parent_info["artifactId"], version=parent_info["version"]) 
            parent_pom_info = None
            if len(parent_pom_infos) > 1:
                logging.warn("Found multiple parent poms with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {}. Using the first one ".format(parent_info["groupId"], parent_info["artifactId"], parent_info["version"], pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
                parent_pom_info = parent_pom_infos[0]
            elif len(parent_pom_infos) == 1:
                parent_pom_info = parent_pom_infos[0]
            else:
                logging.warn("Could not find parent pom with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {} ".format(parent_info["groupId"], parent_info["artifactId"], parent_info["version"], pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
            
        if pom_info["groupId"] == "unspecified" and parent_pom_info:
            logging.debug("Setting groupId to {} from the parent pom for the pom with groupId {}, artifactId {} and version {}".format(parent_pom_info["groupId"], pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
            pom_info["groupId"] = parent_pom_info["groupId"]
        if pom_info["version"] == "unspecified" and parent_pom_info:
            logging.debug("Setting version to {} from the parent pom for the pom with groupId {}, artifactId {} and version {}".format(parent_pom_info["version"], pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
            pom_info["version"] = parent_pom_info["version"]
        elif pom_info["version"].startswith("${"):
            grps = variable_pattern.match( pom_info["version"] );
            if grps:
                prop_name = grps.group(1)
                v = parent_pom_info["properties"].get(prop_name)
                if v:
                    logging.debug("Setting version to '{}' for the pom with groupId {}, artifactId {} and version {}".format(v, pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
                    pom_info["version"] = v
                else:
                    logging.debug("Could not get property {} for the version for the pom with groupId {}, artifactId {} and version {}".format(prop_name, pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
            else:
                logging.debug("Could not parse out a property name from {} for the version for the pom with groupId {}, artifactId {} and version {}".format(pom_info["version"], pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
        new_key = get_pom_key(pom_info)
        if new_key != pom_key:
            logging.debug("Changing the key from '{}' to '{}' for the pom with groupId {}, artifactId {} and version {}".format(pom_key, new_key, pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
            del poms_info[pom_key]
            poms_info[new_key] = pom_info
        if pom_info["name"].find("${") >= 0:
            for m in re.finditer(variable_pattern, pom_info["name"]):
                prop_name = m.group(1)
                if prop_name.startswith("project."):
                    v = pom_info.get(prop_name[8:])
                else:
                    v = parent_pom_info["properties"].get(prop_name)
                if v:
                    logging.debug("Setting name to '{}' for the pom with groupId {}, artifactId {} and version {}".format(v, pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
                    pom_info["name"] = pom_info["name"].replace("${{{}}}".format(prop_name), v)
                else:
                    logging.debug("Could not get property {} for the name for the pom with groupId {}, artifactId {} and version {}".format(prop_name, pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
            else:
                logging.debug("Could not parse out a property name from {} for the name for the pom with groupId {}, artifactId {} and version {}".format(pom_info["name"], pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
        dependencies = pom_info.get("dependencies")
        if dependencies:
            for (dep_key, dep) in dependencies.items():               
                for k in ["groupId", "artifactId", "version"]:
                    val = dep[k] 
                    if val.startswith("${"):
                        grps = variable_pattern.match(val);
                        if grps:
                            prop_name = grps.group(1)
                            if prop_name.startswith("project."):
                                v = pom_info[k]
                            else:
                                v = parent_pom_info["properties"].get(prop_name)
                            if v:
                                logging.debug("Setting {} to '{}' for the dependency with groupId {}, artifactId {} and version {}".format(k, v, dep["groupId"], dep["artifactId"], dep["version"]))
                                dep[k] = v
                            else:
                                logging.debug("Could not get property {} for the {} for the dependency with groupId {}, artifactId {} and version {}".format(prop_name, k, dep["groupId"], dep["artifactId"], dep["version"]))
                        else:
                            logging.debug("Could not parse out a property name from {} for the {} for the dependency with groupId {}, artifactId {} and version {}".format(dep["version"], k, dep["groupId"], dep["artifactId"], dep["version"]))
                new_key = "{}/{}".format(dep["groupId"], dep["artifactId"])
                if new_key != dep_key:
                    logging.debug("Changing the dependency key from '{}' to '{}' for the dependecy with groupId {}, artifactId {} and version {}".format(dep_key, new_key, dep["groupId"], dep["artifactId"], dep["version"]))
                    del dependencies[dep_key]
                    dependencies[new_key] = dep
        if pom_info.get("modules"):
            modules = pom_info.get("modules")
            logging.debug("There are {} modules for pom groupId {}, artifactId {} and version {} ".format(len(modules), pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
            for mod in modules.keys():
                if modules[mod] is None:
                    mod_pom_infos = find_pom_info(poms_info, group_id=pom_info["groupId"], artifact_id=mod, version=pom_info["version"]) 
                    mod_pom_info = None
                    if len(mod_pom_infos) > 1:
                        logging.warn("Found multiple module poms with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {}. Using the first one ".format(pom_info["groupId"], mod, pom_info["version"], pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
                        modules[mod] = mod_pom_infos[0]
                    elif len(mod_pom_infos) == 1:
                        modules[mod] = mod_pom_infos[0]
                    else:
                        logging.warn("Could not find module pom with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {} ".format(pom_info["groupId"], mod, pom_info["version"], pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
            else:    
                logging.debug("No modules for the pom pom groupId {}, artifactId {} and version {} ".format(pom_info["groupId"], pom_info["artifactId"], pom_info["version"]))
    logging.debug("Finsihed resolve_pom_variables(poms_info)\n")
    return poms_info


def load_pom_files_from_workspace(root_path):
    logging.debug("Start of load_pom_files_from_workspace('{}')\n".format(root_path))
    poms_info = {}
    pom_files = sorted(itertools.chain(root_path.glob("pom.xml"), root_path.glob("*/pom.xml"), root_path.glob("*/*/pom.xml")))
    variable_pattern = re.compile(r'\$\{([^}]*)\}')
    for pom_path in pom_files:
        pom_info = load_pom_file(pom_path)
        pom_key = get_pom_key(pom_info)
        if pom_key not in poms_info:
            validate_pom_dependencies(pom_info)
            poms_info[pom_key] = pom_info            
            logging.debug('Loaded pom with the key "{0}" from {1}'.format(pom_key, pom_info["path"]))
        else:
            logging.warn('There is already a pom with the key "{0}". Not adding the one for {1}'.format(pom_key, pom_info["path"]))
    
    resolve_pom_variables(poms_info)
    resolve_pom_variables(poms_info)
    
    logging.debug("Finished load_pom_files_from_workspace('{}')\n".format(root_path))
    return poms_info


def document_workspace(root_path):
    root_path = pathlib.Path(root_path)
    
    poms_info = load_pom_files_from_workspace(root_path)

    logging.info("Displaying the pom dependencies of all the projects in workspace {}\n".format(root_path))

    logging.info('Display of pom dependencies:')
    for v in poms_info.values():
        logging.info('GroupId: {groupId}'.format(**v))
        logging.info('ArtifactId: {artifactId}'.format(**v))
        logging.info('Version: {version}'.format(**v))
        logging.info('Path: {path}'.format(**v))
        logging.info('Name: {name}'.format(**v))
        logging.info('Dependencies:')
        for dep_info in v['dependencies'].values():
            pom_key = "groupId:{groupId};artifactId:{artifactId};version:{version}".format(**dep_info)
            logging.info(' -- GroupId: {}'.format(dep_info['groupId']))
            logging.info('    ArtifactId: {}'.format(dep_info['artifactId']))
            logging.info('    Version: {}'.format(dep_info['version']))
            if pom_key in poms_info:
                logging.info('    LOCAL ENVIRONMENT COPY')


def check_dependencies(poms_info, dependency_poms_infos):
    deps_to_check = []
    for dep_info in dependency_poms_infos:
        dep_pom_info_list = find_pom_info(poms_info, group_id=dep_info["groupId"], artifact_id=dep_info["artifactId"])
        if not dep_pom_info_list:
            logging.info("Dependency not present:                GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}".format(**dep_info))
        elif len(dep_pom_info_list) > 1:
            logging.info("Multiple copied of Dependency present: GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}".format(**dep_info))
            for pom_info in dep_pom_info_list:
                logging.info('\tGroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}'.format(**pom_info))
                logging.info('\t\tPath: {path}'.format(**pom_info))
                logging.info('\t\tName: {name}'.format(**pom_info))
        elif dep_info["version"] == dep_pom_info_list[0]["version"]:
            logging.info("Proper dependency version present:     GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}".format(**(dep_pom_info_list[0])))
            logging.info("\t\tPath: {path}".format(**(dep_pom_info_list[0])))
            logging.info("\t\tName: {name}".format(**(dep_pom_info_list[0])))
            repo_info = get_git_info(dep_pom_info_list[0]["path"])
            logging.info("\t\tGit repo: {repo_url}".format(**repo_info))
            logging.info("\t\tGit branch: {branch}".format(**repo_info))
            
            deps_to_check.append(dep_pom_info_list[0])
        else:
            logging.info("Incorrect dependency version present:  GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}".format(**(dep_pom_info_list[0])))
            logging.info("\t\tPath: {path}".format(**(dep_pom_info_list[0])))
            logging.info("\t\tName: {name}".format(**(dep_pom_info_list[0])))
            repo_info = get_git_info(dep_pom_info_list[0]["path"])
            logging.info("\t\tGit repo: {repo_url}".format(**repo_info))
            logging.info("\t\tGit branch: {branch}".format(**repo_info))
            logging.info("\tRequired version: {}".format(dep_info["version"]))
    for dep_pom_info in deps_to_check:
        logging.info('Using dependent project GroupId: {groupId:<35}\tArtifactId: {artifactId:<40}\tVersion: {version}'.format(**dep_pom_info))
        logging.info('\t\tPath: {path}'.format(**dep_pom_info))
        logging.info('\t\tName: {name}'.format(**dep_pom_info))
        repo_info = get_git_info(dep_pom_info["path"])
        logging.info("\t\tGit repo: {repo_url}".format(**repo_info))
        logging.info("\t\tGit branch: {branch}\n".format(**repo_info))
        logging.info('Dependencies:')
        
        check_dependencies(poms_info, dep_pom_info['dependencies'].values())
        

def check_modules(poms_info, parent_pom_info):
    modules_poms_dict = parent_pom_info['modules']
    for (mod_key, mod_info) in modules_poms_dict.items():
        if not mod_info:
            logging.info("Module not present:                GroupId: {:<35}  ArtifactId: {:<40}  Version: {}".format(parent_pom_info["groupId"], mod_key, parent_pom_info["version"]))
        else:
            logging.info("Module information:     GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}".format(**mod_info))
            logging.info("\t\tPath: {path}".format(**mod_info))
            logging.info("\t\tName: {name}".format(**mod_info))
            repo_info = get_git_info(mod_info["path"])
            logging.info("\t\tGit repo: {repo_url}".format(**repo_info))
            logging.info("\t\tGit branch: {branch}".format(**repo_info))
      
            check_dependencies(poms_info, mod_info['dependencies'].values())
        

def check_poms_against_parent(parent_project_name, workspace):
    root_path = pathlib.Path(workspace)

    logging.info("Attempting to check the pom dependencies for {} pom artifact project in workspace {} against other projects in the same workspace\n".format(parent_project_name, workspace))

    poms_info = load_pom_files_from_workspace(root_path)
    # Find the parent project's pom info
    parent_pom_info_list = find_pom_info(poms_info, artifact_id=parent_project_name)
    if not parent_pom_info_list:
        logging.info("Could not find parent project with artifactId of '{0}' in the workspace {1}.".format(parent_project_name, workspace))
        sys.exit(0)
    if len(parent_pom_info_list) > 1:
        logging.warn("Found multiple parent projects with artifactId of '{0}' in the workspace {1}.".format(parent_project_name, workspace))
        for pom_info in parent_pom_info_list:
            logging.warn('\tGroupId: {groupId:<35}\tArtifactId: {artifactId:<40}\tVersion: {version}'.format(**pom_info))
            logging.warn('\t\tPath: {path}'.format(**pom_info))
            logging.warn('\t\tName: {name}'.format(**pom_info))
        logging.warn("Cannot perform analysis with multiple parent projects.")
        sys.exit(0)
    parent_pom_info = parent_pom_info_list[0]
    repo_info = get_git_info(parent_pom_info["path"])
    logging.info('Using Parent project GroupId: {groupId:<35}\tArtifactId: {artifactId:<40}\tVersion: {version}'.format(**parent_pom_info))
    logging.info('\t\tPath: {path}'.format(**parent_pom_info))
    logging.info('\t\tName: {name}'.format(**parent_pom_info))
    logging.info("\t\tGit repo: {repo_url}".format(**repo_info))
    logging.info("\t\tGit branch: {branch}\n".format(**repo_info))
    logging.info('Dependencies:')
    
    check_modules(poms_info, parent_pom_info)
    
    check_dependencies(poms_info, parent_pom_info['dependencies'].values())
        
    
def checkout_branch(parent_project_name, workspace, branch, reset):
    root_path = pathlib.Path(workspace)

    logging.info("Attempting to check out Branch {} of the git repository for {} pom artifact in workspace {}, with reset flag {}\n".format(branch, parent_project_name, workspace, reset))
    
    poms_info = load_pom_files_from_workspace(root_path)
    # Find the parent project's pom info
    parent_pom_info_list = find_pom_info(poms_info, artifact_id=parent_project_name)
    if not parent_pom_info_list:
        logging.info("Could not find parent project with artifactId of '{0}' in the workspace {1}.".format(parent_project_name, workspace))
        sys.exit(0)
    parent_pom_info = parent_pom_info_list[0]            
    repo = None
    try:
        repo = git.Repo(parent_pom_info["path"], search_parent_directories=True)
    except:        
        logging.info("**** path {0} was found to not be a git repo. ********".format(parent_pom_info["path"]))
        repo = None
    # Make sure not already on the desired branch
    if repo.active_branch.name == branch:
        logging.info("Already on the {} branch  for the project '{}' in the workspace {}.".format(branch, parent_project_name, workspace))
        return
        
    # Check to see if the branch is validate
    all_branches = [e[2:] for e in repo.git.branch('-a').splitlines()]
    if not (branch in all_branches or "remotes/origin/{}".format(branch) in all_branches):
        logging.info("{} is not a valid branch in the repo for the parent project with artifactId of '{}' in the workspace {}.".format(branch, parent_project_name, workspace))
        sys.exit(0)
    changes = repo.index.diff(None)    
    if changes:
        if not reset:
            logging.info("There are {} changed files that need to be dealt with before switching to the {} branch in the repo for the parent project with artifactId of '{}' in the workspace {}.".format(len(changes), branch, parent_project_name, workspace))
            sys.exit(0)
                
        repo.git.checkout(branch, force=True)
    else:
        repo.git.checkout(branch)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--document", dest="document", action="store_true", help="Document the dependencies for all Maven projects in the specified workspace")
    parser.add_argument("-c", "--check-poms", dest="check_poms", action="store_true", help="Check the pom versions for projects in the workspace against a parent project")
    parser.add_argument("-k", "--checkout-branch", dest="checkout_branch", action="store_true", help="Checkout the specified branch of the parent project and check the pom version of the rest of the workspace")
    parser.add_argument("-w", "--workspace", dest="workspace",  help="Workspace path to check. Defaults to '{0}'.".format(environment.WORKSPACE_ROOT_ID), default=environment.WORKSPACE_ROOT_ID)
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Flag to print verbose log messages.")
    parser.add_argument("-p", "--parent", dest="parent_project", help="The ArtifactId of the Maven project that is the parent (all other projects in the workspace should be the versions specified by the parent project)")
    parser.add_argument("-b", "--branch", dest="branch", help="The branch of the parent project to checkout.")
    parser.add_argument("-r", "--reset", dest="reset", action="store_true", help="Flag to indicate to reset any existing change when checking out.")
    parser.add_argument("-o", "--open", dest="open_output", action="store_true", help="Flag to indicate to open the log file in an editor once the script has completed.")

    args = parser.parse_args()
    verbose = args.verbose
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_file_path = None
    
    if args.document:
        log_file_path = common_utils.get_log_file_path(args.workspace, "document_workspace_dependencies")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)
        document_workspace(args.workspace)
    elif args.check_poms:
        if not args.parent_project:
            print("To check the pom versions in the workspace, you must supply a parent project.")
            parser.usage()
            sys.exit(1)
        log_file_path = common_utils.get_log_file_path(args.workspace, "check_poms_against_parent")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)
        check_poms_against_parent(args.parent_project, args.workspace)
    elif args.checkout_branch:
        if not args.parent_project:
            print("To get a branch for a project and check the pom versions in the workspace, you must supply a parent project.")
            parser.usage()
            sys.exit(1)
        if not args.branch:
            print("To get a branch for a project and check the pom versions in the workspace, you must supply a branch to checkout.")
            parser.usage()
            sys.exit(1)
        log_file_path = common_utils.get_log_file_path(args.workspace, "checkout_branch")

        common_utils.setup_logger_to_console_file(log_file_path, log_level)
        checkout_branch(args.parent_project, args.workspace, args.branch, args.reset)
        check_poms_against_parent(args.parent_project, args.workspace)

    logging.info('\n\nLog file: {}'.format(log_file_path))
    if args.open_output:
        common_utils.open_file_in_editor(log_file_path)
        