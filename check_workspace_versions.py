import datetime
import itertools
import os.path
import pathlib
import pprint
import re
import sys
import xml.etree.ElementTree as ET


def get_version_from_pom(pom_path, pom_infos):
    if not pom_path in pom_infos:
        pom_info = load_pom_file(pom_path)
        pom_infos[pom_path] = pom_info

    pass


def load_pom_file(pom_path):
    # print("Attempting to load {}".format(pom_path))
    pom_info = {"path": pom_path}
    pom_tree = ET.parse(pom_path)
    root = pom_tree.getroot()
    nsmap = {"m": "http://maven.apache.org/POM/4.0.0"}

    _el = root.find("m:parent/m:groupId", nsmap)
    groupId = "unknown" if _el is None else _el.text
    _el = root.find("m:parent/m:artifactId", nsmap)
    artId = "unknown" if _el is None else _el.text
    _el = root.find("m:parent/m:version", nsmap)
    version = "unknown" if _el is None else _el.text
    pom_info["parent"] = {"groupId": groupId, "artifactId": artId, "version": version}

    _el = root.find("m:groupId", nsmap)
    pom_info["groupId"] = pom_info["parent"]["groupId"] if _el is None else _el.text
    _el = root.find("m:artifactId", nsmap)
    pom_info["artifactId"] = "unspecified" if _el is None else _el.text
    if '${' in pom_info["artifactId"]:
        pattern = re.compile(r'\$\{([^}]*)\}')
        grps = pattern.match(pom_info["artifactId"]);
        if grps:
            if grps.group(1) == 'project.artifactId':
                pass
    _el = root.find("m:version", nsmap)
    pom_info["version"] = pom_info["parent"]["version"] if _el is None else _el.text
    _el = root.find("m:name", nsmap)
    pom_info["name"] = pom_info["artifactId"] if _el is None else _el.text
    _el = root.find("m:packaging", nsmap)
    pom_info["packaging"] = "unspecified" if _el is None else _el.text

    pom_info["dependencies"] = {}
    dependencies_el = root.findall("*/m:dependencies/m:dependency", nsmap)
    if not dependencies_el:
        dependencies_el = root.findall("m:dependencies/m:dependency", nsmap)
    version_pattern = re.compile(r'\$\{([^}]*)\}')
    for dep_el in dependencies_el:
        _el = dep_el.find("m:version", nsmap)
        version = "unspecified" if _el is None else _el.text
        grps = version_pattern.match(version);
        if grps:
            prop_name = grps.group(1)
            _el = root.find("m:properties/m:{}".format(prop_name), nsmap)
            version = "see parent pom for version property {}".format(prop_name) if _el is None else _el.text
        groupId = dep_el.find("m:groupId", nsmap).text
        artId = dep_el.find("m:artifactId", nsmap).text
        pom_info["dependencies"]["{}/{}".format(groupId, artId)] = {"groupId": groupId,
                                                                    "version": version,
                                                                    "artifactId": artId}
    return pom_info


def validate_pom_dependencies(pom_info):
    is_snapshot = "SNAPSHOT" in pom_info["version"].upper()
    version_desc = "snapshot" if is_snapshot else pom_info["version"] if pom_info["version"] in ["unknown",
                                                                                                 "unspecified"] else "release"
    print("\nPOM {}, {}, is a {} version: {}".format(pom_info["name"], pom_info["path"], version_desc,
                                                     pom_info["version"]))
    snapshot_deps = [v for v in pom_info["dependencies"].values() if "SNAPSHOT" in v["version"].upper()]
    if len(snapshot_deps) > 0:
        if not is_snapshot:
            print("WARNING: a released version, {}, contains {} SNAPSHOT dependencies!".format(pom_info["version"],
                                                                                               len(snapshot_deps)))
        print("\nThe following {} dependencies are SNAPSHOT versions:".format(len(snapshot_deps)))
        for dep_info in snapshot_deps:
            print("    {}/{} version: {}".format(dep_info["groupId"], dep_info["artifactId"], dep_info["version"]))
    # else:
    # print("\nNo snapshot dependencies.")


def get_pom_key(pom_info=None, group_id=None, artifact_id=None, version=None):
    if not pom_info:
        if not version:
            version = ""
        pom_info = {"groupId": group_id, "artifactId": artifact_id, "version": version}

    return "groupId:{groupId};artifactId:{artifactId};version:{version}".format(**pom_info)


def get_parent_pom_key(pom_info):
    return "groupId:{groupId};artifactId:{artifactId};version:{version}".format(**(pom_info["parent"]))


def load_workspace_poms(root_path):
    poms_info = {}

    rootPath = pathlib.Path(root_path)
    pom_files = sorted(
        itertools.chain(rootPath.glob("pom.xml"), rootPath.glob("*/pom.xml"), rootPath.glob("*/*/pom.xml")))
    pp = pprint.PrettyPrinter(indent=4)
    for pom_path in pom_files:
        pom_info = load_pom_file(pom_path)
        pom_key = get_pom_key(pom_info)
        if pom_key not in poms_info:
            print("Loading pom file {0}".format(pom_path))
            validate_pom_dependencies(pom_info)
            poms_info[pom_key] = pom_info
        else:
            print(
                'There is already a pom with the key "{0}". Not adding the one for {1}'.format(pom_key, pom_info.path))
    return poms_info


def get_pom_info(poms_info, pom_info_key):
    matching_keys = [k for k in poms_info.keys() if k.startswith(pom_info_key)]
    if len(matching_keys) > 0:
        return poms_info[matching_keys[0]]
    else:
        return None


def get_project_children(poms_info, pom_info):
    parent_key = get_pom_key(pom_info)
    return [v for v in poms_info.values() if parent_key == get_parent_pom_key(v)]


def main(group_id, artifact_id):
    root_path = environment.WORKSPACE_ROOT_ID

    log_file_path = os.path.join(root_path, 'check_workspace_versions_{}.txt'.format(
        datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')))
    count = 0
    while os.path.isfile(log_file_path) and count < 2000:
        log_file_path = os.path.join(root_path, 'check_workspace_versions_{}.txt'.format(
            datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')))
        count += 1

    with open(log_file_path, 'w') as log_file_h:
        poms_info = {}

        app_pom_info_key = get_pom_key(group_id=group_id, artifact_id=artifact_id)
        app_pom_info = get_pom_info(poms_info, app_pom_info_key)

    print('\n\nLog file: {}'.format(log_file_path))


if __name__ == "__main__":
    group_id = "org.test.package"
    artifact_id = "application"
    main(group_id, artifact_id)
