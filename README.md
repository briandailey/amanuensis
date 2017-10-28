This assumes that you have a cadence that you want to build velocity charts for.

The default cadence is one week (7 days).

Given a date, which you provide as an option, we will find all issues that were
closed in the past N days (default: 7) and add them to a milestone that is named
to correspond with the beginning and end date. The milestone name format is:

"YYYY-MM-DD - YYYY-MM-DD"

If the milestone matching this format already exists, it will clear all existing
issues from it and re-attach the closed issues.

_Note on older milestone dates_: Because the GitHub API is not great at filtering issues
on a private repo ([docs](https://developer.github.com/v3/issues/#list-issues-for-a-repository)) one cannot
easily filter down issues closed between two dates. The only date you can really filter
on is last updated, which is a poor proxy. This doesn't paginate results, so if
you are looking for dates very far back they may not fall within the first page
of 100 results and will therefore not be returned in the search and moved.

### Installation

Python3 only. You probably want to use virtualenv, etc.

  $ git clone git@github.com:briandailey/amanuensis.git
  $ cd amanuensis
  $ pip install -r requirements.txt

### Example Usage

  $ python main.py --repo briandailey/amanuensis --date 2017-10-27
  Using Milestone 127: 2017-10-20 - 2017-10-27
  Found 66 matching issues. Pairing down.
  Found 29 issues closed between 2017-10-20 and 2017-10-27.
  4685 - Lorem ipsum dolor sit - https://github.com/briandailey/amanuensis/issues/4685
