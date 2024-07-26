import base64
from datetime import datetime, date, timedelta
import itertools
import json
import re
from typing import Dict, Union

from logging import debug, info, warn, warning

import backoff
import github
import requests
import yaml
from bs4 import BeautifulSoup
from github.Repository import Repository

from model.helper import helper_strtodate, get_file_path, json_default, disk_path, last_updated_before

import urllib3
http = urllib3.PoolManager()

# todo implement rate limiting https://github.com/PyGithub/PyGithub/issues/1319

class Repo:
    crawl_spare_req = True
    stars: int

    pushed: date = None
    created: date = None
    crawl_created: date = None
    crawl_last_updated: date = None

    def __init__(self, repository: Union[Repository, Dict]):
        """

        :type repository: Repository
        """
        if isinstance(repository, Dict):
            self.__dict__.update(repository)
            return

        self.name = repository.full_name
        self.isfork = repository.fork
        #self.org = repository.organization
        #self.owner = repository.owner
        self.stars = repository.stargazers_count
        self.archived = repository.archived
        self.commits = -1
        #self.watcher = repository.get_watchers().totalCount if Repo.sparereq >= 1 else repository.watchers_count
        self.watcher = repository.watchers_count # this is broken, also with get_watchers always exactly the same number count as stars
        self.license = -1
        self.releases = -1
        self.forks = repository.forks_count # repository.get_forks().totalCount
        self.pushed: date = repository.pushed_at
        self.created: date = repository.created_at
        self.wiki = repository.has_wiki
        self.downloads = repository.has_downloads
        self.open_issues = repository.open_issues_count
        self.open_issues_s30d = -1
        self.open_issues_b30d = -1
        #self.labels = [l.name for l in repository.get_labels()] #'labels': ['bug', 'documentation', 'duplicate', 'enhancement', 'good first issue', 'help wanted', 'invalid', 'question', 'wontfix']
        self.topics = -1
        self.about = repository.description
        self.language = repository.language
        self.languages = -1
        self.size = repository.size
        self.url = repository.html_url
        self.contributors = -1
        self.content_url = f'https://raw.githubusercontent.com/{repository.full_name}/{repository.default_branch}'
        self.url = f'https://github.com/{self.name}'
        self.readme = -1
        self.tree = -1
        self.crawl_created: date = datetime.now()
        self.crawl_last_updated: date = datetime.now()
        self.crawl_last_spare_req = Repo.crawl_spare_req
        self.search_queries = []


        # self.topic = repository.topic TODO
        # self.pull_requests = repository.pull TODO

    #returns true if data was fetched
    @backoff.on_exception(backoff.expo,
                          requests.exceptions.RequestException,
                          max_time=300)
    def fetch_additional_data(self, repo):
        #print(repo.raw_data)
        #0 is just a index without any add requests
        data_fetched = False
        if self.crawl_spare_req >= 1:
            self.tree = Repo.get_tree(repo)
            self.readme = Repo.get_readme(repo)
            self.languages = repo.get_languages()
            self.topics = repo.get_topics()
            data_fetched = True
        if self.crawl_spare_req >= 2:
            self.commits = repo.get_commits().totalCount
            self.contributors = repo.get_contributors().totalCount
            data_fetched = True
        if self.crawl_spare_req >= 3:
            try:
                self.license = repo.get_license().license.name
            except github.GithubException:
                self.license = None
            self.releases = repo.get_releases().totalCount
            data_fetched = True
        if self.crawl_spare_req >= 4:
            self.open_issues = repo.get_issues(state='open').totalCount
            self.open_issues_s30d = repo.get_issues(state='open', since=(datetime.now() - timedelta(30))).totalCount
            self.open_issues_b30d = self.open_issues - self.open_issues_s30d
            data_fetched = True

        return data_fetched
        # stargazers https://api.github.com/repos/newrelic/newrelic-ruby-agent/stargazers?per_page=10000&page=2
        # contributors ... issues with pagination, this is not realiable

    @staticmethod
    def get_tree(repo):
        try:
            return [p.path for p in repo.get_git_tree(repo.get_branch(branch=repo.raw_data['default_branch']).commit.sha).tree]
        except Exception as e:
            warning(f'Could not fetch tree for {repo.name}: {e.data}')
            return -1

    @staticmethod
    def get_readme(repo):
        try:
            return base64.b64decode(repo.get_readme().content).decode('utf-8')
        except Exception as e:
            warning(f'Could not fetch readme for {repo.name}: {e.data}')
            return -1

    # returns true if query was added
    def add_search_query(self, query):
        if query not in self.search_queries:
            self.search_queries.append(query)
            return True
        return False

    def last_updated_before(self, days): # returns true if not updated since X days
        return last_updated_before(self.crawl_last_updated, days)

    def to_disk(self):
        debug(f'Writing {self.name} changes to disk {get_file_path(self.get_filename())}')
        disk_path.mkdir(parents=True, exist_ok=True)
        with open(get_file_path(self.get_filename()), "w") as write_file:
            write_file.write(self.to_json())

    def exists_on_disk(self):
        return get_file_path(self.get_filename()).is_file()

    def from_disk(self):
        with open(get_file_path(self.get_filename())) as fq:
            fd = json.load(fq)
        return Repo(fd)


    def get_filename(self):
        return re.sub(r'[\\/*?:"<>|]', "_", self.name) + '.json'

    def _old_get_readme(self):

        #possible_readmes = [f'{a}.{b}' for a, b in itertools.product(['README', 'readme', 'Readme'],['md', 'MD', 'txt', 'TXT', 'adoc', 'asciidoc', 'markdown'])]
        #possible_readmes.extend(['README', 'readme', 'Readme'])

        r = re.compile("")
        print(self.tree)
        possible_readmes = ['test']
        for possible_readme in possible_readmes:
            readme = http.request('GET', f'{self.content_url}/{possible_readme}')
            if readme.status == 404:
                self.readme_url = ''
            elif readme.status == 200:
                self.readme_url = f'{self.content_url}/{possible_readme}'
                self.readme = readme.data.decode('utf-8') # try decoding as utf-8; or save content_type header
                break
        if self.readme == -1:
            warning(f'no readme found for {self.url}')

    def to_json(self):
        return json.dumps(self, default=json_default)




def random():
    # search repositories based on number of issues with good-first-issues (https://github.blog/2020-01-22-how-we-built-good-first-issues/)
    repositories = g.search_repositories(query='good-first-issues:>3')

    for repo in repositories:
        print(repo)

    # get repo topics
    repo.get_topics()

    # get ocunt of stars
    repo.stargazers_count

    # get list of open issues
    open_issues = repo.get_issues(state='open')
    for issue in open_issues:
        print(issue)

    # top 10 referrers over 14 days
    contents = repo.get_top_referrers()
    print(contents)

    # most pop contents over 14 days
    contents = repo.get_top_paths()
    print(contents)

    # get clones and breakdown for 14 days
    contents = repo.get_clones_traffic()
    contents = repo.get_clones_traffic(per="week")
    print(contents)

    # get nubmer of views and breakdown for 14 days
    contents = repo.get_views_traffic()
    contents = repo.get_views_traffic(per="week")
    print(contents)

    # get commit date
    commit = repo.get_commit(sha=sha)
    print(commit.commit.author.date)

    # get milestone list
    open_milestones = repo.get_milestones(state='open')
    for milestone in open_milestones:
        print(milestone)