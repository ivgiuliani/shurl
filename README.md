Simple URL shortener for intranet/personal use.


Installation instructions
==============================================================================

1. Create a python virtual environment with virtualenv:

        virtualenv ENV

2. Activate the newly created virtual environment:

        source ENV/bin/activate

3. Install dependencies:

        pip install -r PIP_REQUIREMENTS

4. Configure apache2 through mod_wsgi:

        <VirtualHost *:80>
          [...your configuration here...]
          WSGIDaemonProcess shurl user=www-data group=www-data threads=3
          WSGIScriptAlias / /path/to/shurl/shurl.wsgi
          <Directory /path/to/shurl>
            WSGIProcessGroup shurl
            WSGIApplicationGroup %{GLOBAL}
            Order deny,allow
            Allow from all
          </Directory>
        </VirtualHost>

5. If you didn't use `ENV` as the name for the python's virtual environment,
   change it in `shurl.wsgi`
