'''
Script to import the original topic map into Postgres.
'''

import sys
from net.ontopia.topicmaps.utils import ImportExportUtils
from net.ontopia.topicmaps.query.utils import QueryUtils
from java.sql import DriverManager

JDBC_URL = 'jdbc:postgresql://localhost/semaphoto'

PREFIXES = """
using op for i"http://psi.ontopedia.net/"
using ph for i"http://psi.garshol.priv.no/tmphoto/"
using dc for i"http://purl.org/dc/elements/1.1/"
using user for i"http://psi.ontopia.net/userman/"
"""

def get_topic_id(topic, fallback = None):
    if not topic:
        return fallback

    for srcloc in topic.getItemIdentifiers():
        srcloc = srcloc.toString()
        ix = srcloc.rfind('#')
        if ix != -1:
            return srcloc[ix + 1 : ]

def escape(str):
    if str:
        return str.replace("'", "''")
    else:
        return ''

def str_or_null(v):
    if v == None:
        return 'null'
    else:
        return "'%s'" % v

def v_or_null(v):
    if v == None:
        return 'null'
    else:
        return v

tm = ImportExportUtils.getReader(sys.argv[1]).read()
processor = QueryUtils.getQueryProcessor(tm)

conn = DriverManager.getConnection(JDBC_URL)
stmt = conn.createStatement()

processed = set()

# ===== PHOTO

stmt.execute('delete from photo')
result = processor.execute(PREFIXES + """
    instance-of($PHOTO, op:Image),
    { topic-name($PHOTO, $TN), value($TN, $NAME) },
    { ph:time-taken($PHOTO, $TIME) },
    { ph:taken-at($PHOTO : op:Image, $PLACE : op:Place) },
    { ph:taken-during($PHOTO : op:Image, $EVENT : op:Event) },
    subject-locator($PHOTO, $LOC)
    order by $TIME, $LOC?
""")
while result.next():
    photo = result.getValue("PHOTO")
    id = get_topic_id(photo)

    if id in processed:
        continue

    processed.add(id)

    title = escape(result.getValue("NAME"))
    url = result.getValue("LOC")
    time = result.getValue("TIME")
    place = get_topic_id(result.getValue('PLACE'), 'oioi')
    event = get_topic_id(result.getValue('EVENT'), None)

    # description
    # taken during
    # hidden

    print id, title, url, time

    stmt.execute('''
      INSERT INTO photo (id, title, time_taken, taken_at, taken_during, hidden)
      VALUES ('%s', '%s', '%s', '%s', %s, false)
    ''' % (id, title, time, place, str_or_null(event))
    )

# ===== PLACE

stmt.execute('delete from place')
result = processor.execute(PREFIXES + """
    instance-of($PLACE, op:Place),
    { topic-name($PLACE, $TN), value($TN, $NAME) },
    { op:located_in($PLACE : op:Containee, $PARENT : op:Container) },
    { ph:latitude($PLACE, $LAT) },
    { ph:longitude($PLACE, $LONG) }
?""")
while result.next():
    place = result.getValue("PLACE")
    name = escape(result.getValue("NAME"))
    id = get_topic_id(place)
    parent = str_or_null(get_topic_id(result.getValue('PARENT')))
    lat = v_or_null(result.getValue('LAT'))
    lng = v_or_null(result.getValue('LONG'))

    if id in processed:
        continue

    processed.add(id)

    stmt.execute('''
      INSERT INTO place (id, name, parent, latitude, longitude, hidden)
      VALUES ('%s', '%s', %s, %s, %s, false)
    ''' % (id, name, parent, lat, lng)
    )

# ===== EVENT

stmt.execute('delete from event')
result = processor.execute(PREFIXES +
                           """instance-of($EVENT, op:Event),
                              { topic-name($EVENT, $TN), value($TN, $NAME) },
                              ph:start-date($EVENT, $START),
                              ph:end-date($EVENT, $END)
                           ?""")
while result.next():
    event = result.getValue("EVENT")
    name = escape(result.getValue("NAME"))
    id = get_topic_id(event)

    if id in processed:
        continue

    processed.add(id)
    start_date = result.getValue('START')
    end_date = result.getValue('END')

    stmt.execute('''
      INSERT INTO event (id, name, start_date, end_date, hidden)
      VALUES ('%s', '%s', '%s', '%s', false)
    ''' % (id, name, start_date, end_date)
    )

# ===== CATEGORY

stmt.execute('delete from category')
result = processor.execute(PREFIXES + """
    instance-of($CAT, op:Category),
    topic-name($CAT, $TN), value($TN, $NAME),
    { dc:description($CAT, $DESC) }
?""")
while result.next():
    event = result.getValue("CAT")
    name = escape(result.getValue("NAME"))
    id = get_topic_id(event)

    if id in processed:
        continue

    processed.add(id)
    desc = str_or_null(result.getValue('DESC'))

    stmt.execute('''
      INSERT INTO category (id, name, description, hidden)
      VALUES ('%s', '%s', %s, false)
    ''' % (id, name, desc)
    )

# ===== IN_CATEGORY

stmt.execute('delete from in_category')
result = processor.execute(PREFIXES + """
    ph:in-category($PHOTO : ph:categorized, $CAT : ph:categorization)
?""")
while result.next():
    cat = get_topic_id(result.getValue("CAT"))
    photo = get_topic_id(result.getValue("PHOTO"))

    stmt.execute('''
      INSERT INTO in_category (photo, category)
      VALUES ('%s', '%s')
    ''' % (photo, cat)
    )

# ===== PERSON

stmt.execute('delete from person')
result = processor.execute(PREFIXES + """
    instance-of($PERSON, op:Person),
    topic-name($PERSON, $TN), value($TN, $VALUE),
    { user:username($PERSON, $USER),
      user:password($PERSON, $PASS) }
?""")
while result.next():
    person = get_topic_id(result.getValue("PERSON"))
    name = result.getValue("VALUE")
    user = str_or_null(result.getValue("USER"))
    password = str_or_null(result.getValue("PASS"))

    stmt.execute('''
      INSERT INTO person (id, name, username, password, hidden)
      VALUES ('%s', '%s', %s, %s, false)
    ''' % (person, name, user, password)
    )

# ===== DEPICTED_IN

stmt.execute('delete from depicted_in')
result = processor.execute(PREFIXES + """
    ph:depicted-in($PERSON : ph:depicted, $PHOTO : ph:depiction)
?""")
while result.next():
    person = get_topic_id(result.getValue("PERSON"))
    photo = get_topic_id(result.getValue("PHOTO"))

    stmt.execute('''
      INSERT INTO depicted_in (person, photo)
      VALUES ('%s', '%s')
    ''' % (person, photo)
    )
