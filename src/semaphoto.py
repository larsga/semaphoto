
import os
import web
import sparql

# TODO
#  - install Virtuoso on Linux  
#
#  - paging in "person" template
#  - EXIF info window
#  - privacy filtering
#  - places
#  - years and months
#  - map
#  - logging in
#  - admin mode functions: delete etc
#  - rating of photos
#  - comments (requires markup rendering)
#  - metadata about photo collection (requires markup rendering)
#  - layout of photo page
#  - ancestors of place
#  - small map of place
#  - facet navigators
#  - search

# TODO AFTER CHANGEOVER
#  - add config file, for loading location of images
#  - layout of photo page
#  - videos
#  - metadata editor
#  - fullscreen mode
#  - tagging?

ENDPOINT = "http://localhost:8890/sparql"
PREFIXES = "PREFIX sp: <http://psi.garshol.priv.no/semaphoto/ont/>"

urls = (
    '/', 'StartPage',
    '/people\\.jsp', 'PeoplePage',
    '/person\\.jsp', 'PersonPage',
    '/photo\\.jsp', 'PhotoPage',
    '/events\\.jsp', 'EventsPage',
    '/event\\.jsp', 'EventPage',
    '/categories\\.jsp', 'CategoriesPage',
    '/category\\.jsp', 'CategoryPage',
    '/places\\.jsp', 'PlacesPage',
    '/place\\.jsp', 'PlacePage',
    )

class StartPage:
    def GET(self):
        types = [("People", "sp:Person", "people.jsp"),
                 ("Places", "sp:Place", ""),
                 ("Events", "sp:Event", "events.jsp"),
                 ("Categories", "sp:Category", "categories.jsp")]
        counts = [(label, count(type), link) for (label, type, link) in types]

        
        (label, id, time, pid, pname, eid, ename) = \
          q_row("""select ?label, ?id, ?time, ?pid, ?pname, ?eid, ?ename where {
                             ?s dc:title ?label;
                                sp:id ?id;
                                sp:time-taken ?time.
                             OPTIONAL { ?s sp:taken-at ?place.
                                        ?place sp:name ?pname;
                                          sp:id ?pid }
                             OPTIONAL { ?s sp:taken-during ?event.
                                        ?event sp:name ?ename;
                                          sp:id ?eid  }
                             { select ?s where { ?s a sp:Photo. }
                               order by bif:rnd(1000000, ?s) limit 1 }
                    }""")

        place = None
        event = None
        if pid:
            place = (pid, pname)
        if eid:
            event = (eid, ename)
        
        return render.startpage(counts, label, id, time, place, event, conf)

class PeoplePage:
    def GET(self):
        query = """SELECT ?l, ?id, count(?i) WHERE {
          ?p a sp:Person.
          ?p sp:name ?l.
          ?p sp:id ?id.
          ?i sp:depicts ?p.
        } GROUP BY ?l ?id ORDER BY ?l"""
        letters = []
        for (name, id, count) in q(query):
            l = name.value[0]
            if letters and letters[-1][0] == l:
                letters[-1][1].append((name, id, count))
            else:
                letters.append((l, [(name, id, count)]))
            
        return render.people(letters)

class PersonPage:
    def GET(self):
        person_id = web.input()["id"]
        name = q_get('select ?name where { ?s sp:id "%s"; sp:name ?name }' %
                     person_id)
        f = '?i sp:depicts ?p. ?p sp:id "%s". ' % person_id
        return render.photolist(name, conf, ListPager(f), person_id)

class PhotoPage:
    def GET(self):
        photo_id = web.input()["id"]
        
        query = """
          select ?title, ?time, ?event_id, ?event_name, ?place_id, ?place_name,
                 ?desc
          where { 
            ?i sp:id "%s";
              dc:title ?title;
              sp:time-taken ?time.

            OPTIONAL {
              ?i sp:description ?desc.
            }

            OPTIONAL {
              ?i sp:taken-during ?e.
              ?e sp:id ?event_id;
                 sp:name ?event_name.
            }

           OPTIONAL {
              ?i sp:taken-at ?p.
              ?p sp:id ?place_id;
                 sp:name ?place_name.
            }
          } 
        """ % photo_id
        
        (title, time, event_id, event_name, place_id, place_name, desc) = q_row(query)

        query = """
        select ?id, ?name where {
          ?i sp:id "%s";
            sp:in-category ?c.
          ?c sp:id ?id;
             sp:name ?name.
        }
        """
        cats = q(query % photo_id)

        query = """
        select ?id, ?name where {
          ?i sp:id "%s";
            sp:depicts ?p.
          ?p sp:id ?id;
             sp:name ?name.
        }
        """
        people = q(query % photo_id)

        query = """
        select ?id where {
          ?i sp:id "%s";
            sp:time-taken ?time.
          ?i2 sp:id ?id;
            sp:time-taken ?time2.
          FILTER (STR(?time2) < STR(?time))
        } order by desc(?time2) limit 1
        """
        prev = q_get(query % photo_id)

        query = """
        select ?id where {
          ?i sp:id "%s";
            sp:time-taken ?time.
          ?i2 sp:id ?id;
            sp:time-taken ?time2.
          FILTER (STR(?time2) > STR(?time))
        } order by asc(?time2) limit 1
        """
        next = q_get(query % photo_id)
        
        return render.photo(photo_id, title, time, event_id, event_name,
                            place_id, place_name, desc, cats, people,
                            prev, next, conf)

class EventsPage:
    def GET(self):
        query = """SELECT ?l, ?id, ?start, ?end, count(?i) WHERE {
          ?e a sp:Event;
             sp:name ?l;
             sp:id ?id;
             sp:start-date ?start;
             sp:end-date ?end.
          ?i sp:taken-during ?e.
        } GROUP BY ?id ?start ?end ?l 
        ORDER BY ?start"""

        years = {}
        for (name, id, start, end, count) in q(query):
            year = str(start)[ : 4]
            events = years.get(year, [])
            if not events:
                years[year] = events
            events.append((name, id, start, end, count))

        years = years.items()
        years.sort()
        years.reverse()
        return render.events(years)

class EventPage:
    def GET(self):
        event_id = web.input()["id"]
        
        name = q_get('select ?name where { ?s sp:id "%s"; sp:name ?name }' %
                     event_id)

        query = """
          select ?id, ?title, ?time
          where { 
            ?i sp:taken-during ?e;
              sp:id ?id;
              dc:title ?title;
              sp:time-taken ?time.
            ?e sp:id "%s".
          } order by desc(?time) limit 50
        """ % event_id
        
        photos = q(query)
        return render.photolist(name, photos, conf)

class CategoriesPage:
    def GET(self):
        query = """SELECT ?l, ?id, count(?i) WHERE {
          ?p a sp:Category.
          ?p sp:name ?l.
          ?p sp:id ?id.
          ?i sp:in-category ?p.
        } GROUP BY ?l ?id ORDER BY ?l"""
        return render.categories(q(query))

class CategoryPage:
    def GET(self):
        event_id = web.input()["id"]
        
        name = q_get('select ?name where { ?s sp:id "%s"; sp:name ?name }' %
                     event_id)

        query = """
          select ?id, ?title, ?time
          where { 
            ?i sp:in-category ?c;
              sp:id ?id;
              dc:title ?title;
              sp:time-taken ?time.
            ?c sp:id "%s".
          } order by desc(?time) limit 50
        """ % event_id
        
        photos = q(query)
        return render.photolist(name, photos, conf)

class PlacesPage:
    def GET(self):
        return "<p>Uhhh..."

class PlacePage:
    def GET(self):
        place_id = web.input()["id"]
        name = q_get('select ?name where { ?s sp:id "%s"; sp:name ?name }' %
                     place_id)

        query = """
          select ?id, ?title, ?time
          where { 
            ?i sp:taken-at ?p;
              sp:id ?id;
              dc:title ?title;
              sp:time-taken ?time.
            ?p sp:id "%s".
          } order by desc(?time) limit 50
        """ % place_id
        
        photos = q(query)
        return render.photolist(name, photos, conf)

# --- MODEL

class ListPager:

    def __init__(self, fragment):
        self._fragment = fragment
        self._page_no = int(web.input().get("n", 1))
        count = q_get('select count(?i) where { %s } ' % self._fragment)
        self._count = int(count.value)

    def get_page_count(self):
        return self._count / 50 + 1

    def get_page_no(self):
        return self._page_no

    def get_photos(self):
        offset = (self._page_no - 1) * 50
        query = """
          select ?id, ?title, ?time
          where { 
            ?i sp:id ?id;
              dc:title ?title;
              sp:time-taken ?time.
            %s
          } order by desc(?time) offset %s limit 50
        """ % (self._fragment, offset)
        return q(query)
        
class Configuration:

    def get_photo_uri(self):
        return "http://larsga.geirove.org/photoserv.fcgi?"
    
# --- UTILITIES

def q(query):
    return sparql.query(ENDPOINT, PREFIXES + query)

def q_get(query):
    row = sparql.query(ENDPOINT, PREFIXES + query).fetchone()
    (a, ) = row
    return a[0]

def q_row(query):
    row = sparql.query(ENDPOINT, PREFIXES + query).fetchone()
    (a, ) = row
    return a

def count(type):
    query = "SELECT DISTINCT count(*) WHERE {?s a %s}" % type
    result = q(query)
    return int(result.fetchone().next()[0].value)

# --- SETUP
        
conf = Configuration()

web.config.debug = True
web.webapi.internalerror = web.debugerror

appdir = os.path.dirname(__file__)
render = web.template.render(os.path.join(appdir, 'templates/'),
                             base = "base")

app = web.application(urls, globals(), autoreload = False)
#app.internalerror = Error

if __name__ == "__main__":
    app.run()

#print PeoplePage().GET()
