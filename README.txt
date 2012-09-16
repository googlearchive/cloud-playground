


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
