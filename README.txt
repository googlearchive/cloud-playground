===================================
bliss - Cloud Playground IDE
===================================

bliss is a "dev_appserver" in the cloud. It's an experimental IDE for the
Cloud Playground, which serves as a thin wrapper on top of mimic, demonstrating
what you can do with mimic.

===================================
LICENSE
===================================

Note, the Cloud Playground includes libraries that are licensed under terms
other than Apache 2.0.

* Bliss (i.e the source code in this repo). See LICENSE file.

* CodeMirror (http://marijnhaverbeke.nl/git/codemirror) by Marijn Haverbeke. See
  http://codemirror.net/LICENSE.

* Some subdirectories of the CodeMirror distribution include their own LICENSE
  files, and are released under different licences.

* Twitter Bootstrap (https://github.com/twitter/bootstrap.git) See
  https://github.com/twitter/bootstrap/blob/master/LICENSE

===================================
Running Unittests
===================================

The unit tests require
- Python 2.7
- Google App Engine SDK in the PYTHONPATH environment variable

If you're running Linux, you can do

PYTHONPATH=$PYTHONPATH:/path/to/GAE-SDK python run_tests.py

If you're on Windows, the run_tests script will try to guess where the Google
App Engine SDK is (specifically, "C:\Program Files\Google\google_appengine").
If the Google App Engine SDK is installed in another folder, run

  SET PYTHONPATH=%PYTHONPATH%;c:\path\to\GAE-SDK

before running "python run_tests.py".

You can run an individual test file by passing the file name to the run_tests.py
script (the unittest runner finds the file automatically):

  python run_tests.py target_env_test.py
