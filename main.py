import click
import requests
import datetime

CREDENTIALS_FILE=".token"

# Automated description on milestones created with this tool.
AUTOMATED_DESCRIPTION = 'Automatically created by Amanuensis.'


def get_github_token():
    token = ''
    with open(CREDENTIALS_FILE, 'r') as fd:
        token = fd.readline().strip()  # Can't hurt to be paranoid
    return token


def get_closed_issues(org, repo_name, start_date, end_date):
    """ Return all issues from org/repo_name closed between start and end. """

    # There's no easy way to get this (like the search query syntax) for private repos.
    url = 'https://api.github.com/repos/{}/{}/issues'.format(org, repo_name)
    params = {'since': start_date + 'T00:00:00Z', 'state': 'closed', 'sort': 'updated', 'direction': 'asc', 'per_page': 100}
    headers = {'Authorization':'token %s' % get_github_token()}

    r = requests.get(url, params=params, headers=headers)

    start_date_ts = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end_date_ts = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    issues_returned = r.json()
    print("Found {} matching issues. Pairing down.".format(len(issues_returned)))
    matching_issues = []
    for issue in issues_returned:
        if 'pull_request' in issue:
            # We don't want pull requests.
            continue
        closed_at = datetime.datetime.strptime(issue['closed_at'], '%Y-%m-%dT%H:%M:%SZ')
        if start_date_ts < closed_at < end_date_ts:
            matching_issues.append(issue)

    return matching_issues


def get_milestone(org, repo_name, start_date, end_date):
    """ Find the milestone number with the due date and name we are looking for.
    If it doesn't exist, return None. """

    matching_milestone = None
    automated_title = '{} - {}'.format(start_date, end_date)

    url = 'https://api.github.com/repos/{}/{}/milestones'.format(org, repo_name)
    params = {'state': 'open', 'sort': 'due_on', 'direction': 'desc'}
    headers = {'Authorization':'token %s' % get_github_token()}

    r = requests.get(url, params=params, headers=headers)

    # Note that if you set due_on to YYYY-MM-DDT00:00:00 you will actually
    # end up with due_on being 07:00:00 the day prior. So look for that!
    due_on = (datetime.datetime.strptime(end_date, '%Y-%m-%d') - datetime.timedelta(days=1)).strftime('%Y-%m-%d') + 'T07:00:00Z'

    for milestone in r.json():
        if milestone['due_on'] == due_on and \
            milestone['title'] == automated_title and \
            milestone['description'] == AUTOMATED_DESCRIPTION:
            matching_milestone = milestone

    return matching_milestone


def get_or_create_milestone(org, repo_name, start_date, end_date):
    milestone = get_milestone(org, repo_name, start_date, end_date)
    if not milestone:
        milestone = create_milestone(org, repo_name, start_date, end_date)
    return milestone

def create_milestone(org, repo_name, start_date, end_date):
    url = 'https://api.github.com/repos/{}/{}/milestones'.format(org, repo_name)
    data = {
        'title': '{} - {}'.format(start_date, end_date),
        'state': 'open',
        'description': AUTOMATED_DESCRIPTION,
        'due_on': end_date + 'T00:00:00Z',
    }
    headers = {'Authorization':'token %s' % get_github_token()}

    r = requests.post(url, json=data, headers=headers)

    return r.json()


def set_issue_milestone(org, repo_name, issue_number, milestone_number):
    url = 'https://api.github.com/repos/{}/{}/issues/{}'.format(org, repo_name, issue_number)
    headers = {'Authorization':'token %s' % get_github_token()}
    data = {'milestone': milestone_number}

    requests.patch(url, json=data, headers=headers)


@click.command()
@click.option('--repo', '-r', required=True, multiple=True, help="org/repo, can provide > 1")
@click.option('--days', '-d', default=7, help="Days per sprint/cadence.")
@click.option('--date', help="Ending date for sprint (YYYY-MM-DD).", required=True)
@click.option('--token', '-t', help="Your GitHub token (optional, can place in .token file).")
@click.option('--force', '-f', is_flag=True, help="Even if the issues are attached to another milestone, move them.")
def run(days, repo, token, date, force):

    # Get start and end date.
    end_date = datetime.datetime.strptime(date, '%Y-%m-%d')
    start_date = end_date - datetime.timedelta(days=days)

    # Str them to a format GitHub expects.
    end_date = end_date.strftime('%Y-%m-%d')
    start_date = start_date.strftime('%Y-%m-%d')

    for org_repo in repo:
        org, repo_name = org_repo.split('/')
        milestone = get_or_create_milestone(org, repo_name, start_date, end_date)
        print("Using Milestone {}: {}".format(milestone['number'], milestone['title']))
        closed_issues = get_closed_issues(org, repo_name, start_date, end_date)
        print("Found {} issues closed between {} and {}.".format(len(closed_issues), start_date, end_date))
        for issue in closed_issues:
            if not issue['milestone'] or force:
                if issue['milestone'] and issue['milestone']['number'] == milestone['number']:
                    # already in this milestone.
                    continue

                print("{} - {} - {}".format(issue['number'], issue['title'], issue['html_url']))
                set_issue_milestone(org, repo_name, issue['number'], milestone['number'])


if __name__ == '__main__':
    run()
