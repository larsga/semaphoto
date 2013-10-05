
import os, datetime
import web
import markdown2
import photolib

# NOW
#  - order by score
#  - admin mode functions: delete etc
#  - facet navigators
#  - context sequence

#  - script for upload

# LATER
#  - add config file, for loading location of images
#  - layout of photo page
#  - videos
#  - metadata editor
#  - fullscreen mode
#  - tagging?
#  - ipad mode
#  - paging of search

urls = (
    '/', 'StartPage',
    '/index\\.jsp', 'StartPage',
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
    '/best-photos\\.jsp', 'BestPhotosPage',
    '/login,?(.+)?', 'LoginPage',
    '/process-login', 'LoginAction',
    '/process-logout', 'LogoutAction',
    '/set-score', 'SetScoreAction',
    '/add-comment', 'AddCommentAction',
    )

class StartPage:
    def GET(self):
        # do markdown conversion here
        desc = markdown2.markdown(gallery.get_description())
        return render.startpage(conf, gallery, desc, current_user_name())

class PeoplePage:
    def GET(self):
        username = current_user_name()
        letters = {}
        for (person, count) in gallery.get_person_counts(username == None):
            letter = person.get_name()[0]
            l = letters.get(letter, [])
            if not l:
                letters[letter] = l
            l.append((person, count))

        letters = letters.items()
        letters.sort()

        return render.people(letters, username)

class PersonPage:
    def GET(self):
        username = current_user_name()
        person = photolib.Person(web.input()["id"], username == None)
        if person.get_hidden() and not username:
            return render.hidden()
        person.set_pager(ListPager(person))
        return render.photolist(conf, person, username)

class PhotoPage:
    def GET(self):
        username = current_user_name()
        photo = photolib.Photo(web.input()["id"], username == None)
        if photo.get_hidden() and not username:
            return render.hidden()
        return render.photo(conf, photo, username)

class EventsPage:
    def GET(self):
        username = current_user_name()
        years = {}
        for (event, count) in gallery.get_event_counts(username == None):
            year = str(event.get_start_date())[ : 4]
            events = years.get(year, [])
            if not events:
                years[year] = events
            events.append((event, count))

        years = years.items()
        years.sort()
        years.reverse()
        return render.events(years, username)

class EventPage:
    def GET(self):
        username = current_user_name()
        event = photolib.Event(web.input()["id"], username == None)
        event.set_pager(ListPager(event))
        return render.photolist(conf, event, username)

class CategoriesPage:
    def GET(self):
        username = current_user_name()
        return render.categories(gallery.get_category_counts(username == None),
                                 username)

class CategoryPage:
    def GET(self):
        username = current_user_name()
        cat = photolib.Category(web.input()["id"], username == None)
        cat.set_pager(ListPager(cat))
        return render.photolist(conf, cat, username)

class PlacesPage:
    def GET(self):
        username = current_user_name()
        where = None
        if not username:
            where = 'not hidden'
        
        # 1. build tree model
        tree = TreeModel()
        for place in photolib.worm.get_extent(photolib.Place, where):
            pid = place.get_parent() and place.get_parent().get_id()
            tree.add_node(pid, place.get_id(), place.get_name())
        tree.sort()
       
        # 2. render
        return render.places(tree, username)

class PlacePage:
    def GET(self):
        username = current_user_name()
        place_id = web.input()["id"]
        place = photolib.Place(place_id, username == None)
        place.set_pager(ListPager(place))

        places = photolib.worm.get_extent(photolib.Place)
        sidebar = lambda: side_render.place_side(conf, place, places)
        topbar = lambda: side_render.place_top(place)
        return render.photolist(conf, place, username, sidebar, topbar)

class YearPage:
    def GET(self):
        username = current_user_name()
        year = photolib.Year(web.input()["year"], username == None)
        year.set_pager(ListPager(year, idparam = 'year'))
        sidebar = lambda: side_render.month_side(year.get_months())
        return render.photolist(conf, year, username, sidebar)

class MonthPage:
    def GET(self):
        username = current_user_name()
        month = photolib.Month(web.input()["month"], username == None)
        month.set_pager(ListPager(month, idparam = 'month'))
        return render.photolist(conf, month, username)

class MapPage:
    def GET(self):
        username = current_user_name()
        where = None
        if not username:
            where = 'not hidden'
        places = photolib.worm.get_extent(photolib.Place, where)
        return render.mappage(conf, places, username)

class SearchPage:
    def GET(self):
        username = current_user_name()
        return render.search(username)
    
class SearchResultsPage:
    def GET(self):
        search = web.input()["search"]
        username = current_user_name()
        photos = gallery.get_search_results(search, username == None)
        return render.search_result(conf, search, photos, username)
    
messagedict = {
    None : None,
    'failed' : 'Login failed.'
    }
    
class LoginPage:
    def GET(self, message):
        nocache()
        message = messagedict[message]
        referrer = web.ctx.env.get('HTTP_REFERER', '')
        return render.login(current_user_name(), referrer, message)

class LoginAction:
    def POST(self):
        nocache()
        username = web.input()['username']
        person = gallery.get_person_by_username(username)

        if not person or person.get_password() != web.input()['password']:
            web.seeother(web.ctx.homedomain + '/login,failed')
            return

        session.username = username
        goto = web.input()['goto'] or (web.ctx.homedomain + '/')
        web.seeother(goto)

class LogoutAction:
    def POST(self):
        nocache()
        session.username = None
        goto = web.input()['goto'] or (web.ctx.homedomain + '/')
        web.seeother(goto)

class SetScoreAction:
    def POST(self):
        rating = photolib.Rating(None)
        rating.set_photo(web.input().get('id'))
        rating.set_score(int(web.input().get('score')))
        rating.set_username(current_user_name() or 'nobody')
        rating.set_updated(datetime.datetime.now())
        rating.create()
        photolib.conn.commit()

class AddCommentAction:
    def POST(self):
        photoid = web.input().get('id')
        content = web.input().get('comment')
        if not content:
            return '<p>No actual comment.</p>'
        
        comment = photolib.Comment(None)
        comment.set_photo(photoid)
        comment.set_content(content)
        comment.set_datetime(datetime.datetime.now())

        username = current_user_name()
        if username:
            comment.set_username(username)

        else:
            # we don't know the user, so things get a bit more involved
            if web.input().get('clever') or not web.input().get('clever2'):
                return '<p>Spam rejected.</p>'
            name = web.input().get('name')
            if not name:
                return '<p>You have to specify a name.</p>'
            
            comment.set_email(web.input().get('email'))
            comment.set_url(web.input().get('url'))
            comment.set_name(name)
            comment.set_username('nobody')
            
        comment.create()
        photolib.conn.commit()
        web.seeother(web.ctx.homedomain + '/photo.jsp?id=' + photoid)

class BestPhotosPage:
    def GET(self):
        username = current_user_name()
        return render.photolist(conf, BestPager(username == None), username)
        
# --- MODEL

class TreeModel:

    def __init__(self):
        self._id_to_node = {}
        self._roots = []

    def get_roots(self):
        return self._roots
        
    def add_node(self, parent, id, label):
        pnode = self._id_to_node.get(parent)
        if parent and not pnode:
            # there is a parent, but we haven't seen it before, so
            # make a place-holder
            pnode = TreeNode(None, parent)
            self._id_to_node[parent] = pnode
            # as far as we know, this is a root
            self._roots.append(pnode)

        node = self._id_to_node.get(id)
        if not node:
            node = TreeNode(pnode, id, label)
            self._id_to_node[id] = node
            if not pnode:
                self._roots.append(node)
        else:
            # we've been observed as somebody's parent before, so just
            # fill in the values
            node.set(pnode, id, label)

            # when we were seen earlier we must have been considered a
            # root, but if pnode is set that's not true
            if pnode:
                self._roots.remove(node)

    def sort(self):
        self._roots.sort()
        for node in self._roots:
            node.sort()
                
class TreeNode:

    def __init__(self, parent, id, label = None):
        self.set(parent, id, label)
        self._children = []

    def add_child(self, child):
        self._children.append(child)

    def set(self, parent, id, label):
        self._parent = parent
        self._id = id
        self._label = label
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

# ----- PAGING LOGIC

class Pager:

    def __init__(self):
        self._page_no = int(web.input().get("n", 1))

    def get_page_count(self):
        return self._count / 50 + 1

    def get_page_no(self, offset = 0):
        return self._page_no + offset

    def get_offset(self):
        return (self._page_no - 1) * 50

    def get_id(self):
        return None
    
class BestPager(Pager):

    def __init__(self, filter = False):
        Pager.__init__(self)
        self._filter = filter
        self._count = gallery.get_voted_photos(filter)
    
    # --- container object implementation

    def get_name(self):
        return 'Best photos'

    def get_pager(self):
        return self # we cheat a little bit
        
    # --- pager implementation
        
    def can_be_chronological(self):
        return False # sorting by time makes no sense here

    def get_page_count(self):
        return self._count / 50 + 1

    def get_page_no(self, offset = 0):
        return self._page_no + offset

    def get_page_no_params(self, topic_id, page_no = None):
        return "?n=%s" % (page_no or self._page_no)

    def get_photos(self):
        return gallery.get_best_photos(self.get_offset(), self._filter)
    
class ListPager(Pager):

    def __init__(self, obj, sortdir = "desc", count_extra = '', idparam = 'id'):
        Pager.__init__(self)
        self._obj = obj
        self._sortdir = sortdir
        self._idparam = idparam
        self._sortby = web.input().get("sort", "time")
        self._count = self._obj.get_photo_count()
        
    def can_be_chronological(self):
        return True

    def get_sort_by(self):
        return self._sortby

    def get_page_no_params(self, topic_id, page_no = None):
        return "?%s=%s&n=%s" % (self._idparam, topic_id,
                                page_no or self._page_no)

    def get_photos(self):
        return self._obj.get_photos(self.get_offset())
        
class Configuration:

    def get_photo_uri(self):
        return 'http://larsga.webfactional.com/photoserv.py?'

    def get_gmaps_key(self):
        return 'ABQIAAAA8oFUEfcfBwJ3xTqFdvtQYBT4pz8oWygjc4zMKW0Sgg0jlcfanRRyg1iSx13Hptl3x9lAlGQvZxKDXw'

    def get_photo_graph(self):
        return 'http://psi.garshol.priv.no/semaphoto/graph'

    def get_session_dir(self):
        return "/Users/larsga/cvs-co/semaphoto/src/sessions"
    
# --- UTILITIES
    
def current_user_name():
    if not hasattr(session, "username"):
        return None

    return session.username

def nocache():
    web.header("Pragma", "no-cache");
    web.header("Cache-Control", "no-cache, no-store, must-revalidate, post-check=0, pre-check=0");
    web.header("Expires", "Tue, 25 Dec 1973 13:02:00 GMT");
    
# --- CONSTANTS

# typemap = {
#     NS_SP + 'Person'   : 'person.jsp',
#     NS_SP + 'Place'    : 'place.jsp',
#     NS_SP + 'Event'    : 'event.jsp',
#     NS_SP + 'Category' : 'category.jsp',
#     }

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

web.config.session_parameters['cookie_path'] = '/'
web.config.session_parameters['max_age'] = (24 * 60 * 60) * 30 # 30 days
store = web.session.DiskStore(conf.get_session_dir())
session = web.session.Session(app, store)

gallery = photolib.Gallery()

if __name__ == "__main__":
    app.run()
