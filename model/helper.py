from datetime import date, datetime, timedelta
from pathlib import Path
from tokenize import String
from typing import List
from os import getcwd
import yaml

with open(f'{getcwd()}/config.yaml', "r") as yamlfile:
    data = yaml.load(yamlfile, Loader=yaml.Loader)

datefmt = "%Y-%m-%d %H-%M-%S"
_disk_path = data['disk-path']
disk_path = Path(_disk_path)

def get_file_path(file):
    return (disk_path / file)

def helper_strtodate(x):
    if isinstance(x, str):
        x = datetime.strptime(x, datefmt)
    return x

def helper_datetostr(x):
    return x.strftime(datefmt)

# returns true if older target timestamp is older than X days
def last_updated_before(target, days): # returns true if not updated since X days
    if isinstance(target, str):
        target = helper_strtodate(target)
    return (datetime.now() - target) > timedelta(days)

def json_default(value):
    if isinstance(value, date): # json does not support
        return value.strftime(datefmt)
    else:
        return value.__dict__


def github_to_csv(csv_file: String, query):
    with open(csv_file, 'w') as f:  # You will need 'wb' mode in Python 2.x
        w = csv.DictWriter(f, query.projects[0].__dict__.keys())
        w.writeheader()
        for q in query.projects:
           info(q.__dict__)
           w.writerow(q.__dict__)

def github_from_csv(csv_file: String) -> List:
    my_repo = []
    csv.field_size_limit(sys.maxsize)

    with open(csv_file, 'r') as f:
        r = csv.DictReader(f)
        for row in r:
            my_repo.append(Repo(row))

    return my_repo


def queries_to_yaml(queries):
    return yaml.dump(queries)

