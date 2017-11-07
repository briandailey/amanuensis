import click
import requests
import datetime

GITHUB_API_ROOT = 'https://api.github.com'
CREDENTIALS_FILE = ".token"

ZENHUB_CREDENTIALS_FILE = ".zenhubtoken"
ZENHUB_API_ROOT = 'https://api.zenhub.io'

# Automated description on milestones created with this tool.
AUTOMATED_DESCRIPTION = 'Automatically created by Amanuensis.'


class Amanuensis(object):
    """ Because we need state, we have an object in which to put it. """

    def __init__(org_slash_repo_name, start_date, end_date, *args, **kwargs):
        org, repo = org_slash_repo_name.split('/')
        self.org = org
        self.repo_name = repo_name
        self.start_date = start_date
        self.end_date = end_date

    @property
    def github_token(self):
        if not hasattr(self, '_github_token'):
            with open(CREDENTIALS_FILE, 'r') as fd:
                self._github_token = fd.readline().strip()  # Can't hurt to be paranoid
        return self._github_token

    @property
    def zenhub_token(self):
        if not hasattr(self, '_zenhub_token'):
            with open(ZENHUB_CREDENTIALS_FILE, 'r') as fd:
                self._zenhub_token = fd.readline().strip()  # Can't hurt to be paranoid
        return self._zenhub_token

    @property
    def github_headers(self):
        return {'Authorization':'token %s' % self.github_token}

    def get_closed_issues(self, org, repo_name, start_date, end_date):
        """ Return all issues from org/repo_name closed between start and end. """

        # There's no easy way to get this (like the search query syntax) for private repos.
        url = '{}/repos/{}/{}/issues'.format(GITHUB_API_ROOT, org, repo_name)
        params = {'since': start_date + 'T00:00:00Z', 'state': 'closed', 'sort': 'updated', 'direction': 'asc', 'per_page': 100}
        r = requests.get(url, params=params, headers=self.github_headers)

        start_date_ts = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        end_date_ts = datetime.datetime.strptime(end_date, '%Y-%m-%d')

        issues_returned = r.json()
        print("Found {} matching issues. Pairing down.".format(len(issues_returned)))
        matching_issues = []
        for issue in issues_returned:
            if 'pull_request' in issue:
                # We don't want pull requests and there's
                # not a great way to filter them out.
                continue
            closed_at = datetime.datetime.strptime(issue['closed_at'], '%Y-%m-%dT%H:%M:%SZ')
            if start_date_ts < closed_at < end_date_ts:
                matching_issues.append(issue)

        return matching_issues

    @property
    def repo_id(self):
        if not hasattr(self, '_repo_id')
            # First, we have to get the repo id.
            url = '{}/repos/{}/{}'.format(GITHUB_API_ROOT, org, repo_name)
            headers = {'Authorization':'token %s' % get_github_token()}

            r = requests.get(url, headers=headers)

            self._repo_id = r.json()['id']
        return self._repo_id

    def get_milestone(org, repo_name, start_date, end_date):
        """ Find the milestone number with the due date and name we are looking for.
        If it doesn't exist, return None. """

        matching_milestone = None
        automated_title = '{} - {}'.format(start_date, end_date)

        url = '{}/repos/{}/{}/milestones'.format(GITHUB_API_ROOT, org, repo_name)
        params = {'state': 'open', 'sort': 'due_on', 'direction': 'desc'}

        r = requests.get(url, params=params, headers=self.github_headers)

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
        url = '{}/repos/{}/{}/milestones'.format(GITHUB_API_ROOT, org, repo_name)
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
        url = '{}/repos/{}/{}/issues/{}'.format(GITHUB_API_ROOT, org, repo_name, issue_number)
        headers = {'Authorization':'token %s' % get_github_token()}
        data = {'milestone': milestone_number}

        requests.patch(url, json=data, headers=headers)

    @property
    def zenhub_headers(self):
        return {'X-Authentication-Token': self.zenhub_token}

    def set_milestone_start_date(org, repo_name, milestone_number, start_date):
        """ Set the milestone start date on the ZenHub side. """

        url = '{zenhub_api_root}/p1/repositories/{repo_id}/milestones/{milestone_number}/start_date'.format(
            zenhub_api_root=ZENHUB_API_ROOT,
            repo_id=self.repo_id,
            milestone_number=milestone_number)
        # Gotta add the time offset.
        data = {'start_date': start_date + 'T07:00:00Z'}
        r = requests.post(url, data=data, headers=self.zenhub_headers)
        return r


    def get_issue_zenhub_data(issue_number):
        pass

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
        set_milestone_start_date(org, repo_name, milestone['number'], start_date)
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



@click.command()
@click.option('--repo', '-r', required=True, multiple=True, help="org/repo, can provide > 1")
@click.option('--days', '-d', default=7, help="Days per sprint/cadence.")
@click.option('--date', help="Ending date for sprint (YYYY-MM-DD).", required=True)
@click.option('--token', '-t', help="Your GitHub token (optional, can place in .token file).")
@click.option('--force', '-f', is_flag=True, help="Even if the issues are attached to another milestone, move them.")
def cli(days, repo, token, date, force):
    amanuensis = Amanuensis()
    run(days, repo, token, date, force)


if __name__ == '__main__':
    cli()
