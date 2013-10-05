'''
Module for data model.
'''

import operator

import psycopg2
import psycopg2.extensions

import markdown2

DB_CONNECT_STRING = 'dbname=semaphoto host=localhost'

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
conn = psycopg2.connect(DB_CONNECT_STRING)
cur = conn.cursor()

import worm
worm.cursor = cur

# ----- UTILITIES

def update(query, args):
    cur.execute(query, args)

def query_for_set(query, args):
    cur.execute(query, args)
    return set([row[0] for row in cur.fetchall()])

def query_for_list(query, args):
    cur.execute(query, args)
    return [row[0] for row in cur.fetchall()]

def query_for_row(query, args = ()):
    cur.execute(query, args)
    return cur.fetchone()

# ----- FILTER

# when querying the photo table as t1, this snippet will remove all
# photos which are privacy-protected
SQL_PHOTO_FILTER = '''
not (t1.hidden or
 exists (select * from place where id = t1.taken_at and hidden) or
 exists (select * from event where id = t1.taken_during and hidden) or
 exists (select * from depicted_in d where photo = t1.id and exists (select * from person where id = d.person and hidden)) or
 exists (select * from in_category c where photo = t1.id and exists (select * from category where id = c.category and hidden)))
'''

# ----- GALLERY

class Gallery:
    'Container for all photos and other data.'

    def get_title(self):
        return "Lars Marius's photos"

    def get_description(self):
        return """This is my collection of photos gathered since 2000. The photos show both private and professional events, as well as events of general interest, such as holiday trips abroad, etc. The collection is open to anyone, so feel free to look around at any photos you like.

Note that photos showing many people and places are hidden for
privacy reasons. To see these you need to [log in](login.jsp). To get a password you need to email me.

You can read more about the application [on my blog](http://www.garshol.priv.no/blog/126.html)."""
    
    def count(self, kind):
        return worm.query_for_value('select count(*) from ' + kind)

    def get_random_photo(self):
        return worm.query_for_one('select * from photo order by random() limit 1', Photo)

    def get_person_by_username(self, username):
        return worm.query_for_one('select * from person where username = %s',
                                  Person, (username, ))
    
    def get_person_counts(self, filter = False):
        where = ''
        if filter:
            where = 'where not p.hidden'
        cur.execute('''select p.*, count(f.id)
                       from person p
                       join depicted_in d on d.person = p.id
                       join photo f on d.photo = f.id
                       %s
                       group by p.id, p.name, p.hidden, p.username, p.password
                       order by p.name''' % where)
        return [(worm.make(Person, row[0 : -1]), row[-1])
                for row in cur.fetchall()]

    def get_category_counts(self, filter = False):
        where = ''
        if filter:
            where = 'where not p.hidden'
        cur.execute('''select c.*, count(p.id)
                       from category c
                       join in_category inc on inc.category = c.id
                       join photo p on inc.photo = p.id
                       %s
                       group by c.id, c.name, c.hidden, c.description
                       order by c.name''' % where)
        return [(worm.make(Category, row[0 : 4]), row[4]) for row in cur.fetchall()]

    def get_event_counts(self, filter = False):
        where = ''
        if filter:
            where = 'where not e.hidden'
        cur.execute('''select e.*, count(p.id)
                       from event e
                       join photo p on e.id = p.taken_during
                       %s
                       group by e.id, e.name, e.description,
                                e.start_date, e.end_date, e.hidden
                       order by e.start_date''' % where)
        return [(worm.make(Event, row[0 : 6]), row[6]) for row in cur.fetchall()]

    def get_best_photos(self, offset = 0, filter = False):
        if filter:
            filter = ' where ' + SQL_PHOTO_FILTER
        else:
            filter = ''
        cur.execute('''select t1.*, avg(score) as a
                       from photo t1
                       join photo_score on t1.id = photo
                       %s
                       group by t1.id, t1.title, t1.description, t1.taken_at,
                                t1.taken_during, t1.taken_by, t1.time_taken,
                                t1.hidden
                       order by a desc limit 50 offset %s''' %
                    (filter, offset))
        return [worm.make(Photo, row[ : -1]) for row in cur.fetchall()]

    def get_voted_photos(self, filter = False):
        if filter:
            filter = ' and ' + SQL_PHOTO_FILTER
        else:
            filter = ''
        return worm.query_for_value('''
                       select count(t1.*)
                       from photo t1
                       where exists (select * from photo_score s
                                     where s.photo = t1.id)''' + filter)

    def get_search_results(self, search, filter = False):
        if filter:
            filter = ' and ' + SQL_PHOTO_FILTER
        else:
            filter = ''
        query = '''
     select t1.*,
       ts_rank_cd(to_tsvector(t1.title || ' ' || coalesce(t1.description, '')), query) AS rank
     from photo t1, to_tsquery(%%s) query
     where query @@ to_tsvector(t1.title || ' ' || coalesce(t1.description, ''))
     %s
     order by rank desc limit 50''' % filter
        cur.execute(query, (tokenize_for_search(search), ))
        return [worm.make(Photo, row[ : 1]) for row in cur.fetchall()]

def tokenize_for_search(search):
    return ' & '.join([t for t in search.split()])
    
# ----- PAGED CONTAINER OBJECTS

class Paged:    
    def set_pager(self, pager):
        self.pager = pager

    def get_pager(self):
        return self.pager
    
# ----- EVENT

class Event(worm.DatabaseObject, Paged):
    TABLE = 'event'
    ID = 'id'
    TYPEMAP = {}
    
    def __init__(self, id, filter = None):
        worm.DatabaseObject.__init__(self, Event.ID, Event.TABLE)
        self._id = id
        self._name = None
        self._description = None
        self._start_date = None
        self._end_date = None
        self._hidden = None
        self._filter = filter

    def get_photos(self, offset = None):
        filter = ''
        if self._filter:
            filter = SQL_PHOTO_FILTER
        return self._load_one_to_many(Photo, 'taken_during', limit = 50,
                                      offset = offset, order = 'time_taken',
                                      filter = filter)

    def get_photo_count(self):
        filter = ''
        if self._filter:
            filter = SQL_PHOTO_FILTER
        return self._count_one_to_many(Photo, 'taken_during', filter = filter)
    
# ----- PLACE

class Place(worm.DatabaseObject, Paged):
    TABLE = 'place'
    ID = 'id'
    
    def __init__(self, id, filter = None):
        worm.DatabaseObject.__init__(self, Place.ID, Place.TABLE, Place.TYPEMAP)
        self._id = id
        self._name = None
        self._parent = None
        self._latitude = None
        self._longitude = None
        self._hidden = None
        self._filter = filter

    def get_description(self):
        return None # FIXME: apparently places do have descriptions...
        
    def get_ancestors(self):
        'Returns ancestors in order furthers to nearest.'
        ancestors = []
        parent = self.get_parent()
        while parent:
            ancestors.append(parent)
            parent = parent.get_parent()

        ancestors.reverse()
        return ancestors

    def get_children(self):
        return self._load_one_to_many(Place, 'parent')

    def get_photos(self, offset = 0):
        # FIXME: what about photos in descendants?
        filter = None
        if self._filter:
            filter = SQL_PHOTO_FILTER
        return self._load_one_to_many(Photo, 'taken_at', limit = 50,
                                      offset = offset, order = 'time_taken',
                                      filter = filter)

    def get_photo_count(self):
        # FIXME: what about photos in descendants?
        filter = None
        if self._filter:
            filter = SQL_PHOTO_FILTER
        return self._count_one_to_many(Photo, 'taken_at', filter = filter)
        
Place.TYPEMAP = {'parent' : Place}
    
# ----- PERSON
    
class Person(worm.DatabaseObject, Paged):
    TABLE = 'person'
    ID = 'id'
    
    def __init__(self, id, filter = False):
        worm.DatabaseObject.__init__(self, Person.ID, Person.TABLE)
        self._id = id
        self._name = None
        self._hidden = None
        self._filter = ''
        if filter:
            self._filter = SQL_PHOTO_FILTER
    def get_photos(self, offset = None):
        return self._load_many_to_many('person', 'depicted_in', 'photo', Photo,
                                       limit = 50, offset = offset,
                                       order = 'time_taken',
                                       filter = self._filter)

    def get_photo_count(self):
        return self._count_many_to_many('person', 'depicted_in', 'photo', Photo,
                                        filter = self._filter)

# ----- PHOTO

class Photo(worm.DatabaseObject):
    TABLE = 'photo'
    ID = 'id'
    TYPEMAP = {'taken_at' : Place, 'taken_during' : Event, 'taken_by' : Person}
    
    def __init__(self, id, filter = False):
        worm.DatabaseObject.__init__(self, Photo.ID, Photo.TABLE, Photo.TYPEMAP)
        self._id = id
        self._title = None
        self._description = None
        self._time_taken = None
        self._taken_at = None
        self._taken_by = None
        self._taken_during = None
        self._hidden = None
        self.votes = None
        self.filter = filter

    def get_previous(self):
        if self.filter:
            filter = ' and ' + SQL_PHOTO_FILTER
        else:
            filter = ''
        query = '''select t1.id from photo t1
                   where t1.time_taken < %%s
                   %s
                   order by t1.time_taken desc limit 1''' % filter
        return Photo(worm.query_for_value(query, (self._time_taken, )))

    def get_next(self):
        if self.filter:
            filter = ' and ' + SQL_PHOTO_FILTER
        else:
            filter = ''
        query = '''select t1.id from photo t1
                   where t1.time_taken > %%s
                   %s
                   order by t1.time_taken asc limit 1''' % filter
        return Photo(worm.query_for_value(query, (self._time_taken, )))

    def get_vote_count(self):
        self.load_votes()
        return len(self.votes)

    def get_score(self):
        self.load_votes()
        if not self.votes:
            return 0
        total = sum([rating.get_score() for rating in self.votes])
        # return (total + 2.5) / (len(self.votes) + 1)   THIS IS BAYESIAN
        return float(total) / len(self.votes)

    def get_users_vote(self, username):
        self.load_votes()
        for rating in self.votes:
            if rating.get_username() == username:
                return rating.get_score()
        return 0

    def get_people(self):
        return self._load_many_to_many('photo', 'depicted_in', 'person', Person)

    def get_categories(self):
        return self._load_many_to_many('photo', 'in_category', 'category', Category)

    def get_comments(self):
        return self._load_one_to_many(Comment, 'photo', filter = 'verified=1')

    def load_votes(self):
        if self.votes is not None:
            return
        self.votes = self._load_one_to_many(Rating, 'photo')

    def get_hidden(self):
        "Overriding because there's additional logic."
        return self._hidden or hidden(self.get_taken_at()) or \
            hidden(self.get_taken_during()) or \
            one_of_hidden(self.get_categories()) or \
            one_of_hidden(self.get_people())

# ----- CATEGORY

class Category(worm.DatabaseObject, Paged):
    TABLE = 'category'
    ID = 'id'
    
    def __init__(self, id, filter = False):
        worm.DatabaseObject.__init__(self, Category.ID, Category.TABLE)
        self._id = id
        self._name = None
        self._description = None
        self._hidden = None
        self._filter = filter

    def get_photos(self, offset = None):
        filter = ''
        if self._filter:
            filter = SQL_PHOTO_FILTER
        return self._load_many_to_many('category', 'in_category', 'photo',
                                       Photo, limit = 50, offset = offset,
                                       order = 'time_taken', filter = filter)

    def get_photo_count(self):
        filter = ''
        if self._filter:
            filter = SQL_PHOTO_FILTER
        return self._count_many_to_many('category', 'in_category', 'photo',
                                       Photo, filter = filter)

# ----- COMMENT

class Comment(worm.DatabaseObject):
    TABLE = 'comments'
    ID = 'id'
    
    def __init__(self, id):
        worm.DatabaseObject.__init__(self, Comment.ID, Comment.TABLE)
        self._id = id
        self._content = None
        self._photo = None
        self._datetime = None
        self._name = None
        self._url = None
        self._username = None
        self._email = None

    def get_formatted_name(self):
        if False: # FIXME: what if person is logged in?
            return '<a href="person.jsp?id=%s">%s</a>' % (self.pid, self.name)
        elif self._url:
            return '<a href="%s">%s</a>' % (self._url, self._name)
        else:
            return self._name
        
    def get_formatted_content(self):
        return markdown2.markdown(self._content)

    def get_nice_time(self):
        return self._datetime.strftime('%Y-%m-%d %H:%M:%S')

# ----- RATING

class Rating(worm.DatabaseObject):
    TABLE = 'photo_score'
    ID = 'id'
    
    def __init__(self, id):
        worm.DatabaseObject.__init__(self, Rating.ID, Rating.TABLE)
        self._id = id
        self._photo = None
        self._updated = None
        self._username = None
        self._score = None
    
# ----- YEAR

class Year(Paged):

    def __init__(self, year, filter = False):
        self._year = year
        self._filter = filter

    def get_name(self):
        return self._year

    def get_id(self):
        return self._year

    def get_months(self):
        return query_for_list('''
           select distinct substring(time_taken from 1 for 7) as month
           from photo
           where substring(time_taken from 1 for 4) = %s
           order by month''', (self._year, ))

    def get_photo_count(self):
        if self._filter:
            filter = ' and ' + SQL_PHOTO_FILTER
        else:
            filter = ''
        return worm.query_for_value('''
           select count(t1.*)
           from photo t1
           where substring(t1.time_taken from 1 for 4) = %%s %s''' % filter,
                                    (self._year, ))

    def get_photos(self, offset = 0):
        if self._filter:
            filter = ' and ' + SQL_PHOTO_FILTER
        else:
            filter = ''
        query = '''
           select t1.*
           from photo t1
           where substring(t1.time_taken from 1 for 4) = %%s
           %s
           order by t1.time_taken
           limit 50 offset %s
        ''' % (filter, offset)
        return worm.query_for_list(query, Photo, (self._year, ))

# ----- MONTH

class Month(Paged):

    def __init__(self, month, filter = False):
        self._month = month
        self._filter = filter

    def get_name(self):
        return self._month

    def get_id(self):
        return self._month

    def get_photo_count(self):
        if self._filter:
            filter = ' and ' + SQL_PHOTO_FILTER
        else:
            filter = ''
        return worm.query_for_value('''
           select count(t1.*)
           from photo t1
           where substring(t1.time_taken from 1 for 7) = %%s %s''' % filter,
                                    (self._month, ))

    def get_photos(self, offset = 0):
        if self._filter:
            filter = ' and ' + SQL_PHOTO_FILTER
        else:
            filter = ''
        query = '''
           select t1.*
           from photo t1
           where substring(t1.time_taken from 1 for 7) = %%s
           %s
           order by t1.time_taken
           limit 50 offset %s
        ''' % (filter, offset)
        return worm.query_for_list(query, Photo, (self._month, ))

# ----- SECURITY UTILITIES

def hidden(obj):
    return obj and obj.get_hidden()

def one_of_hidden(objects):
    return reduce(operator.or_, [o.get_hidden() for o in objects], False)
