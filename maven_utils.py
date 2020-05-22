import datetime
import itertools
import logging
import os.path
import pathlib
import pprint
import re
import sys
import xml.etree.ElementTree as ET

import git
import requests
from bs4 import BeautifulSoup

import common_utils
import environment


class BasicArtifactInformation:

    def __init__(self, group_id=None, artifact_id=None, version=None):
        self.group_id = group_id
        self.artifact_id = artifact_id
        self.version = version

    def is_snapshot(self):
        return "SNAPSHOT" in self.version.upper()

    def is_locally_managed(self):
        return self.group_id and self.group_id.startswith(environment.GROUP_ID_BASE)


class DependencyInformation(BasicArtifactInformation):

    def __init__(self, group_id=None, artifact_id=None, version=None):
        super().__init__(group_id, artifact_id, version)
        self.group_id = group_id
        self.artifact_id = artifact_id
        self.version = version
        self.type = None
        self.scope = None
        self.exclusions = {}
        self.pom_info = None


class PomInformation(BasicArtifactInformation):
    def __init__(self, group_id=None, artifact_id=None, version=None):
        super().__init__(group_id, artifact_id, version)
        self.group_id = group_id
        self.artifact_id = artifact_id
        self.version = version
        self.name = None
        self.package = None
        self.path = None
        self.url = None
        self.managed_dependencies = {}
        self.dependencies = {}
        self.modules = {}
        self.properties = {}
        self.parent_info = None  # Expecting BasicArtifactInformation
        self.available_versions = None  # If available versions have been pulled from Nexus.
        # See workspace.find_available_versions_of_artifact(group_id, artifact_id)


def load_pom_file(pom_path=None, pom_url=None):
    pom_info = PomInformation()
    if pom_path:
        logging.debug("Attempting to load path {}".format(pom_path))
        pom_info.path = pom_path
        pom_tree = ET.parse(pom_path)
        root = pom_tree.getroot()
    elif pom_url:
        logging.debug("Attempting to load url {}".format(pom_url))
        pom_info.url = pom_url
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            pom_page = requests.get(pom_url, headers=headers)
        except Exception as ex:
            logging.warn("Could not get pom url {}. Exception {}".format(pom_url, ex.getMessage()))
            return None
        if pom_page.status_code != requests.codes.ok:
            logging.warn("Could not get pom url {}. status_code {}".format(pom_url, pom_page.status_code))
            return None
        root = ET.fromstring(pom_page.text)
    else:
        logging.error("Cannot load a pom file from pom_path=None or pom_url=None")
        return None
    nsmap = {"m": "http://maven.apache.org/POM/4.0.0"}

    _el = root.find("m:groupId", nsmap)
    pom_info.group_id = "unspecified" if _el is None else _el.text
    _el = root.find("m:artifactId", nsmap)
    pom_info.artifact_id = "unspecified" if _el is None else _el.text
    if '${' in pom_info.artifact_id:
        pattern = re.compile(r'\$\{([^}]*)\}')
        grps = pattern.match(pom_info["artifactId"]);
        if grps:
            if grps.group(1) == 'project.artifactId':
                pass
    _el = root.find("m:version", nsmap)
    pom_info.version = "unspecified" if _el is None else _el.text
    _el = root.find("m:name", nsmap)
    pom_info.name = pom_info.artifact_id if _el is None else _el.text
    _el = root.find("m:packaging", nsmap)
    pom_info.packaging = "unspecified" if _el is None else _el.text
    _el = root.find("m:parent/m:groupId", nsmap)
    group_id = "unknown" if _el is None else _el.text
    _el = root.find("m:parent/m:artifactId", nsmap)
    artId = "unknown" if _el is None else _el.text
    _el = root.find("m:parent/m:version", nsmap)
    version = "unknown" if _el is None else _el.text
    pom_info.parent = BasicArtifactInformation(group_id, artId, version)

    # Property variables
    properties_els = root.findall("m:properties/*", nsmap)
    for prop_el in properties_els:
        pom_info.properties[prop_el.tag[len(nsmap["m"]) + 2:]] = prop_el.text

    # DependencyManagement Dependencies
    dependencies_el_list = []
    dependencies_el_list.extend(root.findall("*/m:dependencyManagement/m:dependencies/m:dependency", nsmap))
    dependencies_el_list.extend(root.findall("m:dependencyManagement/m:dependencies/m:dependency", nsmap))
    variable_pattern = re.compile(r'\$\{([^}]*)\}')
    logging.debug("Found {1} managed dependencies in pom for {0.group_id} {0.artifact_id} {0.version}".format(pom_info,
                                                                                                              len(
                                                                                                                  dependencies_el_list)))
    logging.debug(
        "Before adding found managed dependencies, # dependencies: {1} for pom for for {0.group_id} {0.artifact_id} {0.version}".format(
            pom_info, len(pom_info.managed_dependencies)))
    for dep_el in dependencies_el_list:
        _el = dep_el.find("m:version", nsmap)
        version = "unspecified" if _el is None else _el.text
        grps = variable_pattern.match(version)
        if grps:
            prop_name = grps.group(1)
            _el = root.find("m:properties/m:{}".format(prop_name), nsmap)
            version = version if _el is None else _el.text
        type_el = dep_el.find("m:type", nsmap)
        type_val = type_el.text if type_el else None
        scope_el = dep_el.find("m:scope", nsmap)
        scope = scope_el.text if scope_el else None
        group_id = dep_el.find("m:groupId", nsmap).text
        artId = dep_el.find("m:artifactId", nsmap).text
        dep_info = DependencyInformation()
        dep_info.group_id = group_id
        dep_info.version = version
        dep_info.artifact_id = artId
        dep_info.scope = scope
        dep_info.type = type_val
        pom_info.managed_dependencies["{}/{}".format(group_id, artId)] = dep_info

    # Dependencies
    dependencies_el_list = []
    dependencies_el_list.extend(root.findall("*/m:dependencies/m:dependency", nsmap))
    dependencies_el_list.extend(root.findall("m:dependencies/m:dependency", nsmap))
    variable_pattern = re.compile(r'\$\{([^}]*)\}')
    logging.debug(
        "Found {1} non-managed dependencies in pom for {0.group_id} {0.artifact_id} {0.version}".format(pom_info, len(
            dependencies_el_list)))
    logging.debug(
        "Before adding found dependencies, # dependencies: {1} for pom for for {0.group_id} {0.artifact_id} {0.version}".format(
            pom_info, len(pom_info.dependencies)))
    for dep_el in dependencies_el_list:
        _el = dep_el.find("m:version", nsmap)
        version = "unspecified" if _el is None else _el.text
        grps = variable_pattern.match(version)
        if grps:
            prop_name = grps.group(1)
            _el = root.find("m:properties/m:{}".format(prop_name), nsmap)
            version = version if _el is None else _el.text
        group_id = dep_el.find("m:groupId", nsmap).text
        artId = dep_el.find("m:artifactId", nsmap).text
        dep_info = DependencyInformation()
        dep_info.group_id = group_id
        dep_info.version = version
        dep_info.artifact_id = artId
        pom_info.dependencies["{}/{}".format(group_id, artId)] = dep_info
    logging.debug("added {1} dependencies for pom for for {0.group_id} {0.artifact_id} {0.version}".format(pom_info,
                                                                                                           len(
                                                                                                               pom_info.dependencies)))
    # Modules (sub-projects)
    modules_el = root.findall("*/m:modules/m:module", nsmap)
    if not modules_el:
        modules_el = root.findall("m:modules/m:module", nsmap)
    for mod_el in modules_el:
        pom_info.modules[mod_el.text] = None

    logging.debug(
        "Finished loading {0} which contains groupId {1.group_id}, artifactId {1.artifact_id}, and version {1.version}, with {2} modules, and {3} managed dependencies, and {4} dependencies, and {5} variables\n".format(
            pom_path if pom_path else pom_url, pom_info, len(pom_info.modules), len(pom_info.managed_dependencies),
            len(pom_info.dependencies), len(pom_info.properties)))
    return pom_info


def validate_pom_dependencies(pom_info):
    is_snapshot = pom_info.is_snapshot()
    version_desc = "snapshot" if is_snapshot else pom_info.version if pom_info.version in ["unknown",
                                                                                           "unspecified"] else "release"
    logging.info("POM {0.name}, {1}, is a {2} version: {0.version}".format(pom_info,
                                                                           pom_info.path if pom_info.path else pom_info.url,
                                                                           version_desc))
    snapshot_deps = [v for v in pom_info.dependencies.values() if "SNAPSHOT" in v.version.upper()]
    if len(snapshot_deps) > 0:
        if not is_snapshot:
            logging.warn(
                "WARNING: a released version, {0.version}, of {0.group_id} {0.artifact_id} contains {1} SNAPSHOT dependencies!".format(
                    pom_info, len(snapshot_deps)))
        logging.info("The following {} dependencies are SNAPSHOT versions:".format(len(snapshot_deps)))
        for dep_info in snapshot_deps:
            logging.info("    {0.group_id}/{o.artifact_id} version: {0.version}".format(dep_info))


def get_pom_key(pom_info=None, group_id=None, artifact_id=None, version=None):
    if not pom_info:
        pom_info = BasicArtifactInformation(group_id, artifact_id, version)

    return "groupId:{0.group_id};artifactId:{0.artifact_id};version:{0.version};".format(pom_info)


def resolve_pom_variables(poms_info):
    logging.debug("Starting resolve_pom_variables(poms_info)\n")
    # Need to go through all poms to see if there are any pom variable substituions that need to be performed
    variable_pattern = re.compile(r'\$\{([^}]*)\}')
    more_poms = {}
    for (pom_key, pom_info) in poms_info.items():
        if pom_info:
            parent_info = pom_info.parent
            if parent_info:
                parent_pom_infos = find_pom_info(poms_info, group_id=parent_info.group_id,
                                                 artifact_id=parent_info.artifact_id, version=parent_info.version)
                if not parent_pom_infos:
                    parent_pom_infos = find_pom_info(more_poms, group_id=parent_info.group_id,
                                                     artifact_id=parent_info.artifact_id, version=parent_info.version)

                parent_pom_info = None
                if len(parent_pom_infos) > 1:
                    logging.warn(
                        "Found multiple parent poms with groupId {0.group_id}, artifactId {0.artifact_id} and version {0.version} for pom groupId {1.group_id}, artifactId {1.artifact_id} and version {1.version}. Using the first one ".format(
                            parent_info, pom_info))
                    parent_pom_info = parent_pom_infos[0]
                elif len(parent_pom_infos) == 1:
                    parent_pom_info = parent_pom_infos[0]
                else:
                    # Try to get remote version from Nexus
                    parent_pom_info = get_remote_artifact_pom(group_id=parent_info.group_id,
                                                              artifact_id=parent_info.artifact_id,
                                                              version=parent_info.version)
                    if parent_pom_info:
                        parent_key = get_pom_key(parent_pom_info)
                        more_poms[parent_key] = parent_pom_info
                        logging.debug(
                            "Found remote parent pom with groupId {0.group_id}, artifactId {0.artifact_id} and version {0.version} for pom groupId {1.group_id}, artifactId {1.artifact_id} and version {1.version} ".format(
                                parent_info, pom_info))
                    else:
                        logging.debug(
                            "Could not find parent pom with groupId {0.group_id}, artifactId {0.artifact_id} and version {0.version} for pom groupId {1.group_id}, artifactId {1.artifact_id} and version {1.version} ".format(
                                parent_info, pom_info))

            if pom_info.group_id == "unspecified" and parent_pom_info:
                logging.debug(
                    "Setting groupId to {} from the parent pom for the pom with groupId {}, artifactId {} and version {}".format(
                        parent_pom_info.group_id, pom_info.group_id, pom_info.artifact_id, pom_info.version))
                pom_info.group_id = parent_pom_info.group_id
            if pom_info.version == "unspecified" and parent_pom_info:
                logging.debug(
                    "Setting version to {} from the parent pom for the pom with groupId {}, artifactId {} and version {}".format(
                        parent_pom_info.version, pom_info.group_id, pom_info.artifact_id, pom_info.version))
                pom_info.version = parent_pom_info.version
            elif pom_info.version.startswith("${"):
                grps = variable_pattern.match(pom_info.version);
                if grps:
                    prop_name = grps.group(1)
                    v = parent_pom_info.properties.get(prop_name)
                    if v:
                        logging.debug(
                            "Setting version to '{}' for the pom with groupId {}, artifactId {} and version {}".format(
                                v, pom_info.group_id, pom_info.artifact_id, pom_info.version))
                        pom_info.version = v
                    else:
                        logging.debug(
                            "Could not get property {} for the version for the pom with groupId {}, artifactId {} and version {}".format(
                                prop_name, pom_info.group_id, pom_info.artifact_id, pom_info.version))
                else:
                    logging.debug(
                        "Could not parse out a property name from {} for the version for the pom with groupId {}, artifactId {} and version {}".format(
                            pom_info.version, pom_info.group_id, pom_info.artifact_id, pom_info.version))
            new_key = get_pom_key(pom_info)
            if new_key != pom_key:
                logging.debug(
                    "Changing the key from '{}' to '{}' for the pom with groupId {}, artifactId {} and version {}".format(
                        pom_key, new_key, pom_info.group_id, pom_info.artifact_id, pom_info.version))
                del poms_info[pom_key]
                poms_info[new_key] = pom_info
            if pom_info.name.find("${") >= 0:
                for m in re.finditer(variable_pattern, pom_info.name):
                    prop_name = m.group(1)
                    if prop_name.startswith("project."):
                        v = pom_info.properties.get(prop_name[8:])
                    else:
                        v = parent_pom_info.properties.get(prop_name)
                    if v:
                        logging.debug(
                            "Setting name to '{}' for the pom with groupId {}, artifactId {} and version {}".format(v,
                                                                                                                    pom_info.group_id,
                                                                                                                    pom_info.artifact_id,
                                                                                                                    pom_info.version))
                        pom_info.name = pom_info.name.replace("${{{}}}".format(prop_name), v)
                    else:
                        logging.debug(
                            "Could not get property {} for the name for the pom with groupId {}, artifactId {} and version {}".format(
                                prop_name, pom_info.group_id, pom_info.artifact_id, pom_info.version))
                else:
                    logging.debug(
                        "Could not parse out a property name from {} for the name for the pom with groupId {}, artifactId {} and version {}".format(
                            pom_info.name, pom_info.group_id, pom_info.artifact_id, pom_info.version))
            for dependencies in [pom_info.dependencies, pom_info.managed_dependencies]:
                if dependencies:
                    for (dep_key, dep) in dependencies.items():
                        for k in ["group_id", "artifact_id", "version"]:
                            val = getattr(dep, k)
                            if val.startswith("${"):
                                grps = variable_pattern.match(val);
                                if grps:
                                    prop_name = grps.group(1)
                                    if prop_name.startswith("project."):
                                        v = getattr(pom_info, k)
                                    else:
                                        v = parent_pom_info.properties.get(prop_name)
                                    if v:
                                        logging.debug(
                                            "Setting {} to '{}' for the dependency with groupId {}, artifactId {} and version {}".format(
                                                k, v, dep.group_id, dep.artifact_id, dep.version))
                                        setattr(dep, k, v)
                                    else:
                                        logging.debug(
                                            "Could not get property {} for the {} for the dependency with groupId {}, artifactId {} and version {}".format(
                                                prop_name, k, dep.group_id, dep.artifact_id, dep.version))
                                else:
                                    logging.debug(
                                        "Could not parse out a property name from {} for the {} for the dependency with groupId {}, artifactId {} and version {}".format(
                                            dep.version, k, dep.group_id, dep.artifact_id, dep.version))
                        new_key = "{}/{}".format(dep.group_id, dep.artifact_id)
                        if new_key != dep_key:
                            logging.debug(
                                "Changing the dependency key from '{}' to '{}' for the dependecy with groupId {}, artifactId {} and version {}".format(
                                    dep_key, new_key, dep.group_id, dep.artifact_id, dep.version))
                            del dependencies[dep_key]
                            dependencies[new_key] = dep
            if pom_info.modules:
                logging.debug("There are {} modules for pom groupId {}, artifactId {} and version {} ".format(
                    len(pom_info.modules), pom_info.group_id, pom_info.artifact_id, pom_info.version))
                for mod in pom_info.modules.keys():
                    if pom_info.modules[mod] is None:
                        mod_pom_infos = find_pom_info(poms_info, group_id=pom_info.group_id, artifact_id=mod,
                                                      version=pom_info.version)
                        mod_pom_info = None
                        if len(mod_pom_infos) > 1:
                            logging.warn(
                                "Found multiple module poms with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {}. Using the first one ".format(
                                    pom_info.group_id, mod, pom_info.version, pom_info.group_id, pom_info.artifact_id,
                                    pom_info.version))
                            pom_info.modules[mod] = mod_pom_infos[0]
                        elif len(mod_pom_infos) == 1:
                            pom_info.modules[mod] = mod_pom_infos[0]
                        else:
                            logging.debug(
                                "Could not find module pom with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {} ".format(
                                    pom_info.group_id, mod, pom_info.version, pom_info.group_id, pom_info.artifact_id,
                                    pom_info.version))
                else:
                    logging.debug(
                        "No modules for the pom pom groupId {}, artifactId {} and version {} ".format(pom_info.group_id,
                                                                                                      pom_info.artifact_id,
                                                                                                      pom_info.version))

        else:
            logging.warn("None pom_info for key {}".format(pom_key))
    # Cannot add new entrie to a dict while iterating over it, so adding them now that for loop is completed
    poms_info.update(more_poms)
    logging.debug("Finsihed resolve_pom_variables(poms_info)\n")
    return poms_info


def resolve_dependencies(poms_info, more_poms, pom_info, dep_key, dep, deps):
    dep_pom_infos = find_pom_info(poms_info, group_id=dep.group_id, artifact_id=dep.artifact_id, version=dep.version)
    if not dep_pom_infos:
        dep_pom_infos = find_pom_info(more_poms, group_id=dep.group_id, artifact_id=dep.artifact_id,
                                      version=dep.version)

    logging.debug("dependencies key: '{}'    -01- dependencies size: {}".format(dep_key, len(deps)))
    dep_pom_info = None
    if len(dep_pom_infos) > 1:
        logging.warn(
            "Found multiple poms for dependency with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {}. Using the first one ".format(
                dep.group_id, dep.artifact_id, dep.version, pom_info.group_id, pom_info.artifact_id, pom_info.version))
        dep_pom_info = dep_pom_infos[0]
    elif len(dep_pom_infos) == 1:
        logging.debug("dependencies key: '{}'    -02- dependencies size: {}".format(dep_key, len(deps)))
        dep_pom_info = dep_pom_infos[0]
    elif dep.is_locally_managed():
        # Try to get remote version from Nexus
        logging.debug("dependencies key: '{}'    -03A- dependencies size: {}".format(dep_key, len(deps)))
        dep_pom_info = get_remote_artifact_pom(group_id=dep.group_id, artifact_id=dep.artifact_id, version=dep.version)
        if dep_pom_info:
            logging.debug("dependencies key: '{}'    -03B- dependencies size: {}".format(dep_key, len(deps)))
            new_dep_key = get_pom_key(dep_pom_info)
            more_poms[new_dep_key] = dep_pom_info
            logging.debug(
                "Found remote pom for dependency with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {} ".format(
                    dep.group_id, dep.artifact_id, dep.version, pom_info.group_id, pom_info.artifact_id,
                    pom_info.version))
        else:
            logging.debug(
                "Could not find pom for dependency with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {} ".format(
                    dep.group_id, dep.artifact_id, dep.version, pom_info.group_id, pom_info.artifact_id,
                    pom_info.version))
    else:
        logging.debug(
            "Could not find pom for dependency with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {} ".format(
                dep.group_id, dep.artifact_id, dep.version, pom_info.group_id, pom_info.artifact_id, pom_info.version))
    if dep_pom_info:
        dep.pom_info = dep_pom_info

    logging.debug("dependencies key: '{}'    -04- dependencies size: {}".format(dep_key, len(deps)))


def resolve_missing_items(poms_info):
    logging.debug("Starting resolve_missing_items(poms_info)\n")
    # Need to go through all poms to see if there are any pom variable substituions that need to be performed
    variable_pattern = re.compile(r'\$\{([^}]*)\}')
    more_poms = {}
    for pom_key in poms_info.keys():
        pom_info = poms_info[pom_key]
        if pom_info:
            if pom_info.dependencies:
                logging.debug("Starting with new pom_info.dependencies of size: {}".format(len(pom_info.dependencies)))
                for dep_key in pom_info.dependencies.keys():
                    logging.debug("pom_info.dependencies key: '{}'    -00- dependencies size: {}".format(dep_key, len(
                        pom_info.dependencies)))
                    dep = pom_info.dependencies[dep_key]
                    if dep.version != "unknown" and dep.version != "unspecified":
                        resolve_dependencies(poms_info, more_poms, pom_info, dep_key, dep, pom_info.dependencies)
            else:
                logging.debug("pom_info.dependencies is empty!")
            if pom_info.managed_dependencies:
                logging.debug("Starting with new pom_info.managed_dependencies of size: {}".format(
                    len(pom_info.managed_dependencies)))
                for dep_key in pom_info.managed_dependencies.keys():
                    logging.debug(
                        "pom_info.managed_dependencies key: '{}'    -00- dependencies size: {}".format(dep_key, len(
                            pom_info.managed_dependencies)))
                    dep = pom_info.managed_dependencies[dep_key]
                    if dep.version != "unknown" and dep.version != "unspecified":
                        resolve_dependencies(poms_info, more_poms, pom_info, dep_key, dep,
                                             pom_info.managed_dependencies)
            else:
                logging.debug("pom_info.managed_dependencies is empty!")

            for (mod_key, mod_pom) in pom_info.modules.items():
                if not mod_pom:
                    mod_pom_infos = find_pom_info(poms_info, group_id=pom_info.group_id, artifact_id=mod_key,
                                                  version=pom_info.version)
                    if not mod_pom_infos:
                        mod_pom_infos = find_pom_info(more_poms, group_id=pom_info.group_id, artifact_id=mod_key,
                                                      version=pom_info.version)
                    if len(mod_pom_infos) > 1:
                        logging.warn(
                            "Found multiple poms for module with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {}. Using the first one ".format(
                                pom_info.group_id, mod_key, pom_info.version, pom_info.group_id, pom_info.artifact_id,
                                pom_info.version))
                        pom_info.modules[mod_key] = mod_pom_infos[0]
                    elif len(mod_pom_infos) == 1:
                        pom_info.modules[mod_key] = mod_pom_infos[0]
                    else:
                        mod_pom_info = get_remote_artifact_pom(group_id=pom_info.group_id, artifact_id=mod_key,
                                                               version=pom_info.version)
                        if mod_pom_info:
                            mod_pom_info_key = get_pom_key(mod_pom_info)
                            more_poms[mod_pom_info_key] = mod_pom_info
                            pom_info.modules[mod_key] = mod_pom_info
                        else:
                            logging.debug(
                                "Could not find pom for module with groupId {}, artifactId {} and version {} for pom groupId {}, artifactId {} and version {} ".format(
                                    pom_info.group_id, mod_key, pom_info.version, pom_info.group_id,
                                    pom_info.artifact_id, pom_info.version))
        else:
            logging.warn("None pom_info for key {}".format(pom_key))
    # Cannot add new entries to a dict while iterating over it, so adding them now that for loop is completed
    if more_poms:
        poms_info.update(more_poms)
        logging.debug("Found {} more poms, so calling resolve_missing_items(poms_info) again just in case!".format(
            len(more_poms)))
        resolve_missing_items(poms_info)
    logging.debug("Finsihed resolve_missing_items(poms_info)\n")
    return poms_info


def load_pom_files_from_workspace(root_path, validate=None):
    logging.debug("Start of load_pom_files_from_workspace('{}')\n".format(root_path))
    poms_info = {}
    pom_files = sorted(
        itertools.chain(root_path.glob("pom.xml"), root_path.glob("*/pom.xml"), root_path.glob("*/*/pom.xml")))
    for pom_path in pom_files:
        pom_info = load_pom_file(pom_path)
        pom_key = get_pom_key(pom_info)
        if pom_key not in poms_info:
            if validate:
                validate_pom_dependencies(pom_info)
            poms_info[pom_key] = pom_info
            logging.debug('Loaded pom with the key "{0}" from {1}'.format(pom_key, pom_info.path))
        else:
            logging.warn(
                'There is already a pom with the key "{0}". Not adding the one for {1}'.format(pom_key, pom_info.path))

    poms_info = resolve_missing_items(poms_info)

    resolve_pom_variables(poms_info)
    resolve_pom_variables(poms_info)

    logging.debug("Finished load_pom_files_from_workspace('{}')\n".format(root_path))
    return poms_info


def parse_artifact_list_page(page_source, group_id, artifact_id):
    artifact_list_dict = {}
    soup = BeautifulSoup(page_source, features="lxml")
    rows = soup.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) == 4:
            anch = cols[0].find("a")
            if anch and cols[2].text.strip() == "":
                version = anch.text[0:-1]
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


def parse_artifact_version_page(page_source, group_id, artifact_id, version):
    artifact_list_dict = {}
    pom_cols = None
    soup = BeautifulSoup(page_source, features="lxml")
    rows = soup.find_all("tr")
    logging.debug("Got {} rows to check for {} {} {}".format(len(rows), group_id, artifact_id, version))
    for row in rows:
        cols = row.find_all("td")
        if len(cols) == 4:
            anch = cols[0].find("a")
            if anch:
                file_name = anch.text
                extension = file_name[-4:].lower()
                if extension in [".ear", ".jar", ".war"] and "-sources.jar" not in file_name:
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
                elif extension == ".pom":
                    pom_cols = cols
    if not artifact_list_dict and pom_cols:
        anch = pom_cols[0].find("a")
        if anch:
            file_name = anch.text
            url = anch.attrs["href"]
            timestamp_str = pom_cols[1].text
            # Convert timestamp string to DateTime - example: 'Mon Apr 06 10:30:10 EDT 2020'
            timestamp = datetime.datetime.strptime(timestamp_str, "%a %b %d %H:%M:%S %Z %Y")
            key = get_pom_key(group_id=group_id, artifact_id=artifact_id, version=version)
            artifact_list_dict[key] = {"url": url,
                                       "version": version,
                                       "groupId": group_id,
                                       "artifactId": artifact_id,
                                       "filename": file_name,
                                       "timestamp": timestamp}
            logging.debug(
                "Got pom file version for {} {} {}".format(len(artifact_list_dict), group_id, artifact_id, version))
    logging.debug("Got {} version(s) for {} {} {}".format(len(artifact_list_dict), group_id, artifact_id, version))
    return artifact_list_dict


def get_artifact_version_from_version_page(url, group_id, artifact_id, version, headers=None):
    if not headers:
        headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        artifact_version_page = requests.get(url, headers=headers)
    except Exception as ex:
        logging.warn(
            "Could not get artifact_version url {} for group_id {} and artifact_id {}. Exception {}".format(url,
                                                                                                            group_id,
                                                                                                            artifact_id,
                                                                                                            ex.getMessage()))
        return None
    if artifact_version_page.status_code != requests.codes.ok:
        logging.warn(
            "Could not get artifact_version url {} for group_id {} and artifact_id {}. status_code {}".format(url,
                                                                                                              group_id,
                                                                                                              artifact_id,
                                                                                                              artifact_version_page.status_code))
        return None
    return parse_artifact_version_page(artifact_version_page.text, group_id, artifact_id, version)


def get_remote_artifact_pom(pom_info=None, group_id=None, artifact_id=None, version=None):
    if pom_info:
        version = pom_info.version
        artifact_id = pom_info.artifact_id
        group_id = pom_info.group_id
    if version in ["unknown", "unspecified"]:
        return None

    group_id_path = group_id.replace(".", "/")
    if is_pom_version_snapshot(version):
        base_url = environment.NEXUS_INFO["snapshots_root_url"]
        # Need to get the Nexus version page and parse it to get the latest pom from that
        # https://asbscr.ic.gc.ca/maven-proxy/content/groups/all-snapshots/ca/gc/ic/cipo/ec/id/CIPO-ec-id-filing/4.2.22-SNAPSHOT/
        version_page_url = "{0}/{1}/{2}/{3}/".format(base_url, group_id_path, artifact_id, version)
        artifact_versions_dict = get_artifact_version_from_version_page(version_page_url, group_id, artifact_id,
                                                                        version)
        if artifact_versions_dict:
            key = get_pom_key(group_id=group_id, artifact_id=artifact_id, version=version)
            if artifact_versions_dict[key]["url"].endswith(".pom"):
                url = artifact_versions_dict[key]["url"]
            else:
                url = artifact_versions_dict[key]["url"][:-4] + ".pom"
        else:
            logging.warn("cannot find version page for {} {} {} at url {}".format(group_id, artifact_id, version,
                                                                                  version_page_url))
            return None
    else:
        base_url = environment.NEXUS_INFO["released_root_url"]
        url = "{0}/{1}/{2}/{3}/{2}-{3}.pom".format(base_url, group_id_path, artifact_id, version)
    logging.debug("For {} {} {}, created pom url: {}".format(group_id, artifact_id, version, url))
    return load_pom_file(pom_url=url)


def is_pom_version_snapshot(version_str):
    return "SNAPSHOT" in version_str.upper()


def generate_pom_partial_key(group_id=None, artifact_id=None, version=None):
    desired_key = "groupId:{0};".format(group_id) if group_id and group_id != "unspecified" else ""
    desired_key = "{0}artifactId:{1};".format(desired_key, artifact_id) if artifact_id else desired_key
    desired_key = "{0}version:{1};".format(desired_key,
                                           version) if version and version != "unspecified" else desired_key
    return desired_key


def find_pom_info(poms_info, group_id=None, artifact_id=None, version=None):
    desired_key = generate_pom_partial_key(group_id, artifact_id, version)

    return [pom_info for (k, pom_info) in poms_info.items() if desired_key in k]


def test_load_pom_files_from_workspace():
    log_file_path = common_utils.get_log_file_path("~/reports", "test_load_pom_files_from_workspace")
    common_utils.setup_logger_to_console_file(log_file_path, logging.DEBUG)
    root_path = pathlib.Path(environment.WORKSPACE_ROOT_ID)
    validate = False

    poms_info = load_pom_files_from_workspace(root_path, validate)
    logging.info(pprint.pformat(poms_info))

    return log_file_path


def test_get_remote_artifact_pom():
    log_file_path = common_utils.get_log_file_path("~/reports", "testing_get_remote_artifact_pom")
    common_utils.setup_logger_to_console_file(log_file_path, logging.DEBUG)
    group_id = "ca.gc.ic.cipo"
    artifact_id = "cipo-parent"
    version = "2.0.11"
    pom_info = get_remote_artifact_pom(group_id=group_id, artifact_id=artifact_id, version=version)
    print("==============================")
    pprint.pprint(pom_info)
    print("==============================")


if __name__ == "__main__":
    test_load_pom_files_from_workspace()
