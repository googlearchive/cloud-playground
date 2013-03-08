#!/bin/sh

gjslint -r app/js -r test/unit -r test/e2e|egrep -v '(E:0121:|E:0240|E:0200)'
