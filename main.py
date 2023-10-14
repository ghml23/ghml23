from github import Github
import logging
from search_github import query_github, query_list_complete, extend_query_list
from model.helper import data
from model.query import Query

logging.basicConfig(level=logging.INFO)
logging.getLogger('backoff').addHandler(logging.StreamHandler())

g = Github(per_page=10000, login_or_token=data['gh-token'])
# add queries here, do not use the created in the search string, as this will be generated from the date vals given
queries = [Query(q['query-string'], q['search-type'], q['from'], q['to'], q['active'], 0) for q in data['queries']]
sub_queries = []

def build_list_of_subqueries(queries):
    queries = extend_query_list(g, queries)
    while not query_list_complete(queries):
        queries = extend_query_list(g, queries)

    return queries

# we need to create the list of queries first
def on_first_run():
    sub_queries = build_list_of_subqueries(queries)  # this needs to be done when query lists are empty yet
    Query.queries_to_yaml_disk(sub_queries) # this is how we write them to disk

# quickfix: uncomment this on first run
#on_first_run()
sub_queries = Query.queries_from_yaml_disk()

total_repo_cnt = 0
query_cnt = 0
for q in sub_queries:
    print(q.to_string())
    if q.active:
        total_repo_cnt += q.repo_count
        query_cnt += 1

print(f'total count of {query_cnt} queries and {total_repo_cnt}')
query_github(g, sub_queries, 4, days=30)
