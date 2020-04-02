import argparse
import datetime
import itertools
import os.path
import pathlib
import pprint
import re
import sys
import xml.etree.ElementTree as ET

import git

import environment

def get_git_info(path):
    # repo_dir = path if path.is_dir() else path.parent  
    # while not git.repo.fun.is_git_dir(repo_dir) and repo_dir != repo_dir.parent:
        # repo_dir = repo_dir.parent
    try:
        repo = git.Repo(path, search_parent_directories=True)
        return {"repo_url": repo.remotes.origin.url,
                "branch": repo.active_branch.name}
    except:        
        print("**** path {0} was found to not be a git repo. ********".format(path))
        return {"repo_url": "Not git repo",
                "branch": "Not git repo"}


def build_nexus_path(pom_info):
    url_parts = {"scheme":'https', "netloc":'asbscr.ic.gc.ca', "path": '/maven-proxy/content/groups/all-released/ca/gc/ic/cipo/ec/id/CIPO-ec-id-mailbox-app/4.0.5/CIPO-ec-id-mailbox-app-4.0.5.pom'}


def load_pom_file(pom_path):
    # print("Attempting to load {}".format(pom_path))
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

    pom_info["dependencies"] = {}
    dependencies_el = root.findall("*/m:dependencies/m:dependency", nsmap)
    if not dependencies_el:
        dependencies_el = root.findall("m:dependencies/m:dependency", nsmap)
    version_pattern = re.compile(r'\$\{([^}]*)\}')
    for dep_el in dependencies_el:
        _el = dep_el.find("m:version", nsmap)   
        version = "unspecified" if _el is None else _el.text
        grps = version_pattern.match( version );
        if grps:
            prop_name = grps.group(1)
            _el = root.find("m:properties/m:{}".format(prop_name), nsmap)   
            version = "see parent pom for version property {}".format(prop_name) if _el is None else _el.text
        group_id = dep_el.find("m:groupId", nsmap).text
        artId = dep_el.find("m:artifactId", nsmap).text
        pom_info["dependencies"]["{}/{}".format(group_id, artId)] = { "groupId": group_id, 
                                                                    "version": version, 
                                                                    "artifactId": artId}
    return pom_info


def validate_pom_dependencies(pom_info, log_file_h):
    is_snapshot = "SNAPSHOT" in pom_info["version"].upper()
    version_desc = "snapshot" if is_snapshot else pom_info["version"] if pom_info["version"] in ["unknown", "unspecified"] else "release"
    print("\nPOM {}, {}, is a {} version: {}".format(pom_info["name"], pom_info["path"], version_desc, pom_info["version"]))
    print("\nPOM {}, {}, is a {} version: {}\n".format(pom_info["name"], pom_info["path"], version_desc, pom_info["version"]), file=log_file_h)
    snapshot_deps = [v for v in pom_info["dependencies"].values() if "SNAPSHOT" in v["version"].upper()]
    if len(snapshot_deps) > 0:
        if not is_snapshot:
            print("WARNING: a released version, {}, contains {} SNAPSHOT dependencies!".format(pom_info["version"], len(snapshot_deps)))
            print("WARNING: a released version, {}, contains {} SNAPSHOT dependencies!\n".format(pom_info["version"], len(snapshot_deps)), file=log_file_h)
        print("\nThe following {} dependencies are SNAPSHOT versions:\n".format(len(snapshot_deps)), file=log_file_h)
        for dep_info in snapshot_deps:
            print("    {}/{} version: {}".format(dep_info["groupId"], dep_info["artifactId"],  dep_info["version"]))
            print("    {}/{} version: {}\n".format(dep_info["groupId"], dep_info["artifactId"],  dep_info["version"]), file=log_file_h)
    # else:
        # print("\nNo snapshot dependencies.")

        
def get_pom_key(pom_info=None, group_id=None, artifact_id=None, version=None):
    if not pom_info:
        pom_info = {"groupId": group_id, "artifactId": artifact_id, "version":version}
        
    return "groupId:{groupId};artifactId:{artifactId};version:{version}".format(**pom_info)


def load_pom_files_from_workspace(root_path, log_file_h):
    poms_info = {}
    pom_files = sorted(itertools.chain(root_path.glob("pom.xml"), root_path.glob("*/pom.xml"), root_path.glob("*/*/pom.xml")))
    # pp = pprint.PrettyPrinter(indent=4)
    for pom_path in pom_files:
        pom_info = load_pom_file(pom_path)
        pom_key = get_pom_key(pom_info)
        if pom_key not in poms_info:
            pprint.pprint(pom_info, log_file_h)
            pprint.pprint(pom_info)
            validate_pom_dependencies(pom_info, log_file_h)
            poms_info[pom_key] = pom_info
        else:
            print('There is already a pom with the key "{0}". Not adding the one for {1}\n'.format(pom_key, pom_info.path), file=log_file_h)
            print('There is already a pom with the key "{0}". Not adding the one for {1}'.format(pom_key, pom_info.path))
    return poms_info


def get_log_file_path(root_path):
    log_file_path = os.path.join(root_path, 'check_pom_dependencies_{}.txt'.format(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')))
    count = 0
    while os.path.isfile(log_file_path) and count < 2000:
        log_file_path = os.path.join(root_path, 'check_pom_dependencies_{}.txt'.format(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')))
        count += 1
    return log_file_path

def find_pom_info(poms_info, group_id=None, artifact_id=None, version=None):
    desired_key = "groupId:{0};".format(group_id) if group_id else ""
    desired_key = "{0}artifactId:{1};".format(desired_key, artifact_id) if artifact_id else desired_key
    desired_key = "{0}version:{1};".format(desired_key, version) if version else desired_key
    
    return [pom_info for (k, pom_info) in poms_info.items() if desired_key in k]


def document_workspace(root_path):
    # root_path = "/cygdrive/c/dev/hague/unused_repos"
    root_path = pathlib.Path(root_path)
    log_file_path = get_log_file_path(root_path)

    with open(log_file_path, 'w') as log_file_h: 
        poms_info = load_pom_files_from_workspace(root_path, log_file_h)
    
        print('\n\nDisplay of pom dependencies:\n', file=log_file_h)
        print('\n\nDisplay of pom dependencies:')
        for v in poms_info.values():
            print('GroupId: {groupId}\nArtifactId: {artifactId}\nVersion: {version}\nPath: {path}\nName: {name}\nDependencies:\n'.format(**v), file=log_file_h)
            print('GroupId: {groupId}\nArtifactId: {artifactId}\nVersion: {version}\nPath: {path}\nName: {name}\nDependencies:'.format(**v))
            for dep_info in v['dependencies'].values():
                pom_key = "groupId:{groupId};artifactId:{artifactId};version:{version}".format(**dep_info)
                # pp.pprint(dep_info)
                print(' -- GroupId: {0}\n    ArtifactId: {1}\n    Version: {2}{3}'.format(dep_info['groupId'], dep_info['artifactId'], dep_info['version'], '\n    LOCAL ENVIRONMENT COPY\n' if pom_key in poms_info else '\n'), file=log_file_h)
                print(' -- GroupId: {0}\n    ArtifactId: {1}\n    Version: {2}{3}'.format(dep_info['groupId'], dep_info['artifactId'], dep_info['version'], '\n    LOCAL ENVIRONMENT COPY' if pom_key in poms_info else ''))
            print()

    print('\n\nLog file: {}'.format(log_file_path))

def check_dependencies(poms_info, dependency_poms_infos, log_file_h):
    deps_to_check = []
    for dep_info in dependency_poms_infos:
        dep_pom_info_list = find_pom_info(poms_info, group_id=dep_info["groupId"], artifact_id=dep_info["artifactId"])
        if not dep_pom_info_list:
            print("Dependency not present:                GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}".format(**dep_info))
            print("Dependency not present:                GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}\n".format(**dep_info), file=log_file_h)
        elif len(dep_pom_info_list) > 1:
            print("\nMultiple copied of Dependency present: GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}\n".format(**dep_info), file=log_file_h)
            print("\nMultiple copied of Dependency present: GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}".format(**dep_info))
            for pom_info in dep_pom_info_list:
                print('\tGroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}\n\t\tPath: {path}\n\t\tName: {name}\n'.format(**pom_info), file=log_file_h)
                print('\tGroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}\n\t\tPath: {path}\n\t\tName: {name}'.format(**pom_info))
        elif dep_info["version"] == dep_pom_info_list[0]["version"]:
            print("\nProper dependency version present:     GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}\n\t\tPath: {path}\n\t\tName: {name}\n".format(**(dep_pom_info_list[0])), file=log_file_h)
            print("\nProper dependency version present:     GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}\n\t\tPath: {path}\n\t\tName: {name}".format(**(dep_pom_info_list[0])))
            repo_info = get_git_info(dep_pom_info_list[0]["path"])
            print("\t\tGit repo: {repo_url}\n\tGit branch: {branch}".format(**repo_info))
            print("\t\tGit repo: {repo_url}\n\tGit branch: {branch}\n".format(**repo_info), file=log_file_h)
            
            deps_to_check.append(dep_pom_info_list[0])
        else:
            print("\nIncorrect dependency version present:  GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}\n\t\tPath: {path}\n\t\tName: {name}\n".format(**(dep_pom_info_list[0])), file=log_file_h)
            print("\nIncorrect dependency version present:  GroupId: {groupId:<35}  ArtifactId: {artifactId:<40}  Version: {version}\n\t\tPath: {path}\n\t\tName: {name}".format(**(dep_pom_info_list[0])))
            repo_info = get_git_info(dep_pom_info_list[0]["path"])
            print("\t\tGit repo: {repo_url}\n\tGit branch: {branch}".format(**repo_info))
            print("\t\tGit repo: {repo_url}\n\tGit branch: {branch}\n".format(**repo_info), file=log_file_h)
    for dep_pom_info in deps_to_check:
        print('\n\nUsing dependent project GroupId: {groupId:<35}\tArtifactId: {artifactId:<40}\tVersion: {version}\n\t\tPath: {path}\n\t\tName: {name}\n'.format(**dep_pom_info), file=log_file_h)
        print('\nUsing dependent project GroupId: {groupId:<35}\tArtifactId: {artifactId:<40}\tVersion: {version}\n\t\tPath: {path}\n\t\tName: {name}'.format(**dep_pom_info))
        repo_info = get_git_info(dep_pom_info["path"])
        print("\t\tGit repo: {repo_url}\n\tGit branch: {branch}".format(**repo_info))
        print("\t\tGit repo: {repo_url}\n\tGit branch: {branch}\n".format(**repo_info), file=log_file_h)
        print('\nDependencies:\n', file=log_file_h)
        print('\nDependencies:')
        
        check_dependencies(poms_info, dep_pom_info['dependencies'].values(), log_file_h)
        

def check_poms_against_parent(parent_project_name, workspace):
    root_path = pathlib.Path(workspace)
    log_file_path = get_log_file_path(root_path)
    with open(log_file_path, 'w') as log_file_h: 

        poms_info = load_pom_files_from_workspace(root_path, log_file_h)
        # Find the parent project's pom info
        parent_pom_info_list = find_pom_info(poms_info, artifact_id=parent_project_name)
        if not parent_pom_info_list:
            print("\nCould not find parent project with artifactId of '{0}' in the workspace {1}.".format(parent_project_name, workspace))
            print("\n\nCould not find parent project with artifactId of '{0}' in the workspace {1}.".format(parent_project_name, workspace), file=log_file_h)
            sys.exit(0)
        if len(parent_pom_info_list) > 1:
            print("\nFound multiple parent projects with artifactId of '{0}' in the workspace {1}.".format(parent_project_name, workspace))
            print("\n\nFound multiple parent projects with artifactId of '{0}' in the workspace {1}.".format(parent_project_name, workspace), file=log_file_h)
            for pom_info in parent_pom_info_list:
                print('\tGroupId: {groupId:<35}\tArtifactId: {artifactId:<40}\tVersion: {version}\n\t\tPath: {path}\n\t\tName: {name}\n'.format(**pom_info), file=log_file_h)
                print('\tGroupId: {groupId:<35}\tArtifactId: {artifactId:<40}\tVersion: {version}\n\t\tPath: {path}\n\t\tName: {name}'.format(**pom_info))
            print("\nCannot perform analysis with multiple parent projects.")
            print("\nCannot perform analysis with multiple parent projects.\n", file=log_file_h)
            sys.exit(0)
        parent_pom_info = parent_pom_info_list[0]
        repo_info = get_git_info(parent_pom_info["path"])
        print('\n\nUsing Parent project GroupId: {groupId:<35}\tArtifactId: {artifactId:<40}\tVersion: {version}\n\t\tPath: {path}\n\t\tName: {name}\n'.format(**parent_pom_info), file=log_file_h)
        print("\t\tGit repo: {repo_url}\n\tGit branch: {branch}\n".format(**repo_info), file=log_file_h)
        print('Dependencies:\n', file=log_file_h)
        print('\nUsing Parent project GroupId: {groupId:<35}\tArtifactId: {artifactId:<40}\tVersion: {version}\n\t\tPath: {path}\n\t\tName: {name}\n'.format(**parent_pom_info))
        print("\t\tGit repo: {repo_url}\n\tGit branch: {branch}".format(**repo_info))
        print('Dependencies:')
        
        check_dependencies(poms_info, parent_pom_info['dependencies'].values(), log_file_h)
        
    print('\n\nLog file: {}'.format(log_file_path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--document", dest="document", action="store_true", help="Document the dependencies for all Maven projects in the specified workspace")
    parser.add_argument("-w", "--workspace", dest="workspace",  help="Workspace path to check. Defaults to '{0}'.".format(environment.WORKSPACE_ROOT_ID), default=environment.WORKSPACE_ROOT_ID)
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Flag to print verbose log messages.")
    parser.add_argument("-p", "--parent", dest="parent_project", help="The ArtifactId of the Maven project that is the parent (all other projects in the workspace should be the versions specified by the parent project)")

    args = parser.parse_args()
    verbose = args.verbose

    if args.document:
        document_workspace(args.workspace)
    elif args.parent_project:
        check_poms_against_parent(args.parent_project, args.workspace)
