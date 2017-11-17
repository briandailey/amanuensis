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

    def __init__(self,
            org_slash_repo_name,
            start_date,
            end_date,
            force_milestone_association=False,
            dry_run=False,
            github_token=None,
            zenhub_token=None,
            *args, **kwargs):
        org, repo_name = org_slash_repo_name.split('/')
        self.org = org
        self.repo_name = repo_name
        self.start_date = start_date
        self.end_date = end_date
        self.force_milestone_association = force_milestone_association
        self.dry_run = dry_run
        if github_token:
            self._github_token = github_token
        if zenhub_token:
            self._zenhub_token = zenhub_token

        self.closed_issues = self.get_closed_issues()
    def __call__(self):
        # Get the milestone for this.
        self.milestone = self.get_or_create_milestone()
        self.milestone_number = self.milestone['number']
        total_points = 0

        # Set the milestone start date on the ZenHub side.
        self.set_milestone_start_date()
        print("Using Milestone {}: {}".format(self.milestone['number'], self.milestone['title']))

        self.closed_issues = self.get_closed_issues()
        print("Found {} issues closed between {} and {}.".format(len(self.closed_issues), self.start_date, self.end_date))
        for issue in self.closed_issues:
            if issue['milestone'] and issue['milestone']['number'] == self.milestone_number:
                # already in this milestone.
                print("#{} was already in milestone.".format(issue['number']))
            elif not issue['milestone'] or self.force_milestone_association:
                print("#{} - {} - {}".format(issue['number'], issue['title'], issue['html_url']))
                self.set_issue_milestone(self.milestone['number'], issue['number'])
            else:
                print("#{} is assigned to another milestone ({}).".format(issue['number'], issue['milestone']['number']))

            zenhub_issue_data = self.get_issue_zenhub_data(issue['number'])
            if not 'estimate' in zenhub_issue_data:
                print("Warning: Issue #{} has no points estimate!".format(issue['number']))
            else:
                total_points += zenhub_issue_data['estimate']['value']

        print("Total points: {}".format(total_points))

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

    def get_closed_issues(self):
        """ Return all issues from org/repo_name closed between start and end. """

        # There's no easy way to get this (like the search query syntax) for private repos.
        url = '{}/repos/{}/{}/issues'.format(GITHUB_API_ROOT, self.org, self.repo_name)
        params = {'since': self.start_date + 'T00:00:00Z', 'state': 'closed', 'sort': 'updated', 'direction': 'asc', 'per_page': 100}
        r = requests.get(url, params=params, headers=self.github_headers)

        start_date_ts = datetime.datetime.strptime(self.start_date, '%Y-%m-%d')
        end_date_ts = datetime.datetime.strptime(self.end_date, '%Y-%m-%d')

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
        if not hasattr(self, '_repo_id'):
            # First, we have to get the repo id.
            url = '{}/repos/{}/{}'.format(GITHUB_API_ROOT, self.org, self.repo_name)
            r = requests.get(url, headers=self.github_headers)

            self._repo_id = r.json()['id']
        return self._repo_id

    def get_milestone(self):
        """ Find the milestone number with the due date and name we are looking for.
        If it doesn't exist, return None. """

        matching_milestone = None
        automated_title = '{} - {}'.format(self.start_date, self.end_date)

        url = '{}/repos/{}/{}/milestones'.format(GITHUB_API_ROOT, self.org, self.repo_name)
        params = {'state': 'open', 'sort': 'due_on', 'direction': 'desc'}

        r = requests.get(url, params=params, headers=self.github_headers)

        # Note that if you set due_on to YYYY-MM-DDT00:00:00 you will actually
        # end up with due_on being 07:00:00 the day prior. So look for that!
        due_on = (datetime.datetime.strptime(self.end_date, '%Y-%m-%d') - datetime.timedelta(days=1)).strftime('%Y-%m-%d') + 'T07:00:00Z'

        for milestone in r.json():
            if milestone['due_on'] == due_on and \
                automated_title in milestone['title'] and \
                milestone['description'] == AUTOMATED_DESCRIPTION:
                matching_milestone = milestone

        return matching_milestone

    def get_or_create_milestone(self):
        milestone = self.get_milestone()
        if milestone:
            print("Using milestone {}...".format(milestone['number']))
        else:
            milestone = self.create_milestone()
        return milestone

    def create_milestone(self):
        url = '{}/repos/{}/{}/milestones'.format(GITHUB_API_ROOT, self.org, self.repo_name)
        data = {
            'title': '{} - {}'.format(self.start_date, self.end_date),
            'state': 'open',
            'description': AUTOMATED_DESCRIPTION,
            'due_on': self.end_date + 'T00:00:00Z',
        }
        print("Creating a new milestone '{}'...".format(data['title']))

        if not self.dry_run:
            r = requests.post(url, json=data, headers=self.github_headers)
            return r.json()
        else:
            return {'number': -1, 'title': data['title'] + ' (Uncreated)'}

    def set_issue_milestone(self, milestone_number, issue_number):
        url = '{}/repos/{}/{}/issues/{}'.format(GITHUB_API_ROOT, self.org, self.repo_name, issue_number)
        data = {'milestone': milestone_number}

        if not self.dry_run:
            requests.patch(url, json=data, headers=self.github_headers)

    @property
    def zenhub_headers(self):
        return {'X-Authentication-Token': self.zenhub_token}

    def set_milestone_start_date(self):
        """ Set the milestone start date on the ZenHub side. """

        url = '{zenhub_api_root}/p1/repositories/{repo_id}/milestones/{milestone_number}/start_date'.format(
            zenhub_api_root=ZENHUB_API_ROOT,
            repo_id=self.repo_id,
            milestone_number=self.milestone_number)
        # Gotta add the time offset.
        data = {'start_date': self.start_date + 'T07:00:00Z'}
        if not self.dry_run:
            r = requests.post(url, data=data, headers=self.zenhub_headers)
            return r

    def get_issue_zenhub_data(self, issue_number):
        url = '{zenhub_api_root}/p1/repositories/{repo_id}/issues/{issue_number}'.format(
            zenhub_api_root=ZENHUB_API_ROOT,
            repo_id=self.repo_id,
            issue_number=issue_number)
        r = requests.get(url, headers=self.zenhub_headers)
        return r.json()


@click.command()
@click.option('--repo', '-r', required=True, multiple=True, help="org/repo, can provide > 1")
@click.option('--days', '-d', default=7, help="Days per sprint/cadence.")
@click.option('--date', help="Ending date for sprint (YYYY-MM-DD).", required=True)
@click.option('--token', '-t', help="Your GitHub token (optional, can place in config file).")
@click.option('--zenhub_token', '-z', help="Your ZenHub token (optional, can place in config file).")
@click.option('--force', '-f', is_flag=True, help="Even if the issues are attached to another milestone, move them.")
@click.option('--dry-run', is_flag=True, help="Don't actually move any issues or create a milestone.")
def cli(days, repo, token, zenhub_token, date, force, dry_run):
    try:
        # Get start and end date.
        end_date = datetime.datetime.strptime(date, '%Y-%m-%d')
        start_date = end_date - datetime.timedelta(days=days)

        # Str them to a format GitHub expects.
        end_date = end_date.strftime('%Y-%m-%d')
        start_date = start_date.strftime('%Y-%m-%d')
    except ValueError as e:
        print("The date format must be YYYY-MM-DD.")
        exit(0)

    for org_repo in repo:
        print("Working with {}".format(org_repo))
        amanuensis = Amanuensis(org_repo,
            force_milestone_association=force,
            start_date=start_date,
            end_date=end_date,
            dry_run=dry_run,
            github_token=token,
            zenhub_token=zenhub_token)
        amanuensis()


if __name__ == '__main__':
    cli()
