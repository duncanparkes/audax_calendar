This is a screenscraper which takes the calendar from http://www.aukweb.net/
and makes it available as a Google Calendar at 
http://www.google.com/calendar/embed?src=ukaudaxcalendar%40googlemail.com&ctz=Europe/London

The durations for events in the Calendar have been calculated using a minimum
speed of 15kph for all events, so should not be trusted 
(The actual minimum speed is usually contained in the event's 
home page - follow the link).

Where an event is not in the UK, the time is probably local time.

Everything here has been screenscraped from the audax website. 
If you see anything that has gone wrong, please drop me an email.

To run your own version of this scraper

* Clone the repository
* Copy ``settings_example.py`` to ``settings.py`` and put in your own details. 
* Set up a cron job to run::

    python AudaxCalendar.py

  periodically - I run it once per day.


Prerequisites
-------------

* Requires ``python-gdata``, the Google Data Python client library.

