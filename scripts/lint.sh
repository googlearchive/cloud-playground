#!/bin/sh

gjslint -r app/js test|egrep -v '(E:0121:|E:0240|E:0200)'
