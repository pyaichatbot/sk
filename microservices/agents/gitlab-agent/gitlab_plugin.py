"""
GitLab Plugin for Semantic Kernel Agent
Based on Microsoft Semantic Kernel agent template approach
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import aiohttp
import json
import time
from enum import Enum


@dataclass
class GitLabSettings:
    """GitLab API configuration settings"""
    gitlab_url: str
    access_token: str
    api_version: str = "v4"


@dataclass
class GitLabProject:
    """GitLab project model"""
    id: int
    name: str
    path: str
    description: Optional[str] = None
    web_url: Optional[str] = None
    created_at: Optional[str] = None
    last_activity_at: Optional[str] = None


@dataclass
class GitLabIssue:
    """GitLab issue model"""
    id: int
    title: str
    description: Optional[str] = None
    state: str = "opened"
    author: Optional[Dict[str, Any]] = None
    assignee: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    web_url: Optional[str] = None
    labels: Optional[List[str]] = None


@dataclass
class GitLabMergeRequest:
    """GitLab merge request model"""
    id: int
    title: str
    description: Optional[str] = None
    state: str = "opened"
    author: Optional[Dict[str, Any]] = None
    assignee: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    web_url: Optional[str] = None
    source_branch: Optional[str] = None
    target_branch: Optional[str] = None


@dataclass
class GitLabUser:
    """GitLab user model"""
    id: int
    username: str
    name: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    web_url: Optional[str] = None


@dataclass
class GitLabCommit:
    """GitLab commit model"""
    id: str
    short_id: str
    title: str
    message: str
    author_name: str
    author_email: str
    authored_date: str
    committer_name: str
    committer_email: str
    committed_date: str
    created_at: str
    web_url: Optional[str] = None


@dataclass
class GitLabBranch:
    """GitLab branch model"""
    name: str
    merged: bool
    protected: bool
    default: bool
    developers_can_push: bool
    developers_can_merge: bool
    can_push: bool
    web_url: Optional[str] = None
    commit: Optional[Dict[str, Any]] = None


@dataclass
class GitLabTag:
    """GitLab tag model"""
    name: str
    message: Optional[str] = None
    commit: Optional[Dict[str, Any]] = None
    release: Optional[Dict[str, Any]] = None
    web_url: Optional[str] = None


@dataclass
class GitLabPipeline:
    """GitLab pipeline model"""
    id: int
    status: str
    ref: str
    sha: str
    web_url: str
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration: Optional[int] = None


class GitLabAPIError(Exception):
    """Custom exception for GitLab API errors"""
    def __init__(self, message: str, status_code: int = None, response_data: Dict = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class GitLabPlugin:
    """GitLab plugin for Semantic Kernel agents"""
    
    def __init__(self, settings: GitLabSettings):
        self.settings = settings
        self.base_url = f"{settings.gitlab_url}/api/{settings.api_version}"
        self.headers = {
            "Authorization": f"Bearer {settings.access_token}",
            "Content-Type": "application/json"
        }
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with retry logic and error handling"""
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(method, url, headers=self.headers, **kwargs) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 401:
                            raise GitLabAPIError("Unauthorized - check your access token", 401)
                        elif response.status == 403:
                            raise GitLabAPIError("Forbidden - insufficient permissions", 403)
                        elif response.status == 404:
                            raise GitLabAPIError("Resource not found", 404)
                        elif response.status == 429:
                            # Rate limited, wait and retry
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(self.retry_delay * (2 ** attempt))
                                continue
                            raise GitLabAPIError("Rate limited", 429)
                        else:
                            error_data = await response.json() if response.content_type == 'application/json' else {}
                            raise GitLabAPIError(
                                f"API request failed: {response.status}",
                                response.status,
                                error_data
                            )
            except aiohttp.ClientError as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    continue
                raise GitLabAPIError(f"Network error: {str(e)}")
        
        raise GitLabAPIError("Max retries exceeded")
    
    async def get_current_user(self) -> GitLabUser:
        """Get current authenticated user information"""
        data = await self._make_request("GET", f"{self.base_url}/user")
        return GitLabUser(
            id=data["id"],
            username=data["username"],
            name=data["name"],
            email=data.get("email"),
            avatar_url=data.get("avatar_url"),
            web_url=data.get("web_url")
        )
    
    async def get_project(self, project_id: str) -> GitLabProject:
        """Get project information by ID or path"""
        data = await self._make_request("GET", f"{self.base_url}/projects/{project_id}")
        return GitLabProject(
            id=data["id"],
            name=data["name"],
            path=data["path"],
            description=data.get("description"),
            web_url=data.get("web_url"),
            created_at=data.get("created_at"),
            last_activity_at=data.get("last_activity_at")
        )
    
    async def get_project_issues(
        self, 
        project_id: str, 
        state: str = "opened",
        labels: Optional[str] = None,
        assignee_id: Optional[int] = None,
        per_page: int = 20
    ) -> List[GitLabIssue]:
        """Get project issues with optional filtering"""
        params = {
            "state": state,
            "per_page": per_page
        }
        
        if labels:
            params["labels"] = labels
        if assignee_id:
            params["assignee_id"] = assignee_id
        
        data = await self._make_request("GET", f"{self.base_url}/projects/{project_id}/issues", params=params)
        return [
            GitLabIssue(
                id=issue["id"],
                title=issue["title"],
                description=issue.get("description"),
                state=issue["state"],
                author=issue.get("author"),
                assignee=issue.get("assignee"),
                created_at=issue.get("created_at"),
                updated_at=issue.get("updated_at"),
                web_url=issue.get("web_url"),
                labels=issue.get("labels", [])
            )
            for issue in data
        ]
    
    async def get_project_merge_requests(
        self,
        project_id: str,
        state: str = "opened",
        per_page: int = 20
    ) -> List[GitLabMergeRequest]:
        """Get project merge requests with optional filtering"""
        params = {
            "state": state,
            "per_page": per_page
        }
        
        data = await self._make_request("GET", f"{self.base_url}/projects/{project_id}/merge_requests", params=params)
        return [
            GitLabMergeRequest(
                id=mr["id"],
                title=mr["title"],
                description=mr.get("description"),
                state=mr["state"],
                author=mr.get("author"),
                assignee=mr.get("assignee"),
                created_at=mr.get("created_at"),
                updated_at=mr.get("updated_at"),
                web_url=mr.get("web_url"),
                source_branch=mr.get("source_branch"),
                target_branch=mr.get("target_branch")
            )
            for mr in data
        ]
    
    async def search_projects(self, search: str, per_page: int = 20) -> List[GitLabProject]:
        """Search for projects by name or description"""
        params = {
            "search": search,
            "per_page": per_page
        }
        
        data = await self._make_request("GET", f"{self.base_url}/projects", params=params)
        return [
            GitLabProject(
                id=project["id"],
                name=project["name"],
                path=project["path"],
                description=project.get("description"),
                web_url=project.get("web_url"),
                created_at=project.get("created_at"),
                last_activity_at=project.get("last_activity_at")
            )
            for project in data
        ]
    
    async def get_issue(self, project_id: str, issue_id: int) -> GitLabIssue:
        """Get specific issue details"""
        data = await self._make_request("GET", f"{self.base_url}/projects/{project_id}/issues/{issue_id}")
        return GitLabIssue(
            id=data["id"],
            title=data["title"],
            description=data.get("description"),
            state=data["state"],
            author=data.get("author"),
            assignee=data.get("assignee"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            web_url=data.get("web_url"),
            labels=data.get("labels", [])
        )
    
    async def get_merge_request(self, project_id: str, merge_request_id: int) -> GitLabMergeRequest:
        """Get specific merge request details"""
        data = await self._make_request("GET", f"{self.base_url}/projects/{project_id}/merge_requests/{merge_request_id}")
        return GitLabMergeRequest(
            id=data["id"],
            title=data["title"],
            description=data.get("description"),
            state=data["state"],
            author=data.get("author"),
            assignee=data.get("assignee"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            web_url=data.get("web_url"),
            source_branch=data.get("source_branch"),
            target_branch=data.get("target_branch")
        )
    
    async def get_project_commits(
        self,
        project_id: str,
        ref_name: str = "main",
        per_page: int = 20
    ) -> List[GitLabCommit]:
        """Get project commits for a specific branch or tag"""
        params = {
            "ref_name": ref_name,
            "per_page": per_page
        }
        
        data = await self._make_request("GET", f"{self.base_url}/projects/{project_id}/repository/commits", params=params)
        return [
            GitLabCommit(
                id=commit["id"],
                short_id=commit["short_id"],
                title=commit["title"],
                message=commit["message"],
                author_name=commit["author_name"],
                author_email=commit["author_email"],
                authored_date=commit["authored_date"],
                committer_name=commit["committer_name"],
                committer_email=commit["committer_email"],
                committed_date=commit["committed_date"],
                created_at=commit["created_at"],
                web_url=commit.get("web_url")
            )
            for commit in data
        ]
    
    async def get_project_branches(
        self,
        project_id: str,
        per_page: int = 20
    ) -> List[GitLabBranch]:
        """Get project branches"""
        params = {"per_page": per_page}
        
        data = await self._make_request("GET", f"{self.base_url}/projects/{project_id}/repository/branches", params=params)
        return [
            GitLabBranch(
                name=branch["name"],
                merged=branch["merged"],
                protected=branch["protected"],
                default=branch["default"],
                developers_can_push=branch["developers_can_push"],
                developers_can_merge=branch["developers_can_merge"],
                can_push=branch["can_push"],
                web_url=branch.get("web_url"),
                commit=branch.get("commit")
            )
            for branch in data
        ]
    
    async def get_project_tags(
        self,
        project_id: str,
        per_page: int = 20
    ) -> List[GitLabTag]:
        """Get project tags"""
        params = {"per_page": per_page}
        
        data = await self._make_request("GET", f"{self.base_url}/projects/{project_id}/repository/tags", params=params)
        return [
            GitLabTag(
                name=tag["name"],
                message=tag.get("message"),
                commit=tag.get("commit"),
                release=tag.get("release"),
                web_url=tag.get("web_url")
            )
            for tag in data
        ]
    
    async def get_project_pipelines(
        self,
        project_id: str,
        ref: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 20
    ) -> List[GitLabPipeline]:
        """Get project pipelines"""
        params = {"per_page": per_page}
        
        if ref:
            params["ref"] = ref
        if status:
            params["status"] = status
        
        data = await self._make_request("GET", f"{self.base_url}/projects/{project_id}/pipelines", params=params)
        return [
            GitLabPipeline(
                id=pipeline["id"],
                status=pipeline["status"],
                ref=pipeline["ref"],
                sha=pipeline["sha"],
                web_url=pipeline["web_url"],
                created_at=pipeline["created_at"],
                updated_at=pipeline["updated_at"],
                started_at=pipeline.get("started_at"),
                finished_at=pipeline.get("finished_at"),
                duration=pipeline.get("duration")
            )
            for pipeline in data
        ]
    
    async def get_pipeline(self, project_id: str, pipeline_id: int) -> GitLabPipeline:
        """Get specific pipeline details"""
        data = await self._make_request("GET", f"{self.base_url}/projects/{project_id}/pipelines/{pipeline_id}")
        return GitLabPipeline(
            id=data["id"],
            status=data["status"],
            ref=data["ref"],
            sha=data["sha"],
            web_url=data["web_url"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            duration=data.get("duration")
        )


# Plugin functions for Semantic Kernel
async def get_current_user(settings: GitLabSettings) -> GitLabUser:
    """Get current authenticated user"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_current_user()


async def get_project(project_id: str, settings: GitLabSettings) -> GitLabProject:
    """Get project information"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_project(project_id)


async def get_project_issues(
    project_id: str, 
    settings: GitLabSettings,
    state: str = "opened",
    labels: Optional[str] = None,
    assignee_id: Optional[int] = None,
    per_page: int = 20
) -> List[GitLabIssue]:
    """Get project issues"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_project_issues(
        project_id, state, labels, assignee_id, per_page
    )


async def get_project_merge_requests(
    project_id: str,
    settings: GitLabSettings,
    state: str = "opened",
    per_page: int = 20
) -> List[GitLabMergeRequest]:
    """Get project merge requests"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_project_merge_requests(project_id, state, per_page)


async def search_projects(search: str, settings: GitLabSettings, per_page: int = 20) -> List[GitLabProject]:
    """Search for projects"""
    plugin = GitLabPlugin(settings)
    return await plugin.search_projects(search, per_page)


async def get_issue(project_id: str, issue_id: int, settings: GitLabSettings) -> GitLabIssue:
    """Get specific issue"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_issue(project_id, issue_id)


async def get_merge_request(project_id: str, merge_request_id: int, settings: GitLabSettings) -> GitLabMergeRequest:
    """Get specific merge request"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_merge_request(project_id, merge_request_id)


async def get_project_commits(
    project_id: str,
    settings: GitLabSettings,
    ref_name: str = "main",
    per_page: int = 20
) -> List[GitLabCommit]:
    """Get project commits"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_project_commits(project_id, ref_name, per_page)


async def get_project_branches(
    project_id: str,
    settings: GitLabSettings,
    per_page: int = 20
) -> List[GitLabBranch]:
    """Get project branches"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_project_branches(project_id, per_page)


async def get_project_tags(
    project_id: str,
    settings: GitLabSettings,
    per_page: int = 20
) -> List[GitLabTag]:
    """Get project tags"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_project_tags(project_id, per_page)


async def get_project_pipelines(
    project_id: str,
    settings: GitLabSettings,
    ref: Optional[str] = None,
    status: Optional[str] = None,
    per_page: int = 20
) -> List[GitLabPipeline]:
    """Get project pipelines"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_project_pipelines(project_id, ref, status, per_page)


async def get_pipeline(project_id: str, pipeline_id: int, settings: GitLabSettings) -> GitLabPipeline:
    """Get specific pipeline"""
    plugin = GitLabPlugin(settings)
    return await plugin.get_pipeline(project_id, pipeline_id)
