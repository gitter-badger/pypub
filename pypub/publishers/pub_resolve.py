# Standard imports
import os
import inspect
import csv

# Third party imports
import requests

# Local imports
from pypub_errors import *


def get_publisher_urls(doi=None, url=None):
    # Get or make CrossRef link, then follow it to get article URL
    if url is not None:
        resp = requests.get(url)
        pub_url = resp.url
    else:
        resp = requests.get('http://dx.doi.org/' + doi)
        pub_url = resp.url

    end_index = pub_url.find('.com') + 4
    base_url = pub_url[:end_index]

    # Nature sites are specific to the different journals
    # I.e. http://nature.com/nrg is for Nature Reviews Genetics
    if 'nature' in base_url:
        base_url = pub_url[:end_index+4]

    base_url = base_url.replace('www.', '')

    return base_url, pub_url


def get_publisher_site_info(base_url):
    # Add the site_features.csv file to the path
    current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    root = os.path.dirname(current_dir)
    #site_features_file = os.path.join(root, '/publishers/site_features.csv')
    site_features_file = root + '/publishers/site_features.csv'

    # Now search the site_features.csv file to get information relevant to that provider
    with open(site_features_file) as f:
        reader = csv.reader(f)
        headings = next(reader)  # Save the first line as the headings
        values = None
        for row in enumerate(reader):
            if base_url in row[1]:
                # Once the correct row is found, save it as values.
                # The [1] here is needed because 'row' is a list where
                # the first value is the row number and the second is
                # the entire list of headings.
                values = row[1]
                break

    if values is None:
        raise UnsupportedPublisherError('No scraper is yet implemented for this publisher')

    # Turn the headings and values into a callable dict
    pub_dict = dict(zip(headings, values))

    return pub_dict
