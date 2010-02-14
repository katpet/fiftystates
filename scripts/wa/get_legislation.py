# ugly hack
import sys
import re
import string
sys.path.append('./scripts')
from pyutils.legislation import LegislationScraper, Bill, Vote
from BeautifulSoup import BeautifulSoup


class WALegislationScraper(LegislationScraper):

    state = 'wa'
    lower_min_id = 1000
    lower_max_id = 4999 
    upper_min_id = 5000
    upper_max_id = 9999
    
    def scrape_metadata(self):
        self._session_dict = {}
        sessions = []
        session_details = {}
        sessions_url = 'http://www.sos.wa.gov/library/legsession.aspx'
        with self.soup_context(sessions_url) as soup:
            for link in soup.findAll('a'):
                # eg. 1st Regular Session: 1889
                # Session name is taken to be the number, like 60th
                # which covers a bienium, like 2007 - 2008
                linktext = link.string
                if linktext:
                    toks = linktext.split(':')
                    yearstr = toks[-1].strip()
                    if not yearstr.isdigit():
                        continue
                    print('year ', yearstr)
                    toks2 = toks[0].split(' ')
                    session_name = toks2[0].strip()
                    print('session ', session_name)
                    year = int(yearstr)

                    # map year to its session number for later lookup
                    # if session is referred to by year rather than number
                    self._session_dict[yearstr] = session_name

                    if not sessions.count(session_name):
                        sessions.append(session_name)
                        session_details[session_name] = {
                            'years': [year],
                            'sub_sessions': []}
                    else:
                        if not session_details[session_name]['years'].count(year):
                            session_details[session_name]['years'].append(year)
                        
                    # eg. 60th 1st Special Election: 2007
                    # use "1st Special Election 2007" as subsession name
                    toks2 = toks2[1:]
                    toks2.append(yearstr)
                    subsession = ' '.join(toks2)
                    print('subsession ', subsession)
                    session_details[session_name]['sub_sessions'].append(subsession)

                print('sessions ', sessions)
                print('details ', session_details)
                                    
        metadata = {
            'state_name': 'Washington',
            'legislature_name': 'Washington State Legislature',
            'upper_chamber_name': 'Senate',
            'lower_chamber_name': 'House of Representatives',
            'upper_title': 'Senator',
            'lower_title': 'Representative',
            'upper_term': 4,
            'lower_term': 2,
            'sessions': sessions,
            'session_details': session_details,
            }

        return metadata

    def scrape_legislators(self, chamber, year):
        # http://www.leg.wa.gov/History/House/ClassPhotos/Pages/default.aspx
        # http://www.leg.wa.gov/History/Senate/ClassPhotos/Pages/default.aspx              # These pages have links to class photos.  
        # Legislator names are listed beneath the class photos.
        
        if chamber == 'upper':
            chamber_name = 'Senate'
        elif chamber == 'lower':
            chamber_name = 'House'
            
        classphotos_url = 'http://www.leg.wa.gov/History/%s/ClassPhotos/Pages/default.aspx' % chamber_name

        with self.soup_context(classphotos_url) as soup:
            classphoto_links = soup.findAll('a', href=re.compile('/History/%s/ClassPhotos/Pages/....%s.aspx' % (chamber_name, chamber_name)))
            for classphoto_link in classphoto_links:
                print('classphoto_link', classphoto_link)
                classphoto_url = 'http://www.leg.wa.gov%s' % classphoto_link['href']
                with self.soup_context(classphoto_url) as classphoto_soup:
                    nametext = classphoto_soup.findAll('p')
                    for p in nametext:
                        print('p', p)

        # http://www.leg.wa.gov/History/House/ClassPhotos/Pages/1889house.aspx
        # http://www.leg.wa.gov/History/House/ClassPhotos/Pages/2009house.aspx
        # http://www.leg.wa.gov/History/Senate/ClassPhotos/Pages/1889Senate.aspx

    def _scrape_bill_docs(self, soup, bill):
        # There's a link on each bill summary page called
        # 'Text of a Legislative Document' which points to
        # a page with a table of documents.
        # eg. a href="../tld/results.aspx?params=2009-10,5001"
        doclist_link = soup.find(text=re.compile('Text of a Legislative Document'))
        print 'doclist_link', doclist_link
        doclist_tag = doclist_link.findParent()
        doclist_url = '%s%s' % ('http://dlr.leg.wa.gov/tld/', doclist_tag['href'])
        print 'doclist_url', doclist_url

        with self.soup_context(doclist_url) as doclist_soup:
            doctable = doclist_soup.find(id=re.compile('ctl00_contentRegion_ctl04_grdView'))
            if not doctable:
                return

            rows = doctable.findAll('tr')
            for i, row in enumerate(rows):
                if i < 2:
                    continue
                tds = row.findAll('td')
                print('row', i)
                doc_type = None
                doc_name = None
                doc_htm_url = None
                for j, td in enumerate(tds):
                    print(' td', j)
                    if j == 0:
                        continue
                    if j == 1:
                        tag_htm = td.find('a', id=re.compile('ctl00_contentRegion_ctl04_grdView_ctl0%s_htmLink' % i))
                        
                        print('tag_htm', tag_htm)
                        
                        if tag_htm:
                            doc_htm_url = tag_htm['href']
                            print('doc_htm_url', doc_htm_url)
                    if j == 2:
                        tag_name = td.find(id=re.compile('ctl00_contentRegion_ctl04_grdView_ctl0%s_lblName' % i))
                        if tag_name:
                            doc_name = tag_name.string
                            print('docname', doc_name)
                            print('tag_name', tag_name)
                    if j == 3:
                        tag_type = td.find(id=re.compile('ctl00_contentRegion_ctl04_grdView_ctl0%s_lblDocumentType' % i))
                        if tag_type:
                            doc_type = tag_type.string
                            print('type', doc_type)
                    
                if not doc_type or not doc_name or not doc_htm_url:
                    continue
                if doc_type == "Bills":
                    print 'add_version ', doc_name, doc_htm_url
                    bill.add_version(doc_name, doc_htm_url)
                else:
                    print 'add_document ', doc_name, doc_htm_url
                    bill.add_document(doc_name, doc_htm_url)

    def _scrape_bill_sponsors(self, soup, bill):
        sponsor_type = 'primary'
        for sponsor in soup.findAll('a', title=re.compile('View Bills Sponsored by')):
        
            bill.add_sponsor(sponsor_type, sponsor.string)
            sponsor_type = 'cosponsor'

    def _scrape_bill_votes(self, soup, bill, chamber):
        # scrape votes
        # http://flooractivityext.leg.wa.gov/rollcall.aspx?id=9695&bienId=4
        for roll_call_link in soup.findAll('a', href=re.compile('ShowRollCall')):
            print('roll_call ', roll_call_link)
            print('roll_call href ', roll_call_link['href'])
            href = roll_call_link['href']
            #if href.count('(') and href.count(')') and href.count(','):
            toks = href.split('(')
            toks = toks[1].split(')')
            toks = toks[0].split(',')
            id = toks[0]
            bienId = toks[1]
            roll_call_url = 'http://flooractivityext.leg.wa.gov/rollcall.aspx?id=%s&bienId=%s' % (id, bienId)
            print('roll_call_url ', roll_call_url)

            with self.soup_context(roll_call_url) as roll_call_info:
                rows = roll_call_info.findAll('tr')
                date = rows[3].find('td').string
                motion = rows[2].find('td').string

                #strip cruft
                motion = string.replace(motion, '&amp;', '')
                motion = string.replace(motion, '&nbsp;', '')
                motion = string.replace(motion, '  ', ' ')

                print('orig motion ', motion)
                # eg. "House vote on Final Passage"
                # lop off first three words to get motion: "Final Passage"
                # first word is chamber
                if toks[0] == 'House':
                    chamber = 'lower'
                elif toks[0] == 'Senate':
                    chamber = 'upper'
                print('chamber ', chamber)
                toks = motion.split(' ')
                motion = ' '.join(toks[3:])
                print('motion ', motion)
                print('date ', date)

                counts = roll_call_info.find(text=re.compile('Yeas:'))
                print('yeas ', counts)
                toks = counts.string.splitlines()
                for tok in toks:
                    print( 'tok ', tok)
                    toks2 = tok.strip().split('&')[0].split(' ')
                    if toks2[0] == 'Yeas:':
                        yes_count = int(toks2[1])
                        print('yes_count ', yes_count)
                    elif toks2[0] == 'Nays:':
                        no_count = int(toks2[1])
                        print('no_count ', no_count)
                    elif toks2[0] == 'Absent:':
                        absent_count = int(toks2[1])
                        print('abs_coount ', absent_count)
                    elif toks2[0] == 'Excused:':
                        excused_count = int(toks2[1])
                        print('excused_count ', excused_count)
                        
                vote = Vote(chamber, date, motion, True, yes_count, no_count, excused_count)
                vote.add_source(roll_call_url)
                #Vote('upper', '12/7/08', 'Final passage', True, 30, 8, 3)

#                        voterLists = roll_call_info.findAll('span', {'class': 'RollCall'})
#                        for voterList in voterLists:
#                            print('voterList ', voterList)
#                            toks = voterList.string.split(',')
#                            for tok in toks:
#                                print('tok ', tok)

                #eg. &nbsp;&nbsp;Representatives Alexander, Angel, Simpson, G., and Mr. Speaker
                #eg. &nbsp;&nbsp;Representative Alexander

                start_tok = 'Representative'
                if chamber == 'upper':
                    start_tok = 'Senator'

                nameLists = roll_call_info.findAll(text=re.compile(start_tok))
                print 'len nameLists', len(nameLists)
                print 'nameLists', nameLists
                if not nameLists:
                    continue
                nameListIdx = 0
                for i, count in enumerate([yes_count, no_count, absent_count, excused_count]):
                    print 'i,count', i, count
                    if count is 0:
                        continue
                    nameList = nameLists[nameListIdx]
                    nameListIdx = nameListIdx + 1

                    start_tok = 'Representative'
                    if chamber == 'upper':
                        start_tok = 'Senator'
                    if count > 1:
                        start_tok = '%ss' % start_tok
                    print 'start_tok', start_tok

                    if not nameList:
                        continue

                    if count > 2:
                        toks = nameList.split(',')
                    else:
                        toks = nameList.split('and')


                    #eg. &nbsp&nbsp;Senators Benton
                    #eg. &nbsp&nbsp;Senator Benton
                    first_tok = toks.pop(0)
                    print 'first_tok', first_tok
                    name = first_tok.split(start_tok)[-1].strip()
                    print('first_name', name)
                    if i == 0:
                        vote.yes(name)
                    elif i == 2:
                        vote.no(name)

                    if count == 1:
                        continue
                    if count == 2:
                        last_tok = toks[0]
                    else:
                        #eg. and Zarelli
                        last_tok = toks.pop(-1)
                    print 'last_tok', last_tok
                    name = last_tok.replace('and ', '', 1)
                    if type == 'yes':
                        vote.yes(name)
                    elif type == 'no':
                        vote.no(name)
                    print('last_name', name)

                    sz = len(toks)
                    for j, tok in enumerate(toks):
                        name = tok.strip()
                        if name[1] == '.':
                            continue
                        if j+1 < sz:
                            next_tok = toks[j+1].strip()
                            if next_tok[1] == '.':
                                name = ('%s, %s' % (name, next_tok))
                        print('name', name)
                        if type == 'yes':
                            vote.yes(name)
                        elif type == 'no':
                            vote.no(name)
                    print 'nameList ', nameList



    def scrape_bills(self,chamber,year):
        self.log("Getting bill list for %s %s" % (chamber, year))

        if chamber == 'upper':
            min_id = self.upper_min_id
            max_id = self.upper_max_id
        elif chamber == 'lower':
            min_id = self.lower_min_id
            max_id = self.lower_max_id

        for id in range(min_id, max_id):
            bill_info_url = 'http://dlr.leg.wa.gov/billsummary/default.aspx?year=%s&bill=%s' % (year, id)
            with self.soup_context(bill_info_url) as soup:
                print('opened %s', id)
                bill_id = soup.find('span', id='ctl00_contentRegion_lblShortBillID').string
                bill_title = soup.find('span', id='ctl00_contentRegion_lblBriefDescription').string

                print('bill_id ', bill_id)
                print('bill_title ', bill_title)
                session_name = self._session_dict[year]

                bill = Bill(session_name, chamber, bill_id, bill_title)
                bill.add_source(bill_info_url)

                self._scrape_bill_docs(soup, bill)

                self._scrape_bill_sponsors(soup, bill)
                self._scrape_bill_votes(soup, bill, chamber)

                self.add_bill(bill)

if __name__ == '__main__':
    WALegislationScraper.run()

#http://search.leg.wa.gov/advanced/3.0/FindSub.asp?UnMarkXMark=21#Item18
#http://search.leg.wa.gov/advanced/3.0/FindSub.asp?UnMark=21#Item18
# http://dlr.leg.wa.gov/topicalindex/Results.aspx?year=1991
# biennium: 91-92, 93-94, 95-96, 97-98, 99-00, 01-02, 03-04, 05-06, 07-08, 09-10 
# http://apps.leg.wa.gov/rosters/Members.aspx
# http://apps.leg.wa.gov/rosters/Members.aspx?Chamber=H
# http://apps.leg.wa.gov/rosters/Members.aspx?Chamber=S
#http://www.leg.wa.gov/house/representatives/Pages/default.aspx
#http://www.leg.wa.gov/Senate/Senators/Pages/default.aspx
# http://www.leg.wa.gov/LIC/Documents/SubscriptionsEndOfSessionHistorical/MembersOfLeg%202009.pdf
# http://www.sos.wa.gov/library/legsession.aspx
# http://dlr.leg.wa.gov/searchresults/default.aspx?id=13&params=3,3,4,12/1/1990&desc=7BsBOdyv8SiC1uaQgEsQdCc1VE0e%2bhfv45XXdb0Tdn5PL/0IBZ5qP/xWc3xnOEnFjlGKEpsS592r8XQ3Ds0%2b31r3YW0n%2bAwcb4P8Q0k9S9c%3d&bienString=1991-92

# http://www.leg.wa.gov/History/House/ClassPhotos/Pages/1889house.aspx
# http://www.leg.wa.gov/History/House/ClassPhotos/Pages/2009house.aspx
# http://www.leg.wa.gov/History/Senate/ClassPhotos/Pages/1889Senate.aspx
