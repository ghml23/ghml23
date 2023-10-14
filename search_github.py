import time
from datetime import datetime, timedelta
from logging import info, debug, error
import copy

import backoff as backoff
import requests
from github import Github

from model.query import Query
from model.repo import Repo

from typing import List
from github.GithubException import RateLimitExceededException

# set sparereq level accordingly to save requests to github API as it is rate limited
#    * 0 ... 0 requests per project
#    * 1 ... 1 requests per project
#    * 2 ... 4 requests per project
#    * 3 ... 7 requests per project

def get_middle_of_date(a, b):
    d1 = datetime.strptime(a, "%Y-%m-%d")
    d2 = datetime.strptime(b, "%Y-%m-%d")
    return d1.date() + (d2 - d1) / 2

def split_query(query):
    # query is to large, extending query to set new from and to date
    nq1 = copy.copy(query)
    nq2 = copy.copy(query)
    new_date = get_middle_of_date(query.date_from, query.date_to)
    nq1.date_to = new_date.strftime("%Y-%m-%d")
    nq2.date_from = (new_date + timedelta(days=1)).strftime("%Y-%m-%d")
    return [nq1, nq2]

@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_time=300)
def run_github_query(g: Github, query):
    try:
        info(f'Running github search query {query.get_search_str()}')
        github_search = g.search_repositories(query=query.get_search_str(), sort=query.sort)
        query.repo_count = github_search.totalCount
        info(f'"{query.query}" returned {query.repo_count} projects')
    except RateLimitExceededException as e:
        info("Hitting rate limit, sleeping and appending query to list of queries")
        debug(e.data)
        time.sleep(10)
        github_search = run_github_query(g, query)

    return github_search

def extend_query_list(g: Github, queries: List[Query]) -> List[Query]:
    for query in queries:
        if not query.active:
            continue

        run_github_query(g, query)

        # if query returns more than 1000 repos, we have to split it
        if query.repo_count >= 1000:
            queries.extend(split_query(query))
            query.active = False
            info(f'Deactivating github search query {query.get_search_str()} because it returns more than 1000 results')
            # to not run into secondary rate limits (comp. heavy operations) we need to slow down this proccess
            continue

    return queries

def query_list_complete(queries):
    for query in queries:
        if query.active and query.repo_count >= 1000:
            return False

    return True

def check_rate_limit_and_wait(g):
    #RateLimit(core=Rate(reset=2022-07-04 17:15:41, remaining=4895, limit=5000))
    rlimit = g.get_rate_limit()
    if rlimit.core.remaining < 50:
        info('Rate limit almost reached, waiting till we have new credits')
        time.sleep(60)
        check_rate_limit_and_wait(g)

# days = 7 # max age of repo data
def query_github(g: Github, queries: List[Query], spare_req: int = 5, days: int = 7) -> List[Query]:
    Repo.crawl_spare_req = spare_req # set limitation to save api requests

    # re run with just active queries
    for query in queries:
        if not query.active:
            continue

        if not (query.last_updated_before(days) or query.crawl_last_complete_target < Repo.crawl_spare_req):
            info(f'Query {query.query} was finished max {days} ago with higher or same crawl detail target, skipping ...')
            continue

        info(f'Running {query.query}')

        # query every repo
        # test if repo exists in config file
        # if so - are there any values missing which would be check now?
        for repo in run_github_query(g, query):
            wr_to_disk = False
            check_rate_limit_and_wait(g)
            repo_obj = Repo(repo)

            if repo_obj.exists_on_disk():

                repo_on_disk = repo_obj.from_disk()
                # if repo on disk is not updates since X days, or crawl spare req is now higher than the one on disk
                if not (repo_on_disk.last_updated_before(days) or repo_on_disk.crawl_last_spare_req < Repo.crawl_spare_req):
                    info(f'Repo {repo_obj.name} exists on disk and is up to date (max {days} days old) with crawl target {repo_on_disk.crawl_last_spare_req} now {Repo.crawl_spare_req}')
                    repo_obj = repo_on_disk
                else:
                    info(f'Updating repo {repo_obj.name}, since it is older than {days} or more infos are requested {Repo.crawl_spare_req} vs {repo_on_disk.crawl_last_spare_req}')
                    repo_obj.crawl_created = repo_on_disk.crawl_created # copy repo updated
                    repo_obj.search_queries = repo_on_disk.search_queries # copy search query
                    try:
                        wr_to_disk = repo_obj.fetch_additional_data(repo) # fetch infos and set flag if obj has changed
                    except Exception as e:
                        error(f"could not fetch additional data of {repo_obj.name} with {e}")
            else:
                info(f'Fetching new repo {repo_obj.name} with detail {Repo.crawl_spare_req} to disk')
                try:
                    wr_to_disk = repo_obj.fetch_additional_data(repo) # fetch infos and set flag if obj has changed
                except Exception as e:
                    error(f"could not fetch additional data of {repo_obj.name} with {e}")

            wr_to_disk = repo_obj.add_search_query(query.get_search_str()) or wr_to_disk  # add query and set flag if obj has changed

            if wr_to_disk:
                repo_obj.to_disk()

            query.projects.append(repo_obj)

        info(f'"{query.query}" returned {query.repo_count} projects, fetched a total of {len(query.projects)} projects')
        query.add_last_run(datetime.now(), Repo.crawl_spare_req)
        Query.queries_to_yaml_disk(queries)

    return queries

