"""
GitHub Skill - GitHub operations via gh CLI
"""
import json
import subprocess
import os
from typing import Dict, List, Any, Optional


def run_gh(args: List[str]) -> Dict[str, Any]:
    """Run gh command and return structured result"""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            timeout=60
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "Command timed out"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def run_git(args: List[str], cwd: str = None) -> Dict[str, Any]:
    """Run git command"""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=cwd
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def get_issue(owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
    """Get issue details"""
    result = run_gh(["issue", "view", str(issue_number), "--repo", f"{owner}/{repo}", "--json", "title,body,state,labels,assignees,createdAt,updatedAt"])
    if result["status"] == "success":
        try:
            issue_data = json.loads(result["stdout"])
            return {"status": "success", "issue": issue_data}
        except json.JSONDecodeError:
            return {"status": "failed", "error": "Failed to parse issue JSON"}
    return result


def create_branch(branch_name: str, base_branch: str = "main") -> Dict[str, Any]:
    """Create and checkout new branch"""
    # Fetch latest
    run_git(["fetch", "origin"])
    # Create branch
    result = run_git(["checkout", "-b", branch_name, f"origin/{base_branch}"])
    if result["status"] == "success":
        return {"status": "success", "branch": branch_name, "base": base_branch}
    return result


def commit_changes(message: str, files: List[str] = None) -> Dict[str, Any]:
    """Stage and commit changes"""
    files = files or ["."]
    # Stage files
    for f in files:
        result = run_git(["add", f])
        if result["status"] == "failed":
            return result
    # Commit
    result = run_git(["commit", "-m", message])
    if result["status"] == "success":
        # Get commit hash
        hash_result = run_git(["rev-parse", "HEAD"])
        commit_hash = hash_result["stdout"].strip() if hash_result["status"] == "success" else None
        return {"status": "success", "message": message, "commit_hash": commit_hash}
    return result


def push_branch(branch_name: str, force: bool = False) -> Dict[str, Any]:
    """Push branch to origin"""
    args = ["push", "origin", branch_name]
    if force:
        args.insert(1, "--force")
    result = run_git(args)
    if result["status"] == "success":
        return {"status": "success", "branch": branch_name, "pushed": True}
    return result


def create_pr(title: str, body: str, base_branch: str = "main", head_branch: str = None, draft: bool = False) -> Dict[str, Any]:
    """Create a pull request"""
    args = ["pr", "create", "--title", title, "--body", body, "--base", base_branch]
    if head_branch:
        args.extend(["--head", head_branch])
    if draft:
        args.append("--draft")
    
    result = run_gh(args)
    if result["status"] == "success":
        # Parse PR URL from output
        pr_url = result["stdout"].strip()
        return {"status": "success", "pr_url": pr_url, "title": title}
    return result


def get_pr_status(pr_number: int) -> Dict[str, Any]:
    """Get PR status and checks"""
    result = run_gh(["pr", "view", str(pr_number), "--json", "state,mergeable,statusCheckRollup,reviewDecision,url"])
    if result["status"] == "success":
        try:
            pr_data = json.loads(result["stdout"])
            return {"status": "success", "pr": pr_data}
        except json.JSONDecodeError:
            return {"status": "failed", "error": "Failed to parse PR JSON"}
    return result


# Handlers
def get_issue_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    return get_issue(
        owner=args.get("owner", ""),
        repo=args.get("repo", ""),
        issue_number=args.get("issue_number", 0)
    )


def create_branch_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    return create_branch(
        branch_name=args.get("branch_name", ""),
        base_branch=args.get("base_branch", "main")
    )


def commit_changes_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    return commit_changes(
        message=args.get("message", ""),
        files=args.get("files", ["."])
    )


def push_branch_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    return push_branch(
        branch_name=args.get("branch_name", ""),
        force=args.get("force", False)
    )


def create_pr_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    return create_pr(
        title=args.get("title", ""),
        body=args.get("body", ""),
        base_branch=args.get("base_branch", "main"),
        head_branch=args.get("head_branch"),
        draft=args.get("draft", False)
    )


def get_pr_status_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    return get_pr_status(args.get("pr_number", 0))


if __name__ == "__main__":
    # Test
    result = get_issue_handler({"owner": "test", "repo": "test", "issue_number": 1})
    print(json.dumps(result, indent=2))