#!/usr/bin/python

from __future__ import division

import re
import datetime
import urlparse

from urllib2 import urlopen

import gdata.calendar.service
import atom.service

from settings import google_username, google_password, google_source

import BeautifulSoup
import dateutil.parser

calendar_name = '/calendar/feeds/default/private/full'
event_id_name = 'ukaudaxcalendar#event_id'
event_status_name = 'ukaudaxcaledar#event_status'

event_link_format = "http://www.aukweb.net/cal/calsolo.php?Ride=%s"
google_api_when_date_format = '%Y-%m-%dT%H:%M:%S.000'

# This will be used everywhere as the minimum speed
# in kph in order to calculate a rough end time.
# Some events will have a lower minimum speed
# which we could get from the event details page,
# but that would involve opening every event so this
# will do for the moment.

minimum_speed = 15
calendar_query_back_days = 10
calendar_query_forward_days = 1000

def DateRangeQuery(calendar_service, start_date=None, end_date=None, futureevents="false", max_results=25):
    print 'Date range query for events on Primary Calendar: %s to %s' % (start_date, end_date,)
    query = gdata.calendar.service.CalendarEventQuery('default', 'private', 'full')
    if start_date is not None:
      query.start_min = start_date.strftime("%Y-%m-%d")
    if end_date is not None:
      query.start_max = end_date.strftime("%Y-%m-%d")
    query.futureevents = futureevents
    query._SetMaxResults(str(max_results))
    feed = calendar_service.CalendarQuery(query)

    for i, an_event in enumerate(feed.entry):
        print '\t%s. %s' % (i, an_event.title.text,)
        for a_when in an_event.when:
            print '\t\tStart time: %s' % (a_when.start_time,)
            print '\t\tEnd time:   %s' % (a_when.end_time,)

    return feed
  
            
def InsertSingleEvent(calendar_service,
                      calendar_name=calendar_name, 
                      title = None, 
                      content='',
                      where='', 
                      start_time=None,
                      end_time=None):
    """This function is mostly copied from the python tab of the
    google calendar API documentation."""
    
    event = gdata.calendar.CalendarEventEntry()
    event.title = atom.Title(text=title)
    event.content = atom.Content(text=content)
    event.where.append(gdata.calendar.Where(value_string=where))

    start_time = start_time.strftime(google_api_when_date_format)
    end_time = end_time.strftime(google_api_when_date_format)
    event.when.append(gdata.calendar.When(start_time=start_time, end_time=end_time))

    try:
        new_event = calendar_service.InsertEvent(event, calendar_name)
        success = True
    except:
        success = False

    if success:
        print 'New single event inserted: %s' % (new_event.id.text,)
        print '\tEvent edit URL: %s' % (new_event.GetEditLink().href,)
        print '\tEvent HTML URL: %s' % (new_event.GetHtmlLink().href,)
        
        return new_event
    else:
        print '************************************************************'
        print 'Failed to insert event'
        print 'with title: %s' %repr(event.title)
        return None


calendar_url = "http://www.aukweb.net/events/?From=13%2F02%2F2011&To=24&Days=&Category=&Dist_min=&Dist_max=&Aaa=&Region="
#example_file_name = "source/calist5.php"

class AudaxEvent:
    def __init__(self):
        self.status = None
        self.distance = None
        self.start_datetime = None
        self.end_datetime = None
        self._date = None
        self.id = None
        self.link = None
        self.place = None
        self.name = None
        self._start_time = None
        self._day = None
        self.AA_points = None
        self.climb = None
        self.code = None
        self.pbp = False
        self.paypal = False
        self.cost = None
        self.organiser = None

    def getTitleString(self):
        if self.status == 'C':
            # This event is cancelled. We should make that clear in
            # the title
            cancelled_bit = "CANCELLED "
        else:
            cancelled_bit = ""
        
        title_string = "%s%s %s" %(cancelled_bit, self.distance, self.name)

        return title_string

    def getContentString(self):
        if self.status == 'C':
            # This event is cancelled. We should make that clear in
            # the content as well
            cancelled_bit = "CANCELLED\n"
        else:
            cancelled_bit = None

        if self.climb is not None:
          climb_bit = "Climb: %sm" %(self.climb)
        else:
          climb_bit = None

        content_string = "\n".join([x for x in [cancelled_bit,
                                    '<a href="%s">%s</a>' %(self.link, self.name),
                                    "Distance: %skm" %(self.distance),
                                    "Start: %s" %(self._start_time),
                                    "%s %s %s" %(self.code, '[PBP]' if self.pbp else '', 'AA%s' %self.AA_points if self.AA_points else ''),
                                    climb_bit,
                                    "Cost: &pound;%.2f %s" %(self.cost, '(paypal)' if self.paypal else ''),
                                    "Organiser: %s" %(self.organiser)
                                    ] if x])

        return content_string
      
    def __repr__(self):
        return repr((self.distance, self.name, self.organiser, self.start_datetime, self.end_datetime))

def main():

    # 1) log in to the calendar

    calendar_service = gdata.calendar.service.CalendarService()
    calendar_service.email = google_username
    calendar_service.password = google_password 
    calendar_service.source = google_source
    calendar_service.ProgrammaticLogin()
  
    # 2) fetch a list of the ids of events in the calendar already
    
    event_dict = {}
    
    #feed = calendar_service.GetCalendarEventFeed()

    start_date = datetime.datetime.today() - datetime.timedelta(calendar_query_back_days)
    end_date = datetime.datetime.today() + datetime.timedelta(calendar_query_forward_days)
    feed = DateRangeQuery(calendar_service, start_date=start_date, end_date=end_date, max_results=10000)
    
    for i, an_event in enumerate(feed.entry):
        for extended_property in an_event.extended_property:
          if extended_property.name == event_id_name:
            event_dict[extended_property.value] = an_event
          #print an_event.when.start_time, an_enent.when.end_time

#    print event_dict

    # 3) get list of events from audax website
    events_list = []
  
    #example_file = open(example_file_name)
    #file_contents = example_file.read()
    url_obj = urlopen(calendar_url)
    file_contents = url_obj.read()

    # In a nasty hacky way, let's replace accented characters with
    # their unaccented friends.
    file_contents = re.sub('\xea', 'e', file_contents)

    soup = BeautifulSoup.BeautifulSoup(file_contents, convertEntities=BeautifulSoup.BeautifulStoneSoup.ALL_ENTITIES)
    events_div = soup.find(None, {'id': 'eventlist'})
    
    days = events_div.findAll('div', {'class': re.compile('^day.*')})

    for day in days:
        event_date = dateutil.parser.parse(day.h4.string, fuzzy=True)

        events = day.findAll('div', {'class': re.compile('^event.*')})

        for event_soup in events:
            event = AudaxEvent()

            relative_link = event_soup.a['href']
            event.id = relative_link.split('/')[1]
            event.link = urlparse.urljoin(calendar_url, relative_link)

            bolds = event_soup.findAll('b')
            event.code = bolds[0].string.strip()
            
            paypal_img = bolds[1].img
            if paypal_img:
                event.paypal = True
                paypal_img.extract()
                
            string1 = ' '.join(bolds[1].contents)
            # The \.? in the middle of the time is to cope with this erroneous time format:
            # u' 400km       7.:00 from Denmead    Denmead SR Series'
            first_string_regex = re.compile(r'\s*(\d*)km\s*([\d:]{1,2})\.?:?([\d:]{2})\s*from\s*([\w ,\'/\.&\-()]*?)\s{2,}([\w ]*)')

            match = first_string_regex.match(string1)

            try:
                distance_string, start_hours, start_minutes, event.place, event.name = match.groups()
            except:
                import pdb;pdb.set_trace()

            event.distance = int(distance_string)

            # This means the event is a Fleches, or something.
            no_times = start_hours == '::'
            
            if no_times:
                event_time = datetime.time(0)
            else:
                event_time = datetime.time(int(start_hours), int(start_minutes))

            event.start_datetime = datetime.datetime.combine(event_date, event_time)
            
            if no_times:
                event.end_datetime = event.start_datetime + datetime.timedelta(days=1)
            else:
                event.end_datetime = event.start_datetime + datetime.timedelta(hours=event.distance/minimum_speed)
            
            string2 = bolds[1].nextSibling

            second_string_regex = re.compile(r'\n\s*([A-Z]*)\s*(?:\[(PBP)\])?\s*(?:AA(\d*\.?\d*))?\s*(?:\[(\d*)m\])?\s*\xa3(\d*\.?\d*)\s*(.*)')
            match2 = second_string_regex.match(string2)
            try:
                event.code, pbp_string, aa_points_string, climb_string, cost_string, organiser_string = match2.groups()
            except:
                import pdb;pdb.set_trace()

            if pbp_string:
                event.pbp = True
            if aa_points_string: 
                event.AA_points = float(aa_points_string)
            if climb_string: 
                event.climb = int(climb_string)

            event.cost = float(cost_string)
            event.organiser = ' '.join(organiser_string.split())

            events_list.append(event)

    for event in events_list:
        # Have we added an event with this id before?
        # if so, we'll check that the content string of the event hasn't changed,
        # and if it has, we'll change it.

        print event.id
        if event.id in event_dict.keys():
            print "Seen this event before"
            google_api_event = event_dict[event.id]

            new_content_string = event.getContentString()

            if google_api_event.content.text != new_content_string:
              # We need to update the event.
              print "Updating event %s with new content string"
              print new_content_string
              google_api_event.title.text = event.getTitleString()
              google_api_event.content.text = new_content_string
              google_api_event = calendar_service.UpdateEvent(google_api_event.GetEditLink().href, google_api_event)

            for when in google_api_event.when:
              old_start_time = when.start_time.split(".000")[0]+".000"
              old_end_time = when.end_time.split(".000")[0]+".000"

              new_start_time = event.start_datetime.strftime(google_api_when_date_format)
              new_end_time = event.end_datetime.strftime(google_api_when_date_format)

              if new_start_time != old_start_time or new_end_time != old_end_time:
                print "Datetimes have changed."
                print "Old start: %s" %(old_start_time)
                print "New start: %s" %(new_start_time)
                print "Old end: %s" %(old_end_time)
                print "New end: %s" %(new_end_time)
                
                # we need to update the when.
                google_api_event.when = [gdata.calendar.When(start_time=new_start_time, end_time=new_end_time)]
                google_api_event = calendar_service.UpdateEvent(google_api_event.GetEditLink().href, google_api_event)
                
        else:
            # We need to add the event.
        
            googleapi_event = InsertSingleEvent(calendar_service, calendar_name, event.getTitleString(), event.getContentString() , event.place, event.start_datetime, event.end_datetime)
            
            if googleapi_event:
                # so that we can check if an event has already been added, etc
                # we'll add an id to them.
                googleapi_event.extended_property.append(gdata.calendar.ExtendedProperty(name=event_id_name, value=event.id))
                calendar_service.UpdateEvent(googleapi_event.GetEditLink().href, googleapi_event)


if __name__ == "__main__":
  main()


