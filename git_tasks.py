import argparse
import datetime
import logging
import os.path
import pathlib
import shutil

import git

import common_utils
import environment


def test():
    repoPath = "/cygdrive/c/dev/hague/new_workspace/"
    oldBranch = "old_branch"
    newBranch = "new_branch"
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

    new_repo = git.Repo(repo.working_dir)
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


def compare_against_master_branch(path, git_repo, branch_name, parent_branch_name):
    # git_repo.git.pull()
    git_repo.git.fetch("--all")
    master_branch_name = get_remote_branch_name(git_repo, parent_branch_name)
    if not master_branch_name:
        logging.warning("Cannot find {} branch for git repo {}.".format(parent_branch_name, git_repo.working_dir))
        return None
    git_repo.git.fetch("--all")
    git_repo.git.reset("--hard", "origin/{}".format(master_branch_name))
    last_master_commit = git_repo.head.commit
    master_commit_date = datetime.datetime.fromtimestamp(last_master_commit.committed_date)
    commits_msgs_l = []
    num_commits_ahead = num_commits_behind = 0
    dev_commit_date = dev_commit_date = None
    develop_branch_name = get_remote_branch_name(git_repo, branch_name)
    if develop_branch_name:
        git_repo.git.checkout(develop_branch_name)
        git_repo.git.fetch("--all")
        git_repo.git.reset("--hard", "origin/{}".format(develop_branch_name))
        last_develop_commit = git_repo.head.commit
        dev_commit_date = datetime.datetime.fromtimestamp(last_develop_commit.committed_date)

        commit_messages = git_repo.git.log('origin/%s..origin/%s' % (develop_branch_name, master_branch_name),
                                           '--pretty=format:%ad %an', '--abbrev-commit')
        # If no commit messages, then the develop branch is up to date with the master branch
        if commit_messages:
            num_commits_behind = len(commit_messages.splitlines())
            # rootLogger = logging.getLogger()
            # if rootLogger.isEnabledFor(logging.DEBUG):
            # logging.debug("Commits in {} but not in {}: {}".format(develop_branch_name, master_branch_name, commit_messages.splitlines()))
        commit_messages = git_repo.git.log('origin/%s..origin/%s' % (master_branch_name, develop_branch_name),
                                           '--pretty=format:%ad %an', '--abbrev-commit')
        # If no commit messages, then the master branch is up to date with the develop branch
        if commit_messages:
            num_commits_ahead = len(commit_messages.splitlines())
            # rootLogger = logging.getLogger()
            # if rootLogger.isEnabledFor(logging.DEBUG):
            # logging.debug("Commits in {} but not in {}: {}".format(develop_branch_name, master_branch_name, commit_messages.splitlines()))
    else:
        develop_branch_name = ""

    master_commit_date_str = master_commit_date.strftime('%Y-%m-%d %H:%M:%S') if master_commit_date else ""
    dev_commit_date_str = dev_commit_date.strftime('%Y-%m-%d %H:%M:%S') if dev_commit_date else ""
    logging.info("{:<40}  {:<20}  {:<20}  {:<20}  {:<20}  {:4}               {:4}".format(path.name, master_branch_name,
                                                                                          master_commit_date_str,
                                                                                          develop_branch_name,
                                                                                          dev_commit_date_str,
                                                                                          num_commits_ahead,
                                                                                          num_commits_behind))


def compare_against_master_branch_in_workspace(root_path_str, branch_name, parent_branch_name):
    root_path = pathlib.Path(root_path_str)

    logging.getLogger("git").setLevel(logging.WARNING)
    logging.info("{:<40}  {:<20}  {:<20}  {:<20}  {:<20}  # Commits Ahead    # Commits Behind".format("Repository",
                                                                                                      "Master branch",
                                                                                                      "Date last commit",
                                                                                                      "Develop branch",
                                                                                                      "Date last commit",
                                                                                                      "#"))
    for path in root_path.iterdir():
        if path.is_dir():
            try:
                repo = git.Repo(path)
            except:
                logging.debug("**** path {0} was found to not be a git repo. ********".format(path))
                continue
            if repo:
                if repo.is_dirty() and not root_path.samefile(environment.PYTHON_WORKSPACE_PATH):
                    logging.warning("{} contains modifications and do not want to overwrite them.".format(path))
                else:
                    compare_against_master_branch(path, repo, branch_name, parent_branch_name)


def list_branches_in_workspace(root_path_str, branches_to_show):
    root_path = pathlib.Path(root_path_str)

    logging.getLogger("git").setLevel(logging.WARNING)
    for path in root_path.iterdir():
        if path.is_dir():
            try:
                repo = git.Repo(path, search_parent_directories=True)
            except:
                logging.debug("**** path {0} was found to not be a git repo. ********".format(path))
                continue
            if repo:
                repo.git.fetch("--all")
                dev_branch_name = get_remote_branch_name(repo, "develop")
                if not dev_branch_name:
                    dev_branch_name = "<unknown>"
                master_branch_name = get_remote_branch_name(repo, "master")
                if not master_branch_name:
                    master_branch_name = "<unknown>"

                current_branch = repo.head.ref.name

                branches = [br.strip() for br in repo.git.branch('-a').splitlines()]
                if branches_to_show != "*":
                    branches = [branch for branch in branches if branch.endswith(branches_to_show)]
                logging.info("{} Branches for git repo in {}:".format(branches_to_show, repo.working_dir))
                for br in branches:
                    logging.info("\t{}".format(br))
                logging.info(
                    "Develop branch: {:<30}  master branch: {:<30}  current branch: {}\n".format(dev_branch_name,
                                                                                                 master_branch_name,
                                                                                                 current_branch))


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
            "Cannot perform pre-release check because the module {} sub-test_data does not exist in the workspace {}!".format(
                module_name, workspace_path_str))
        return
    try:
        repo = git.Repo(module_path, search_parent_directories=True)
    except:
        logging.warning(
            "Cannot perform pre-release check because the module {} sub-test_data in the workspace {} is not a git repository!".format(
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
                repo.git.fetch("--all")
                remote_br_name = get_remote_branch_name(repo, branch_name)
                if remote_br_name:
                    repo.git.checkout(remote_br_name)
                    repo.git.pull()
                    logging.info(
                        "Checked out branch {} and pulled updates in the git repo {}".format(branch_name, path))
                else:
                    logging.info("The git repo {} does not have a branch '{}'".format(path, branch_name))


def check_status(workspace_path_str):
    root_path = pathlib.Path(workspace_path_str)

    for path in root_path.iterdir():
        if path.is_dir():
            try:
                repo = git.Repo(path, search_parent_directories=True)
            except:
                logging.debug("**** path {0} was found to not be a git repo. ********".format(path))
                continue
            if repo:
                repo.git.fetch("--all")

                current_branch = repo.head.ref.name
                remote_branch = "origin/{0}".format(current_branch)
                commits_behind = [c for c in repo.iter_commits('{0}..{1}'.format(current_branch, remote_branch))]
                num_behind = len(commits_behind)
                commits_ahead = [c for c in repo.iter_commits('{0}..{1}'.format(remote_branch, current_branch))]
                num_ahead = len(commits_ahead)
                ahead_str = "\033[93m{} commits ahead remote\033[0m".format(num_ahead) if num_ahead > 0 else ""
                behind_str = "\033[93m{} commits behind remote\033[0m".format(num_behind) if num_behind > 0 else ""
                if num_ahead == 0 and num_behind == 0:
                    ahead_str = "\033[92mUp to date with remote\033[0m"
                logging.info(
                    "\033[94m{:<40}\033[0m on branch: {:<25}   {}   {}".format(path.name, current_branch, ahead_str,
                                                                               behind_str))
                if repo.is_dirty():
                    changed_files = [item.a_path for item in repo.index.diff(None)]
                    logging.info("\tModified local files:")
                    for file in changed_files:
                        logging.info("\t\t\033[95m{}\033[0m".format(file))
                root_logger = logging.getLogger()
                if root_logger.isEnabledFor(logging.DEBUG) and num_ahead > 0:
                    for commit in commits_ahead:
                        logging.debug(
                            "\tCommit ahead: {}  {}  {}".format(datetime.datetime.fromtimestamp(commit.committed_date),
                                                                commit.author, commit.message))
                if root_logger.isEnabledFor(logging.DEBUG) and num_behind > 0:
                    for commit in commits_behind:
                        logging.debug(
                            "\tCommit behind: {}  {}  {}".format(datetime.datetime.fromtimestamp(commit.committed_date),
                                                                 commit.author, commit.message))

                logging.info(" ")
            else:
                logging.debug("path {} is not a git repo.\n".format(path))


def steps_to_merge_forward(path, to_branch_name, from_branch_name, force_rebase=None):
    try:
        repo = git.Repo(path, search_parent_directories=True)
    except:
        logging.debug("**** path {0} was found to not be a git repo. ********".format(path))
        return

    if repo:
        if repo.is_dirty():
            logging.warning("Not going to try to merge when there are changes not committed.")
            return

        if not repo.index.unmerged_blobs():
            current_branch = repo.head.ref.name
            if current_branch != to_branch_name:
                logging.info("git checkout {}".format(to_branch_name))
                repo.git.checkout(to_branch_name)

            try:
                if force_rebase:
                    logging.info("git merge {}".format(from_branch_name))
                    repo.git.merge(from_branch_name, "-X patience")
                else:
                    logging.info("git merge {}".format(from_branch_name))
                    repo.git.merge(from_branch_name)
            except git.exc.GitCommandError as gce:
                logging.warning(
                    "GitCommandError thrown while trying to merge {} into {}".format(from_branch_name, to_branch_name),
                    gce)

        conflicted_files = []
        unmerged_blobs = repo.index.unmerged_blobs()
        if unmerged_blobs:
            # We're really interested in the stage each blob is associated with.
            # So we'll iterate through all of the paths and the entries in each value
            # list, but we won't do anything with most of the values.
            for (path, list_of_blobs) in unmerged_blobs.items():
                for (stage, blob) in list_of_blobs:
                    # Now we can check each stage to see whether there were any conflicts
                    if stage != 0:
                        conflicted_files.append(path)
        else:
            logging.debug("No unmerged files.")

        if conflicted_files:
            logging.info(
                "Please resolve the following files, add them to the commit, and then run the same command for this script again to complete the merge")
            for f in conflicted_files:
                logging.info("\t- {}".format(f))
            return
        else:
            logging.debug("No conflicting files.")

        if len(repo.index.diff("HEAD")) > 0:
            logging.info("need to git commit")
            # repo.index.commit()
        else:
            logging.debug("No differences with HEAD, so no need to commit ")

        commit_messages = repo.git.log('origin/{0}..{0}'.format(to_branch_name), '--oneline')
        # If no commit messages, then the local branch is up to date with the remote branch
        num_commits = len(commit_messages.splitlines()) > 0 if commit_messages else 0
        if num_commits > 0:
            logging.info("git push because need to push {} commits to remote".format(num_commits))
            repo.remotes.origin.push()
        else:
            logging.debug("No differences with remote origin, so no need to push")
    else:
        logging.warning("Did not get a git repo from the path {}. ********".format(path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("-l", "--list_branches", dest="list_branches", nargs="?", default=None, const="*",
                              help="List the branches of all the git repos in the workspace")
    action_group.add_argument("-c", "--create_workspace", dest="create_workspace", action="store_true",
                              help="Create a new workspace")
    action_group.add_argument("-u", "--uptodate", dest="uptodate_master", action="store_true",
                              help="Check to see if the specified branch is up to date with the master branch for each repo in the workspace")
    action_group.add_argument("-p", "--pull", dest="pull_branches", action="store_true",
                              help="Pull the develop and master branches for all repos in the workspace")
    action_group.add_argument("-e", "--checkout", dest="checkout", action="store_true",
                              help="Checkout the specified branch in all git repos, if it already exists, in the workspace.")
    action_group.add_argument("-r", "--prerelease", dest="prerelease_check", action="store_true",
                              help="Perform pre-release check on the specified branch of the specified module")
    action_group.add_argument("-s", "--status", dest="status", action="store_true",
                              help="Display the git status for all repositories in the specified workspace.")
    action_group.add_argument("-x", "--xx_test", dest="xx_new_function", action="store_true",
                              help="testing functionality currently working on.")
    parser.add_argument("-w", "--workspace", dest="workspace",
                        help="Workspace path to check. Defaults to '{0}'.".format(environment.WORKSPACE_ROOT_ID),
                        default=environment.WORKSPACE_ROOT_ID)
    parser.add_argument("-y", "--python_workspace", dest="use_python_workspace", action="store_true",
                        help="Use the python workspace instead of the workspace argument.")
    parser.add_argument("-m", "--module", dest="module_name",
                        help="Module to use. Must be a sub test_data of the workspace test_data.", )
    parser.add_argument("-b", "--branch", dest="branch_name", default="develop",
                        help="Branch to compare to master branch or to checkout. Defaults to '%(default)s'.", )
    parser.add_argument("--parent_branch", dest="parent_branch_name", default="master",
                        help="Branch to compare against. Defaults to '%(default)s'.", )
    parser.add_argument("--repo", dest="repo_path",
                        help="Path to repository to use, instead of checking all repositories in a workspace.", )
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

    logging.getLogger("git").setLevel(logging.WARNING)

    workspace_path_str = environment.PYTHON_WORKSPACE_PATH if args.use_python_workspace else args.workspace

    if args.list_branches:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_list_branches")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)

        logging.info("Listing the branches for git repos in the workspace {}.\n\n".format(workspace_path_str))
        list_branches_in_workspace(workspace_path_str, args.list_branches)

    elif args.create_workspace:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_create_workspace")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)
        root_path = pathlib.Path(workspace_path_str)

        logging.info("Creating a new workspace in {}.\n\n".format(workspace_path_str))
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
                repo = None
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
                repo = None
                try:
                    repo = git.Repo(path, search_parent_directories=True)
                except:
                    logging.debug("**** path {0} was found to not be a git repo. ********".format(path))
                if repo:
                    logging.info(
                        "Checking to see if git repos in {} have their {} branch up to date with their master branch.\n\n".format(
                            workspace_path_str, args.branch_name))
                    logging.info("{:<40}  {:<20}  {:<20}  {:<20}  {:<20}  # Commits Ahead    # Commits Behind".format(
                        "Repository", "Master branch", "Date last commit", "Develop branch", "Date last commit", "#"))
                    compare_against_master_branch(path, repo, args.branch_name, args.parent_branch_name)
                else:
                    logging.warning("The repo path {} is not a valid git repo to check.".format(path))
            else:
                logging.warning("The repo path {} is does not exist or is not a test_data.".format(path))
        else:
            logging.info(
                "Checking to see if git repos in {} have their {} branch up to date with their master branch.\n\n".format(
                    workspace_path_str, args.branch_name))
            compare_against_master_branch_in_workspace(workspace_path_str, args.branch_name, args.parent_branch_name)

    elif args.prerelease_check:
        if not args.branch_name or not args.module_name:
            parser.error(
                "The branch name (-b <value> or --branch <value>) and module name (-m <value> or --module <value>) options are required to perform a pre-release check.")
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_prerelease_check")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)

        logging.info("Performing pre-release check on the {} branch of the {} module in the {} workspace.\n\n".format(
            args.branch_name, args.module_name, workspace_path_str))
        prerelease_check(workspace_path_str, args.branch_name, args.module_name)

    elif args.checkout:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_checkout")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)

        logging.info(
            "Checkout the {} branch of each git repo in the {} workspace if it exists.\n\n".format(args.branch_name,
                                                                                                   workspace_path_str))
        checkout_same_branch_in_workspace(workspace_path_str, args.branch_name)

    elif args.status:
        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_status")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)

        logging.info("Check the git status of all repos in the workspace {}.\n\n".format(workspace_path_str))
        check_status(workspace_path_str)

    elif args.xx_new_function:
        if not args.branch_name or not args.module_name:
            parser.error(
                "The branch name (-b <value> or --branch <value>) and module name (-m <value> or --module <value>) options are required to perform a pre-release check.")

        log_file_path = common_utils.get_log_file_path("~/reports", "git_tasks_merge_forward")
        common_utils.setup_logger_to_console_file(log_file_path, log_level)
        repo_path = pathlib.Path(workspace_path_str).joinpath(args.module_name)
        logging.info(
            "Attempting to merge/rebase the {} parent branch to the {} branch in the git repo in {}.\n\n".format(
                args.parent_branch_name, args.branch_name, repo_path))

        steps_to_merge_forward(repo_path, args.branch_name, args.parent_branch_name, force_rebase=args.force)

    logging.info('\n\nLog file: {}'.format(log_file_path))
    if args.open_output and log_file_path:
        common_utils.open_file_in_editor(log_file_path)
