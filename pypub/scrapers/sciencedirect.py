# -*- coding: utf-8 -*-
"""
Module: pypub.scrapers.sciencedirect

Status: In progress

#TODO: Add a verbose printout so I can see what's happening
#TODO: Profile usage, why is this sooooooo slow
#TODO: Add tests, this stuff will break!
#TODO: Allow extraction of the refs as a csv,json,xml, etc - this might go into utils



Tasks/Examples:
---------------
1) ****** Get references given a pii value *******
from pypub.scrapers import sciencedirect as sd 

refs = sd.get_references('0006899387903726',verbose=True)

refs = sd.get_references('S1042368013000776',verbose=True)

df = refs[0].to_data_frame(refs)




Currently I am building something that allows extraction of references from
a Sciencedirect URL.



"""

import sys

#TODO: Move this into a compatability module
#-----------------------------------------------------
PY2 = int(sys.version[0]) == 2

if PY2:
    from urllib2 import unquote as urllib_unquote
else:
    from urllib.parse import unquote as urllib_unquote
#-----------------------------------------------------

from ..utils import get_truncated_display_string as td
from ..utils import get_class_list_display_string as cld

from .. import errors

import pandas as pd
import urllib
import re
#------------------
import requests
from bs4 import BeautifulSoup

_SD_URL = 'http://www.sciencedirect.com'

class ScienceDirectAuthorAffiliations(object):
    
    def __init__(self,li_tag):
        self.id = li_tag['id']
        self.raw = li_tag.contents[1]

    def __repr__(self):
        return u'' + \
        ' id: %s\n' % self.id + \
        'raw: %s\n' % td(self.raw)      

class ScienceDirectAuthor(object):
    
    def __init__(self,li_tag):
        
        
        """
        
        Example:
        <li class="author small" data-refs="aff1 aff2 aff3 cor1" id="au1">John Doe MD, MSc<sup> a,b,c,
        <a class="icon-correspondence-author" href="#cor1" id="r-cor1" title="Corresponding author contact information"> </a></sup></li>
        
        Improvements
        ------------
        1) Allow retrieval of icon info:
            - corresponding author info
            - email author
        2) Split name into parts
        
        
        """
        #class="author-group" id="augrp0010"
        #author small
        #author medium last 
        
        #<li class='Author medium last" data-refs="cor1" id="au3">
        #<a class='icon-correspondance-author'
        #<a class="icon-email-author"       
        #
        #class="author-affiliations" id="augrp0010"
        #   class="affiliation" id="aff1"        
        
        #1) Get text that is not in sup DONE
        #2) Grab data-refs "aff1,aff2,etc" DONE
        #3) 
        
        #1st bit of text is the name, then we hav
        self.raw = li_tag.contents[0] 
        self._data_refs = re.compile('[^\S]+').split(li_tag['data-refs'])
        #This is a list:
        #http://www.crummy.com/software/BeautifulSoup/bs4/doc/#multi-valued-attributes
        self._class = li_tag['class']
    
    def populate_affiliations(self,aff_objs):
        self.affiliations = [x for x in aff_objs if x.id in self._data_refs]

    def __repr__(self):
        return u'' + \
        '         raw: %s\n' % self.raw + \
        'affiliations: %s\n' % cld(self.affiliations)    

class ScienceDirectEntry(object):
    
    """
    
    This could be a step above the reference since it would, for example,
    contain all authors on a paper    
    
    Attributes
    ----------
    pi : string
        The unique identifier
        
    See Also
    --------
    ScienceDirectRef
    
    Examples
    --------
    from pypub.scrapers import sciencedirect as sd 
    url = 'http://www.sciencedirect.com/science/article/pii/S1042368013000776'
    #More affiliations
    url = 'http://www.sciencedirect.com/science/article/pii/S1042368013000818'
    sde = sd.ScienceDirectEntry(url,verbose=True)
    
    Improvements
    ------------
    - Add citing articles
    - Add Recommended Articles
    
    """
    def __init__(self,url,verbose=False,session=None):
        
        self.url = url
        
        #We're grabbing everything after the last '/'
        self.pii = re.search('[^/]+$',self.url).group(0)


        #Web page retrieval
        #------------------        
        if session is None:
            s = requests.Session()
        else:
            s = session
       
        if verbose:
            print('Requesting main page for pii: %s' % self.pii)
            
        r = s.get(url,cookies={'Site':'Mobile'})
        
        soup = BeautifulSoup(r.text)
        
        self.soup = soup
        
        #TODO: Can we wrap this with a parse expection?
        #i.e. consolidate these lines?
        article_abstract = soup.find('div',id='article-abstract')
        
        if article_abstract is None:
            raise errors.ParseException('Unable to find abstract section of page')
        

        
        #Things to get:
        #--------------
        self.publication = self._findValue(article_abstract,'a','publication-title')
        
        self.date = self._findValue(article_abstract,'span','cover-date')
        #TODO: Extract year        
        
        temp = self._findValue(article_abstract,'p','publication-volume-issue')        
        #'January 2014, Vol.25(1):33–46, doi:10.1016/j.nec.2013.08.001'
        #The volume and issue are not accessible individually
        #We can get , Vol.25(1) from the first anchor tag text inside of 
        #the acnhor tag that is not in the span (which is self.date)        
        
        #self.issue = 
        self.first_page = self._findValue(article_abstract,'span','first-page')
        self.last_page = self._findValue(article_abstract,'span','last-page')
        #special_issue #p,publication-special-issue
        #
        
        #DOI retrieval
        #-------------
        #Could also graph href inside of the class and strip http://dx.doi.org/
        #This might be more reliable than assuming we have doi:asdfasdf
        self.doi = self._findValue(article_abstract,'span','article-doi')
        if self.doi is not None:
            self.doi = self.doi[4:] #doi:asdfasdfasdf => remove 'doi":'
            
        self.title = self._findValue(article_abstract,'h1','article-title')
        #Authors:
        #-------
        #Look for <li> tags with class="author*"
        #TODO: Can move compiling to initialization
        self.authors = [ScienceDirectAuthor(x) for x in article_abstract.find_all('li',class_=re.compile('^author'))]

        aff_tags = article_abstract.find_all('li',class_='affiliation label')
        self.affiliations = [ScienceDirectAuthorAffiliations(x) for x in aff_tags]
        
        for author in self.authors:
            author.populate_affiliations(self.affiliations)
        
        keyword_tags = article_abstract.find_all('li',{'class':'article-keyword'})
        self.keywords = [x.text for x in keyword_tags]
        
        import pdb
        pdb.set_trace()
        
    def __repr__(self):
        return u'' + \
        '      title: %s\n' % td(self.title) + \
        '    authors: %s\n' % 'TODO' + \
        'publication: %s\n' % self.publication + \
        '       date: %s\n' % self.date + \
        '        doi: %s\n' % '1'


    def _findValue(self,tags,tag_name,class_name):
        """
        This is a small helper that is used to pull out values from a tag
        given the value of the tags class attribute. See the example.
        
        Parameters:
        -----------
        tag_name : str
            Tag name or type, such as 'li','span', or 'div'
        class_name : str
            Used for selecting a specific value
        ref_tags : bs4.element.Tag
            
        Example:
        --------
        #Our goal is to extract: Can. J. Physiol. Pharmacol.
        #One of the tags is:
        <span class="r_publication">Can. J. Physiol. Pharmacol.</span>
        
        self._findValue('span','r_publication')
            
        """
        
        temp = tags.find(tag_name,{'class':class_name})
        if temp is None:
            return None
        else:
            return temp.text  

    @classmethod
    def from_pii(pii):
        return ScienceDirectEntry(_SD_URL + '/science/article/pii/' + pii)

#TODO: Inherit from some abstract ref class
#I think the abstract class should only require conversion to a common standard
class ScienceDirectRef(object):
  
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
    issue
    series
    date : string
        This appears to always be the year but I'm not sure. More 
    pages
    
    scopus_link       = None
    doi : string
        Digital Object Identifier. May be None if not present. This is
        currently based on the presence of a link to fulltext via Crossref.
    _data_sceid       = None
        I believe this is the Scopus ID
    pii               = None 
        This is the ID used to identify an article on ScienceDirect.
        See also: https://en.wikipedia.org/wiki/Publisher_Item_Identifier
    pdf_link : string (default None)
        If not None, this link points to the pdf of the article.
    scopus_cite_count = None    
    
    Improvements
    ------------
    1) Allow resolving the DOI via the pii
    2) Some references are not parsed properly by SD. As such the raw
    information should be stored as well in those cases, along with a flag
    indicating that this has occurred (e.g. see #71 for pii: S1042368013000776)
        
    
    See Also:
    get_references
    
    """
    def __init__(self,ref_tags,ref_link_info,ref_id):
     
        """
     
        Parameters:
        -----------
        ref_tags: bs4.element.Tag
            Html tags as soup of the reference. Information provided is that
            needed in order to form a citation for the given reference.
        ref_link_info: str
            Html, not yet souped. Contains extra information such as links to
            a pdf (if known) and other goodies
        ref_id: int
            The id of the reference as ordered in the citing entry. A value
            of 1 indicates that this object is the first reference in the bibliography.
            
     
        """


        self.ref_tags = ref_tags

 
        find = self._findValue 
        #Reference Bibliography Section: 
        #-------------------------------
        #Example str: <span class="r_volume">Volume 47</span>
        self.ref_id      = ref_id + 1 #Input is 0 based
        self.title       = find('li','reference-title')  
        self.authors = find('li','reference-author')
        #NOTE: We can also get individual authors if we would like.
        #        
        #   Search would be on: 
        #       <span class="reference-author">
        #   instead of on the list.
        
        #Unfortunately r_publication is found both for the title and for
        #the publication. Some custom code is needed to first go into a r_series
        #span and then to the publication
        self.publication = None
        r_source_tag = ref_tags.find('span',{'class':'r_series'})

        if r_source_tag is not None:
            pub_tag = r_source_tag.find('span',{'class':'r_publication'})
            if pub_tag is not None:
                self.publication = pub_tag.text      

        temp_volume      = find('span','r_volume')
        if temp_volume is None:
            self.volume = None
        else:
            self.volume = temp_volume.replace('Volume ','')
            
        self.issue  = find('span','r_issue')
        self.series = find('span','r_series')
        self.date   = find('span','r_pubdate')
        
        temp_pages  = find('span','r_pages')
        if temp_pages is None:
            self.pages = None
        else:
            #TODO: is the unicode working properly ??? 576â€“577 and ideally 576-577
            self.pages = temp_pages.replace('pp. ','')
        
        
        #Reference Meta Section:
        #-----------------------        
        link_soup = BeautifulSoup(ref_link_info)      
        
        #Each section is contained a div tag with the class boxLink, although
        #some classes have more text in the class attribute, thus the *)
        box_links = link_soup.find_all('div',{'class':re.compile('boxLink*')})        
        
        self.scopus_link       = None
        self.doi               = None
        self._data_sceid       = None
        self.pii               = None 
        self.pdf_link          = None
        self.scopus_cite_count = None
        
        #This code is a bit hard to read but each 'if statement' shows what
        #is needed in order to resolve the item.
        for box_link in box_links:
            
            div_class_values = box_link.attrs['class']
            link_tag = box_link.find('a')
            if 'SC_record' in div_class_values:
                #"View Record in Scopus"
                #They changed to returning a full link
                #I should really use a library to resolve based on both
                #although the input should be the current page, not the base
                #self.scopus_link = _SD_URL + link_tag.attrs['href']
                self.scopus_link = link_tag.attrs['href']
            elif 'S_C_pdfLink' in link_tag.attrs['class']:
                #Link to PDF
                self.pdf_link = _SD_URL + link_tag.attrs['href']
            elif 'cLink' in link_tag.attrs['class']:
                #Article Link
                temp     = link_tag.attrs['href']
                match    = re.search('/pii/(.*)',temp)
                self.pii = match.group(1)
            elif 'Full Text via CrossRef' in link_tag.text:
                #CrossRef link provides DOI as href
                #In old code it was a query parameter but this
                #has now moved to a "data-url" attribute
                temp  = link_tag.attrs['href']
                #http://dx.doi.org/10.1037%2Fh0075243
                match = re.search('dx\.doi\.org/(.*)',temp)
                #Unquote removes %xx escape characters
                self.doi = urllib_unquote(match.group(1))
            else:
                span_tag = link_tag.find('span')
                if 'citedBy_' in span_tag.attrs['class']:
                    #Cited By Scopus Count
                    #
                    #NOTE: Apparently the citedByScopus doesn't get added
                    #until later so we need to look for the scan tag. Let's
                    #do this only if all else fails.
                    self._data_sceid   = span_tag.attrs['data-sceid']
                else:
                    #import pdb
                    #pdb.set_trace()
                    raise Exception('Failed to match link')

    
    
    def to_data_frame(self,all_entries):
        """
        Return a Pandas DataFrame
        
        Parameters
        ----------
        all_entries : [ScienceDirectRef]        
        
        Testing
        -------
        wtf = refs[0].to_data_frame(refs)
        """
        
        
        c_attr = ['ref_id','title','authors','publication', 'volume','issue',
                'series','date','pages','volume','scopus_link','doi','pii',
                'pdf_link','scopus_cite_count']
        all_data = []
        for entry in all_entries:
            all_data.append([getattr(entry,x) for x in c_attr])

        return pd.DataFrame(all_data,columns=c_attr)        
    
  
    
    def get_simple_string():
        #TODO: Implement
        #The goal is to represent the object as a single string
        #Essentially as a citation
        pass
        
    def __repr__(self):
        return u'' + \
        '           ref_id: %s\n' % self.ref_id +\
        '            title: %s\n' % td(self.title) + \
        '          authors: %s\n' % self.all_authors + \
        '      publication: %s\n' % self.publication + \
        '           volume: %s\n' % self.volume +\
        '            issue: %s\n' % self.issue + \
        '           series: %s\n' % self.series + \
        '             date: %s\n' % self.date + \
        '            pages: %s\n' % self.pages + \
        '           volume: %s\n' % self.volume + \
        '      scopus_link: %s\n' % td(self.scopus_link) + \
        '              doi: %s\n' % self.doi + \
        '              pii: %s\n' % self.pii + \
        '         pdf_link: %s\n' % td(self.pdf_link) + \
        'scopus_cite_count: %s\n' % self.scopus_cite_count    
        
        
def ReferenceParser(object):
    #TODO: move code from get_references into here and have that method
    #initialize this object and call it ( .run()? )
    #
    #This would also swallow _update_counts
    pass

def get_references(pii,verbose=False):
    
    """
    This function gets references for a Sciencedirect URL that is of the
    form:
    
        http://www.sciencedirect.com/science/article/pii/################
        
        e.g. http://www.sciencedirect.com/science/article/pii/0006899387903726
        
        
        
    
    Implementation Notes:
    ---------------------
    From what I can tell this information is not exposed via the ElSevier API.
    
    In order to minimize complexity, the mobile site is requested: via a cookie.


    
    Code Layout and Algorithm Notes:
    --------------------------------
    
    
    TODO: Finish this
    - get references, extra step after page
    - get reference counts, extra step after references
    
    """

    

    #TODO: Move this to ScienceDirectEntry - I'm thinking of makign this its own
    #class as well
    #
    #TODO: Make this a class reference parser

    #*** These tags are mobile-site specific

    #If you view the references, they should be wrapped by an <ol> tag
    #with the attribute class="article-references"    
    REFERENCE_SECTION_TAG_TUPLE =  ("ol",{"class":"article-references"})
    
    #When we don't have proper access rights, this is present in the html
    GUEST_TAG_TUPLE = ("li",{"id":"menuGuest"})
    
    #Entries are "li" tags with classes of the form:
    #   article-reference-article
    #   article-reference-other-ref
    REFERENCE_TAG_TUPLE = ("li",{"class":re.compile('article-reference-*')})
    
    #This is the URL to the page that contains the document info, including
    #reference material
    BASE_URL = _SD_URL + '/science/article/pii/'
    
    #This URL was found first via Fiddler, then via closer inspection of the script
    #'article_catalyst.js' under sciencedirect.com/mobile/js in the function
    #resolveReferences
    REF_RESOLVER_URL = _SD_URL + '/science/referenceResolution/ajaxRefResol'
    

    #Step 1 - Make the request
    #--------------------------------------------------------------------------
      
    s = requests.Session()    
       
    if verbose:
        print('Requesting main page for pii: %s' % pii)
    r = s.get(BASE_URL +  pii,cookies={'Site':'Mobile'})
    
    
    #Step 2 - Get the references tags
    #--------------------------------------------------------------------------
    #The reference tags contain most of the information about references
    #They are however missing a lot of the linking information
    #e.g. link to the article, pdf download, etc
    soup = BeautifulSoup(r.text)
    
    reference_section = soup.find(*REFERENCE_SECTION_TAG_TUPLE)  
    
    if reference_section is None:
        #Then we might be a guest. In other words, we might not have sufficient
        #priveleges to access the data we want. Generally this is protected via
        #IP mask. When I'm working from home I need to VPN into work so
        #that I can access the data :/
        temp = soup.find(*GUEST_TAG_TUPLE)
        if temp is None:
            #We might have no references ... (Doubtful)
            raise errors.ParseException("References were not found ..., code error likely")
        else:
            raise errors.InsufficientCredentialsException("Insufficient access rights to get referencs, requires certain IP addresses (e.g. university based IP)")
    
    ref_tags = reference_section.find_all(*REFERENCE_TAG_TUPLE)    
    
    n_refs = len(ref_tags)
    
    if n_refs == 0:
        return None
    
    #Step 3 - Resolve reference links
    #--------------------------------------------------------------------------
    #The returned html code contains javascript which returns more information
    #about each reference, such as:
    #
    #   - links to the full text
    #   - DOI   
    
    
    #Step 3.1 - Make the request for the information
    #--------------------------------------------------------------------------    
    #We need the eid of the current entry, it is of the form: 
    #
    #   SDM.pm.eid = "1-s2.0-0006899387903726"
    #
    #   * I think this entry gets deleted after the requests so it may not be
    #   visible  if looking for it in Chrome. 
    match = re.search('SDM\.pm\.eid\s*=\s*"([^"]+)"',r.text)
    eid   = match.group(1)
    
    #This list comes from the resolveReferences function in article_catalyst.js
    payload = {
        '_eid'           : eid,
        '_refCnt'        : n_refs,
        '_docType'       : 'article', #yikes, this might change ...
        '_refRangeStart' : '1',
        '_refRangeCount' : str(n_refs)} #This is normally in sets of 20's ...
        #I'm not sure if it is important to limit this. The browser then 
        #makes a request fromr 1 count 20, 21 count 20, 41 count 20 etc, 
        #It always goes by 20 even if there aren't 20 left
    
    if verbose:
        print('Requesting reference links')  
    r2 = s.get(REF_RESOLVER_URL,params=payload)    
    
    #Step 3.2 - Parse the returned information into single entries
    #--------------------------------------------------------------------------
    #This could probably be optimized in terms of execution time. We basically
    #get back a single script tag. Inside is some sort of hash map for links
    #for each reference.
    #
    #The script tag is of the form:
    #   myMap['bibsbref11']['refHtml']= "<some html stuffs>"; 
    #   myMap['bibsbref11']['absUrl']= "http://www.sciencedirect.com/science/absref/sd/0018506X7790068X";
    #   etc.
    #
    #   - Each entry is quite long.
    #   - Normally contains html
    #   - can be empty i.e. myMap['bibsbref11']['refHtml'] = "";
    #   - the refHtml is quite interesting
    #   - the absolute url is not always present (and currently not parsed)
    more_soup   = BeautifulSoup(r2.text)    
    script_tag  = more_soup.find('script')
    
    #We unquote the script text as it is transmitted with characters escaped
    #and we want the parsed data to contain the non-escaped text
    #
    #We might eventually want to move this to being after the regular expression ...
    script_text = urllib_unquote(script_tag.text)
        
    ref_match_result = re.findall("myMap\['bibsbref(\d+)'\]\['refHtml'\]=\s?" + '"([^"]*)";',script_text) 
    #Tokens:
    #0 - the # from bibsbref#
    #1 - the html content from the 'refHtml' entry
    #    
    #NOTE: We don't really use the #, so we might remove the () around
    #\d+ which would shift the index from 1 to 0
    if verbose:
        print('Creating reference objects')  
    ref_objects = [ScienceDirectRef(ref_tag,ref_link_info[1],ref_id) for \
                    ref_tag,ref_link_info,ref_id in \
                    zip(ref_tags,ref_match_result,range(n_refs))]     


    #Step 4:
    #--------------------------------------------------------------------------
    #TODO: Improve documentation for this step
    
    if verbose:
        print('Retrieving Scopus Counts')

    ref_scopus_eids  = [] #The Scopus IDs of the references to resolve
    #but with a particular formatting ...
    ref_count = 0 #Number of references we haven't resolved
    
    ref_count_list = [] 
    #NOTE: Browser requests these in the reverse order ...
    for ref_id, ref in enumerate(ref_objects):
        
        if ref._data_sceid is not None:
            ref_scopus_eids.append(ref._data_sceid + ',' + str(ref_id+1) + '~')
            ref_count += 1
            
            #If we've got enough, then update the counts
            #The 20 may be arbitrary but it was what was used in original JS
            if ref_count > 20:
                ref_count_list += _update_counts(s,ref_scopus_eids,REF_RESOLVER_URL)
                ref_count = 0
                ref_scopus_eids  = []

    #Get any remaining reference counts
    if ref_count != 0:
         ref_count_list += _update_counts(s,ref_scopus_eids,REF_RESOLVER_URL)        

    #Take the raw data and set the citation count for each object
    for ref_tuple in ref_count_list:
        ref_id    = int(ref_tuple[0]) - 1
        ref_count = int(ref_tuple[1])
        ref_objects[ref_id].scopus_cite_count = ref_count


    #All done!
    #---------
    return ref_objects    
  
def _update_counts(s,eids,resolve_url):
    
    """
    Helper for get_references()
    
    Parameters
    ----------
    s : Session
        The Requests Session
    eids : list
        List of eids but with a particular format
        e.g. ... TODO
    resolve_url : string
        This is a hardcoded value, eventually we'll pull this from the class
    
    Returns
    -------
    """
    payload = {'_updateCitedBy' : ''.join(eids)}
    r = s.get(resolve_url,params=payload)          
    #TODO: Check for 200
    data = urllib_unquote(r.text)
    
    #myXabsCounts['citedBy_26']='Citing Articles (41)';
    cited_by_results = re.findall("myXabsCounts\['citedBy_(\d+)'\]='[^\(]+\((\d+)",data)
    
    return cited_by_results
    #TODO: parse response
    #????? Why is the order scrambled - this seems to be on their end ...????
    """
    NOTE: This is now Citing Articles, references to Scopus have been dropped
    myXabsCounts['citedBy_16']='Cited By in Scopus (128)';
    myXabsCounts['citedBy_15']='Cited By in Scopus (25)';
    myXabsCounts['citedBy_1']='Cited By in Scopus (2)';
    myXabsCounts['citedBy_3']='Cited By in Scopus (29)';
    """
    #TODO: go through refs and apply new values ...  
    