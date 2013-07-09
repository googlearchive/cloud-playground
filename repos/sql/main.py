import os
import logging
import webapp2

from google.appengine.api import app_identity
from google.appengine.api import rdbms

import jinja2

template_path = os.path.join(os.path.dirname(__file__))

jinja2_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_path)
)

# Assume Cloud SQL instance name matches app id
APP_ID = app_identity.get_application_id()
CLOUDSQL_INSTANCE = '{}:{}'.format(APP_ID, APP_ID)

# To create the intial database, follow the setup instructions
# https://developers.google.com/appengine/training/cloud-sql/deploy_the_app
DATABASE_NAME = 'guestbook'
USER_NAME = None #'username'
PASSWORD = None #'password'


def get_connection():
    if os.environ['SERVER_SOFTWARE'].startswith('Development/'):
      return rdbms.connect(instance=CLOUDSQL_INSTANCE, database=DATABASE_NAME)
    else:
      return rdbms.connect(instance=CLOUDSQL_INSTANCE, database=DATABASE_NAME,
                           user=USER_NAME, password=PASSWORD, charset='utf8')


class MainHandler(webapp2.RequestHandler):
    def get(self):
        # Viewing guestbook
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT guest_name, content, created_at FROM entries '
                       'ORDER BY created_at DESC limit 20')
        rows = cursor.fetchall()
        conn.close()
        template_values = {"rows": rows}
        template = jinja2_env.get_template('index.html')
        self.response.out.write(template.render(template_values))


class GuestBook(webapp2.RequestHandler):
    def post(self):
        # Posting a new guestbook entry
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO entries (guest_name, content) '
                       'VALUES (%s, %s)',
                       (self.request.get('guest_name'),
                        self.request.get("content")))
        conn.commit()
        conn.close()
        self.redirect("/")


application = webapp2.WSGIApplication([
    ("/", MainHandler),
    ("/sign", GuestBook),
], debug=True)
