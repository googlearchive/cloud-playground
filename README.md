# Introduction #
Cloud Playground is a place for developers to experiment and play with some of the services offered by the Google Cloud Platform (http://cloud.google.com/), such as [Google App Engine](https://developers.google.com/appengine/), [Google Cloud Storage](https://developers.google.com/storage/) and [Google Cloud SQL](https://developers.google.com/cloud-sql/). Think of the playground as an easy way to get to know these services, or just quickly try out a new API, without having to download the SDK or having to run `appcfg.py update` every time you want to test your changes.


# About this project #
This project contains the source code for the Cloud Playground, so you can see how the playground works, develop your own tools and experiments, or just create your own private playground using an App Engine app id you created.


# Try it out! #
You can try out the Cloud Playground here:

https://cloud-playground.appspot.com/

| ![https://cloud-playground.googlecode.com/files/cloud-playground-editor.png](https://cloud-playground.googlecode.com/files/cloud-playground-editor.png) |
|:--------------------------------------------------------------------------------------------------------------------------------------------------------|


# Using the source #
There are two important projects which together create the Cloud Playground:

  1. [mimic](https://github.com/fredsa/mimic) is a regular (or "special", depending on how you look at things) Python App Engine app, which serves as a development server (similar to the App Engine SDK "dev\_appserver"), but which runs in the production App Engine environment, providing you access to the production APIs and environment while still offering a quick and easy way to test out bits of code.

  1. [bliss](https://github.com/fredsa/cloud-playground) (this project) is an experimental, trivial browser based code editor which lets edit code in the mimic virtual file system (backed by the App Engine datastore), providing you with a user interface so you can see what the mimic app can do for you.


# Creating a private cloud playground #

  1. [Create an App Engine app id](https://appengine.google.com/) where you will run your own private Cloud Playground

  1. Create a git clone of bliss and its submodules:

    ```bash
    git clone --recursive https://github.com/fredsa/cloud-playground
    cd cloud-playground
    ```

  1. Modify the the various `handlers:` sections in the various `*.yaml` files (`app.yaml`, `playground.yaml` etc.) to require admin login (`login: admin`) and https (`secure: always`)

  1. Optionally, try running the cloud playground on http://localhost:8080/

    ```bash
    scripts/run.sh
    ```

  1. Deploy the modified app to the app id you just created

    ```bash
    scripts/deploy.sh --application your-app-id
    ```

  1. Verify that all the URL handlers are indeed correctly locked down

  1. Have fun!


# Other fun places to play #
  * [Go Playground](http://play.golang.org/)
  * [AJAX APIs Playground](https://code.google.com/apis/ajax/playground/)
  * [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
  * [Google Mirror API Playground](https://developers.google.com/glass/playground)
  * [devtable](https://devtable.com/)
  * [Codeenvy](https://codenvy.com/)


# License(s) #

_Note, the Cloud Playground includes libraries that are licensed under terms other than Apache 2.0._

* Bliss (i.e the source code in this repo) — [LICENSE](https://github.com/fredsa/cloud-playground/blob/master/LICENSE) file

* [AngularJS](code.angularjs.org) — https://github.com/angular/angular.js/blob/master/LICENSE

* [Karma](http://karma-runner.github.io/) — https://github.com/karma-runner/karma/blob/master/LICENSE

* [CodeMirror](http://marijnhaverbeke.nl/git/codemirror) by Marijn Haverbeke — http://codemirror.net/LICENSE

* Some subdirectories of the CodeMirror distribution include their own `LICENSE` files, and are released under different licences

* [Twitter Bootstrap](https://github.com/twitter/bootstrap.git) — https://github.com/twitter/bootstrap/blob/master/LICENSE

* [Werkzeug](http://werkzeug.pocoo.org/) — https://github.com/mitsuhiko/werkzeug/blob/master/LICENSE

* [Flask](http://flask.pocoo.org/) — http://flask.pocoo.org/docs/license/
