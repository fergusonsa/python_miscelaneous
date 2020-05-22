import argparse
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
import maven_utils


def get_git_info(path):
    if not path:
        return {"repo_url": "Not git repo",
                "branch": "Not git repo"}
    try:
        repo = git.Repo(path, search_parent_directories=True)
        return {"repo_url": repo.remotes.origin.url,
                "branch": repo.active_branch.name}
    except:
        logging.warning("**** path {0} was found to not be a git repo. ********".format(path))
        return {"repo_url": "Not git repo",
                "branch": "Not git repo"}


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
            logging.warning(
                "Could not get artifact_url {} for group_id {} and artifact_id {}. Exception {}".format(artifact_url,
                                                                                                        group_id,
                                                                                                        artifact_id,
                                                                                                        ex.getMessage()))
            continue
        if artifact_list_page.status_code != requests.codes.ok:
            logging.warning(
                "Could not get artifact_url {} for group_id {} and artifact_id {}. status_code {}".format(artifact_url,
                                                                                                          group_id,
                                                                                                          artifact_id,
                                                                                                          artifact_list_page.status_code))
            continue
        logging.debug("Got artifact list page from url: {}".format(artifact_url))
        artifact_list_dict = maven_utils.parse_artifact_list_page(artifact_list_page.text, group_id, artifact_id)
        logging.debug("Got {} version pages to parse for {} versions".format(len(artifact_list_dict), url_desc))
        for artifact_item in sorted(artifact_list_dict.values(), key=lambda k: k["timestamp"], reverse=True):
            artifact_versions_dict = maven_utils.get_artifact_version_from_version_page(artifact_item["url"], group_id,
                                                                                        artifact_id,
                                                                                        artifact_item["version"],
                                                                                        headers)
            if artifact_versions_dict:
                logging.debug(
                    "For {} {}, Got artifact version page from url: {}, with dict {}".format(group_id, artifact_id,
                                                                                             artifact_item["url"],
                                                                                             artifact_versions_dict))

                available_versions[url_desc].update(artifact_versions_dict)
    logging.debug("Found {0} snapshot versions and {1} released versions in the pages for {1} {2}".format(
        len(available_versions.get("snapshots_root_url", [])), len(available_versions.get("released_root_url", [])),
        group_id, artifact_id))
    return available_versions


def get_latest_version_key(pom_info, is_snapshot):
    if not pom_info.available_versions:
        pom_info.available_versions = find_available_versions_of_artifact(pom_info.group_id, pom_info.artifact_id)
    if pom_info.available_versions:
        versions = pom_info.available_versions.get(
            "snapshots_root_url") if is_snapshot else pom_info.available_versions.get("released_root_url")
        if versions:
            return max(versions, key=lambda v: versions[v]["timestamp"])
        else:
            logging.debug(
                "There are no available {1} versions for the pom with {0.group_id} {0.artifact_id} and version {0.version}".format(
                    pom_info, "snapshot" if is_snapshot else "release"))
            return None
    else:
        logging.debug(
            "Could not get available_versions for the pom with {0.group_id} {0.artifact_id} and version {0.version}".format(
                pom_info))
        return None


def test_find_available_versions_of_artifact():
    log_file_path = common_utils.get_log_file_path("~/reports", "testing_find_available_versions_of_artifact")
    common_utils.setup_logger_to_console_file(log_file_path, log_level)
    group_id = "ca.gc.ic.cipo.ec.id"
    artifact_id = "CIPO-ec-id-core"
    artifact_versions_dict = find_available_versions_of_artifact(group_id, artifact_id)
    pprint.pprint(artifact_versions_dict)

    print("==============================")
    print(max(set(artifact_versions_dict["snapshots_root_url"].keys())))
    print("==============================")
    pprint.pprint(artifact_versions_dict["snapshots_root_url"].keys())
    print("==============================")
    pprint.pprint(
        artifact_versions_dict["snapshots_root_url"][max(set(artifact_versions_dict["snapshots_root_url"].keys()))])


def document_workspace(root_path):
    root_path = pathlib.Path(root_path)

    poms_info = maven_utils.load_pom_files_from_workspace(root_path, True)

    logging.info("Displaying the pom dependencies of all the projects in workspace {}\n".format(root_path))

    logging.info('Display of pom dependencies:')
    for key in sorted(poms_info.keys()):
        v = poms_info[key]
        if not v.path:
            continue
        logging.info('GroupId: {0.group_id:<35}  ArtifactId: {0.artifact_id:<50}  Version: {0.version}}'.format(v))
        logging.info('Path: {0.path}'.format(v))
        logging.info('Name: {0.name}'.format(v))
        repo_info = get_git_info(v.path)
        logging.info("Git repo: {repo_url}".format(**repo_info))
        logging.info("Git branch: {branch}".format(**repo_info))

        if v.modules:
            logging.info('Modules:')
            for mod_key in sorted(v.modules.keys()):
                mod_info = v.modules[mod_key]
                if mod_info:
                    pom_key = "groupId:{0.group_id};artifactId:{0.artifact_id};version:{0.version}}".format(mod_info)
                    logging.info(
                        ' -- GroupId: {0.group_id:<35}  ArtifactId: {0.artifact_id:<50}  Version: {0.version}}'.format(
                            mod_info))
                    if pom_key in poms_info and poms_info[pom_key].path:
                        logging.info('    LOCAL ENVIRONMENT COPY')
                else:
                    logging.warning(
                        "Empty Modules mod_info for key '{}' for pom groupId: {} artifactId: {} version: {}".format(
                            mod_key, v.group_id, v.artifact_id, v.version))
        if v['dependenciesManagement']:
            logging.info('Managed Dependencies:')
            for dep_key in sorted(v['dependenciesManagement'].keys()):
                dep_info = v['dependenciesManagement'][dep_key]
                pom_key = "groupId:{0.group_id};artifactId:{0.artifact_id};version:{0.version}}".format(dep_info)
                logging.info(
                    ' -- GroupId: {0.group_id:<35}  ArtifactId: {0.artifact_id:<50}  Version: {0.version}}'.format(
                        dep_info))
                if pom_key in poms_info and poms_info[pom_key].path:
                    logging.info('    LOCAL ENVIRONMENT COPY')
        if v.dependencies:
            logging.info('Dependencies:')
            for dep_key in sorted(v.dependencies.keys()):
                dep_info = v.dependencies[dep_key]
                pom_key = "groupId:{0.group_id};artifactId:{0.artifact_id};version:{0.version}".format(dep_info)
                logging.info(
                    ' -- GroupId: {0.group_id:<35}  ArtifactId: {0.artifact_id:<50}  Version: {0.version}'.format(
                        dep_info))
                if pom_key in poms_info and poms_info[pom_key].path:
                    logging.info('    LOCAL ENVIRONMENT COPY')
        logging.info(" ")


def display_dependencies(poms_info, dependency_poms_infos):
    deps_to_check = []
    for dep_info in dependency_poms_infos:
        dep_pom_info_list = maven_utils.find_pom_info(poms_info, group_id=dep_info.group_id,
                                                      artifact_id=dep_info.artifact_id)
        if not dep_pom_info_list:
            logging.info(
                "Dependency not present:                GroupId: {0.group_id:<35}  ArtifactId: {0.artifact_id:<50}  Version: {0.version}}".format(
                    dep_info))
        elif len(dep_pom_info_list) > 1:
            logging.info(
                "Multiple copies of Dependency present: GroupId: {0.group_id:<35}  ArtifactId: {0.artifact_id:<50}  Version: {0.version}}".format(
                    dep_info))
            for pom_info in dep_pom_info_list:
                logging.info(
                    '\tGroupId: {0.group_id:<35}  ArtifactId: {0.artifact_id:<50}  Version: {0.version}}'.format(
                        pom_info))
                logging.info('\t\tPath: {0.path}'.format(pom_info))
                logging.info('\t\tName: {0.name}'.format(pom_info))
        elif dep_info.version == dep_pom_info_list[0].version:
            logging.info(
                "Proper dependency version present:     GroupId: {0.group_id:<35}  ArtifactId: {0.artifact_id:<50}  Version: {0.version}}".format(
                    dep_pom_info_list[0]))
            logging.info("\t\tPath: {0.path}".format(dep_pom_info_list[0]))
            logging.info("\t\tName: {0.name}".format(dep_pom_info_list[0]))
            if dep_pom_info_list[0].path:
                repo_info = get_git_info(dep_pom_info_list[0].path)
                logging.info("\t\tGit repo: {repo_url}".format(**repo_info))
                logging.info("\t\tGit branch: {branch}".format(**repo_info))

            deps_to_check.append(dep_pom_info_list[0])
        else:
            logging.info(
                "Incorrect dependency version present:  GroupId: {0.group_id:<35}  ArtifactId: {0.artifact_id:<50}  Version: {0.version}}".format(
                    dep_pom_info_list[0]))
            logging.info("\t\tPath: {0.path}".format(dep_pom_info_list[0]))
            logging.info("\t\tName: {0.name}".format(dep_pom_info_list[0]))
            if dep_pom_info_list[0].path:
                repo_info = get_git_info(dep_pom_info_list[0].path)
                logging.info("\t\tGit repo: {repo_url}".format(**repo_info))
                logging.info("\t\tGit branch: {branch}".format(**repo_info))
            logging.info("\tRequired version: {}".format(dep_info.version))
    for dep_pom_info in deps_to_check:
        logging.info(
            'Using dependent project GroupId: {0.group_id:<35}\tArtifactId: {0.artifact_id:<50}\tVersion: {0.version}}'.format(
                dep_pom_info))
        logging.info('\t\tPath: {0.path}'.format(dep_pom_info))
        logging.info('\t\tName: {0.name}'.format(dep_pom_info))
        if dep_pom_info.path:
            repo_info = get_git_info(dep_pom_info.path)
            logging.info("\t\tGit repo: {repo_url}".format(**repo_info))
            logging.info("\t\tGit branch: {branch}\n".format(**repo_info))
        logging.info('Dependencies:')

        display_dependencies(poms_info, dep_pom_info.dependencies.values())


def display_modules(poms_info, parent_pom_info):
    modules_poms_dict = parent_pom_info.modules
    if modules_poms_dict:
        logging.info('Modules:')
        for mod_key in sorted(modules_poms_dict.keys()):
            mod_info = modules_poms_dict[mod_key]
            if not mod_info:
                logging.info(
                    "Module not present:                GroupId: {:<35}  ArtifactId: {:<50}  Version: {}".format(
                        parent_pom_info.group_id, mod_key, parent_pom_info.version))
            else:
                logging.info(
                    "Module information:     GroupId: {0.group_id:<35}  ArtifactId: {0.artifact_id:<50}  Version: {0.version}}".format(
                        mod_info))
                logging.info("\t\tPath: {0.path}".format(mod_info))
                logging.info("\t\tName: {0.name}".format(mod_info))
                if mod_info.path:
                    repo_info = get_git_info(mod_info.path)
                    logging.info("\t\tGit repo: {repo_url}".format(**repo_info))
                    logging.info("\t\tGit branch: {branch}".format(**repo_info))

                display_dependencies(poms_info, mod_info.dependencies.values())


def check_poms_against_parent(parent_project_name, workspace):
    root_path = pathlib.Path(workspace)

    logging.info(
        "Attempting to check the pom dependencies for {} pom artifact project in workspace {} against other projects in the same workspace\n".format(
            parent_project_name, workspace))

    poms_info = maven_utils.load_pom_files_from_workspace(root_path)
    # Find the parent project's pom info
    parent_pom_info_list = maven_utils.find_pom_info(poms_info, artifact_id=parent_project_name)
    if not parent_pom_info_list:
        logging.info(
            "Could not find parent project with artifactId of '{0}' in the workspace {1}.".format(parent_project_name,
                                                                                                  workspace))
        sys.exit(0)
    if len(parent_pom_info_list) > 1:
        logging.warning(
            "Found multiple parent projects with artifactId of '{0}' in the workspace {1}.".format(parent_project_name,
                                                                                                   workspace))
        for pom_info in parent_pom_info_list:
            logging.warning(
                '\tGroupId: {0.group_id:<35}\tArtifactId: {0.artifact_id:<50}\tVersion: {0.version}}'.format(pom_info))
            logging.warning('\t\tPath: {0.path}'.format(pom_info))
            logging.warning('\t\tName: {0.name}'.format(pom_info))
        logging.warning("Cannot perform analysis with multiple parent projects.")
        sys.exit(0)
    parent_pom_info = parent_pom_info_list[0]
    logging.info(
        'Using Parent project GroupId: {0.group_id:<35}\tArtifactId: {0.artifact_id:<50}\tVersion: {0.version}}'.format(
            parent_pom_info))
    logging.info('\t\tPath: {0.path}'.format(parent_pom_info))
    logging.info('\t\tName: {0.name}'.format(parent_pom_info))
    if parent_pom_info.path:
        repo_info = get_git_info(parent_pom_info.path)
        logging.info("\t\tGit repo: {repo_url}".format(**repo_info))
        logging.info("\t\tGit branch: {branch}\n".format(**repo_info))

    display_modules(poms_info, parent_pom_info)

    logging.info('Managed Dependencies:')
    display_dependencies(poms_info, parent_pom_info['dependenciesManagement'].values())
    logging.info('Dependencies:')
    display_dependencies(poms_info, parent_pom_info.dependencies.values())


def checkout_branch(parent_project_name, workspace, branch, reset):
    root_path = pathlib.Path(workspace)

    logging.info(
        "Attempting to check out Branch {} of the git repository for {} pom artifact in workspace {}, with reset flag {}\n".format(
            branch, parent_project_name, workspace, reset))

    poms_info = maven_utils.load_pom_files_from_workspace(root_path)
    # Find the parent project's pom info
    parent_pom_info_list = maven_utils.find_pom_info(poms_info, artifact_id=parent_project_name)
    if not parent_pom_info_list:
        logging.info(
            "Could not find parent project with artifactId of '{0}' in the workspace {1}.".format(parent_project_name,
                                                                                                  workspace))
        sys.exit(0)
    parent_pom_info = parent_pom_info_list[0]
    repo = None
    try:
        repo = git.Repo(parent_pom_info.path, search_parent_directories=True)
    except:
        logging.info("**** path {0} was found to not be a git repo. ********".format(parent_pom_info.path))
        repo = None
    # Make sure not already on the desired branch
    if repo.active_branch.name == branch:
        logging.info(
            "Already on the {} branch  for the project '{}' in the workspace {}.".format(branch, parent_project_name,
                                                                                         workspace))
        return

    # Check to see if the branch is validate
    all_branches = [e[2:] for e in repo.git.branch('-a').splitlines()]
    if not (branch in all_branches or "remotes/origin/{}".format(branch) in all_branches):
        logging.info(
            "{} is not a valid branch in the repo for the parent project with artifactId of '{}' in the workspace {}.".format(
                branch, parent_project_name, workspace))
        sys.exit(0)
    changes = repo.index.diff(None)
    if changes:
        if not reset:
            logging.info(
                "There are {} changed files that need to be dealt with before switching to the {} branch in the repo for the parent project with artifactId of '{}' in the workspace {}.".format(
                    len(changes), branch, parent_project_name, workspace))
            sys.exit(0)

        repo.git.checkout(branch, force=True)
    else:
        repo.git.checkout(branch)


def display_dependencies_tree(all_poms, pom_info, indent_prefix_str=None, displayed_modules_l=None, local_only=None,
                              show_max_versions=None):
    if not indent_prefix_str:
        indent_prefix_str = ""
    if not displayed_modules_l:
        displayed_modules_l = []
    if pom_info:
        displayed_modules_l.append(maven_utils.get_pom_key(pom_info))
        header_indent_prefix = "{}----".format(indent_prefix_str)
        logging.info("{}+ {:<35}  {:<50}  {}".format(header_indent_prefix, pom_info.group_id, pom_info.artifact_id,
                                                     pom_info.version))
        if (local_only and pom_info.path) or not local_only:
            indent_prefix = "{}    ".format(indent_prefix_str)
            mod_indent_prefix = "{}    |    |".format(indent_prefix_str)
            dep_indent_prefix = "{}         |".format(indent_prefix_str)
            path_or_url = pom_info.path if pom_info.path else pom_info.url
            logging.info("{}|         {}     {}".format(indent_prefix, pom_info.name, path_or_url))
            if pom_info.path:
                repo_info = get_git_info(pom_info.path)
                logging.info(
                    "{}|         Git branch: {}   {}".format(indent_prefix, repo_info["branch"], repo_info["repo_url"]))
            if show_max_versions and pom_info.available_versions:
                if pom_info.available_versions.get("snapshots_root_url"):
                    max_snap_version_key = get_latest_version_key(pom_info, is_snapshot=True)
                    max_snap_version = pom_info.available_versions["snapshots_root_url"][max_snap_version_key][
                        "version"]
                    max_snap_timestamp = pom_info.available_versions["snapshots_root_url"][max_snap_version_key][
                        "timestamp"]
                else:
                    max_snap_version_key = None
                    max_snap_version = None
                    max_snap_timestamp = None
                if pom_info.available_versions.get("relesased_root_url"):
                    max_release_version_key = get_latest_version_key(pom_info, is_snapshot=False)
                    max_release_version = pom_info.available_versions["relesased_root_url"][max_release_version_key][
                        "version"]
                    max_release_timestamp = pom_info.available_versions["relesased_root_url"][max_release_version_key][
                        "timetamp"]
                else:
                    max_release_version_key = None
                    max_release_version = None
                    max_release_timestamp = None

                logging.info(
                    "{}|         Latest snapshot version: {} with timestamp {} and key {}  Latest released version: {} with timestamp {} and key {}".format(
                        indent_prefix, max_snap_version, max_snap_timestamp, max_snap_version_key, max_release_version,
                        max_release_timestamp, max_release_version_key))
            modules_poms_dict = pom_info.modules
            if modules_poms_dict:
                logging.info("{}|----+ Modules:".format(indent_prefix))
                for mod_key in sorted(modules_poms_dict.keys()):
                    mod_info = modules_poms_dict[mod_key]
                    if mod_info:
                        full_key = maven_utils.get_pom_key(mod_info)
                        if full_key not in displayed_modules_l:
                            displayed_modules_l.append(full_key)
                            display_dependencies_tree(all_poms, mod_info, indent_prefix_str=mod_indent_prefix,
                                                      displayed_modules_l=displayed_modules_l, local_only=local_only,
                                                      show_max_versions=show_max_versions)
                        else:
                            logging.info(
                                "{}----- {:<35}  {:<50}  {}  ^^".format(mod_indent_prefix, pom_info.group_id, mod_key,
                                                                        pom_info.version))
                    else:
                        logging.info("{}----- {:<35}  {:<50}  {}".format(mod_indent_prefix, pom_info.group_id, mod_key,
                                                                         pom_info.version))
            dependency_poms_infos = pom_info.managed_dependencies
            if dependency_poms_infos:
                logging.info("{}|----+ Managed Dependencies:".format(indent_prefix))
                for dep_key in sorted(dependency_poms_infos.keys()):
                    dep_info = dependency_poms_infos[dep_key]
                    dep_pom_info_list = maven_utils.find_pom_info(all_poms, group_id=dep_info.group_id,
                                                                  artifact_id=dep_info.artifact_id,
                                                                  version=dep_info.version)
                    if not dep_pom_info_list:
                        logging.info("{}----- {:<35}  {:<50}  {} ??".format(mod_indent_prefix, dep_info.group_id,
                                                                            dep_info.artifact_id, dep_info.version))
                    elif dep_info.version == dep_pom_info_list[0].version:
                        full_key = maven_utils.get_pom_key(dep_info)
                        if full_key not in displayed_modules_l:
                            displayed_modules_l.append(full_key)
                            display_dependencies_tree(all_poms, dep_pom_info_list[0],
                                                      indent_prefix_str=mod_indent_prefix,
                                                      displayed_modules_l=displayed_modules_l, local_only=local_only,
                                                      show_max_versions=show_max_versions)
                        else:
                            logging.info("{}----- {:<35}  {:<50}  {}  ^^".format(mod_indent_prefix, dep_info.group_id,
                                                                                 dep_info.artifact_id,
                                                                                 dep_info.version))
                    elif dep_pom_info_list[0].path:
                        logging.info("{}----- {:<35}  {:<50}  {:<13} #{} Local version is {}".format(mod_indent_prefix,
                                                                                                     dep_info.group_id,
                                                                                                     dep_info.artifact_id,
                                                                                                     dep_info.version,
                                                                                                     len(
                                                                                                         dep_pom_info_list),
                                                                                                     dep_pom_info_list[
                                                                                                         0].version))
                    else:
                        logging.info("{}----- {:<35}  {:<50}  {} #{}".format(mod_indent_prefix, dep_info.group_id,
                                                                             dep_info.artifact_id, dep_info.version,
                                                                             len(dep_pom_info_list)))
            dependency_poms_infos = pom_info.dependencies
            if dependency_poms_infos:
                logging.info("{}-----+ Dependencies:".format(indent_prefix))
                for dep_key in sorted(dependency_poms_infos.keys()):
                    dep_info = dependency_poms_infos[dep_key]
                    dep_pom_info_list = maven_utils.find_pom_info(all_poms, group_id=dep_info.group_id,
                                                                  artifact_id=dep_info.artifact_id,
                                                                  version=dep_info.version)
                    if not dep_pom_info_list:
                        logging.info("{}----- {:<35}  {:<50}  {}".format(dep_indent_prefix, dep_info.group_id,
                                                                         dep_info.artifact_id, dep_info.version))
                    elif dep_info.version == dep_pom_info_list[0].version:
                        full_key = maven_utils.get_pom_key(dep_info)
                        if full_key not in displayed_modules_l:
                            displayed_modules_l.append(full_key)
                            display_dependencies_tree(all_poms, dep_pom_info_list[0],
                                                      indent_prefix_str=dep_indent_prefix,
                                                      displayed_modules_l=displayed_modules_l, local_only=local_only,
                                                      show_max_versions=show_max_versions)
                        else:
                            logging.info("{}----- {:<35}  {:<50}  {}  ^^".format(dep_indent_prefix, dep_info.group_id,
                                                                                 dep_info.artifact_id,
                                                                                 dep_info.version))
                    elif dep_pom_info_list[0].path:
                        logging.info("{}----- {:<35}  {:<50}  {:<13} #{} Local version is {}".format(dep_indent_prefix,
                                                                                                     dep_info.group_id,
                                                                                                     dep_info.artifact_id,
                                                                                                     dep_info.version,
                                                                                                     len(
                                                                                                         dep_pom_info_list),
                                                                                                     dep_pom_info_list[
                                                                                                         0].version))
                    else:
                        logging.info("{}----- {:<35}  {:<50}  {} #{}".format(dep_indent_prefix, dep_info.group_id,
                                                                             dep_info.artifact_id, dep_info.version,
                                                                             len(dep_pom_info_list)))


def check_for_latest_dependency_versions(parent_project_name, workspace):
    root_path = pathlib.Path(workspace)

    logging.info(
        "Attempting to check the pom dependencies for {} pom artifact project in workspace {} to see if there are more recent versions\n".format(
            parent_project_name, workspace))

    poms_info = maven_utils.load_pom_files_from_workspace(root_path)
    # Find the parent project's pom info
    parent_pom_info_list = maven_utils.find_pom_info(poms_info, artifact_id=parent_project_name)
    if not parent_pom_info_list:
        logging.info(
            "Could not find parent project with artifactId of '{0}' in the workspace {1}.".format(parent_project_name,
                                                                                                  workspace))
        sys.exit(0)
    if len(parent_pom_info_list) > 1:
        logging.warning(
            "Found multiple parent projects with artifactId of '{0}' in the workspace {1}.".format(parent_project_name,
                                                                                                   workspace))
        for pom_info in parent_pom_info_list:
            logging.warning(
                '\tGroupId: {0.group_id:<35}\tArtifactId: {0.artifact_id:<50}\tVersion: {0.version}}'.format(pom_info))
            logging.warning('\t\tPath: {0.path}'.format(pom_info))
            logging.warning('\t\tName: {0.name}'.format(pom_info))
        logging.warning("Cannot perform analysis with multiple parent projects.")
        sys.exit(0)
    parent_pom_info = parent_pom_info_list[0]
    parent_pom_info.available_versions = find_available_versions_of_artifact(parent_pom_info.group_id,
                                                                             parent_pom_info.artifact_id)

    for pom_info in parent_pom_info.modules.values():
        if pom_info:
            pom_info.available_versions = find_available_versions_of_artifact(pom_info.group_id, pom_info.artifact_id)

    for dep_info in parent_pom_info.dependencies.values():
        if not dep_info.pom_info and dep_info.is_locally_managed():
            dep_info.pom_info.available_versions = find_available_versions_of_artifact(dep_info.pom_info.group_id,
                                                                                       dep_info.pom_info.artifact_id)

    # 9:29 AM 2020-05-15    WORKING HERE          
    display_dependencies_tree(poms_info, parent_pom_info, show_max_versions=True)


def load_poms_for_artifact(group_id, artifact_id, version):
    all_poms = {}
    pom_info = maven_utils.get_remote_artifact_pom(group_id=group_id, artifact_id=artifact_id, version=version)
    key = maven_utils.get_pom_key(pom_info)
    all_poms[key] = pom_info

    all_poms = maven_utils.resolve_missing_items(all_poms)

    maven_utils.resolve_pom_variables(all_poms)
    maven_utils.resolve_pom_variables(all_poms)
    return all_poms, pom_info


def check_for_conflicting_dependency_versions(group_id, artifact_id, version):
    if not group_id or not artifact_id or not version:
        logging.error(
            "Must have a group_id '{}', artifact_id '{}' and version '{}' to check for conflicting dependency versions.".format(
                group_id, artifact_id, version))
        return
    all_poms, pom_info = load_poms_for_artifact(group_id, artifact_id, version)
    import pprint
    pprint.pprint(all_poms)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("-d", "--document", dest="document", action="store_true",
                              help="Document the dependencies for all Maven projects in the specified workspace")
    action_group.add_argument("-c", "--check-poms", dest="check_poms", action="store_true",
                              help="Check the pom versions for projects in the workspace against a parent project")
    action_group.add_argument("-t", "--check-poms_tree", dest="check_poms_tree", action="store_true",
                              help="Check the pom versions for projects in the workspace against a parent project. Same as -c but displays in a tree format.")
    action_group.add_argument("-k", "--checkout-branch", dest="checkout_branch", action="store_true",
                              help="Checkout the specified branch of the parent project and check the pom version of the rest of the workspace")
    action_group.add_argument("-n", "--check_poms_newer", dest="check_poms_newer", action="store_true",
                              help="Check the poms for newer versions of snapsots and/or releases")
    action_group.add_argument("-x", "--xxx_developing_new_functionality", dest="xx_new_function", action="store_true",
                              help="testing new functionality")
    parser.add_argument("-w", "--workspace", dest="workspace",
                        help="Workspace path to check. Defaults to '{0}'.".format(environment.WORKSPACE_ROOT_ID),
                        default=environment.WORKSPACE_ROOT_ID)
    parser.add_argument("-p", "--parent", dest="parent_project",
                        help="The ArtifactId of the Maven project that is the parent (all other projects in the workspace should be the versions specified by the parent project)")
    parser.add_argument("-g", "--group_id", dest="group_id",
                        help="The GroupId of the Maven project that is the parent (all other projects in the workspace should be the versions specified by the parent project)")
    parser.add_argument("-l", "--local_only", dest="local_only", action="store_true",
                        help="Flag to only display details of modules present in the workspace. default is to display details of all modules, local and remote.")
    parser.add_argument("-e", "--version", dest="version", help="The version of the parent project to check.")
    parser.add_argument("-b", "--branch", dest="branch", help="The branch of the parent project to checkout.")
    parser.add_argument("-r", "--reset", dest="reset", action="store_true",
                        help="Flag to indicate to reset any existing change when checking out.")
    parser.add_argument("-o", "--open", dest="open_output", action="store_true",
                        help="Flag to indicate to open the log file in an editor once the script has completed.")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        help="Flag to print verbose log messages.")

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
    elif args.check_poms_tree:
        if not args.parent_project:
            print("To check the pom versions in the workspace, you must supply a parent project.")
            parser.usage()
            sys.exit(1)
        log_file_path = common_utils.get_log_file_path(args.workspace, "check_poms_against_parent_tree")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)
        root_path = pathlib.Path(args.workspace)
        logging.info(
            "Attempting to check the pom dependencies for {} pom artifact project in workspace {} against other projects in the same workspace\n".format(
                args.parent_project, args.workspace))

        poms_info = maven_utils.load_pom_files_from_workspace(root_path)
        # Find the parent project's pom info
        parent_pom_info_list = maven_utils.find_pom_info(poms_info, artifact_id=args.parent_project)
        if not parent_pom_info_list:
            logging.info("Could not find parent project with artifactId of '{0}' in the workspace {1}.".format(
                args.parent_project, args.workspace))
            sys.exit(0)
        if len(parent_pom_info_list) > 1:
            logging.warning("Found multiple parent projects with artifactId of '{0}' in the workspace {1}.".format(
                args.parent_project, args.workspace))
            for pom_info in parent_pom_info_list:
                logging.warning(
                    '\tGroupId: {0.group_id:<35}\tArtifactId: {0.artifact_id:<50}\tVersion: {0.version}}'.format(
                        pom_info))
                logging.warning('\t\tPath: {0.path}   Url: {url}'.format(pom_info))
                logging.warning('\t\tName: {0.name}'.format(pom_info))
            local_poms = [p for p in parent_pom_info_list if p.path]
            if len(local_poms) == 1:
                logging.warning(
                    "Using only local workspace pom instance: {0.group_id} {0.artifact_id} {0.version}} in path {0.path}".format(
                        local_poms[0]))
                display_dependencies_tree(poms_info, local_poms[0], local_only=args.local_only)
            else:
                logging.warning("Cannot perform analysis with multiple parent projects.")
                sys.exit(0)
        else:
            display_dependencies_tree(poms_info, parent_pom_info_list[0], local_only=args.local_only)

    elif args.checkout_branch:
        if not args.parent_project:
            print(
                "To get a branch for a project and check the pom versions in the workspace, you must supply a parent project.")
            parser.usage()
            sys.exit(1)
        if not args.branch:
            print(
                "To get a branch for a project and check the pom versions in the workspace, you must supply a branch to checkout.")
            parser.usage()
            sys.exit(1)

        log_file_path = common_utils.get_log_file_path(args.workspace, "checkout_branch")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)
        checkout_branch(args.parent_project, args.workspace, args.branch, args.reset)
        check_poms_against_parent(args.parent_project, args.workspace)

    elif args.check_poms_newer:

        if not args.parent_project:
            print("To check the pom versions in the workspace, you must supply a parent project.")
            parser.usage()
            sys.exit(1)
        log_file_path = common_utils.get_log_file_path(args.workspace, "check_poms_for_newer_versions")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)
        check_for_latest_dependency_versions(args.parent_project, args.workspace)

    elif args.xx_new_function:

        if not args.parent_project:
            print("To check for newer pom versions, you must supply a parent project.")
            parser.usage()
            sys.exit(1)
        if not args.group_id:
            print("To check for newer pom versions, you must supply a group id.")
            parser.usage()
            sys.exit(1)
        if not args.version:
            print("To check for newer pom versions, you must supply a version for the parent module.")
            parser.usage()
            sys.exit(1)

        log_file_path = common_utils.get_log_file_path(args.workspace, "check_poms_for_newer_versions")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)
        check_for_conflicting_dependency_versions(args.group_id, args.parent_project, args.version)

    logging.info('\n\nLog file: {}'.format(log_file_path))
    if args.open_output and log_file_path:
        common_utils.open_file_in_editor(log_file_path)
