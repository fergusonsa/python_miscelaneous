import argparse
import datetime
import itertools
import logging
import os.path
import pathlib
import pprint
import re
import shutil
import sys

import git

import common_utils
import environment


def test():
    repoPath = "/cygdrive/c/dev/hague/new_workspace/cipo-ec-id-filing"
    oldBranch = "CIPO-ec-id-filing-4.2.9"
    newBranch = "Hague_Rel2c"
    r = git.Repo(repoPath)
    r.fetch()

    tags = r.tags
    last_tag = tags[-1]
    tag_date = datetime.datetime.fromtimestamp(last_tag.tag.tagged_date)

    commitMessages = g.log('%s..%s' % (oldBranch, newBranch), '--pretty=format:%ad %an - %s', '--abbrev-commit')


def get_diffs(repo, tag_name):
    git_diffs = repo.head.commit.diff(tag_name)
    diffs = [{"file": d.a_path, "change_type": d.change_type} for d in git_diffs]
    return diffs


def get_logs(repo, branch=None, tag_name=None):
    if not branch:
        branch = repo.head.ref.name
    if not tag_name:
        tag_name = repo.tags[-1].name

    git = git.Repo(repo.working_dir)
    logs = repo.log('%s..%s' % (tag_name, branch))
    log_list = []
    commit_info = {}
    for strng in logs.splitlines():
        if strng.startswith("commit"):
            if commit_info:
                log_list.append(commit_info)
            commit_info = {}
            commit_info["commit"] = strng
        elif strng.startswith("Author:"):
            commit_info["author"] = strng
        elif strng.startswith("Date:"):
            commit_info["date"] = strng
        elif strng != "":
            commit_info["message"] = strng
    if commit_info:
        log_list.append(commit_info)
    return log_list


def create_release_log():
    # Get the repoPath
    repo_path = "/cygdrive/c/dev/hague/new_workspace/cipo-ec-id-filing"

    r = git.Repo(repo_path)
    r.fetch()

    current_branch = r.head.ref.name

    # Get the last release tag
    last_release_tag = r.tags[-1]
    last_release_tag_name = last_release_tag.name
    tag_date = datetime.datetime.fromtimestamp(last_release_tag.tag.tagged_date)

    diffs = r.head.commit.diff(last_release_tag_name)


def get_remote_branch_name(git_repo, br_name):
    branches = [br.strip() for br in git_repo.git.branch('-r').splitlines()]
    for name in [br_name, br_name.lower(), br_name.capitalize(), br_name.upper()]:
        remote_name = "origin/{}".format(name)
        if remote_name in branches:
            return name
    logging.debug("Did not find branch {} ('{}', '{}', or '{}') in branches: {}".format(br_name, br_name.lower(),
                                                                                        br_name.capitalize(),
                                                                                        br_name.upper(), branches))
    return None


def get_local_branch_name(git_repo, br_name):
    for name in [br_name.lower(), br_name.capitalize(), br_name.upper()]:
        if name in git_repo.heads:
            return name
    return None


def compare_against_master_branch(git_repo, branch_name):
    git_repo.git.pull()
    master_branch_name = get_remote_branch_name(git_repo, "master")
    if not master_branch_name:
        logging.warning("Cannot find master branch for git repo {}.".format(git_repo.working_dir))
        return None
    develop_branch_name = get_remote_branch_name(git_repo, branch_name)
    if not develop_branch_name:
        logging.warning("Cannot find {} branch for git repo {}.".format(branch_name, git_repo.working_dir))
        return None
    git_repo.git.checkout(master_branch_name)
    git_repo.git.pull()
    git_repo.git.checkout(develop_branch_name)
    git_repo.git.pull()

    commit_messages = git_repo.git.log('%s..%s' % (develop_branch_name, master_branch_name),
                                      '--pretty=format:%ad %an - %s', '--abbrev-commit')
    # If no commit messages, then the develop branch is up to date with the master branch
    if commit_messages:
        commits_msgs_l = commit_messages.splitlines()
        logging.info("There are {} commits in the {} branch that are not in the {} branch of the {} git repo".format(
            len(commits_msgs_l), master_branch_name, develop_branch_name, git_repo.working_dir))
    else:
        logging.info("The {} branch is up to date with the {} branch of the {} git repo".format(develop_branch_name,
                                                                                                master_branch_name,
                                                                                                git_repo.working_dir))


def compare_against_master_branch_in_workspace(root_path_str, branch_name):
    root_path = pathlib.Path(root_path_str)

    for path in root_path.iterdir():
        if path.is_dir():
            try:
                repo = git.Repo(path, search_parent_directories=True)
            except:
                logging.debug("**** path {0} was found to not be a git repo. ********".format(path))
                continue
            if repo:
                compare_against_master_branch(repo, branch_name)


def list_branches_in_workspace(root_path_str):
    root_path = pathlib.Path(root_path_str)

    for path in root_path.iterdir():
        if path.is_dir():
            try:
                repo = git.Repo(path, search_parent_directories=True)
            except:
                logging.debug("**** path {0} was found to not be a git repo. ********".format(path))
                continue
            if repo:
                dev_branch_name = get_remote_branch_name(repo, "develop")
                if not dev_branch_name:
                    dev_branch_name = "<unknown>"
                master_branch_name = get_remote_branch_name(repo, "master")
                if not master_branch_name:
                    master_branch_name = "<unknown>"

                branches = [br.strip() for br in repo.git.branch('-a').splitlines()]
                logging.info("Branches for git repo in {}:".format(repo.working_dir))
                for br in branches:
                    logging.info("\t{}".format(br))
                logging.info("Develop branch: {:<40}  master branch: {}\n".format(dev_branch_name, master_branch_name))


def create_workspace(workspace_str):
    root_path = pathlib.Path(workspace_str)

    if not root_path.exists():
        root_path.mkdir(parents=True)
    elif root_path.is_dir():
        if any(root_path.iterdir()):
            logging.warning(
                "Cannot checkout a new workspace to {} because theer are already files there!".format(workspace_str))
            return
    for url in environment.GIT_REMOTES:
        repo_name = url.rpartition("/")[2][:-4]
        dir_path_str = os.path.join(workspace_str, repo_name)
        logging.info("Cloning {} from {} into {}".format(repo_name, url, dir_path_str))
        repo = git.Repo.clone_from(url, dir_path_str)

        dev_branch_name = get_remote_branch_name(repo, "develop")
        master_branch_name = get_remote_branch_name(repo, "master")
        if dev_branch_name:
            repo.git.checkout(dev_branch_name)
        if master_branch_name:
            repo.git.checkout(master_branch_name)


def pull_dev_master_branches_in_workspace(workspace_str):
    root_path = pathlib.Path(workspace_str)

    if not root_path.exists():
        logging.warning("Cannot pull changes because the workspace {} does not exist!".format(workspace_str))
        return
    for path in root_path.iterdir():
        if path.is_dir():
            try:
                repo = git.Repo(path, search_parent_directories=True)
            except:
                logging.debug("**** path {0} was found to not be a git repo. ********".format(path))
                continue
            if repo:
                current_branch = repo.head.ref.name
                dev_branch_name = get_remote_branch_name(repo, "develop")
                msg = ""
                if dev_branch_name:
                    repo.git.checkout(dev_branch_name)
                    repo.git.pull()
                    msg = dev_branch_name
                    logging.debug("pulled {} branch for {}".format(dev_branch_name, path))
                else:
                    logging.debug("Could not find develop branch for {}".format(path))
                master_branch_name = get_remote_branch_name(repo, "master")
                if master_branch_name:
                    repo.git.checkout(master_branch_name)
                    repo.git.pull()
                    logging.debug("pulled {} branch for {}".format(master_branch_name, path))
                    msg = msg + ", " + master_branch_name if msg else master_branch_name
                else:
                    logging.debug("Could not find master branch for {}".format(path))

                if current_branch:
                    repo.git.checkout(current_branch)
                    if current_branch != dev_branch_name and current_branch != master_branch_name:
                        repo.git.pull()
                        logging.debug("pulled {} branch for {}".format(current_branch, path))
                        msg = msg + ", " + current_branch if msg else current_branch
                if msg:
                    logging.info("Following branches have been pulled for {}: {}\n".format(path, msg))
                else:
                    logging.info("No branches have been pulled for {}\n".format(path))


def prerelease_check(workspace_path_str, branch, module_name):
    root_path = pathlib.Path(workspace_path_str)

    if not root_path.exists():
        logging.warning(
            "Cannot perform pre-release check because the workspace {} does not exist!".format(workspace_path_str))
        return
    module_path = root_path.joinpath(module_name)
    if not module_path.is_dir():
        logging.warning(
            "Cannot perform pre-release check because the module {} sub-directory does not exist in the workspace {}!".format(
                module_name, workspace_path_str))
        return
    try:
        repo = git.Repo(module_path, search_parent_directories=True)
    except:
        logging.warning(
            "Cannot perform pre-release check because the module {} sub-directory in the workspace {} is not a git repository!".format(
                module_name, workspace_path_str))
        return
    if repo:
        remote_br_name = get_remote_branch_name(repo, branch)
        if not remote_br_name or remote_br_name != branch:
            logging.warning(
                "Cannot perform pre-release check because the specified branch '{}' is not a valid branch for the module {} git repo in the workspace {}!".format(
                    branch, module_name, workspace_path_str))
            return
        repo.git.checkout(branch)
        repo.git.pull()
        logging.info("Pulled updates for the {} branch".format(branch))
    import workspace
    poms_info = workspace.load_pom_files_from_workspace(module_path, validate=True)


def checkout_same_branch_in_workspace(workspace_path_str, branch_name):
    root_path = pathlib.Path(workspace_path_str)

    if not root_path.exists():
        logging.warning("Cannot pull changes because the workspace {} does not exist!".format(workspace_path_str))
        return
    for path in root_path.iterdir():
        if path.is_dir():
            try:
                repo = git.Repo(path, search_parent_directories=True)
            except:
                logging.debug("**** path {0} was found to not be a git repo. ********".format(path))
                continue
            if repo:
                remote_br_name = get_remote_branch_name(repo, branch_name)
                if remote_br_name:
                    repo.git.checkout(remote_br_name)
                    repo.git.pull()
                    logging.info(
                        "Checked out branch {} and pulled updates in the git repo {}".format(branch_name, path))
                else:
                    logging.info("The git repo {} does not have a branch '{}'".format(path, branch_name))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("-l", "--list_branches", dest="list_branches", action="store_true",
                              help="testing new functionality")
    action_group.add_argument("-c", "--create_workspace", dest="create_workspace", action="store_true",
                              help="Create a new workspace")
    action_group.add_argument("-u", "--uptodate", dest="uptodate_master", action="store_true",
                              help="Check to see if the specified branch is up to date with the master branch for each repo in the workspace")
    action_group.add_argument("-p", "--pull", dest="pull_branches", action="store_true",
                              help="Pull the develop and master branches for all repos in the workspace")
    action_group.add_argument("-e", "--checkout", dest="checkout", action="store_true",
                              help="Checkout the specified branch in all git repos, if it already exists, in the workspace.")
    action_group.add_argument("-s", "--prerelease", dest="prerelease_check", action="store_true",
                              help="testing functionality currently working on.")
    action_group.add_argument("-x", "--xx_test", dest="xx_new_function", action="store_true",
                              help="testing functionality currently working on.")
    parser.add_argument("-w", "--workspace", dest="workspace",
                        help="Workspace path to check. Defaults to '{0}'.".format(environment.WORKSPACE_ROOT_ID),
                        default=environment.WORKSPACE_ROOT_ID)
    parser.add_argument("-y", "--python_workspace", dest="use_python_workspace", action="store_true",
                        help="Use the python workspace instead of the workspace argument.")
    parser.add_argument("-m", "--module", dest="module_name",
                        help="Module to use. Must be a sub directory of the workspace directory.", )
    parser.add_argument("-b", "--branch", dest="branch_name", default="develop",
                        help="Branch to compare to master branch or to checkout. Defaults to '%(default)s'.", )
    parser.add_argument("-r", "--repo", dest="repo_path",
                        help="Branch to compare to master branch. Defaults to '%(default)s'.", )
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        help="Flag to print verbose log messages.")
    parser.add_argument("-f", "--force", dest="force", action="store_true",
                        help="Force the action being attempted. If creating a workspace, then any existing files in the workspace will be deleted.")
    parser.add_argument("-o", "--open", dest="open_output", action="store_true",
                        help="Flag to indicate to open the log file in an editor once the script has completed.")

    args = parser.parse_args()
    verbose = args.verbose
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_file_path = None

    workspace_path_str = environment.PYTHON_WORKSPACE_PATH if args.use_python_workspace else args.workspace

    if args.list_branches:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_list_branches")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)

        logging.info("Listing the branches for git repos in the workspace {}.\n".format(workspace_path_str))
        list_branches_in_workspace(workspace_path_str)

    elif args.create_workspace:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_create_workspace")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)
        root_path = pathlib.Path(workspace_path_str)
        if args.force and root_path.is_dir() and any(root_path.iterdir()):
            logging.info(
                "Deleting all existing files and directories from {} before creating a new workspace".format(root_path))
            shutil.rmtree(root_path, ignore_errors=True)
        create_workspace(workspace_path_str)

    elif args.pull_branches:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_pull_branches")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)

        if args.repo_path:
            path = pathlib.Path(args.repo_path)
            if path.is_dir():
                try:
                    repo = git.Repo(path, search_parent_directories=True)
                except:
                    logging.debug("**** path {0} was found to not be a git repo. ********".format(path))

                if repo:
                    current_branch = repo.head.ref.name
                    dev_branch_name = get_remote_branch_name(repo, "develop")
                    msg = ""
                    if dev_branch_name:
                        repo.git.checkout(dev_branch_name)
                        repo.git.pull()
                        msg = dev_branch_name
                        logging.debug("pulled {} branch for {}".format(dev_branch_name, path))
                    else:
                        logging.debug("Could not find develop branch for {}".format(path))
                    master_branch_name = get_remote_branch_name(repo, "master")
                    if master_branch_name:
                        repo.git.checkout(master_branch_name)
                        repo.git.pull()
                        logging.debug("pulled {} branch for {}".format(master_branch_name, path))
                        msg = msg + ", " + master_branch_name if msg else master_branch_name
                    else:
                        logging.debug("Could not find master branch for {}".format(path))

                    if current_branch:
                        repo.git.checkout(current_branch)
                        if current_branch != dev_branch_name and current_branch != master_branch_name:
                            repo.git.pull()
                            logging.debug("pulled {} branch for {}".format(current_branch, path))
                            msg = msg + ", " + current_branch if msg else current_branch
                    if msg:
                        logging.info("Following branches have been pulled for {}: {}\n".format(path, msg))
                    else:
                        logging.info("No branches have been pulled for {}\n".format(path))

        else:
            pull_dev_master_branches_in_workspace(workspace_path_str)

    elif args.uptodate_master:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_uptodate_master")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)

        if args.repo_path:
            path = pathlib.Path(args.repo_path)
            if path.is_dir():
                try:
                    repo = git.Repo(path, search_parent_directories=True)
                except:
                    logging.debug("**** path {0} was found to not be a git repo. ********".format(path))
                if repo:
                    compare_against_master_branch(repo, args.branch_name)

        else:
            compare_against_master_branch_in_workspace(workspace_path_str, args.branch_name)

    elif args.prerelease_check:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_prerelease_check")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)

        prerelease_check(workspace_path_str, args.branch_name, args.module_name)

    elif args.checkout:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_checkout")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)

        checkout_same_branch_in_workspace(workspace_path_str, args.branch_name)

    elif args.xx_new_function:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_test")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)

        prerelease_check(workspace_path_str, args.branch_name, args.module_name)

    logging.info('\n\nLog file: {}'.format(log_file_path))
    if args.open_output and log_file_path:
        common_utils.open_file_in_editor(log_file_path)
