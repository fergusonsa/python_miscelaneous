import datetime

import git

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

def get_diffs(repo, tagName):
    git_diffs = repo.head.commit.diff(tagName)
    diffs = [{"file": d.a_path, "change_type": d.change_type } for d in git_diffs]
    return diffs

def get_logs(repo, branch=None, tagName=None):
    if !branch:
        branch = repo.head.ref.name
    if !tagName:
        tagName = repo.tags[-1].name
        
    git = git.Repo(repo.working_dir)
    logs = repo.log('%s..%s' % (tagName, branch))
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
    repoPath = "/cygdrive/c/dev/hague/new_workspace/cipo-ec-id-filing"
    
    r = git.Repo(repoPath)
    r.fetch()

    currentBranch = r.head.ref.name
    
    # Get the last release tag
    lastReleaseTag = r.tags[-1]
    lastReleaseTagName = lastReleaseTag.name
    tag_date = datetime.datetime.fromtimestamp(lastReleaseTag.tag.tagged_date)

    diffs = r.head.commit.diff(lastReleaseTagName)

    
if __name__ == "__main__":
    create_release_log()