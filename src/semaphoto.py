
import os
import web
import markdown2
import sparql

# TODO
#  - install Virtuoso on Linux  
#
#  - Norwegian character problem
#  - facet navigators
#  - context sequence

#  - logging in
#    - rating of photos
#    - comments (requires markup rendering)
#    - privacy filtering
#    - admin mode functions: delete etc

# TODO AFTER CHANGEOVER
#  - add config file, for loading location of images
#  - layout of photo page
#  - videos
#  - metadata editor
#  - fullscreen mode
#  - tagging?

NS_SP = 'http://psi.garshol.priv.no/semaphoto/ont/'
ENDPOINT = "http://localhost:8890/sparql"
PREFIXES = 'PREFIX sp: <%s>' % NS_SP

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
    '/year\\.jsp', 'YearPage',
    '/month\\.jsp', 'MonthPage',
    '/map\\.jsp', 'MapPage',
    '/search-form\\.jsp', 'SearchPage',
    '/search-result\\.jsp', 'SearchResultsPage',
    )

class StartPage:
    def GET(self):
        types = [("People", "sp:Person", "people.jsp"),
                 ("Places", "sp:Place", "places.jsp"),
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

        p = q('''
          select ?l ?d where {
            <%s> rdfs:label ?l; sp:description ?d
          }
        ''' % conf.get_photo_graph())[0]
        (title, desc) = p

        total = q_get('select count(*) where { ?s a sp:Photo }')

        # do markdown conversion here
        desc = markdown2.markdown(desc.value)
        return render.startpage(counts, label, id, time, place, event, conf,
                                title, desc, total)

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
        f = '?i sp:taken-during ?e. ?e sp:id "%s". ' % event_id
        return render.photolist(name, conf, ListPager(f, "asc"), event_id)

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
        cat_id = web.input()["id"]
        name = q_get('select ?name where { ?s sp:id "%s"; sp:name ?name }' %
                     cat_id)
        f = '?i sp:in-category ?c. ?c sp:id "%s". ' % cat_id
        return render.photolist(name, conf, ListPager(f), cat_id)

class PlacesPage:
    def GET(self):
        # 1. do flat query
        query = '''
          select ?parent, ?place, ?label, ?id where {
            ?place a sp:Place;
              sp:name ?label;
              sp:id ?id.
            OPTIONAL {
              ?place sp:contained-in ?parent .
            }
          }
        '''
        
        # 2. build tree model
        tree = TreeModel()
        for (parent, place, label, id) in q(query):
            tree.add_node(parent and str(parent), str(place), label.value, id.value)
        tree.sort()
       
        # 3. render
        return render.places(tree)

class PlacePage:
    def GET(self):
        place_id = web.input()["id"]

        # main page
        name = q_get('select ?name where { ?s sp:id "%s"; sp:name ?name }' %
                     place_id)
        f = '''
          ?p sp:id "%s".
          ?i sp:taken-at ?c. 
          ?c sp:contained-in ?p option (transitive, t_min (0), t_distinct)
        ''' % place_id

        # side bar
        children = q('''
          select ?pid ?label where {
            ?place sp:contained-in ?parent.
            ?parent sp:id "%s".
            ?place sp:id ?pid;
               sp:name ?label.
          }
        ''' % place_id)
        coords = q('''select ?lt ?ln where {
          ?parent sp:id "%s";
            sp:latitude ?lt;
            sp:longitude ?ln. }''' % place_id)
        positioned = []
        if coords:
            query = '''
              select ?place, ?label, ?id, ?lat, ?long, ?desc where {
                ?place a sp:Place;
                  sp:name ?label;
                  sp:id ?id;
                  sp:latitude ?lat;
                  sp:longitude ?long.
                OPTIONAL {
                  ?place sp:description ?desc.
                }
              }
            '''
            positioned = q(query)
            
        sidebar = lambda: side_render.place_side(place_id, children,
                                                 coords, positioned)

        # top bar
        ancestors = []
        current = place_id
        while 1:
            row = q_row('''select ?pid ?label where {
              ?s sp:id "%s";
                sp:contained-in ?parent.
              ?parent sp:id ?pid;
                sp:name ?label.
            }
            ''' % current)
            if row:
                (pid, label) = row
                ancestors.append((pid, label))
                current = pid
            else:
                break
        if ancestors:
            ancestors.reverse()
            topbar = lambda: side_render.place_top(ancestors)
        else:
            topbar = None
            
        return render.photolist(name, conf, ListPager(f), place_id, sidebar,
                                topbar)

class YearPage:
    def GET(self):
        year = web.input()["year"]
        f = 'FILTER(bif:starts_with(?time, "%s-"))' % year
        qe = '?i sp:time-taken ?time .'

        monthquery = '''
          select distinct bif:substring(?time, 1, 7) as ?month where {
            ?i sp:time-taken ?time
            FILTER(bif:starts_with(?time, "%s-")).
          } order by ?month
        ''' % year

        months = [month.value for (month,) in q(monthquery)]
        sidebar = lambda: side_render.month_side(months)
        return render.photolist(year, conf, ListPager(f, "asc", qe, "year"),
                                year, sidebar)

class MonthPage:
    def GET(self):
        month = web.input()["month"]
        f = 'FILTER(bif:starts_with(?time, "%s-"))' % month
        qe = '?i sp:time-taken ?time .'
        return render.photolist(month, conf, ListPager(f, "asc", qe, "month"),
                                month)

class MapPage:
    def GET(self):
        query = '''
          select ?place, ?label, ?id, ?lat, ?long, ?desc where {
            ?place a sp:Place;
              sp:name ?label;
              sp:id ?id;
              sp:latitude ?lat;
              sp:longitude ?long.
            OPTIONAL {
              ?place sp:description ?desc.
            }
          }
        '''
        return render.mappage(conf, q(query))

class SearchPage:
    def GET(self):
        return render.search()
    
class SearchResultsPage:
    def GET(self):
        # this is the default Virtuoso fct search query, modified for
        # our purposes
        search = web.input()["search"]
        query = '''
select ?s1 as ?c1, ( bif:search_excerpt ( bif:vector ( %s ) , ?o1 ) ) as ?c2, ?type, ?id where 
  { 
    { 
      { 
        select ?s1, ( ?sc * 3e-1 ) as ?sc, ?o1, ( sql:rnk_scale ( <LONG::IRI_RANK> ( ?s1 ) ) ) as ?rank where 
        { 
          quad map virtrdf:DefaultQuadMap 
          { 
            graph <http://psi.garshol.priv.no/semaphoto/graph>
            { 
              ?s1 ?s1textp ?o1 .
              ?o1 bif:contains '%s' option ( score ?sc ) .
              
            }
           }
         }
       order by desc ( ?sc * 3e-1 + sql:rnk_scale ( <LONG::IRI_RANK> ( ?s1 ) ) ) limit 50 offset 0 
      }
     }
     ?s1 a ?type; sp:id ?id .
   }
  ''' % (token_list_for_search(search),
         tokenize_for_search(search))
        results = q(query)
        return render.search_result(conf, search, results, typemap)

def tokenize_for_search(search):
    return '( %s )' % ' AND '.join([t.upper() for t in search.split()])

def token_list_for_search(search):
    return ', '.join(["'%s'" % t.upper() for t in search.split()])

# --- MODEL

class TreeModel:

    def __init__(self):
        self._uri_to_node = {}
        self._roots = []

    def get_roots(self):
        return self._roots
        
    def add_node(self, parent, place, label, id):
        pnode = self._uri_to_node.get(parent)
        if parent and not pnode:
            # there is a parent, but we haven't seen it before, so
            # make a place-holder
            pnode = TreeNode(None, parent)
            self._uri_to_node[parent] = pnode
            # as far as we know, this is a root
            self._roots.append(pnode)

        node = self._uri_to_node.get(place)
        if not node:
            node = TreeNode(pnode, place, label, id)
            self._uri_to_node[place] = node
            if not pnode:
                self._roots.append(node)
        else:
            # we've been observed as somebody's parent before, so just
            # fill in the values
            node.set(pnode, place, label, id)

            # when we were seen earlier we must have been considered a
            # root, but if pnode is set that's not true
            if pnode:
                self._roots.remove(node)

    def sort(self):
        self._roots.sort()
        for node in self._roots:
            node.sort()
                
class TreeNode:

    def __init__(self, parent, uri, label = None, id = None):
        self.set(parent, uri, label, id)
        self._children = []

    def add_child(self, child):
        self._children.append(child)

    def set(self, parent, uri, label, id):
        self._parent = parent
        self._uri = uri
        self._label = label
        self._id = id
        if parent:
            parent.add_child(self)

    def get_children(self):
        return self._children

    def get_label(self):
        return self._label

    def get_id(self):
        return self._id

    def get_uri(self):
        return self._uri

    def sort(self):
        self._children.sort()
        for node in self._children:
            node.sort()

    def __cmp__(self, other):
        if not isinstance(other, TreeNode):
            return -1

        return cmp(self._label, other.get_label())
            
class ListPager:

    def __init__(self, fragment, sortdir = "desc", count_extra = '',
                 idparam = 'id'):
        self._fragment = fragment
        self._page_no = int(web.input().get("n", 1))
        count = q_get('select count(?i) where { %s %s } ' %
                      (count_extra, self._fragment))
        self._count = int(count.value)
        self._sortdir = sortdir
        self._idparam = idparam

    def get_page_count(self):
        return self._count / 50 + 1

    def get_page_no(self, offset = 0):
        return self._page_no + offset

    def get_page_no_params(self, topic_id, page_no):
        return "?%s=%s&n=%s" % (self._idparam, topic_id, page_no)

    def get_photos(self):
        offset = (self._page_no - 1) * 50
        query = """
          select ?id, ?title, ?time
          where { 
            ?i sp:id ?id;
              dc:title ?title;
              sp:time-taken ?time.
            %s
          } order by %s(?time) offset %s limit 50
        """ % (self._fragment, self._sortdir, offset)
        return q(query)
        
class Configuration:

    def get_photo_uri(self):
        return 'http://larsga.geirove.org/photoserv.fcgi?'

    def get_gmaps_key(self):
        return None

    def get_photo_graph(self):
        return 'http://psi.garshol.priv.no/semaphoto/graph'
    
# --- UTILITIES

def q(query):
    return sparql.query(ENDPOINT, PREFIXES + query).fetchall()

def q_get(query):
    row = sparql.query(ENDPOINT, PREFIXES + query).fetchone()
    # FIXME: need to handle no values, somehow
    (a, ) = row
    return a[0]

def q_row(query):
    rows = sparql.query(ENDPOINT, PREFIXES + query).fetchall()
    if rows:
        return rows[0]
    else:
        return None

def count(type):
    query = "SELECT DISTINCT count(*) WHERE {?s a %s}" % type
    result = q(query)
    return int(result[0][0].value)

# --- CONSTANTS

typemap = {
    NS_SP + 'Person'   : 'person.jsp',
    NS_SP + 'Place'    : 'place.jsp',
    NS_SP + 'Event'    : 'event.jsp',
    NS_SP + 'Category' : 'category.jsp',
    }

# --- SETUP
        
conf = Configuration()

web.config.debug = True
web.webapi.internalerror = web.debugerror

appdir = os.path.dirname(__file__)
render = web.template.render(os.path.join(appdir, 'templates/'),
                             base = "base")
side_render = web.template.render(os.path.join(appdir, 'templates/'))

app = web.application(urls, globals(), autoreload = False)
#app.internalerror = Error

if __name__ == "__main__":
    app.run()
