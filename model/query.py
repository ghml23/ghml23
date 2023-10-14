from datetime import datetime, date
from logging import info, debug

import yaml

from model.helper import get_file_path, helper_datetostr, last_updated_before
from model.repo import Repo
from typing import List

class Query:
    query = None
    sort = None
    date_from = None
    date_to = None
    active = True # if query is to large, it might needs to be extended and set inactive
    repo_count = 0
    projects = [] # type: List[Repo]
    unique_projects = []

    def __init__(self, query, sort, date_from, date_to, active, repo_count):
        self.query = query
        self.sort = sort
        self.date_from = date_from
        self.date_to = date_to
        self.active = active
        self.repo_count = repo_count
        self.query_date: date = helper_datetostr(datetime.now())
        self.repo_fetched = 0
        self.crawl_last_complete_run = "1970-01-01 00-00-00"
        self.crawl_last_complete_target = 0

    def last_updated_before(self, days):
        return last_updated_before(self.crawl_last_complete_run, days)

    def add_last_run(self, dt, target):
        debug(f'adding last run {dt} target {target}')
        if isinstance(dt, date):
            dt = helper_datetostr(dt)
        self.crawl_last_complete_run = dt
        self.crawl_last_complete_target = target

    def get_search_str(self):
        return f'{self.query} created:{self.date_from}..{self.date_to}'

    def get_len_projects(self):
        return len(self.projects)

    def get_len_unique_projects(self):
        return len(self.unique_projects)

    def to_string(self):
        #Query('monitoring security in:readme,name,description stars:>1 forks:>0 followers:>1 fork:true', 'updated', '2000-01-01', '2024-01-01'),
        return f"Query('{self.query}', '{self.sort}', '{self.date_from}', '{self.date_to}', {self.active}, {self.repo_count}),"

    @staticmethod
    def queries_to_yaml_disk(data, filename='queries.yml'):
        info(f'Dumping queries to disk: {filename}')
        with open(get_file_path(filename), 'w') as f:
            yaml.dump(data, f)

    @staticmethod
    def queries_from_yaml_disk(filename='queries.yml'):
        info(f'Fetching queries from disk: {filename}')
        queries = []
        with open(get_file_path(filename), 'r') as f:
            data = yaml.load_all(f, Loader=yaml.Loader)
            for x in data:
                data = x


        return data