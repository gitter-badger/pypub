# -*- coding: utf-8 -*-
"""

Module: pypub.scrapers.scraper_skeleton

Status: In progress


#TODO: Add tests, this stuff will break!
#TODO: Allow extraction of the refs as a csv,json,xml, etc - this might go into utils

#TODO: STANDARDIZE THE FUNCTION INPUTS!!!
     - Either get references and get entry info both using a URL as the input, or
       both using a DOI/PII as an input. Different inputs for each is confusing.

Tasks/Examples:
---------------
1) ****** Get references given a doi value *******
from pypub.scrapers import ________ as __

refs = __.get_references('0006899387903726',verbose=True)

refs = __.get_references('S1042368013000776',verbose=True)

df = refs[0].to_data_frame(refs)


Currently I am building something that allows extraction of references from
a URL.

"""

import sys
import os

#TODO: Move this into a compatability module
#-----------------------------------------------------
PY2 = sys.version_info.major == 2

if PY2:
    from urllib import unquote as urllib_unquote
    from urllib import quote as urllib_quote
else:
    from urllib.parse import unquote as urllib_unquote
    from urllib.parse import quote as urllib_quote
#-----------------------------------------------------

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pypub.utils import get_truncated_display_string as td
from pypub.utils import findValue

from pypub_errors import *

import re
#-------------------
import requests
from bs4 import BeautifulSoup

_SP_URL = ''

class Author(object):

    def __init__(self, li_tag):

        """
        Parameters
        ----------
        li_tag

        Returns
        -------

        Improvements
        ------------
        1) Allow retrieval of icon info:
            - corresponding author info
            - email author
        2) Split name into parts

        """

        # Get author name
        self.raw = li_tag.contents[0].text

        self.affiliations = None
        self.email = None

        # Get author affiliations
        aff_list = li_tag.find_all('span', {'class' : 'affiliation__name'})
        if aff_list is not None:
            self.affiliations = [aff.text for aff in aff_list]

        # Get author email
        link = li_tag.find('a', {'title' : 'Email author'})
        if link is not None:
            self.email = link['href'][7:]  # Extract email link and remove 'mailto:' from beginning

    def __repr__(self):
        return u'' + \
                'name: %s\n' % self.raw + \
        'affiliations: %s\n' % self.affiliations + \
             'email: %s\n' % self.email


class Entry(object):
    """
    This could be a step above the reference since it would, for example,
    contain all authors on a paper.

    Attributes
    ----------
    doi : string
        The unique identifier

    See Also
    ----------
    SpringerRef

    Examples
    ----------
    from pypub.scrapers import springer as sp
    url = ''
    wye = __.Entry(url,verbose=True)

    Improvements
    ----------
    - Add citing articles

    """
    def __init__(self, soup, verbose=False):

        # Get entry content information
        mainContent = soup.find('div', {'class' : 'ArticleHeader'})
        if mainContent is None:
            raise ParseException('Unable to find main content of page')


        # Metadata:
        #---------------
        self.title = findValue(mainContent, 'h1', 'ArticleTitle', 'class').title()

        self.publication = findValue(mainContent, 'span', 'JournalTitle', 'class')

        # Two dates are given: original publication date and
        # online publication date. This returns the original journal pub date.
        yearwrapper = mainContent.find('span', {'class' : 'ArticleCitation_Year'})
        self.date = yearwrapper.find('time').text
        self.year = self.date[-4:]

        self.volume = findValue(mainContent, 'span', 'ArticleCitation_Volume', 'class')

        # SpringerLink doesn't seem to list article pages
        self.pages = None

        # SpringerLink keeps keywords below the abstract, separate from header info
        keybox = soup.find('div', {'class' : 'KeywordGroup'})
        if keybox is None:
            raise ParseException('Unable to find keywords')
        wordlist = keybox.find_all('span', {'class' : 'Keyword'})
        self.keywords = [w.text for w in wordlist]


        # DOI Retrieval:
        #---------------
        # This might be more reliable than assuming we have the DOI in the title
        self.doi = findValue(mainContent, 'p', 'article-doi', 'class')
        doi_startindex = self.doi.find('10.')
        self.doi = self.doi[doi_startindex:] # to get rid of whitespace at the beginning


        # Authors:
        #---------
        # Find list items within the ordered list with id 'authors'
        # Need to find only classless li's so that it doesn't also retrieve the child li's corresponding
        # to author affiliations at this stage.
        authorList = mainContent.find('ul', {'class' : 'authors'}).find_all('li', {'class' : None})
        self.authors = [SpringerAuthor(x) for x in authorList]
        '''
        corr = mainContent.find('p', {'id' : 'correspondence'})
        email = findValue(corr, 'a', 'Link to email address', 'title')
        '''


    def __repr__(self):
        return u'' + \
        '       title: %s\n' % td(self.title) + \
        '     authors: %s\n' % self.authors + \
        '    keywords: %s\n' % self.keywords + \
        ' publication: %s\n' % self.publication + \
        '        date: %s\n' % self.date + \
        '      volume: %s\n' % self.volume + \
        '       pages: %s\n' % self.pages + \
        '         doi: %s\n' % self.doi


    @classmethod
    def from_doi(doi):
        entry = SpringerEntry(_SP_URL + '/doi/' + str(doi) + '/abstract')
        return entry


# TODO: Inherit from some abstract ref class
# I think the abstract class should only require conversion to a common standard
class SpringerRef(object):
    """
    This is the result class of calling get_references. It contains the
    bibliographic information about the reference, as well as additional meta
    information such as a DOI (if known).

    Attributes:
    -----------
    ref_id : int
        The index of the reference in the citing document. A value of 1
        indicates that the reference is the first reference in the citing
        document.
    title : string
    authors : string
        List of the authors. This list may be truncated if there are too many
        authors, e.g.: 'N. Zabihi, A. Mourtzinos, M.G. Maher, et al.'
    publication : string
        Abbreviated (typically?) form of the journal
    volume : string
    date : string
        This appears to always be the year
    doi : string
        Digital Object Identifier. May be None if not present. This is
        currently based on the presence of a link to fulltext via Crossref.
    pdf_link : string (default None)
        If not None, this link points to the pdf of the article.


    See Also:
    get_references

    """
    def __init__(self, ref_tags, ref_id):

        """

        Parameters:
        -----------
        ref_tags: bs4.element.Tag
            Html tags as soup of the reference. Information provided is that
            needed in order to form a citation for the given reference.
        ref_id: int
            The id of the reference as ordered in the citing entry. A value
            of 1 indicates that this object is the first reference in the bibliography.


        """

        self.ref_tags = ref_tags

        # Reference Bibliography Section:
        #--------------------------------
        self.ref_id = ref_id + 1 # Input is 0 indexed

        # SpringerList has the entire citation in plaintext in one <div> tag.
        # Annoying. Uhhhh... let's just grab all of it at once for now and parse it later.

        self.citation = findValue(ref_tags, 'div', 'CitationContent', 'class')

        '''
        self.title = findValue(ref_tags, 'span', 'articleTitle', 'class')
        authorlist = ref_tags.find_all('span', 'author', 'class')
        self.authors = [x.text for x in authorlist]

        self.publication = findValue(ref_tags, 'span', 'journalTitle', 'class')
        self.volume = findValue(ref_tags, 'span', 'vol', 'class')
        self.date = findValue(ref_tags, 'span', 'pubYear', 'class')

        firstp = findValue(ref_tags, 'span', 'pageFirst', 'class')
        lastp = findValue(ref_tags, 'span', 'pageLast', 'class')
        if (firstp is not None) and (lastp is not None):
            self.pages = firstp + '-' + lastp
        '''

        # Reference Meta Section:
        #------------------------------

        self.crossref = None
        self.pubmed = None
        self.pubmed_central = None
        self.doi = None


        # External links (i.e. PubMed, CrossRef) are kept in a span tag
        links = ref_tags.find('span', 'Occurrences', 'class')

        # Only proceed if either internal or external references were found
        if links is not None:
            links = links.find_all('span', {'class' : 'Occurrence'})

            # Check against all possible link options and save links.
            #
            # NOTE: links are returned URL encoded (using urllib.quote(), but DOI
            # and PubMed IDs are not encoded. This means that if extracting the DOI
            # from one of the returned URLs, it needs to be first unquoted.
            #
            for link in links:
                href = link.find('a', href=True)['href']

                if 'OccurrenceDOI' in link['class']:
                    self.crossref = href
                elif 'OccurrencePID' in link['class']:
                    self.pubmed = href
                elif 'OccurrencePMCID' in link['class']:
                    self.pubmed_central = href

    '''
    def __repr__(self):
        return u'' + \
        '                    ref_id: %s\n' % self.ref_id + \
        '                     title: %s\n' % td(self.title) + \
        '                   authors: %s\n' % self.authors + \
        '               publication: %s\n' % self.publication + \
        '                    volume: %s\n' % self.volume + \
        '                      date: %s\n' % self.date + \
        '                     pages: %s\n' % self.pages + \
        '               pubmed_link: %s\n' % self.pubmed + \
        '                 pubmed_id: %s\n' % self.pubmed_id + \
        '             crossref_link: %s\n' % self.crossref + \
        '                  CAS_link: %s\n' % self.cas + \
        '             abstract_link: %s\n' % self.abstract + \
        '           references_link: %s\n' % self.ref_references + \
        '                  pdf_link: %s\n' % self.pdf_link + \
        '                       doi: %s\n' % self.doi + \
        'web of science times cited: %s\n' % self.citetimes
    '''

    def __repr__(self):
        return u'' + \
        '                    ref_id: %s\n' % self.ref_id + \
        '                  citation: %s\n' % self.citation + \
        '             crossref_link: %s\n' % self.crossref + \
        '                    pubmed: %s\n' % self.pubmed + \
        '            pubmed_central: %s\n' % self.pubmed_central + \
        '                       doi: %s\n' % self.doi



def get_references(input, verbose=False):
    """
    This function gets references for a Springer URL that is of the
    form:

        http://www.link.springer.com/article/####################

        e.g. http://link.springer.com/article/10.1186/s12984-016-0150-9

    """

    # TODO: Make this a class reference parser

    # If you view the references, they should be wrapped by a <ol> tag
    # with the attribute class="BibliographyWrapper"
    REFERENCE_SECTION_TAG =  ('ol', {'class' : 'BibliographyWrapper'})

    # TODO: check what this guest tag actually looks like
    # When we don't have proper access rights, this is present in the html
    GUEST_TAG = ('li', {'id' : 'menuGuest'})

    # Entries are "li" tags with ids of the form:
    #   b1, b2, b3, etc.
    # Hopefully this doesn't grab other random list items on the page
    REFERENCE_TAG = ('li', {'class' : 'Citation'})


    # Step 1 - Make the request
    #--------------------------------------------------------------------------
    soup = make_soup(input, 'references', verbose)

    # Step 2 - Get the references tags
    #--------------------------------------------------------------------------
    # The reference tags contain most of the information about references
    # They are however missing a lot of the linking information
    # e.g. link to the article, pdf download, etc

    reference_section = soup.find(*REFERENCE_SECTION_TAG)

    if reference_section is None:
        # Then we might be a guest. In other words, we might not have sufficient
        # privileges to access the data we want. Generally this is protected via
        # IP mask. When I'm working from home I need to VPN into work so
        # that I can access the data :/
        print("reference_section is None")
        temp = soup.find(*GUEST_TAG)
        if temp is None:
            #We might have no references ... (Doubtful)
            raise ParseException("References were not found ..., code error likely")
        else:
            raise InsufficientCredentialsException("Insufficient access rights to get referencs, requires certain IP addresses (e.g. university based IP)")

    ref_tags = reference_section.find_all(*REFERENCE_TAG)

    n_refs = len(ref_tags)

    if n_refs == 0:
        return None


    # Step 3 - Create reference objects
    #--------------------------------------------------------------------------
    # The reference objects parse out information for each reference
    # as well as external links.
    if verbose:
        print('Creating reference objects')
    ref_objects = [SpringerRef(ref_tag, ref_id) for \
                    ref_tag, ref_id in \
                    zip(ref_tags, range(n_refs))]


    #All done!
    #---------
    return ref_objects


def get_entry_info(input, verbose=False):
    soup = make_soup(input, 'entry', verbose)
    return SpringerEntry(soup, verbose)

def make_soup(input, type, verbose=False):
    # Check if the input is a DOI or URL
    if is_url(input):
        doi = extract_doi(input)
    elif is_doi(input):
        doi = input
    else:
        raise ValueError('Input not recognized as a valid DOI or SpringerLink URL')

    # Web page retrieval
    #-------------------
    soup = connect(doi, type, verbose)
    return soup


def is_url(input):
    if input.find('springer') != -1:
        return True
    else:
        return False

def is_doi(input):
    if input.find('10.') == 0:
        return True
    else:
        return False


def extract_doi(url):

    # DOI is used in SpringerLink URLs after '/article/', i.e.
    # http://link.springer.com/article/10.1186/s12984-016-0150-9
    # This finds the indices of '/article/' and gets everything afterward
    articleindex = url.find('/article/')
    doi = url[articleindex+8:]

    return doi


def connect(doi, type, verbose=None):

    # Construct valid SpringerLink URL from given DOI
    url = _SP_URL + '/article/' + doi

    # Web page retrieval
    #-------------------
    s = requests.Session()

    if verbose:
        print('Requesting main page for doi: %s' % doi)

    r = s.get(url)
    soup = BeautifulSoup(r.text)

    return soup
